import os
import joblib
import osmnx as ox
import networkx as nx
import folium
from shapely.geometry import LineString, Point
from statistics import mode
import geopandas as gpd
import pandas as pd

import requests

API_URL = "http://127.0.0.1:5000/calculate"

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
        print("✅ Loaded ML model successfully.")
    except Exception as e:
        print(f"⚠️ Could not load ML model: {e}")
        model = None

    network_type = "walk" if mode == "pedestrian" else "drive"

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

    def calculate_costs(start_coords, end_coords, distance_km):
        from pathshield_app.cost_calculator import AucklandDrivingCostCalculator

        calculator = AucklandDrivingCostCalculator()

        time_of_day = "midday"
        route_efficiency = 0.9

        travel_time_info = calculator.estimate_travel_time(distance_km, time_of_day, route_efficiency)
        fuel_cost_info = calculator.calculate_fuel_cost(distance_km, vehicle_type="suv", fuel_type="91_unleaded")
        toll_cost = calculator.estimate_toll_costs(start_coords, end_coords)

        print("🛣️ Route Cost Estimates:")
        print(f" - Distance: {distance_km:.2f} km")
        print(f" - Travel Time: {travel_time_info['travel_time_minutes']:.1f} minutes")
        print(f" - Fuel Cost: ${fuel_cost_info['fuel_cost']:.2f}")
        print(f" - Toll Cost: ${toll_cost:.2f}")

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
        
        # compute great-circle distance in kilometers using the haversine formula
        from math import radians, sin, cos, atan2, sqrt

        lat1, lon1 = orig_point
        lat2, lon2 = dest_point
        R = 6371.0  # Earth radius in kilometers
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance_km = R * c

        from pathshield_app.cost_calculator import AucklandDrivingCostCalculator
        
        # Compute costs (use same logic as calculate_costs but capture values to inject into HTML)
        try:

            calculator = AucklandDrivingCostCalculator()
            time_of_day = "midday"
            route_efficiency = 0.9

            travel_time_info = calculator.estimate_travel_time(distance_km, time_of_day, route_efficiency) or {}
            fuel_cost_info = calculator.calculate_fuel_cost(distance_km, vehicle_type="suv", fuel_type="91_unleaded") or {}
            toll_cost = calculator.estimate_toll_costs(orig_point, dest_point) or 0.0

            travel_minutes = float(travel_time_info.get("travel_time_minutes", travel_time_info.get("minutes", 0)))
            fuel_cost = float(fuel_cost_info.get("fuel_cost", 0.0))
            total_cost = fuel_cost + float(toll_cost)
            cost_per_km = total_cost / distance_km if distance_km and distance_km > 0 else 0.0

            distance_str = f"{distance_km:.2f} km"
            travel_str = f"{travel_minutes:.1f} min"
            fuel_str = f"${fuel_cost:.2f}"
            toll_str = f"${float(toll_cost):.2f}"
            total_str = f"${total_cost:.2f}"
            per_km_str = f"${cost_per_km:.2f}/km"

            print("🛣️ Route Cost Estimates:")
            print(f" - Distance: {distance_str}")
            print(f" - Travel Time: {travel_str}")
            print(f" - Fuel Cost: {fuel_str}")
            print(f" - Toll Cost: {toll_str}")

        except Exception as e:
            print(f"⚠️ Could not compute costs: {e}")
            distance_str = f"{distance_km:.2f} km"
            travel_str = "-"
            fuel_str = "-"
            toll_str = "-"
            total_str = "-"
            per_km_str = "-"

        # Inject cost panel and back button into the <body> of the saved map HTML
        injection = f"""
        <!-- Cost Panel Styles -->
            <style>
            .cost-panel {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 1000;
            max-width: 300px;
            border-left: 4px solid #28a745;
            }}
            .cost-panel h4 {{
            margin-top: 0;
            color: #28a745;
            border-bottom: 1px solid #eee;
            padding-bottom: 8px;
            }}
            .cost-breakdown {{
            margin-top: 10px;
            }}
            .cost-item {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            padding: 3px 0;
            border-bottom: 1px dotted #eee;
            }}
            .cost-total {{
            font-weight: bold;
            font-size: 1.1em;
            color: #28a745;
            border-top: 2px solid #28a745;
            margin-top: 8px;
            padding-top: 8px;
            }}
            .vehicle-selector {{
            margin-bottom: 10px;
            }}
            .vehicle-selector select {{
            width: 100%;
            padding: 5px;
            border-radius: 4px;
            border: 1px solid #ddd;
            }}
            </style>

        <!-- Cost Panel -->
        <div id="cost-panel" class="cost-panel">
            <h4>Route Cost Analysis</h4>
            <div class="vehicle-selector">
            <label for="vehicle-type">Vehicle Type:</label>
            <select id="vehicle-type">
            <option value="small_car">Small Car</option>
            <option value="medium_car" selected>Medium Car</option>
            <option value="large_car">Large Car</option>
            <option value="suv">SUV</option>
            <option value="truck_ute">Truck/Ute</option>
            <option value="ev_small">Small EV</option>
            <option value="ev_medium">Medium EV</option>
            <option value="ev_large">Large EV</option>
            </select>
            </div>
            <div id="cost-details">
            <div class="cost-item">
            <span>Distance:</span>
            <span id="cost-distance">-</span>
            </div>
            <div class="cost-item">
            <span>Travel Time:</span>
            <span id="cost-time">-</span>
            </div>
            <div class="cost-breakdown">
            <div class="cost-item">
            <span>Fuel Cost:</span>
            <span id="cost-fuel">-</span>
            </div>
            <div class="cost-item">
            <span>Time Cost:</span>
            <span id="cost-time-value">-</span>
            </div>
            <div class="cost-item">
            <span>Operating Costs:</span>
            <span id="cost-operating">-</span>
            </div>
            <div class="cost-item">
            <span>Toll Costs:</span>
            <span id="cost-toll">-</span>
            </div>
            </div>
            <div class="cost-item cost-total">
            <span>Total Cost:</span>
            <span id="cost-total">- NZD</span>
            </div>
            <div class="cost-item">
            <span>Cost per km:</span>
            <span id="cost-per-km">-</span>
            </div>
            </div>
            <div id="cost-loading" style="display: none; text-align: center;">
            <div class="spinner-border spinner-border-sm" role="status">
            <span class="visually-hidden">Loading...</span>
            </div>
            <span style="margin-left: 5px;">Calculating costs...</span>
            </div>
        </div>

        <!-- Compute New Route Button -->
        <div style="position:fixed; bottom:20px; right:20px; z-index:9999; background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            border-left: 4px solid #28a745; font-color: #000000;">
            <a style="font-size:60px;" href="/map">Compute New Route</a>
        </div>

        <script>
        // Populate cost fields with server-calculated values (initial load)
        document.addEventListener("DOMContentLoaded", function() {{
            try {{
            document.getElementById('cost-distance').innerText = "{distance_str}";
            document.getElementById('cost-time').innerText = "{travel_str}";
            document.getElementById('cost-fuel').innerText = "{fuel_str}";
            document.getElementById('cost-toll').innerText = "{toll_str}";
            document.getElementById('cost-total').innerText = "{total_str} NZD";
            document.getElementById('cost-per-km').innerText = "{per_km_str}";
            }} catch (e) {{
            console.warn("Could not populate cost panel:", e);
            }}
        }});
        </script>
        """

        # Read the saved map HTML, insert injection before </body> if present, otherwise append
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                html = f.read()
            if "</body>" in html:
                html = html.replace("</body>", injection + "\n</body>", 1)
            else:
                html = html + injection
            with open(map_path, "w", encoding="utf-8") as f:
                f.write(html)
        except Exception as e:
            print(f"⚠️ Could not inject HTML into map file: {e}")
        
        return m

    return {
        "start": start_address,
        "end": end_address,
        "map": get_route_map(start_address, end_address)._repr_html_()
    }

    


