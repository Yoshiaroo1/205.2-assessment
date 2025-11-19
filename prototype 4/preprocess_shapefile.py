import geopandas as gpd
import pandas as pd

# load your CSV
df = pd.read_csv("new dat\\Table ST_Full Data_data.csv")

# load the area unit boundary shapefile from Stats NZ (GeoJSON or SHP)
area_shapes = gpd.read_file("new data\\NZ bounding\\territorial-authority-2025.shp")   # or .shp

# standardize the name columns
df['Area Unit'] = df['Area Unit'].str.strip().str.lower()
area_shapes['AU_NAME'] = area_shapes['AU_NAME'].str.strip().str.lower()

# merge crime records with spatial geometry
geo = df.merge(area_shapes, left_on="Area Unit", right_on="AU_NAME", how="left")

# convert to true GeoDataFrame
geo = gpd.GeoDataFrame(geo, geometry="geometry", crs=area_shapes.crs)

geo["centroid"] = geo.geometry.centroid
geo["lon"] = geo.centroid.x
geo["lat"] = geo.centroid.y

import osmnx as ox

# download driving network for Auckland
G = ox.load_graphml("pathshield_app\\data\\auckland_drive.graphml")

# for each record: find the nearest node on the road network
geo["nearest_osm_node"] = geo.apply(
    lambda row: ox.distance.nearest_nodes(G, row["lon"], row["lat"]),
    axis=1
)

# determine which column contains the incident description
_possible_cols = ['incident type','offence type','offence','type','crime type','description','incident','offence_description','offence_desc']
_inc_col = next((c for c in geo.columns if c.lower() in _possible_cols), None)
if _inc_col is None:
    raise KeyError("No incident/ offence column found in geo. Expected one of: " + ", ".join(_possible_cols))

# keyword -> severity (1 = low, 5 = critical)
_keyword_severity = {
    'homicide': 5, 'murder': 5, 'manslaughter': 5,
    'attempt': 4, 'attempted': 4,
    'sexual': 5, 'rape': 5, 'sexual assault': 5,
    'assault': 4, 'battery': 4,
    'armed': 5, 'weapon': 5, 'shooting': 5, 'stabbing': 5,
    'robbery': 4, 'burglary': 3, 'break and enter': 3,
    'theft': 2, 'shoplift': 2, 'shoplifting': 2,
    'vehicle': 2, 'motor vehicle': 2, 'car theft': 3,
    'arson': 5,
    'fraud': 2, 'scam': 2, 'drugs': 3,
    'vandal': 1, 'damage': 1, 'graffiti': 1,
    'threat': 3
}

def _compute_severity(text):
    txt = (str(text) or "").lower()
    # check for exact keyword occurrences (longer keywords first)
    for kw in sorted(_keyword_severity, key=len, reverse=True):
        if kw in txt:
            return _keyword_severity[kw]
    # fallback: if numeric count column exists, use it (e.g., 'Offences' or 'Count')
    for possible_count in ['count','counts','number','offence count','offences']:
        if possible_count in (c.lower() for c in geo.columns):
            try:
                return min(5, max(1, int(geo.loc[0, [c for c in geo.columns if c.lower()==possible_count][0]]) // 1))
            except Exception:
                break
    # default mid-low severity
    return 2

# assign severity score and label
geo['severity_score'] = geo[_inc_col].apply(_compute_severity)

def _label(score):
    if score >= 5:
        return 'critical'
    if score >= 4:
        return 'high'
    if score >= 3:
        return 'moderate'
    if score == 2:
        return 'low'
    return 'very low'

geo['severity_label'] = geo['severity_score'].apply(_label)

# aggregate severity by area unit (use either Area Unit or AU_NAME depending on what's present)
_area_col = 'Area Unit' if 'Area Unit' in geo.columns else ('AU_NAME' if 'AU_NAME' in geo.columns else None)
if _area_col:
    _agg = geo.groupby(_area_col).severity_score.agg(['mean','sum','count']).rename(columns={'mean':'severity_mean','sum':'severity_sum','count':'incident_count'})
    _agg['severity_mean_norm'] = (_agg['severity_mean'] - _agg['severity_mean'].min()) / (_agg['severity_mean'].ptp() if _agg['severity_mean'].ptp() else 1)
    geo = geo.merge(_agg.reset_index(), left_on=_area_col, right_on=_area_col, how='left')

# final columns: severity_score, severity_label, and aggregated stats per area (if available)