import re
import math
import os
import json

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"
with open(wbt_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find all Solid objects in swift_city.wbt
solids = []
matches = re.finditer(r'Solid\s*\{', content)
for m in matches:
    start_idx = m.start()
    open_count = 0
    end_idx = start_idx
    for i in range(start_idx, len(content)):
        if content[i] == '{':
            open_count += 1
        elif content[i] == '}':
            open_count -= 1
            if open_count == 0:
                end_idx = i + 1
                break
    block = content[start_idx:end_idx]
    name_match = re.search(r'name\s*"([^"]+)"', block)
    if not name_match:
        continue
    name = name_match.group(1)
    trans_match = re.search(r'translation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
    rot_match = re.search(r'rotation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
    size_match = re.search(r'size\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
    
    tx, ty, tz = [float(x) for x in trans_match.groups()] if trans_match else (0, 0, 0)
    rot = [float(x) for x in rot_match.groups()] if rot_match else (0, 0, 1, 0)
    size = [float(x) for x in size_match.groups()] if size_match else (0, 0, 0)
    
    solids.append({
        "name": name,
        "trans": (tx, ty, tz),
        "rot": rot,
        "size": size,
        "block": block[:200]
    })

print(f"Total Solids found: {len(solids)}")
road_solids = [s for s in solids if "ROAD" in s["name"] or "JUNCTION" in s["name"]]
print(f"Road/Junction Solids found: {len(road_solids)}")
for r in road_solids:
    print(f"Name: {r['name']:30s} Pos: ({r['trans'][0]:7.1f}, {r['trans'][1]:7.1f}, {r['trans'][2]:5.2f}) Size: {r['size']} Rot: {r['rot']}")

# Compare with ambulance_001_controller.py LOOP_WAYPOINTS
sys_path = r"d:\REC\hack\Phoenix\swift-system\webots\controllers"
import sys
sys.path.append(sys_path)
import road_network

print("\n=== ROAD_NETWORK LANES IN ROAD_NETWORK.PY ===")
for lane_name, lane in road_network.ROAD_NETWORK.items():
    print(f"Lane: {lane_name:20s} Dir: {lane.direction:5s} Start: {lane.start_point} End: {lane.end_point}")
    print(f"   Waypoints: {lane.waypoints}")
