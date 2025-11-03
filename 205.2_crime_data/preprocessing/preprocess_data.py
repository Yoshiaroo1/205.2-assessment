import pandas as pd
import os
import geopandas as gpd
from sklearn.preprocessing import StandardScaler, LabelEncoder
import matplotlib.pyplot as plt

#define paths and constants
DATA_FOLDER = 'data/'
SHAPEFILE_PATH = "data/TA2014.shp"
CSV_FILES = ['assault_data.csv', 'endanger_persons_data.csv',
              'seoffences_data.csv', 'robbery_data.csv']

#load and merge CSV files
def load_and_merge_data(data_folder, csv_files):
    data_frames = []
    for file in csv_files:
        df = pd.read_csv(os.path.join(data_folder, file))
        data_frames.append(df)
    merged_data = pd.concat(data_frames, ignore_index=True)
    print(f"Merged data shape: {merged_data.shape}")
    return merged_data

df = load_and_merge_data(DATA_FOLDER, CSV_FILES)

df.columns = df.columns.str.lower().str.replace(' ', '_').str.replace(r'[^\w\s]', '', regex=True)

#convert 'year_month' to datetime
df['year_month'] = pd.to_datetime(df['year_month'], errors='coerce', dayfirst=True)

#extract numeric features
df['year'] = df['year_month'].dt.year
df['month'] = df['year_month'].dt.month
df['day'] = df['year_month'].dt.day

#missing values with 0 in victimisation counts and mean for others
df = df.drop_duplicates()
for col in df.select_dtypes(include=['float64', 'int64']).columns:
    if 'victimisation' in col:
        df[col] = df[col].fillna(0, inplace=True) #counts -> 0
    else:
        df[col].fillna(df[col].mean(), inplace=True) #other numeric -> mean

#encode categorical variables
categorical_cols = ['anzsoc_division', 'anzsoc_group', 'area_unit', 
                    'region', 'territorial_authority', 'ta2014_nam', 'category']
label_encoders = {}
for col in categorical_cols:
    le = LabelEncoder()
    df[col] = df[col].astype(str)  # Ensure all data is string type
    df[col] = le.fit_transform(df[col])
    label_encoders[col] = le
    print(f"Encoded {col} with classes: {le.classes_}")

#add centroid coordinates from shapefile
gdf = gpd.read_file(SHAPEFILE_PATH)
gdf.columns = gdf.columns.str.lower()
gdf['centroid_lon'] = gdf.geometry.centroid.x
gdf['centroid_lat'] = gdf.geometry.centroid.y

#debug 
if 'ta2014_nam' in gdf.columns and 'ta2014_nam' in df.columns:
    df = df.merge(gdf[['ta2014_nam', 'centroid_lon', 'centroid_lat']], on='ta2014_nam', how='left')
    print("Merged centroid coordinates into main dataframe.")
else:
    print("Warning: 'ta2014_nam' column missing in either dataframe for merging centroids.")

#scale numeric features
numeric_cols = ['number_of_victimisations', 'victimisations']
scaler = StandardScaler()
for col in numeric_cols:
    if col in df.columns:
        df[col] = scaler.fit_transform(df[[col]])
        print(f"Scaled column: {col}")

#save preprocessed data
output_path = os.path.join(DATA_FOLDER, 'preprocessed_data.csv')
df.to_csv(output_path, index=False)
print(f"Preprocessed data saved to {output_path}")

print(list(df.columns))

