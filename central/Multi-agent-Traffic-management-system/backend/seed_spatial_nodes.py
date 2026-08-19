import os
import psycopg2
from dotenv import load_dotenv

# Load credentials from your .env file
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "traffic_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "your_password_here")

# Downtown Los Angeles Origin (Node 0)
ORIGIN_LAT = 34.0522
ORIGIN_LON = -118.2437

# Roughly 500 meters in degrees
LAT_OFFSET = 0.0045 
LON_OFFSET = 0.0055

def seed_database():
    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS
    )
    cursor = conn.cursor()

    # 1. Enable PostGIS (if not already enabled)
    cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # 2. Create the spatial table
    print("Creating spatial intersections table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spatial_intersections (
            node_id INTEGER PRIMARY KEY,
            geom GEOMETRY(Point, 4326)
        );
    """)

    # 3. Clear any existing data to prevent primary key collisions on re-runs
    cursor.execute("TRUNCATE TABLE spatial_intersections;")

    # 4. Generate and insert the 25 nodes
    print("Injecting 25 grid nodes into PostGIS...")
    for node_id in range(25):
        row, col = divmod(node_id, 5)
        
        # Calculate physical GPS coordinates
        node_lat = ORIGIN_LAT - (row * LAT_OFFSET)
        node_lon = ORIGIN_LON + (col * LON_OFFSET)

        # ST_SetSRID and ST_MakePoint are PostGIS C-functions that construct the geometry
        cursor.execute("""
            INSERT INTO spatial_intersections (node_id, geom) 
            VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326));
        """, (node_id, node_lon, node_lat))

    # 5. Create the GiST Spatial Index for blazing fast heatmap queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_spatial_geom 
        ON spatial_intersections USING GIST (geom);
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Successfully seeded PostGIS with 5x5 LA coordinate grid.")

if __name__ == "__main__":
    seed_database()
