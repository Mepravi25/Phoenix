import os
import re
import math

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"

with open(wbt_path, "r", encoding="utf-8") as f:
    text = f.read()

def get_top_nodes(text):
    nodes = []
    i = 0
    n = len(text)
    while i < n:
        while i < n and (text[i].isspace() or text[i] == '#'):
            if text[i] == '#':
                while i < n and text[i] != '\n':
                    i += 1
            else:
                i += 1
        if i >= n:
            break
        m = re.match(r'(?:DEF\s+([A-Za-z0-9_]+)\s+)?([A-Za-z0-9_]+)\s*\{', text[i:])
        if not m:
            i += 1
            continue
        def_name = m.group(1)
        node_type = m.group(2)
        start_pos = i
        brace_pos = i + m.end() - 1
        depth = 0
        j = brace_pos
        while j < n:
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        end_pos = j + 1
        node_str = text[start_pos:end_pos]
        nodes.append((def_name, node_type, start_pos, end_pos, node_str))
        i = end_pos
    return nodes

nodes = get_top_nodes(text)

trees = []
road_obbs = []
road_circles = []
buildings = []
signals = []
vehicles = []
river = None

# Extract signals
robot_blocks = re.finditer(r'Robot\s*\{\s*translation\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)[\s\S]*?children\s*\[([\s\S]*?)\]\s*name\s+\"([^\"]+)\"', text)
for rb in robot_blocks:
    rx, ry = float(rb.group(1)), float(rb.group(2))
    rname = rb.group(5)
    children_str = rb.group(4)
    inner_solids = re.finditer(r'Solid\s*\{\s*translation\s+([\d\.\-]+)\s+([\d\.\-]+)[\s\S]*?name\s+\"([^\"]*SIGNAL[^\"]*)\"', children_str)
    for isol in inner_solids:
        ix, iy = float(isol.group(1)), float(isol.group(2))
        sname = isol.group(3)
        signals.append({"name": sname, "x": rx + ix, "y": ry + iy})

for def_name, node_type, start_pos, end_pos, node_str in nodes:
    nm_match = re.search(r'name\s+\"([^\"]+)\"', node_str)
    name = def_name or (nm_match.group(1) if nm_match else "UNNAMED")
    
    if name == "ground":
        continue

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
        trees.append({
            "name": name, "x": tx, "y": ty, "z": tz
        })
        continue

    if node_type == "Robot":
        if "SIGNAL" not in name:
            vehicles.append({"name": name, "x": tx, "y": ty})
        continue

    if name == "city_river":
        box_m = re.search(r'geometry\s+Box\s*\{\s*size\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
        if box_m:
            sx, sy = float(box_m.group(1)), float(box_m.group(2))
            river = {"x": tx, "y": ty, "sx": sx, "sy": sy}
        continue

    if name.startswith("LABEL_"):
        continue

    if (name.startswith("ROAD_") or name.startswith("JUNCTION_") or "JUNCTION" in name or "ROUNDABOUT" in name or name.startswith("SIDEWALK_") or "LANE" in name or "STREET" in name or "AVENUE" in name or "STOP_LINE" in name):
        cyl_m = re.search(r'geometry\s+Cylinder\s*\{\s*height\s+([\d\.\-]+)\s+radius\s+([\d\.\-]+)', node_str)
        box_m = re.search(r'geometry\s+Box\s*\{\s*size\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
        
        if cyl_m:
            r = float(cyl_m.group(2))
            road_circles.append({"name": name, "x": tx, "y": ty, "r": r})
        elif box_m:
            sx, sy = float(box_m.group(1)), float(box_m.group(2))
            road_obbs.append({"name": name, "x": tx, "y": ty, "sx": sx, "sy": sy, "rot": rot_z})
        continue

    box_m = re.search(r'geometry\s+Box\s*\{\s*size\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
    cyl_m = re.search(r'geometry\s+Cylinder\s*\{\s*height\s+([\d\.\-]+)\s+radius\s+([\d\.\-]+)', node_str)
    if box_m:
        sx, sy = float(box_m.group(1)), float(box_m.group(2))
        buildings.append({"name": name, "x": tx, "y": ty, "sx": sx, "sy": sy, "rot": rot_z})
    elif cyl_m:
        r = float(cyl_m.group(2))
        buildings.append({"name": name, "x": tx, "y": ty, "r": r})

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

ROAD_CLEARANCE = 2.0      # Safe clearance from road edge (meters)
SIGNAL_CLEARANCE = 2.5    # Safe clearance from signal poles (meters)
VEHICLE_CLEARANCE = 3.0   # Safe clearance from vehicle spawns (meters)
BUILDING_CLEARANCE = 1.0  # Safe clearance from building walls (meters)
RIVER_CLEARANCE = 2.0     # Safe clearance from river bank (meters)
TREE_CLEARANCE = 1.8      # Safe clearance from other trees (meters)

road_violations = 0
intersection_violations = 0
signal_violations = 0
vehicle_violations = 0
building_violations = 0
river_violations = 0
tree_overlaps = 0

for i, t in enumerate(trees):
    tx, ty = t['x'], t['y']
    
    # Check roads & junctions
    for r in road_obbs:
        d = point_to_obb_distance(tx, ty, r['x'], r['y'], r['sx'], r['sy'], r['rot'])
        if d < ROAD_CLEARANCE:
            road_violations += 1
            if "JUNCTION" in r['name']:
                intersection_violations += 1
                
    for c in road_circles:
        d = math.hypot(tx - c['x'], ty - c['y']) - c['r']
        if d < ROAD_CLEARANCE:
            road_violations += 1
            if "JUNCTION" in c['name'] or "ROUNDABOUT" in c['name']:
                intersection_violations += 1

    # Check signals
    for s in signals:
        if math.hypot(tx - s['x'], ty - s['y']) < SIGNAL_CLEARANCE:
            signal_violations += 1

    # Check vehicles
    for v in vehicles:
        if math.hypot(tx - v['x'], ty - v['y']) < VEHICLE_CLEARANCE:
            vehicle_violations += 1

    # Check river
    if river:
        if point_to_obb_distance(tx, ty, river['x'], river['y'], river['sx'], river['sy'], 0.0) < RIVER_CLEARANCE:
            river_violations += 1

    # Check tree overlaps
    for j in range(i + 1, len(trees)):
        t2 = trees[j]
        if math.hypot(tx - t2['x'], ty - t2['y']) < TREE_CLEARANCE:
            tree_overlaps += 1

print("\n================ FINAL VERIFICATION REPORT ================")
print(f"Total remaining trees:           {len(trees)}")
print(f"Trees on road / within {ROAD_CLEARANCE}m:     {road_violations}")
print(f"Trees on intersections:          {intersection_violations}")
print(f"Trees blocking traffic signals:  {signal_violations}")
print(f"Trees blocking vehicles:         {vehicle_violations}")
print(f"Trees in river:                  {river_violations}")
print(f"Trees overlapping each other:    {tree_overlaps}")
print("===========================================================")

if (road_violations == 0 and intersection_violations == 0 and signal_violations == 0 and 
    vehicle_violations == 0 and river_violations == 0 and tree_overlaps == 0):
    print("SUCCESS: ALL VERIFICATION CHECKLIST ITEMS PASSED 100%!")
else:
    print("WARNING: Violations remaining, adjustment required.")
