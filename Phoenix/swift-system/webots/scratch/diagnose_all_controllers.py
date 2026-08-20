import os
import sys
import json
import math

sys.path.append(r"d:\REC\hack\Phoenix\swift-system\webots\controllers")
sys.path.append(r"d:\REC\hack\Phoenix\swift-system\webots\controllers\vehicle_controller")
sys.path.append(r"d:\REC\hack\Phoenix\swift-system\webots\controllers\car_001_controller")
sys.path.append(r"d:\REC\hack\Phoenix\swift-system\webots\controllers\car_002_controller")
sys.path.append(r"d:\REC\hack\Phoenix\swift-system\webots\controllers\car_003_controller")
sys.path.append(r"d:\REC\hack\Phoenix\swift-system\webots\controllers\car_004_controller")
sys.path.append(r"d:\REC\hack\Phoenix\swift-system\webots\controllers\ambulance_001_controller")

import road_network

print("=== CHECKING ALL ROAD NETWORK LANES & OFFSETS ===")
for l_id, lane in road_network.ROAD_NETWORK.items():
    dx = lane.end_point[0] - lane.start_point[0]
    dy = lane.end_point[1] - lane.start_point[1]
    dist = math.hypot(dx, dy)
    ux, uy = (dx/dist, dy/dist) if dist > 0 else (1, 0)
    print(f"Lane {l_id:20s}: dir={lane.direction:5s} start=({lane.start_point[0]:7.1f},{lane.start_point[1]:7.1f}) end=({lane.end_point[0]:7.1f},{lane.end_point[1]:7.1f}) unit=({ux:.2f},{uy:.2f}) heading={math.degrees(lane.target_heading):.1f}°")

print("\n=== VEHICLE SPAWNS IN ROAD_NETWORK.PY ===")
for v_id, sp in road_network.DETERMINISTIC_VEHICLE_SPAWNS.items():
    print(f"Vehicle {v_id:15s}: pos=({sp['x']:7.1f}, {sp['y']:7.1f}) heading={math.degrees(sp['heading']):.1f}°")

print("\n=== VEHICLE ROUTES IN ROAD_NETWORK.PY ===")
for v_id, route in road_network.VEHICLE_ROUTES.items():
    print(f"Vehicle {v_id:15s}: route={route}")

