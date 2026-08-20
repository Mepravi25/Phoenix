import os
import re
import sys

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

print("=== ACCURATE WBT VEHICLE PARSING ===")
for v in vehicles:
    idx = wbt_text.find(f"DEF {v}")
    if idx != -1:
        # Find next DEF or end of file
        next_def = wbt_text.find("DEF ", idx + 10)
        block = wbt_text[idx:next_def] if next_def != -1 else wbt_text[idx:]
        
        node_type = "Robot" if "Robot {" in block[:50] else ("Solid" if "Solid {" in block[:50] else "UNKNOWN")
        
        trans_m = re.search(r'translation\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)', block)
        rot_m = re.search(r'rotation\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)', block)
        ctrl_m = re.search(r'controller\s+"([^"]+)"', block)
        
        t_str = f"({trans_m.group(1)}, {trans_m.group(2)}, {trans_m.group(3)})" if trans_m else "N/A"
        r_str = f"rot: {rot_m.group(4)}" if rot_m else "N/A"
        c_str = ctrl_m.group(1) if ctrl_m else "NONE"
        
        print(f"{v:15s} [{node_type:5s}] pos={t_str:25s} controller='{c_str}'")
    else:
        print(f"{v:15s} NOT FOUND")
