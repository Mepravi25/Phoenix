import time
import schedule
import psycopg2
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

# ==========================================
# CONFIGURATION
# ==========================================
DB_HOST = "localhost"
DB_NAME = "traffic_db"
DB_USER = "postgres"
DB_PASS = "postgres"  # Update this!
NUM_NODES = 25  # Matches the 5x5 grid in orchestrator_dashboard.py
EPOCHS = 50
LEARNING_RATE = 0.01

# ==========================================
# 1. PYTORCH MODEL DEFINITION
# ==========================================
class LinearSpatialGraphModel(nn.Module):
    """
    A lightweight spatial graph convolution layer.
    Mathematically: H_pred = ReLU(A_hat @ H_0 @ W)
    """
    def __init__(self, num_nodes):
        super().__init__()
        # The learnable weight matrix W. 
        # We initialize it randomly, and backpropagation will optimize it.
        self.W = nn.Parameter(torch.randn(num_nodes, num_nodes) * 0.1)

    def forward(self, H_0, A_hat):
        # A_hat @ H_0 diffuses the traffic spatially
        # @ self.W applies the learned amplification/decay
        H_1 = torch.matmul(torch.matmul(A_hat, H_0), self.W)
        return torch.relu(H_1)

# ==========================================
# 2. DATA INGESTION & TENSOR FORMATTING
# ==========================================
def fetch_and_prep_data():
    print("Fetching training data from PostgreSQL...")
    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
    )
    
    # We select exactly 25 unique sensors to match the 5x5 hackathon dashboard grid
    query = f"""
        SELECT timestamp, sensor_id, speed 
        FROM metr_la_traffic 
        WHERE sensor_id IN (
            SELECT DISTINCT sensor_id FROM metr_la_traffic LIMIT {NUM_NODES}
        )
        ORDER BY timestamp ASC;
    """
    df = pd.read_sql(query, conn)
    conn.close()

    # Pivot the narrow relational data back into a Wide Matrix (Time x Nodes)
    pivot_df = df.pivot(index='timestamp', columns='sensor_id', values='speed')
    pivot_df.fillna(method='ffill', inplace=True) # Forward fill missing sensor drops
    pivot_df.fillna(0, inplace=True)
    
    # Convert speeds to "congestion/flush time" proxy (lower speed = higher congestion)
    # This aligns the real data with your Hackathon simulation logic
    max_speed = pivot_df.max().max()
    congestion_matrix = (max_speed - pivot_df.values) / 5.0 
    
    # Create input (H_0) and target (H_1) pairs. 
    # We train the model to predict the traffic state 5 minutes into the future.
    X = torch.tensor(congestion_matrix[:-1], dtype=torch.float32) # Time t
    Y = torch.tensor(congestion_matrix[1:], dtype=torch.float32)  # Time t+1
    
    return X, Y

# ==========================================
# 3. THE TRAINING LOOP
# ==========================================
def train_stgnn_job():
    print(f"\n--- Starting 24-Hour STGNN Training Job at {time.strftime('%H:%M:%S')} ---")
    
    X, Y = fetch_and_prep_data()
    
    # Generate a dummy normalized adjacency matrix (A_hat) for the 25 nodes
    # In a full production system, this would be computed from exact GPS coordinates
    A_hat = torch.eye(NUM_NODES) + 0.1 * torch.randn(NUM_NODES, NUM_NODES)
    A_hat = torch.clamp(A_hat, min=0)
    
    model = LinearSpatialGraphModel(NUM_NODES)
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.MSELoss() # Mean Squared Error
    
    print(f"Training on {len(X)} time-steps...")
    for epoch in range(EPOCHS):
        optimizer.zero_grad()
        
        # Forward pass
        predictions = model(X, A_hat)
        
        # Calculate loss (Energy gradient)
        loss = criterion(predictions, Y)
        
        # Backward pass (Backpropagation)
        loss.backward()
        optimizer.step()
        
        if epoch % 10 == 0 or epoch == EPOCHS - 1:
            print(f"Epoch {epoch:02d}/{EPOCHS} - Loss: {loss.item():.4f}")

    # ==========================================
    # 4. SERIALIZATION FOR THE ORCHESTRATOR
    # ==========================================
    print("Training complete. Exporting weights...")
    # Detach the matrix from the computation graph and push it to the CPU
    weight_matrix = model.W.detach().cpu()
    
    # Save precisely the format that orchestrator_dashboard.py expects
    torch.save({'weight_matrix': weight_matrix}, "stgnn_weights.pt")
    print("Successfully saved 'stgnn_weights.pt'. The Orchestrator will now use real intelligence.")

# ==========================================
# 5. SCHEDULER
# ==========================================
if __name__ == "__main__":
    # Run the job once immediately on startup
    train_stgnn_job()
    
    # Schedule to run continuously every 24 hours
    schedule.every(24).hours.do(train_stgnn_job)
    
    print("\nTraining pipeline is active. Sleeping until the next 24-hour cycle...")
    while True:
        schedule.run_pending()
        time.sleep(60) # Sleep for 60 seconds before checking the schedule again
