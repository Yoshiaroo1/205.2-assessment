import sqlite3

def init_db(db_path="navigation.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS roads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        osm_id INTEGER,
        name TEXT,
        geom TEXT,
        length_m REAL
    );

    CREATE TABLE IF NOT EXISTS traffic (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        road_id INTEGER,
        timestamp TEXT,
        speed_kmh REAL,
        FOREIGN KEY (road_id) REFERENCES roads(id)
    );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
