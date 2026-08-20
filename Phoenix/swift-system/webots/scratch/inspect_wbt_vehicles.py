import os
import re
import sys

# Add controllers to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "controllers")))
import road_network

wbt_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "worlds", "swift_city.wbt"))
with open(wbt_path, "r", encoding="utf-8") as f:
    wbt_text = f.read()

vehicles = [
    "CAR_001", "CAR_002", "CAR_003", "CAR_004", "CAR_005",
    "CAR_006", "CAR_007", "CAR_008", "CAR_009", "CAR_010",
    "BIKE_001", "BIKE_002", "BIKE_003", "BIKE_004", "BIKE_005",
    "AMBULANCE_001", "FIRE_ENGINE_001"
]

print("=== WBT VEHICLE STATUS IN WORLD FILE ===")
for v in vehicles:
    # Match DEF block
    m = re.search(rf'DEF\s+{v}\s+(Robot|Solid)\s*\{{([^}}]+)\}}', wbt_text, re.DOTALL)
    if m:
        n_type = m.group(1)
        body = m.group(2)
        trans = re.search(r'translation\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)', body)
        rot = re.search(r'rotation\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)', body)
        ctrl = re.search(r'controller\s+"([^"]+)"', body)
        
        t_str = f"({trans.group(1)}, {trans.group(2)}, {trans.group(3)})" if trans else "UNKNOWN"
        r_str = f"({rot.group(1)}, {rot.group(2)}, {rot.group(3)}, {rot.group(4)})" if rot else "UNKNOWN"
        c_str = ctrl.group(1) if ctrl else "NONE"
        print(f"{v} [{n_type}] -> pos: {t_str}, rot: {r_str}, controller: '{c_str}'")
    else:
        print(f"{v} -> NOT FOUND")

print("\n=== DETERMINISTIC SPAWNS IN ROAD_NETWORK.PY ===")
spawns = road_network.DETERMINISTIC_VEHICLE_SPAWNS
for v, data in spawns.items():
    print(f"{v} -> x: {data['x']}, y: {data['y']}, heading: {data['heading']}")

print("\n=== VEHICLE ROUTES IN ROAD_NETWORK.PY ===")
routes = road_network.VEHICLE_ROUTES
for v, r in routes.items():
    print(f"{v} -> route: {r}")
