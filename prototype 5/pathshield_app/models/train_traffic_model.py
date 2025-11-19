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
G = ox.load_graphml("pathshield_app\\data\\auckland_drive.graphml")

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
# 3. Load Auckland Transport traffic data (adt)
# -----------------------------------------------------------------------------
print("🚗 Loading Auckland Transport traffic dataset...")

TRAFFIC_FILE = "pathshield_app\\data\\trafficservice.geojson"
LOAD_CRIMEDATA = "pathshield_app\\data\\linked_areas.geojson"

if not os.path.exists(TRAFFIC_FILE):
    raise FileNotFoundError(
        "⚠️ trafficservice.geojson not found. "
        "Download it from https://data-atgis.opendata.arcgis.com/datasets/ATgis::trafficservice/about "
        "and place it in the 'data/' directory."
    )

if not os.path.exists(LOAD_CRIMEDATA):
    raise FileNotFoundError("⚠️ linked_areas.geojson not found.")

# --- Force GeoDataFrame loading with proper geometry ---
traffic = gpd.read_file(TRAFFIC_FILE)
crime = gpd.read_file(LOAD_CRIMEDATA)

# Ensure geometry column is correctly set
if "GEOMETRY" in traffic.columns:
    traffic = gpd.GeoDataFrame(traffic, geometry="GEOMETRY", crs=traffic.crs)
elif "geometry" in traffic.columns:
    traffic = gpd.GeoDataFrame(traffic, geometry="geometry", crs=traffic.crs)
else:
    raise ValueError("❌ No geometry column found in traffic dataset")

if "GEOMETRY" in crime.columns:
    crime = gpd.GeoDataFrame(crime, geometry="GEOMETRY", crs=crime.crs)
elif "geometry" in crime.columns:
    crime = gpd.GeoDataFrame(crime, geometry="geometry", crs=crime.crs)
else:
    raise ValueError("❌ No geometry column found in crime dataset")

# Ensure CRS exists
if edges.crs is None:
    edges.set_crs("EPSG:4326", inplace=True)
if traffic.crs is None:
    traffic.set_crs(edges.crs, inplace=True)
if crime.crs is None:
    crime.set_crs(edges.crs, inplace=True)

# Align CRS
traffic = traffic.to_crs(edges.crs)
crime = crime.to_crs(edges.crs)

print(f"✅ Loaded {len(traffic)} traffic records with CRS {traffic.crs}")
print(f"✅ Loaded {len(crime)} crime records with CRS {crime.crs}")

# ---------------------------------------------------------------
# 4. Spatially join traffic points and crime areas to road edges
# ---------------------------------------------------------------
print("🔗 Spatially joining traffic data and crime data to road edges...")

# Drop leftover join index columns if they exist
for gdf_name, gdf in [("edges", edges), ("traffic", traffic), ("crime", crime)]:
    for col in ["index_right", "index_left"]:
        if col in gdf.columns:
            gdf.drop(columns=[col], inplace=True)

# Reset indices to avoid conflicts
edges = edges.reset_index(drop=True)
traffic = traffic.reset_index(drop=True)
crime = crime.reset_index(drop=True)

# Perform spatial joins with explicit suffixes
edges = gpd.sjoin(edges, crime[["geometry", "severity"]], how="left", predicate="intersects", rsuffix="_crime")
edges = gpd.sjoin(edges, traffic[["geometry", "adt"]], how="left", predicate="intersects", rsuffix="_traffic")

print("✅ Spatial join complete.")

# ---------------------------------------------------------------
# 5. Clean and map features to numeric
# ---------------------------------------------------------------
# Map severity strings to numeric safely
severity_mapping = {
    "Very Low": 1,
    "Low": 2,
    "Medium": 3,
    "High": 4,
    "Very High": 5
}

if "severity" in edges.columns:
    edges["severity"] = edges["severity"].map(severity_mapping)

# Fill any NaNs in severity with default value 1
edges["severity"] = edges["severity"].fillna(1).astype(float)

# Ensure adt is numeric and fill missing values
if "adt" in edges.columns:
    edges["adt"] = pd.to_numeric(edges["adt"], errors="coerce")
    if edges["adt"].notna().any():
        edges["adt"] = edges["adt"].fillna(edges["adt"].median())
    else:
        edges["adt"] = edges["adt"].fillna(1)
else:
    edges["adt"] = 1.0

# ---------------------------------------------------------------
# 6. Build synthetic target
# ---------------------------------------------------------------
edges["target_desirability"] = 1 / (1 + edges["severity"]) + 1 / (1 + edges["adt"])

# Ensure no NaNs remain in target
edges["target_desirability"] = edges["target_desirability"].fillna(edges["target_desirability"].median())

# ---------------------------------------------------------------
# 7. Prepare feature matrix and target for model
# ---------------------------------------------------------------
X = edges[["severity", "adt"]]
y = edges["target_desirability"]

# Final sanity check
if X.isna().any().any():
    raise ValueError("NaNs found in feature matrix X")
if y.isna().any():
    raise ValueError("NaNs found in target y")

# ---------------------------------------------------------------
# 8. Train RandomForestRegressor
# ---------------------------------------------------------------
print("🧠 Training RandomForestRegressor...")
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

print(f"✅ Model trained. Test R²: {model.score(X_test, y_test):.3f}")

# ---------------------------------------------------------------
# 9. Save the trained model
# ---------------------------------------------------------------
os.makedirs("models", exist_ok=True)
model_path = "pathshield_app/models/traffic_model.pkl"
joblib.dump(model, model_path)
print(f"💾 Model saved to {model_path}")
print("🎉 Training complete.")
