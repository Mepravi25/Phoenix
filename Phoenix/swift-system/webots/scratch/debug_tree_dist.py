import math
from parse_top_vrml import get_top_nodes
import re

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"
with open(wbt_path, "r", encoding="utf-8") as f:
    text = f.read()

nodes = get_top_nodes(text)

trees = []
road_obbs = []

for node_type, start_pos, end_pos, node_str in nodes:
    nm_match = re.search(r'name\s+\"([^\"]+)\"', node_str)
    name = nm_match.group(1) if nm_match else "UNNAMED"
    
    tr_match = re.search(r'translation\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
    tx = float(tr_match.group(1)) if tr_match else 0.0
    ty = float(tr_match.group(2)) if tr_match else 0.0
    tz = float(tr_match.group(3)) if tr_match else 0.0
    
    rot_match = re.search(r'rotation\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
    if rot_match:
        rx, ry, rz, angle = float(rot_match.group(1)), float(rot_match.group(2)), float(rot_match.group(3)), float(rot_match.group(4))
        rot_z = angle if rz > 0 else (-angle if rz < 0 else 0.0)
    else:
        rot_z = 0.0

    if name.startswith("TREE_"):
        trees.append({"name": name, "x": tx, "y": ty})
    elif (name.startswith("ROAD_") or name.startswith("JUNCTION_") or "JUNCTION" in name or "ROUNDABOUT" in name):
        box_m = re.search(r'geometry\s+Box\s*\{\s*size\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
        if box_m:
            sx, sy = float(box_m.group(1)), float(box_m.group(2))
            road_obbs.append({"name": name, "x": tx, "y": ty, "sx": sx, "sy": sy, "rot": rot_z})

def point_to_obb_distance(px, py, cx, cy, sx, sy, rot):
    dx = px - cx
    dy = py - cy
    cos_a = math.cos(-rot)
    sin_a = math.sin(-rot)
    local_x = dx * cos_a - dy * sin_a
    local_y = dx * sin_a + dy * cos_a
    hx = sx / 2.0
    hy = sy / 2.0
    dx_bound = abs(local_x) - hx
    dy_bound = abs(local_y) - hy
    if dx_bound <= 0 and dy_bound <= 0:
        return max(dx_bound, dy_bound)
    out_x = max(0.0, dx_bound)
    out_y = max(0.0, dy_bound)
    return math.hypot(out_x, out_y)

# Test first 10 trees
for t in trees[:10]:
    min_d = 999999
    closest_r = None
    for r in road_obbs:
        d = point_to_obb_distance(t['x'], t['y'], r['x'], r['y'], r['sx'], r['sy'], r['rot'])
        if d < min_d:
            min_d = d
            closest_r = r
    print(f"Tree {t['name']:<16} at ({t['x']:6.1f}, {t['y']:6.1f}) -> closest road {closest_r['name']:<30} dist={min_d:6.2f}m")
