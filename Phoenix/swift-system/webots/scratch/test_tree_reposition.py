import os
import re
import math
from parse_top_vrml import get_top_nodes

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"

with open(wbt_path, "r", encoding="utf-8") as f:
    text = f.read()

nodes = get_top_nodes(text)

# 1. Parse all objects
trees = []
road_obbs = []
road_circles = []
buildings = []
signals = []
vehicles = []
river = None

# Extract signals and sub-solids from entire text as well
# Signals: Solid { ... name "J..._SIGNAL" ... } or Robot { translation ... children [ Solid { translation ... name "..._SIGNAL" } ] }
signal_matches = re.finditer(r'Solid\s*\{\s*translation\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)[\s\S]*?name\s+\"([^\"]*SIGNAL[^\"]*)\"', text)

for m in signal_matches:
    # Check parent robot translation if nested
    # For now, let's find all signal locations in world coordinates
    pass

# Helper to extract world coordinates of signals
def extract_all_signals(text):
    sigs = []
    # Find all Robot controllers for traffic signals
    robot_blocks = re.finditer(r'Robot\s*\{\s*translation\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)[\s\S]*?children\s*\[([\s\S]*?)\]\s*name\s+\"([^\"]+)\"', text)
    for rb in robot_blocks:
        rx, ry = float(rb.group(1)), float(rb.group(2))
        rname = rb.group(5)
        children_str = rb.group(4)
        # Find inner solids
        inner_solids = re.finditer(r'Solid\s*\{\s*translation\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)[\s\S]*?name\s+\"([^\"]+)\"', children_str)
        for isol in inner_solids:
            ix, iy = float(isol.group(1)), float(isol.group(2))
            sname = isol.group(4)
            if "SIGNAL" in sname:
                sigs.append({"name": sname, "x": rx + ix, "y": ry + iy})
    return sigs

signals = extract_all_signals(text)

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

# 2. Geometry functions
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

def point_to_circle_distance(px, py, cx, cy, radius):
    return math.hypot(px - cx, py - cy) - radius

ROAD_CLEARANCE = 2.0      # Safe clearance from road edge (meters)
SIGNAL_CLEARANCE = 2.5    # Safe clearance from signal poles (meters)
VEHICLE_CLEARANCE = 3.0   # Safe clearance from vehicle spawns (meters)
BUILDING_CLEARANCE = 1.0  # Safe clearance from building walls (meters)
RIVER_CLEARANCE = 2.0     # Safe clearance from river bank (meters)
TREE_CLEARANCE = 2.0      # Safe clearance from other trees (meters)

def is_valid_tree_pos(px, py, placed_trees):
    # Check terrain bounds
    if abs(px) > 1380 or abs(py) > 1380:
        return False
        
    # Check road OBBs
    for r in road_obbs:
        if point_to_obb_distance(px, py, r['x'], r['y'], r['sx'], r['sy'], r['rot']) < ROAD_CLEARANCE:
            return False
            
    # Check road Circles (roundabouts)
    for c in road_circles:
        if point_to_circle_distance(px, py, c['x'], c['y'], c['r']) < ROAD_CLEARANCE:
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
            if point_to_obb_distance(px, py, b['x'], b['y'], b['sx'], b['sy'], b['rot']) < BUILDING_CLEARANCE:
                return False
        elif 'r' in b:
            if point_to_circle_distance(px, py, b['x'], b['y'], b['r']) < BUILDING_CLEARANCE:
                return False

    # Check already placed trees
    for pt in placed_trees:
        if math.hypot(px - pt['x'], py - pt['y']) < TREE_CLEARANCE:
            return False

    return True

# Process all trees
unmodified_count = 0
moved_count = 0
removed_count = 0

placed_trees = []
final_tree_updates = [] # (tree_obj, new_x, new_y) or None if removed

for t in trees:
    tx, ty = t['x'], t['y']
    
    # Check if current position is valid
    if is_valid_tree_pos(tx, ty, placed_trees):
        placed_trees.append({'name': t['name'], 'x': tx, 'y': ty})
        final_tree_updates.append((t, tx, ty))
        unmodified_count += 1
    else:
        # Try to move tree to nearby safe location
        moved = False
        # Search in concentric circles around original position
        for r_step in range(3, 30, 2):  # 3m to 29m search radius
            num_angles = 16
            for a_idx in range(num_angles):
                angle = (2 * math.pi / num_angles) * a_idx
                nx = tx + r_step * math.cos(angle)
                ny = ty + r_step * math.sin(angle)
                
                if is_valid_tree_pos(nx, ny, placed_trees):
                    placed_trees.append({'name': t['name'], 'x': nx, 'y': ny})
                    final_tree_updates.append((t, nx, ny))
                    moved_count += 1
                    moved = True
                    break
            if moved:
                break
                
        if not moved:
            final_tree_updates.append((t, None, None))
            removed_count += 1

print("\n--- PROPOSED TREE PLACEMENT RESULTS ---")
print(f"Total original trees: {len(trees)}")
print(f"Unmodified (already safe): {unmodified_count}")
print(f"Moved to nearby grass:     {moved_count}")
print(f"Removed (no safe spot):   {removed_count}")
print(f"Total remaining trees:    {len(placed_trees)}")
