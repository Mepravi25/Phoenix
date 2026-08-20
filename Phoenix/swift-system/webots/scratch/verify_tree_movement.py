import os
import re
import math
import time

t0 = time.time()
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
        # Support DEF Name TypeName { ... } as well as TypeName { ... }
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
            "name": name, "x": tx, "y": ty, "z": tz,
            "start": start_pos, "end": end_pos, "str": node_str
        })
        continue

    if node_type == "Robot":
        if "SIGNAL" in name or "controller" in node_str.lower() and "junction_signal" in node_str.lower():
            inner_solids = re.finditer(r'Solid\s*\{\s*translation\s+([\d\.\-]+)\s+([\d\.\-]+)[\s\S]*?name\s+\"([^\"]*SIGNAL[^\"]*)\"', node_str)
            for isol in inner_solids:
                ix, iy = float(isol.group(1)), float(isol.group(2))
                sname = isol.group(3)
                signals.append({"name": sname, "x": tx + ix, "y": ty + iy})
        else:
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

print(f"Extracted: {len(trees)} trees, {len(road_obbs)} road OBBs, {len(road_circles)} road circles, {len(signals)} signals, {len(vehicles)} vehicles, {len(buildings)} buildings.")

ROAD_CLEARANCE = 2.0      # Safe clearance from road edge (meters)
SIGNAL_CLEARANCE = 2.5    # Safe clearance from signal poles (meters)
VEHICLE_CLEARANCE = 3.0   # Safe clearance from vehicle spawns (meters)
BUILDING_CLEARANCE = 1.0  # Safe clearance from building walls (meters)
RIVER_CLEARANCE = 2.0     # Safe clearance from river bank (meters)
TREE_CLEARANCE = 1.8      # Safe clearance from other trees (meters)

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

OBS_GRID_SIZE = 50.0
obs_grid = {}

def add_obs_to_grid(item, item_type):
    if item_type == 'road_obb' or item_type == 'building_box':
        max_r = math.hypot(item['sx'] / 2.0, item['sy'] / 2.0)
        item['max_r'] = max_r
        min_x, max_x = item['x'] - max_r - 5.0, item['x'] + max_r + 5.0
        min_y, max_y = item['y'] - max_r - 5.0, item['y'] + max_r + 5.0
    elif item_type == 'road_circle' or item_type == 'building_circle':
        min_x, max_x = item['x'] - item['r'] - 5.0, item['x'] + item['r'] + 5.0
        min_y, max_y = item['y'] - item['r'] - 5.0, item['y'] + item['r'] + 5.0
    else:
        min_x, max_x = item['x'] - 5.0, item['x'] + 5.0
        min_y, max_y = item['y'] - 5.0, item['y'] + 5.0
        
    gx_min, gx_max = int(min_x // OBS_GRID_SIZE), int(max_x // OBS_GRID_SIZE)
    gy_min, gy_max = int(min_y // OBS_GRID_SIZE), int(max_y // OBS_GRID_SIZE)
    
    for gx in range(gx_min, gx_max + 1):
        for gy in range(gy_min, gy_max + 1):
            key = (gx, gy)
            if key not in obs_grid:
                obs_grid[key] = []
            obs_grid[key].append((item, item_type))

for r in road_obbs: add_obs_to_grid(r, 'road_obb')
for c in road_circles: add_obs_to_grid(c, 'road_circle')
for b in buildings:
    if 'sx' in b: add_obs_to_grid(b, 'building_box')
    else: add_obs_to_grid(b, 'building_circle')
for s in signals: add_obs_to_grid(s, 'signal')
for v in vehicles: add_obs_to_grid(v, 'vehicle')

TREE_GRID_SIZE = 10.0
tree_grid = {}

def is_valid_tree_pos(px, py):
    if abs(px) > 1380 or abs(py) > 1380:
        return False
        
    if river:
        if point_to_obb_distance(px, py, river['x'], river['y'], river['sx'], river['sy'], 0.0) < RIVER_CLEARANCE:
            return False

    gx = int(px // OBS_GRID_SIZE)
    gy = int(py // OBS_GRID_SIZE)
    key = (gx, gy)
    if key in obs_grid:
        for item, itype in obs_grid[key]:
            if itype == 'road_obb':
                if point_to_obb_distance(px, py, item['x'], item['y'], item['sx'], item['sy'], item['rot']) < ROAD_CLEARANCE:
                    return False
            elif itype == 'road_circle':
                if math.hypot(px - item['x'], py - item['y']) - item['r'] < ROAD_CLEARANCE:
                    return False
            elif itype == 'building_box':
                if point_to_obb_distance(px, py, item['x'], item['y'], item['sx'], item['sy'], item['rot']) < BUILDING_CLEARANCE:
                    return False
            elif itype == 'building_circle':
                if math.hypot(px - item['x'], py - item['y']) - item['r'] < BUILDING_CLEARANCE:
                    return False
            elif itype == 'signal':
                if math.hypot(px - item['x'], py - item['y']) < SIGNAL_CLEARANCE:
                    return False
            elif itype == 'vehicle':
                if math.hypot(px - item['x'], py - item['y']) < VEHICLE_CLEARANCE:
                    return False

    tgx = int(px // TREE_GRID_SIZE)
    tgy = int(py // TREE_GRID_SIZE)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            tkey = (tgx + dx, tgy + dy)
            if tkey in tree_grid:
                for tx, ty in tree_grid[tkey]:
                    if math.hypot(px - tx, py - ty) < TREE_CLEARANCE:
                        return False

    return True

def add_tree_to_grid(tx, ty):
    tgx = int(tx // TREE_GRID_SIZE)
    tgy = int(ty // TREE_GRID_SIZE)
    tkey = (tgx, tgy)
    if tkey not in tree_grid:
        tree_grid[tkey] = []
    tree_grid[tkey].append((tx, ty))

unmodified_count = 0
moved_count = 0
removed_count = 0

tree_results = [] # list of (tree_dict, new_x, new_y) or (tree_dict, None, None)

for t in trees:
    tx, ty = t['x'], t['y']
    
    if is_valid_tree_pos(tx, ty):
        add_tree_to_grid(tx, ty)
        tree_results.append((t, tx, ty))
        unmodified_count += 1
    else:
        moved = False
        for r_m in (2.5, 4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 22.0, 26.0, 30.0):
            num_angles = 16
            for a_i in range(num_angles):
                ang = (2 * math.pi / num_angles) * a_i
                nx = tx + r_m * math.cos(ang)
                ny = ty + r_m * math.sin(ang)
                
                if is_valid_tree_pos(nx, ny):
                    add_tree_to_grid(nx, ny)
                    tree_results.append((t, nx, ny))
                    moved_count += 1
                    moved = True
                    break
            if moved:
                break
                
        if not moved:
            tree_results.append((t, None, None))
            removed_count += 1

t1 = time.time()
print(f"\n--- VERIFIED TREE PLACEMENT RESULTS (Time: {t1 - t0:.2f}s) ---")
print(f"Total original trees: {len(trees)}")
print(f"Unmodified (already safe): {unmodified_count}")
print(f"Moved to nearby grass:     {moved_count}")
print(f"Removed (no safe spot):   {removed_count}")
print(f"Total remaining trees:    {len(trees) - removed_count}")
