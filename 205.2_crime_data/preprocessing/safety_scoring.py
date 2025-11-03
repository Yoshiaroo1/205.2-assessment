import pandas as pd
import os

df = pd.read_csv('data/preprocess_data')

#weights
crime_weights = {
    "Assault": 0.9,
    "Harm or endanger persons": 0.8,
    "Robbery, blackmail, and extortion": 0.7,
    "Sexual Offences": 1.0
}

#label encoded weights
encoded_weights = {
    0: 0.9,  #assault
    1: 0.8,  #harm or endanger persons
    2: 0.7,  #robbery blackmail and extortion
    3: 1.0   #sexual offences
}

#calculate base risk
df['base_risk'] = df.apply(lambda row: row['number_of_victimisations'] * encoded_weights.get(row['anzsoc_division'], 0.5), axis=1)

#change base risk by victimisation counts
df['adjusted_risk'] = df['base_risk'] * (1 + (df['victimisations'] / df['victimisations'].max()))

#safety scoring
df['safety_score'] = 100 - (df['adjusted_risk'] / df['adjusted_risk'].max() * 100)

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

df['safety_level'] = df['safety_score'].apply(categorize)

#calculate average safety score per area unit
area_safety = df.groupby('area_unit', as_index=False).agg({'safety_score': 'mean',
                                                           'centroid_lon': 'first',
                                                           'centroid_lat': 'first'})

#categorize suburb safety levels
area_safety['safety_level'] = area_safety['safety_score'].apply(categorize)

#save both dataframes
detailed_df_path = os.path.join('data', 'detailed_safety_scores.csv')
suburb_df_path = os.path.join('data', 'suburb_safety_scores.csv')

df.to_csv(detailed_df_path, index=False)
area_safety.to_csv(suburb_df_path, index=False)
print(f"Detailed safety scores saved to {detailed_df_path}")
print(f"Suburb safety scores saved to {suburb_df_path}")

print("Sample suburb safety scores:")
print(area_safety.head())