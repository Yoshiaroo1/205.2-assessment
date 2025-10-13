import os
import time
from flask import Flask, request, render_template, jsonify
import osmnx as ox
import networkx as nx
import geopandas as gpd
import pandas as pd
import joblib
from shapely.geometry import LineString, Point
import folium

# ---------------------------------------------------------------------
# FLASK APP SETUP
# ---------------------------------------------------------------------
app = Flask(__name__)

# Paths
MODEL_PATH = "models/traffic_model.pkl"
TRAFFIC_FILE = "data/trafficservice.geojson"
CACHE_GRAPH = "data/auckland_drive.graphml"

# ---------------------------------------------------------------------
# LOAD ML MODEL
# ---------------------------------------------------------------------
try:
    model = joblib.load(MODEL_PATH)
    print("✅ Loaded ML model successfully.")
except Exception as e:
    print(f"⚠️ Could not load ML model: {e}")
    model = None

# ---------------------------------------------------------------------
# LOAD OR CACHE OSM GRAPH
# ---------------------------------------------------------------------
def load_graph():
    if os.path.exists(CACHE_GRAPH):
        print("📂 Loading cached graph...")
        G = ox.load_graphml(CACHE_GRAPH)
    else:
        print("🌏 Downloading road network (first time only)... this may take a few minutes")
        G = ox.graph_from_place("Auckland, New Zealand", network_type="drive")
        ox.save_graphml(G, CACHE_GRAPH)
        print("✅ Graph cached to disk.")
    return G

G = load_graph()
G = ox.add_edge_speeds(G)
G = ox.add_edge_travel_times(G)

# Convert to projected CRS for distance accuracy
nodes, edges = ox.graph_to_gdfs(G)
edges = edges.to_crs(epsg=2193)  # NZTM projection
graph_crs = edges.crs

# ---------------------------------------------------------------------
# LOAD TRAFFIC DATA
# ---------------------------------------------------------------------
try:
    traffic = gpd.read_file(TRAFFIC_FILE)
    if "GEOMETRY" in traffic.columns and "geometry" not in traffic.columns:
        traffic = traffic.rename(columns={"GEOMETRY": "geometry"}).set_geometry("geometry")
    traffic = traffic.to_crs(graph_crs)
    print("✅ Loaded traffic data.")
except Exception as e:
    print(f"⚠️ Could not load traffic data: {e}")
    traffic = None

# ---------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------
def predict_congestion(edge_row):
    """Use ML model to predict congestion-adjusted speed"""
    if model is None:
        return edge_row.get("speed_kph", 40)

    # Build features in the exact order used during training
    feature_order = ["speed_kph", "ADT", "length_m"]

    # Prepare feature dictionary with safe defaults
    feature_data = {
        "ADT": edge_row.get("ADT", 12000),
        "speed_kph": edge_row.get("speed_kph", 50),
        "length_m": edge_row.get("length", 100)
    }

    # Create DataFrame and enforce column order
    features = pd.DataFrame([[feature_data[f] for f in feature_order]], columns=feature_order)

    try:
        pred_speed = model.predict(features)[0]
        return max(pred_speed, 5.0)  # clamp to avoid zero speeds
    except Exception as e:
        print(f"⚠️ Prediction failed for edge: {e}")
        return edge_row.get("speed_kph", 40)





def get_route_map(origin, destination):
    """Generate map with route based on ML-adjusted travel times."""
    print("🚗 Computing route...")

    orig_point = ox.geocode(origin)
    dest_point = ox.geocode(destination)

    orig_node = ox.distance.nearest_nodes(G, orig_point[1], orig_point[0])
    dest_node = ox.distance.nearest_nodes(G, dest_point[1], dest_point[0])

    # Find the shortest path using current travel times
    route = nx.shortest_path(G, orig_node, dest_node, weight="travel_time")

    # Only adjust travel times for edges in the route
    route_edges = list(zip(route[:-1], route[1:]))
    for u, v in route_edges:
        # Some graphs may have multiple edges between nodes (MultiDiGraph)
        keys = G[u][v].keys() if hasattr(G[u][v], "keys") else [0]
        for key in keys:
            data = G[u][v][key]
            if "speed_kph" in data:
                ml_speed = predict_congestion(data)
                data["travel_time"] = (data["length"] / 1000) / (ml_speed / 60)  # minutes
            else:
                print("⚠️ Edge missing speed_kph, skipping ML adjustment.")

    route = nx.shortest_path(G, orig_node, dest_node, weight="travel_time")

    # Create folium map
    m = folium.Map(location=orig_point, zoom_start=13)
    route_coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in route]
    folium.PolyLine(route_coords, color="blue", weight=6, opacity=0.8).add_to(m)

    folium.Marker(location=orig_point, popup="Origin", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(location=dest_point, popup="Destination", icon=folium.Icon(color="red")).add_to(m)

    map_path = os.path.join("templates", "route_map.html")
    m.save(map_path)
    
    # Inject a simple back button
    with open(map_path, "a") as f:
        f.write("""
        <div style="position:fixed; bottom:20px; right:20px; z-index:9999; ">
            <a style="font-size:60px;" href="/" class="btn btn-success btn-lg">Compute New Route</a>
        </div>
        """)
        
    return "route_map.html"

# Simple in-memory progress store
progress_store = {}

# ---------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        origin = request.form["origin"]
        destination = request.form["destination"]
        if origin and destination:
            map_file = get_route_map(origin, destination)
            return render_template(map_file)
    return render_template("index.html")

# ---------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
