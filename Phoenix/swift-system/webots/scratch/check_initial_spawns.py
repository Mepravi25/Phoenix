import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "controllers")))
import road_network

from road_network import (
    ROAD_NETWORK,
    VEHICLE_ROUTES,
    DETERMINISTIC_VEHICLE_SPAWNS,
    get_lateral_distance_to_lane,
    Lane
)

# Parse WBT positions
wbt_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "worlds", "swift_city.wbt"))
with open(wbt_path, "r", encoding="utf-8") as f:
    wbt_text = f.read()

vehicles = [
    "CAR_001", "CAR_002", "CAR_003", "CAR_004", "CAR_005",
    "CAR_006", "CAR_007", "CAR_008", "CAR_009", "CAR_010",
    "BIKE_001", "BIKE_002", "BIKE_003", "BIKE_004", "BIKE_005",
    "AMBULANCE_001", "FIRE_ENGINE_001"
]

print("=== CHECKING WBT INITIAL POSITIONS AGAINST ASSIGNED ROUTE START LANE ===")
for v in vehicles:
    idx = wbt_text.find(f"DEF {v}")
    if idx != -1:
        next_def = wbt_text.find("DEF ", idx + 10)
        block = wbt_text[idx:next_def] if next_def != -1 else wbt_text[idx:]
        import re
        trans_m = re.search(r'translation\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)', block)
        if trans_m:
            wx, wy = float(trans_m.group(1)), float(trans_m.group(2))
            route = VEHICLE_ROUTES.get(v, [])
            if not route and v == "FIRE_ENGINE_001":
                route = ["LANE_J3_J5_SB", "LANE_J5_J6_WB", "LANE_J6_J4_NE"]
            
            if route:
                first_lane_id = route[0]
                lane = ROAD_NETWORK.get(first_lane_id)
                if lane:
                    dist = get_lateral_distance_to_lane(wx, wy, lane)
                    print(f"{v:15s}: WBT pos=({wx:7.2f}, {wy:7.2f}) | First Lane: {first_lane_id:15s} | Distance to Lane Center: {dist:5.2f}m {'[OK]' if dist <= 2.0 else '[OFF-ROAD!]'}")
                else:
                    print(f"{v:15s}: Lane {first_lane_id} not found")
            else:
                print(f"{v:15s}: No route assigned")
