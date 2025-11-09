"""
train_traffic_model.py
----------------------
Trains a RandomForestRegressor to predict road-segment travel times in Auckland
based on OSM road data and Auckland Transport’s traffic count dataset.
"""

import os
import re
import joblib
import numpy as np
import pandas as pd
import geopandas as gpd
import osmnx as ox
from shapely.geometry import Point
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

# -----------------------------------------------------------------------------
# 1. Load the Auckland road network
# -----------------------------------------------------------------------------
print("📍 Loading Auckland road network (this may take a few minutes)...")
G = ox.load_graphml("data/auckland_drive.graphml")

edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
print(f"✅ Loaded {len(edges)} road segments")

# -----------------------------------------------------------------------------
# 2. Clean and normalize speed values
# -----------------------------------------------------------------------------
def parse_speed(value):
    """Convert OSM maxspeed field to float (km/h)."""
    if isinstance(value, list):
        value = value[0]
    if isinstance(value, str):
        match = re.search(r'\d+', value)
        if match:
            return float(match.group())
        else:
            return np.nan
    try:
        return float(value)
    except (ValueError, TypeError):
        return np.nan

edges["speed_kph"] = edges["maxspeed"].apply(parse_speed)
edges["speed_kph"] = edges["speed_kph"].fillna(50.0)
edges["speed_kph"] = edges["speed_kph"].clip(lower=10, upper=120)

# -----------------------------------------------------------------------------
# 3. Load Auckland Transport traffic data (ADT)
# -----------------------------------------------------------------------------
print("🚗 Loading Auckland Transport traffic dataset...")

TRAFFIC_FILE = "data/trafficservice.geojson"

if not os.path.exists(TRAFFIC_FILE):
    raise FileNotFoundError(
        "⚠️ trafficservice.geojson not found. "
        "Download it from https://data-atgis.opendata.arcgis.com/datasets/ATgis::trafficservice/about "
        "and place it in the 'data/' directory."
    )

traffic_df = gpd.read_file(TRAFFIC_FILE)
print(f"✅ Loaded {len(traffic_df)} traffic count records")

traffic_df = traffic_df.rename(columns=lambda x: x.strip().upper())
if "ADT" not in traffic_df.columns:
    raise ValueError("ADT column not found in traffic dataset")

traffic_df["ADT"] = pd.to_numeric(traffic_df["ADT"], errors="coerce")
traffic_df = traffic_df.dropna(subset=["ADT"])

# -----------------------------------------------------------------------------
# 3.5 Ensure traffic dataset has correct geometry column and CRS
# -----------------------------------------------------------------------------
# Sometimes the GeoJSON uses 'GEOMETRY' instead of 'geometry'
if "geometry" not in traffic_df.columns and "GEOMETRY" in traffic_df.columns:
    traffic_df = traffic_df.set_geometry("GEOMETRY")

# Make sure CRS matches the road edges
if traffic_df.crs is None:
    print("⚠️ No CRS found for traffic dataset. Assuming EPSG:4326 (WGS84).")
    traffic_df.set_crs("EPSG:4326", inplace=True)

# Reproject to match the OSM edges CRS
traffic_df = traffic_df.to_crs(edges.crs)


# -----------------------------------------------------------------------------
# 4. Spatially join traffic points with road edges
# -----------------------------------------------------------------------------
print("🔗 Spatially joining traffic data to road edges...")

edges["centroid"] = edges["geometry"].centroid
edges_gdf = gpd.GeoDataFrame(edges, geometry="centroid", crs=edges.crs)

edges_joined = gpd.sjoin_nearest(
    edges_gdf, traffic_df, how="left", distance_col="dist_to_traffic"
)

edges_joined["ADT"] = edges_joined["ADT"].fillna(edges_joined["ADT"].median())
print(f"✅ Spatial join complete — {edges_joined['ADT'].notna().sum()} edges have ADT values")

# -----------------------------------------------------------------------------
# 5. Compute target travel times and feature matrix
# -----------------------------------------------------------------------------
edges_joined["length_m"] = edges_joined["length"]
edges_joined["travel_time_min"] = (edges_joined["length_m"] / 1000) / (edges_joined["speed_kph"] / 60)

X = edges_joined[["speed_kph", "ADT", "length_m"]]
y = edges_joined["travel_time_min"]

# -----------------------------------------------------------------------------
# 6. Train the RandomForest model
# -----------------------------------------------------------------------------
print("🧠 Training RandomForestRegressor...")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestRegressor(
    n_estimators=150,
    random_state=42,
    n_jobs=-1,
    max_depth=15
)
model.fit(X_train, y_train)

preds = model.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_test, preds))
print(f"✅ Model trained successfully — RMSE: {rmse:.3f} minutes")

# -----------------------------------------------------------------------------
# 7. Save model and optionally visualize results
# -----------------------------------------------------------------------------
os.makedirs("models", exist_ok=True)
model_path = "models/traffic_model.pkl"
joblib.dump(model, model_path)
print(f"💾 Model saved to {model_path}")

# Optional quick visualization (can be commented out)
try:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 10))
    edges_joined.plot(ax=ax, column="ADT", legend=True, cmap="viridis")
    plt.title("Road Segments Colored by ADT (Traffic Volume)")
    plt.tight_layout()
    plt.show()
except Exception as e:
    print(f"(Skipping visualization: {e})")

print("🎉 Training complete.")
