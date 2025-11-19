import os
import joblib
import osmnx as ox
import networkx as nx
import folium
from shapely.geometry import LineString, Point
from statistics import mode
import geopandas as gpd
import pandas as pd

def generate_route(start_address, end_address, mode='walk'):
    """
    generates a route between two addresses in Auckland using OSM data

    Args:
        start_address (str): The starting address.
        end_address (str): The destination address.
        mode (str): The mode of transportation ('walk', 'bike', 'drive').

    Returns:
        dict: contains start, end, and HTML map of the route.
    
    """

    # Paths
    MODEL_PATH = "pathshield_app\\models\\traffic_model.pkl"
    TRAFFIC_FILE = "pathshield_app\\data\\trafficservice.geojson"
    CACHE_GRAPH = "pathshield_app\\data\\auckland_drive.graphml"

    # ---------------------------------------------------------------------
    # LOAD ML MODEL
    # ---------------------------------------------------------------------
    try:
        model = joblib.load(MODEL_PATH)
        print(" Loaded ML model successfully.")
    except Exception as e:
        print(f"Could not load ML model: {e}")
        model = None

    network_type = "walk" if mode == "pedestrian" else "drive"

    # ---------------------------------------------------------------------
    # LOAD OR CACHE OSM GRAPH
    # ---------------------------------------------------------------------
    def load_graph():
        if os.path.exists(CACHE_GRAPH):
            print("Loading cached graph...")
            G = ox.load_graphml(CACHE_GRAPH)
        else:
            print("🌏 Downloading road network (first time only)... this may take a few minutes")
            G = ox.graph_from_place("Auckland, New Zealand", network_type="drive")
            ox.save_graphml(G, CACHE_GRAPH)
            print("✅Graph cached to disk.")
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
        if model is None:
            return edge_row.get("speed_kph", 40)

        feature_order = ["severity", "adt"]
        feature_data = {
            "adt": edge_row.get("adt", 12000),
            "severity": edge_row.get("severity", 1)
        }

        features = pd.DataFrame([[feature_data[f] for f in feature_order]], columns=feature_order)

        try:
            pred_speed = model.predict(features)[0]
            return max(pred_speed, 1.0)
        except Exception as e:
            print(f"⚠️ Prediction failed for edge: {e}")
            return edge_row.get("speed_kph", 40)


    def get_route_map(origin, destination):
        """Generate map showing both original and ML-adjusted routes."""

        print("🚗 Computing routes...")

        # Geocode addresses
        orig_point = ox.geocode(origin)
        dest_point = ox.geocode(destination)

        orig_node = ox.distance.nearest_nodes(G, orig_point[1], orig_point[0])
        dest_node = ox.distance.nearest_nodes(G, dest_point[1], dest_point[0])

        # -------------------------------
        # Original route (without ML)
        # -------------------------------
        route_original = nx.shortest_path(G, orig_node, dest_node, weight="travel_time")
        route_original_coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in route_original]

        # -------------------------------
        # Adjust travel times using ML
        # -------------------------------
        route_edges = list(zip(route_original[:-1], route_original[1:]))
        for u, v in route_edges:
            keys = G[u][v].keys() if hasattr(G[u][v], "keys") else [0]
            for key in keys:
                data = G[u][v][key]
                if "speed_kph" in data:
                    ml_speed = predict_congestion(data)
                    data["travel_time"] = (data["length"] / 1000) / (ml_speed / 60)  # minutes

        # ML-adjusted route
        route_ml = nx.shortest_path(G, orig_node, dest_node, weight="travel_time")
        route_ml_coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in route_ml]

        # -------------------------------
        # Create folium map
        # -------------------------------
        m = folium.Map(location=orig_point, zoom_start=13)

        # Original route (pale red)
        folium.PolyLine(
            route_original_coords,
            color="#ee0000",  # pale red
            weight=6,
            opacity=0.6,
            tooltip="Original route"
        ).add_to(m)

        # ML-adjusted route (green)
        folium.PolyLine(
            route_ml_coords,
            color="green",
            weight=6,
            opacity=0.8,
            tooltip="ML-adjusted route"
        ).add_to(m)

        # Markers
        folium.Marker(location=orig_point, popup="Origin", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(location=dest_point, popup="Destination", icon=folium.Icon(color="red")).add_to(m)

        # Save map
        map_path = os.path.join("pathshield_app/templates", "route_map.html")
        m.save(map_path)

        # Inject back button
        with open(map_path, "a") as f:
            f.write("""
            <div style="position:fixed; bottom:20px; right:20px; z-index:9999; ">
                <a style="font-size:60px;" href="/map" class="btn btn-success btn-lg">Compute New Route</a>
            </div>
            """)

        return m

    return {
        "start": start_address,
        "end": end_address,
        "map": get_route_map(start_address, end_address)._repr_html_()
    }

    


