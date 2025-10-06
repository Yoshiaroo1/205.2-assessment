import osmnx as ox
import sqlite3

def load_osm(place="Auckland, New Zealand", db_path="navigation.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Download OSM graph
    G = ox.graph_from_place(place, network_type="drive")
    edges = ox.graph_to_gdfs(G, nodes=False)

    for _, row in edges.iterrows():
        # Handle osmid
        osmid = row["osmid"]
        if isinstance(osmid, list):
            osmid = osmid[0]  # or ",".join(map(str, osmid))

        # Handle name
        name = row["name"]
        if isinstance(name, list):
            name = name[0]    # or ",".join(name)
        if name is None:
            name = "Unnamed Road"

        # Insert into SQLite
        cur.execute(
            "INSERT INTO roads (osm_id, name, geom, length_m) VALUES (?, ?, ?, ?)",
            (osmid, name, row["geometry"].wkt, row["length"])
        )

    conn.commit()
    conn.close()
    print("✅ Loaded OSM data into SQLite")

if __name__ == "__main__":
    load_osm()

