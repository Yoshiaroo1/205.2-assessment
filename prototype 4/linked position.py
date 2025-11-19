from pathlib import Path
import sys
import logging
import pandas as pd
import geopandas as gpd
from rapidfuzz import process, fuzz
import re
from unidecode import unidecode

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

#abbreviation handle
ABBREVIATIONS = {
    r"\bst\b": "saint",
    r"\bmt\b": "mount",
    r"\bave\b": "avenue",
    r"\bdr\b": "drive",
    r"\brd\b": "road",
    r"\bct\b": "court",
    r"\bpl\b": "place",
    r"\bpk\b": "park",
    r"\bblvd\b": "boulevard",
}

def expand_abbreviations(name: str) -> str:
    """Replace common abbreviations with full words."""
    for abbr, full in ABBREVIATIONS.items():
        name = re.sub(abbr, full, name, flags=re.IGNORECASE)
    return name

#normalize 
def normalize_name(s):
    """Normalize a string for comparison, including abbreviations, but keep spaces."""
    if pd.isna(s):
        return ""
    s = str(s).strip().lower()
    s = unidecode(s)                   # remove accents
    s = expand_abbreviations(s)        # expand abbreviations
    s = re.sub(r"[^a-z0-9\s]", "", s)  # remove punctuation, keep spaces
    s = re.sub(r"\b(north|south|east|west|n|s|e|w)\b", "", s)  # remove directions
    s = re.sub(r"\s+", " ", s)         # collapse multiple spaces
    return s

def find_column_ignore_case(df, targets):
    """Return first column name from df that matches any of targets ignoring case."""
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
    # fallback: pick the longest string column
    str_cols = [c for c in gdf.columns if gdf[c].dtype == object]
    if not str_cols:
        return None
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
        match, score, _ = process.extractOne(str(name), choices, scorer=fuzz.token_sort_ratio)
        mapping[name] = match if score >= score_cutoff else None
    return mapping

def preview_name_mismatches(df, gdf, csv_name_col, shp_name_col, limit=30):
    """Print names in CSV vs shapefile that do not match exactly."""
    df_names = set(df[csv_name_col].apply(normalize_name))
    gdf_names = set(gdf[shp_name_col].astype(str).apply(normalize_name))

    unmatched_csv = sorted(df_names - gdf_names)
    unmatched_shp = sorted(gdf_names - df_names)

    print("\n names in CSV not found in shapefile (sample):")
    for name in unmatched_csv[:limit]:
        print("  CSV →", name)

    print("\n names in shapefile not found in CSV (sample):")
    for name in unmatched_shp[:limit]:
        print("  SHP →", name)

    print(f"\nTotal unmatched (CSV): {len(unmatched_csv)}")
    print(f"Total unmatched (Shapefile): {len(unmatched_shp)}")


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

    # detect area/name columns
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

    # --- Preview mismatches before merging ---
    print("\nPreviewing unmatched names before merge:")
    preview_name_mismatches(df, gdf, csv_area_col, shp_name_col, limit=30)

    # --- Normalize names for merging ---
    df["_area_norm"] = df[csv_area_col].apply(normalize_name)
    gdf["_shp_name"] = gdf[shp_name_col].astype(str).str.strip()
    gdf["_shp_name_norm"] = gdf["_shp_name"].apply(normalize_name)

    # 1️⃣ Exact match
    merged = df.merge(
        gdf[["_shp_name", "_shp_name_norm", "geometry"]],
        left_on="_area_norm",
        right_on="_shp_name_norm",
        how="left"
    )

    num_exact_unmatched = merged["_shp_name"].isna().sum()
    print(f"\nExact match succeeded for {merged.shape[0] - num_exact_unmatched} of {merged.shape[0]} rows")

    # 2️⃣ Fuzzy match for unmatched
    if num_exact_unmatched > 0:
        unmatched_mask = merged["_shp_name"].isna()
        csv_names_unmatched = merged.loc[unmatched_mask, "_area_norm"].unique()
        gdf_names_norm = gdf["_shp_name_norm"].unique()

        norm_mapping = fuzzy_map(csv_names_unmatched, gdf_names_norm, score_cutoff=85)
        norm_to_orig = dict(zip(gdf["_shp_name_norm"], gdf["_shp_name"]))

        # Apply fuzzy mapping
        merged.loc[unmatched_mask, "_shp_name"] = merged.loc[unmatched_mask, "_area_norm"].map(
            lambda x: norm_to_orig.get(norm_mapping.get(x))
        )

        # Fill geometry
        geom_lookup = dict(zip(gdf["_shp_name"], gdf.geometry))
        merged["geometry"] = merged.apply(
            lambda row: geom_lookup.get(row["_shp_name"]) if pd.notna(row["_shp_name"]) else row.get("geometry"),
            axis=1
        )

        num_fuzzy_unmatched = merged["_shp_name"].isna().sum()
        print(f"After fuzzy matching, still unmatched: {num_fuzzy_unmatched} rows")

        # Show CSV rows still unmatched after fuzzy matching
        still_unmatched = merged[merged["_shp_name"].isna()]
        print(f"\nCSV rows still unmatched after fuzzy matching: {len(still_unmatched)} rows")
        print(still_unmatched[[csv_area_col]].to_string(index=False))



    #geo dataframe
    merged_gdf = gpd.GeoDataFrame(merged, geometry="geometry", crs=gdf.crs)

    # 4️⃣ Ensure WGS84 CRS
    try:
        merged_gdf = merged_gdf.to_crs(epsg=4326)
    except Exception:
        logging.warning("Could not reproject to EPSG:4326; proceeding with existing CRS.")

    # 5️⃣ Preview merged table
    print("\nMerged GeoDataFrame preview (first 10 rows):")
    #print(merged_gdf.head(10)[[csv_area_col, "_shp_name", "geometry"]].to_string(index=False))

    # Save GeoJSON
    out_geojson = root / "linked_areas.geojson"
    merged_gdf.to_file(out_geojson, driver="GeoJSON")
    logging.info("Saved merged GeoDataFrame to %s", out_geojson)


if __name__ == "__main__":
    main()
