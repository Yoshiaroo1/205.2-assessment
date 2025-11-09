import pandas as pd
import geopandas as gpd
import os

#paths
DATA_FOLDER = "data"
SHAPEFILE_PATH = os.path.join(DATA_FOLDER, "TA2025.shp")  # <-- Updated shapefile path
CSV_PATH = os.path.join(DATA_FOLDER, "preprocess_data.csv")

#load
df = pd.read_csv(CSV_PATH)
gdf = gpd.read_file(SHAPEFILE_PATH)


if "TA2025_NAME" in gdf.columns:
    gdf = gdf.rename(columns={"TA2025_NAME": "area_unit"})
elif "TA2025" in gdf.columns:
    gdf = gdf.rename(columns={"TA2025": "area_unit"})

#weights
encoded_weights = {
    0: 0.9,  # Assault
    1: 0.8,  # Harm or endanger persons
    2: 0.7,  # Robbery, blackmail, and extortion
    3: 1.0   # Sexual Offences
}

#calc base risk
df["base_risk"] = df.apply(
    lambda row: row["number_of_victimisations"] * encoded_weights.get(row["anzsoc_division"], 0.5),
    axis=1
)

#calc by victimisation counts
df["adjusted_risk"] = df["base_risk"] * (1 + (df["victimisations"] / df["victimisations"].max()))

#safety scoring
df["safety_score"] = 100 - (df["adjusted_risk"] / df["adjusted_risk"].max() * 100)

#categorize safety levels
def categorize(score):
    if score >= 80:
        return "Very Safe"
    elif score >= 60:
        return "Safe"
    elif score >= 40:
        return "Moderate"
    elif score >= 20:
        return "Unsafe"
    else:
        return "Very Unsafe"

df["safety_level"] = df["safety_score"].apply(categorize)

#scoring per area unit
area_safety = (
    df.groupby("area_unit", as_index=False)
      .agg({"safety_score": "mean"})
)

#merge with geodataframe
merged = gdf.merge(area_safety, on="area_unit", how="left")

#calc centroids
merged["centroid_lon"] = merged.geometry.centroid.x
merged["centroid_lat"] = merged.geometry.centroid.y

#categorize suburb safety levels
merged["safety_level"] = merged["safety_score"].apply(categorize)

#save both detailed and aggregated outputs
detailed_df_path = os.path.join(DATA_FOLDER, "detailed_safety_scores.csv")
suburb_df_path = os.path.join(DATA_FOLDER, "suburb_safety_scores.csv")

df.to_csv(detailed_df_path, index=False)
merged.drop(columns="geometry").to_csv(suburb_df_path, index=False)

print(f"Detailed safety scores saved to {detailed_df_path}")
print(f"Suburb safety scores saved to {suburb_df_path}")
print("\nSample suburb safety scores:")
print(merged[["area_unit", "safety_score", "safety_level"]].head())
