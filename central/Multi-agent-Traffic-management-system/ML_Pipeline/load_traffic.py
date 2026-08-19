import psycopg2
import pandas as pd
from io import StringIO

print("Loading CSV...")
# 1. Read the dataset (first column contains the timestamps)
df = pd.read_csv('METR-LA.csv', index_col=0)
df.index = pd.to_datetime(df.index)

print("Transforming matrix to narrow relational format...")
# 2. Melt the wide matrix into a narrow 3-column table
df_long = df.reset_index().melt(
    id_vars=['index'], 
    var_name='sensor_id', 
    value_name='speed'
)
df_long.rename(columns={'index': 'timestamp'}, inplace=True)

# 3. Write to an in-memory string buffer for high-speed I/O
print("Buffering data...")
buffer = StringIO()
df_long.to_csv(buffer, index=False, header=False)
buffer.seek(0)

# 4. Connect to PostgreSQL and execute bulk COPY
print("Connecting to PostgreSQL and executing bulk COPY...")
conn = psycopg2.connect(
    dbname="traffic_db",
    user="postgres",
    password="postgres",  # Update with your credentials
    host="localhost"
)
cursor = conn.cursor()

# 5. Use copy_expert to pipe the buffer directly to the table
cursor.copy_expert(
    "COPY metr_la_traffic (timestamp, sensor_id, speed) FROM STDIN WITH CSV", 
    buffer
)

conn.commit()
cursor.close()
conn.close()
print("Ingestion complete!")
