import os
import re
import math

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"

with open(wbt_path, "r", encoding="utf-8") as f:
    text = f.read()

# Helper to get top nodes
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
        m = re.match(r'([A-Za-z0-9_]+)\s*\{', text[i:])
        if not m:
            i += 1
            continue
        node_type = m.group(1)
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
        nodes.append((node_type, start_pos, end_pos, node_str))
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

# Extract signals and sub-solids from entire text
# Signals: Solid { ... name "J..._SIGNAL" ... } or Robot { translation ... children [ Solid { translation ... name "..._SIGNAL" } ] }
robot_blocks = re.finditer(r'Robot\s*\{\s*translation\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)[\s\S]*?children\s*\[([\s\S]*?)\]\s*name\s+\"([^\"]+)\"', text)
for rb in robot_blocks:
    rx, ry = float(rb.group(1)), float(rb.group(2))
    rname = rb.group(5)
    children_str = rb.group(4)
    inner_solids = re.finditer(r'Solid\s*\{\s*translation\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)[\s\S]*?name\s+\"([^\"]+)\"', children_str)
    for isol in inner_solids:
        ix, iy = float(isol.group(1)), float(isol.group(2))
        sname = isol.group(4)
        if "SIGNAL" in sname:
            signals.append({"name": sname, "x": rx + ix, "y": ry + iy})

# Extract top level objects
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
        trees.append({
            "name": name, "x": tx, "y": ty, "z": tz,
            "start": start_pos, "end": end_pos, "str": node_str
        })
        continue

    if node_type == "Robot":
        vehicles.append({"name": name, "x": tx, "y": ty})

    if name == "city_river":
        box_m = re.search(r'geometry\s+Box\s*\{\s*size\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
        if box_m:
            sx, sy = float(box_m.group(1)), float(box_m.group(2))
            river = {"x": tx, "y": ty, "sx": sx, "sy": sy}
        continue

    if (name.startswith("ROAD_") or name.startswith("JUNCTION_") or "JUNCTION" in name or "ROUNDABOUT" in name or name.startswith("SIDEWALK_") or "LANE" in name or "STREET" in name or "AVENUE" in name):
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

# Precompute bounding boxes for road OBBs & buildings for fast spatial filtering
for r in road_obbs:
    # Conservative bounding radius
    r['max_r'] = math.hypot(r['sx'] / 2.0, r['sy'] / 2.0)

for b in buildings:
    if 'sx' in b:
        b['max_r'] = math.hypot(b['sx'] / 2.0, b['sy'] / 2.0)

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

GRID_SIZE = 20.0
tree_grid = {}

def add_tree_to_grid(gx_idx, gy_idx, tx, ty):
    key = (gx_idx, gy_idx)
    if key not in tree_grid:
        tree_grid[key] = []
    tree_grid[key].append((tx, ty))

def is_valid_tree_pos(px, py):
    if abs(px) > 1380 or abs(py) > 1380:
        return False
        
    # Check road OBBs
    for r in road_obbs:
        # Fast bounding circle check
        if math.hypot(px - r['x'], py - r['y']) > r['max_r'] + ROAD_CLEARANCE:
            continue
        if point_to_obb_distance(px, py, r['x'], r['y'], r['sx'], r['sy'], r['rot']) < ROAD_CLEARANCE:
            return False
            
    # Check road Circles (roundabouts)
    for c in road_circles:
        if math.hypot(px - c['x'], py - c['y']) - c['r'] < ROAD_CLEARANCE:
            return False
            
    # Check River
    if river:
        if point_to_obb_distance(px, py, river['x'], river['y'], river['sx'], river['sy'], 0.0) < RIVER_CLEARANCE:
            return False
            
    # Check Signals
    for s in signals:
        if math.hypot(px - s['x'], py - s['y']) < SIGNAL_CLEARANCE:
            return False
            
    # Check Vehicles
    for v in vehicles:
        if math.hypot(px - v['x'], py - v['y']) < VEHICLE_CLEARANCE:
            return False

    # Check Buildings
    for b in buildings:
        if 'sx' in b:
            if math.hypot(px - b['x'], py - b['y']) > b['max_r'] + BUILDING_CLEARANCE:
                continue
            if point_to_obb_distance(px, py, b['x'], b['y'], b['sx'], b['sy'], b['rot']) < BUILDING_CLEARANCE:
                return False
        elif 'r' in b:
            if math.hypot(px - b['x'], py - b['y']) - b['r'] < BUILDING_CLEARANCE:
                return False

    # Fast spatial grid check for existing trees
    g_x = int(px // GRID_SIZE)
    g_y = int(py // GRID_SIZE)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            key = (g_x + dx, g_y + dy)
            if key in tree_grid:
                for tx, ty in tree_grid[key]:
                    if math.hypot(px - tx, py - ty) < TREE_CLEARANCE:
                        return False

    return True

unmodified_count = 0
moved_count = 0
removed_count = 0

tree_results = [] # list of (tree_dict, new_x, new_y) or (tree_dict, None, None)

for idx, t in enumerate(trees):
    tx, ty = t['x'], t['y']
    
    if is_valid_tree_pos(tx, ty):
        g_x = int(tx // GRID_SIZE)
        g_y = int(ty // GRID_SIZE)
        add_tree_to_grid(g_x, g_y, tx, ty)
        tree_results.append((t, tx, ty))
        unmodified_count += 1
    else:
        moved = False
        # Concentric rings search
        for r_m in (2.5, 4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 22.0, 26.0, 30.0):
            num_angles = 16
            for a_i in range(num_angles):
                ang = (2 * math.pi / num_angles) * a_i
                nx = tx + r_m * math.cos(ang)
                ny = ty + r_m * math.sin(ang)
                
                if is_valid_tree_pos(nx, ny):
                    g_x = int(nx // GRID_SIZE)
                    g_y = int(ny // GRID_SIZE)
                    add_tree_to_grid(g_x, g_y, nx, ny)
                    tree_results.append((t, nx, ny))
                    moved_count += 1
                    moved = True
                    break
            if moved:
                break
                
        if not moved:
            tree_results.append((t, None, None))
            removed_count += 1

print("\n--- FAST TREE PLACEMENT RESULTS ---")
print(f"Total original trees: {len(trees)}")
print(f"Unmodified (already safe): {unmodified_count}")
print(f"Moved to nearby grass:     {moved_count}")
print(f"Removed (no safe spot):   {removed_count}")
print(f"Total remaining trees:    {len(trees) - removed_count}")
