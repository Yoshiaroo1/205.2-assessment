from pathlib import Path
import sys
import logging
import pandas as pd
import geopandas as gpd
from rapidfuzz import process, fuzz

# linked position.py
# Link areas from CSV to NZ territorial authority shapefile so result can be used with osmnx.
# Usage: place this file in the same project root that contains the "new data" folder and run it.
# Requirements: geopandas, pandas, rapidfuzz (for fuzzy matching), pyproj
# Install if needed: pip install geopandas pandas rapidfuzz



logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def find_column_ignore_case(df, targets):
    """Return first column name from df that matches any of targets ignoring case; else None."""
    lc = {c.lower(): c for c in df.columns}
    for t in targets:
        if t.lower() in lc:
            return lc[t.lower()]
    return None


def best_name_field(gdf):
    """Try to find a sensible name column in the shapefile GeoDataFrame."""
    candidates = [
        "TA2025_NAM", "Name", "NAME", "TA_NAME", "NAME_2025", "terr_name",
        "territory", "Area", "area", "TA2025_NAM_1", "TA_NAME_2025"
    ]
    col = find_column_ignore_case(gdf, candidates)
    if col:
        return col
    # fallback: choose the longest string column (likely a name)
    str_cols = [c for c in gdf.columns if gdf[c].dtype == object]
    if not str_cols:
        return None
    # pick the column with the largest average length
    avg_len = {c: gdf[c].dropna().astype(str).map(len).mean() for c in str_cols}
    return max(avg_len, key=avg_len.get)


def detect_area_column_csv(df):
    return find_column_ignore_case(df, ["Area", "area", "TA", "territory", "name", "Area Unit", "area unit"])


def fuzzy_map(csv_names, gdf_names, score_cutoff=80):
    """Map each csv_name to best gdf_name using rapidfuzz. Returns dict csv_name->gdf_name."""
    mapping = {}
    choices = list(gdf_names)
    for name in sorted(set(csv_names)):
        if pd.isna(name) or str(name).strip() == "":
            mapping[name] = None
            continue
        match, score, idx = process.extractOne(str(name), choices, scorer=fuzz.token_sort_ratio)
        if score >= score_cutoff:
            mapping[name] = match
        else:
            mapping[name] = None
    return mapping


def main():
    root = Path(__file__).parent.resolve()
    csv_path = root / "new data" / "combined_by_area_with_severity.csv"
    shp_path = root / "new data" / "auckland suburbs" / "statistical-area-2-2025.shp"

    if not csv_path.exists():
        logging.error("CSV not found: %s", csv_path)
        sys.exit(1)
    if not shp_path.exists():
        logging.error("Shapefile not found: %s", shp_path)
        sys.exit(1)

    # read CSV and shapefile
    df = pd.read_csv(csv_path)
    gdf = gpd.read_file(shp_path)

    # detect columns
    csv_area_col = detect_area_column_csv(df)
    if not csv_area_col:
        logging.error("Could not detect an Area column in CSV. Columns: %s", list(df.columns))
        sys.exit(1)
    logging.info("Using CSV area column: %s", csv_area_col)

    shp_name_col = best_name_field(gdf)
    if not shp_name_col:
        logging.error("Could not detect a name column in shapefile. Columns: %s", list(gdf.columns))
        sys.exit(1)
    logging.info("Using shapefile name column: %s", shp_name_col)

   # --- After reading CSV and shapefile ---

    # Normalize names
    df[csv_area_col] = df[csv_area_col].astype(str).str.strip()
    gdf[shp_name_col] = gdf[shp_name_col].astype(str).str.strip()

    # Rename shapefile column for clarity
    gdf = gdf.rename(columns={shp_name_col: "_shp_name"})
    gdf["_shp_name_lc"] = gdf["_shp_name"].str.lower()
    df["_area_lc"] = df[csv_area_col].str.lower()

    # 1️⃣ Exact match first
    merged = df.merge(gdf[["_shp_name", "_shp_name_lc", "geometry"]],
                    left_on="_area_lc", right_on="_shp_name_lc",
                    how="left")

    num_exact_unmatched = merged["_shp_name"].isna().sum()
    logging.info("Exact match succeeded for %d of %d rows",
                merged.shape[0] - num_exact_unmatched, merged.shape[0])

    # 2️⃣ Fuzzy match for unmatched rows
    if num_exact_unmatched > 0:
        unmatched_mask = merged["_shp_name"].isna()
        csv_names_unmatched = merged.loc[unmatched_mask, csv_area_col].unique()
        gdf_names = gdf["_shp_name"].unique()

        mapping = fuzzy_map(csv_names_unmatched, gdf_names, score_cutoff=85)

        # Apply fuzzy mapping
        merged.loc[unmatched_mask, "_shp_name"] = merged.loc[unmatched_mask, csv_area_col].map(mapping)
        # Fill in geometry for fuzzy matches
        # Create a lookup dict: shapefile name -> geometry
        geom_lookup = dict(zip(gdf["_shp_name"], gdf.geometry))
        merged["geometry"] = merged.apply(
            lambda row: geom_lookup.get(row["_shp_name"]) if pd.notna(row["_shp_name"]) else row.get("geometry"),
            axis=1
        )

        num_fuzzy_unmatched = merged["_shp_name"].isna().sum()
        logging.info("After fuzzy matching, still unmatched: %d rows", num_fuzzy_unmatched)

    # 3️⃣ Create final GeoDataFrame
    merged_gdf = gpd.GeoDataFrame(merged, geometry="geometry", crs=gdf.crs)

    # 4️⃣ Ensure WGS84 CRS for OSMnx
    try:
        merged_gdf = merged_gdf.to_crs(epsg=4326)
    except Exception:
        logging.warning("Could not reproject to EPSG:4326; proceeding with existing CRS.")

    #print head
    logging.info("Merged GeoDataFrame preview:\n%s", merged_gdf.head().to_string())
    
    # Save GeoJSON
    out_geojson = root / "linked_areas.geojson"
    merged_gdf.to_file(out_geojson, driver="GeoJSON")
    logging.info("Saved merged GeoDataFrame to %s", out_geojson)


if __name__ == "__main__":
    main()