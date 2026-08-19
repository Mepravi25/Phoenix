import json
import math
import os
import time
import cv2
import numpy as np
import paho.mqtt.client as mqtt
from ultralytics import YOLO
from sklearn.ensemble import RandomForestRegressor

# ==========================================
# CONFIGURATION
# ==========================================
BROKER_HOST = os.getenv("MQTT_BROKER", "test.mosquitto.org").strip()
BROKER_PORT = 1883
UPDATE_TOPIC = "city/intersections/update"
NODE_ID = 0  # This physical camera represents Intersection 0
VIDEO_SOURCE = "traffic.mp4" # Replace with 0 for webcam or a video file path

# Load the lightweight YOLOv8 Nano model
print("Loading YOLO model...")
model = YOLO('yolov8n.pt')

# COCO dataset class IDs for vehicles
VEHICLE_CLASSES = [2, 3, 5, 7] # 2: car, 3: motorcycle, 5: bus, 7: truck

# ==========================================
# MOCK MODEL (Matches your earlier script)
# ==========================================
def build_mock_model() -> RandomForestRegressor:
    rng = np.random.default_rng(42)
    queue_lengths = np.arange(0, 41, dtype=float).reshape(-1, 1)
    flush_times = 2.0 + (queue_lengths.ravel() * 0.8) + rng.normal(0, 0.6, 41)
    rf_model = RandomForestRegressor(n_estimators=80, random_state=42)
    rf_model.fit(queue_lengths, flush_times)
    return rf_model

FLUSH_PREDICTOR = build_mock_model()

def predict_flush_time(queue_length: int) -> int:
    prediction = FLUSH_PREDICTOR.predict(np.array([[queue_length]], dtype=float))[0]
    return max(1, math.ceil(float(prediction)))

# ==========================================
# MQTT SETUP
# ==========================================
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="cv-edge-node-0")
client.connect_async(BROKER_HOST, BROKER_PORT, keepalive=60)
client.loop_start()

# ==========================================
# THE CV PROCESSING LOOP
# ==========================================
def run_vision_pipeline():
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if not cap.isOpened():
        print("Error: Could not open video source.")
        return

    print("Starting Live Video Processing. Press 'q' in the video window to quit.")
    
    last_publish = time.monotonic()
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            # Loop the video for the hackathon demo if it ends
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
            
        current_time = time.monotonic()
        
        # We only process and publish every 2 seconds to match the Orchestrator's cadence
        if current_time - last_publish >= 2.0:
            # 1. Run YOLO inference on the frame
            results = model(frame, verbose=False)[0]
            
            # 2. Count bounding boxes that match vehicle classes
            vehicle_count = 0
            for box in results.boxes:
                class_id = int(box.cls[0])
                if class_id in VEHICLE_CLASSES:
                    vehicle_count += 1
            
            # 3. Calculate flush time using the same logic as the simulator
            flush_time = predict_flush_time(vehicle_count)
            
            # 4. Publish to the Orchestrator
            payload = [{"node": NODE_ID, "flush_time": flush_time}]
            client.publish(UPDATE_TOPIC, json.dumps(payload), qos=1)
            last_publish = current_time
            
            print(f"Node {NODE_ID} | Vehicles Detected: {vehicle_count} | Predicted Flush: {flush_time}s")

            # 5. (Optional) Draw the bounding boxes for a cool live demo screen
            annotated_frame = results.plot()
            cv2.imshow("Intersection Camera Agent", annotated_frame)
            
        # The waitKey is required for cv2.imshow to update the GUI thread
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    client.loop_stop()

if __name__ == "__main__":
    run_vision_pipeline()
