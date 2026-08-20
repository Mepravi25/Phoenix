import os
import sys
import re

# Add controllers path
sys.path.append(r"d:\REC\hack\Phoenix\swift-system\webots\controllers")
import road_network

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"
with open(wbt_path, "r", encoding="utf-8") as f:
    wbt_text = f.read()

print("==================================================")
print("COMPARING WEBOTS WORLD ROADS WITH ROAD_NETWORK.PY")
print("==================================================")

# Parse all Solid/Transform objects with names in wbt_text
# We search for Solid { ... name "XYZ" ... translation X Y Z ... size S1 S2 S3 ... rotation R1 R2 R3 R4 ... }
objects = []
matches = list(re.finditer(r'(Solid|Transform)\s*\{', wbt_text))

for m in matches:
    start_idx = m.start()
    open_count = 0
    end_idx = start_idx
    for i in range(start_idx, len(wbt_text)):
        if wbt_text[i] == '{':
            open_count += 1
        elif wbt_text[i] == '}':
            open_count -= 1
            if open_count == 0:
                end_idx = i + 1
                break
    block = wbt_text[start_idx:end_idx]
    name_m = re.search(r'name\s*"([^"]+)"', block)
    if not name_m:
        continue
    name = name_m.group(1)
    trans_m = re.search(r'translation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
    size_m = re.search(r'size\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
    rot_m = re.search(r'rotation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
    
    tx, ty, tz = [float(x) for x in trans_m.groups()] if trans_m else (0, 0, 0)
    sx, sy, sz = [float(x) for x in size_m.groups()] if size_m else (0, 0, 0)
    rot = [float(x) for x in rot_m.groups()] if rot_m else None
    
    objects.append({
        "name": name,
        "type": m.group(1),
        "trans": (tx, ty, tz),
        "size": (sx, sy, sz),
        "rot": rot
    })

print(f"Total parsed objects with names: {len(objects)}")

# 1. Compare Junctions
print("\n--- 1. JUNCTION COMPARISON ---")
wbt_junctions = {o["name"]: o for o in objects if "JUNCTION" in o["name"] and not o["name"].startswith("LABEL")}
for j_id, j_info in road_network.JUNCTION_REGISTRY.items():
    center = j_info.get("center")
    wbt_j = wbt_junctions.get(j_id)
    if wbt_j:
        w_t = wbt_j["trans"]
        w_s = wbt_j["size"]
        dx = abs(center[0] - w_t[0])
        dy = abs(center[1] - w_t[1])
        status = "MATCH" if dx < 1.0 and dy < 1.0 else f"MISMATCH (diff={dx:.1f}, {dy:.1f})"
        print(f"Junction {j_id:12s} | PY: ({center[0]:7.1f}, {center[1]:7.1f}) | WBT: ({w_t[0]:7.1f}, {w_t[1]:7.1f}, {w_t[2]:4.2f}) Size: {w_s[:2]} | {status}")
    else:
        print(f"Junction {j_id:12s} | PY: ({center[0]:7.1f}, {center[1]:7.1f}) | WBT: MISSING IN WORLD!")

# 2. Compare Roads
print("\n--- 2. ROAD COMPARISON ---")
wbt_roads = {o["name"]: o for o in objects if "ROAD" in o["name"]}
print(f"Total WBT Road objects: {len(wbt_roads)}")
for name, r in wbt_roads.items():
    print(f"WBT Road: {name:32s} Center: ({r['trans'][0]:7.1f}, {r['trans'][1]:7.1f}, {r['trans'][2]:4.2f}) Size: ({r['size'][0]:6.1f}, {r['size'][1]:6.1f}, {r['size'][2]:4.2f}) Rot: {r['rot']}")

# 3. Check Initial Spawns of Vehicles in WBT vs road_network.py
print("\n--- 3. VEHICLE INITIAL POSITIONS IN WBT vs ROAD_NETWORK.PY ---")
wbt_vehicles = {o["name"]: o for o in objects if o["name"].startswith(("CAR_", "BIKE_", "AMBULANCE_", "FIRE_"))}
for v_id, v_obj in wbt_vehicles.items():
    w_t = v_obj["trans"]
    py_spawn = road_network.DETERMINISTIC_VEHICLE_SPAWNS.get(v_id)
    if py_spawn:
        px, py = py_spawn["x"], py_spawn["y"]
        dx = abs(px - w_t[0])
        dy = abs(py - w_t[1])
        status = "OK" if dx < 1.0 and dy < 1.0 else f"DIFF ({dx:.1f}, {dy:.1f})"
        print(f"Vehicle {v_id:15s} | WBT Pos: ({w_t[0]:7.1f}, {w_t[1]:7.1f}, {w_t[2]:4.2f}) | PY Spawn: ({px:7.1f}, {py:7.1f}) | {status}")
    else:
        print(f"Vehicle {v_id:15s} | WBT Pos: ({w_t[0]:7.1f}, {w_t[1]:7.1f}, {w_t[2]:4.2f}) | PY Spawn: NONE")

