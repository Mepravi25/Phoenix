import os
import re
import math
from parse_top_vrml import get_top_nodes

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"

with open(wbt_path, "r", encoding="utf-8") as f:
    text = f.read()

nodes = get_top_nodes(text)

trees = []
road_obbs = []
road_circles = []
buildings = []
river = None
signals = []
vehicles = []

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
        # webots rotation is (axis_x, axis_y, axis_z, angle_in_radians)
        # if rz > 0: angle_z = angle, if rz < 0: angle_z = -angle
        rot_z = angle if rz > 0 else (-angle if rz < 0 else 0.0)
    else:
        rot_z = 0.0

    # Trees
    if name.startswith("TREE_"):
        # scale from node_str if any, else scale 1.2
        # Shape { ... geometry Cylinder { height H radius R } }
        cyl_match = re.search(r'geometry\s+Cylinder\s*\{\s*height\s+([\d\.\-]+)\s+radius\s+([\d\.\-]+)', node_str)
        trunk_r = float(cyl_match.group(2)) if cyl_match else 0.42
        
        sph_match = re.search(r'geometry\s+Sphere\s*\{\s*radius\s+([\d\.\-]+)', node_str)
        canopy_r = float(sph_match.group(1)) if sph_match else 3.0
        
        trees.append({
            "name": name, "x": tx, "y": ty, "z": tz,
            "trunk_r": trunk_r, "canopy_r": canopy_r,
            "start": start_pos, "end": end_pos, "str": node_str
        })
        continue

    # Vehicles / Robots
    if node_type == "Robot" or "VEHICLE" in name or "CAR" in name or "BUS" in name or "AMBULANCE" in name or "FIRE" in name or "POLICE" in name:
        vehicles.append({"name": name, "x": tx, "y": ty})
        # Check if vehicle has children roads or is a robot
        
    # River
    if name == "city_river":
        box_m = re.search(r'geometry\s+Box\s*\{\s*size\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
        if box_m:
            sx, sy = float(box_m.group(1)), float(box_m.group(2))
            river = {"x": tx, "y": ty, "sx": sx, "sy": sy}
        continue

    # Roads, Junctions, Roundabouts, Sidewalks
    if (name.startswith("ROAD_") or name.startswith("JUNCTION_") or "JUNCTION" in name or "ROUNDABOUT" in name or name.startswith("SIDEWALK_") or "LANE" in name or "STREET" in name or "AVENUE" in name):
        # Check if cylinder (Roundabout) or Box (Road/Junction)
        cyl_m = re.search(r'geometry\s+Cylinder\s*\{\s*height\s+([\d\.\-]+)\s+radius\s+([\d\.\-]+)', node_str)
        box_m = re.search(r'geometry\s+Box\s*\{\s*size\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
        
        if cyl_m:
            r = float(cyl_m.group(2))
            road_circles.append({"name": name, "x": tx, "y": ty, "r": r})
        elif box_m:
            sx, sy = float(box_m.group(1)), float(box_m.group(2))
            road_obbs.append({"name": name, "x": tx, "y": ty, "sx": sx, "sy": sy, "rot": rot_z})
        continue

    # Signals
    if "SIGNAL" in name:
        signals.append({"name": name, "x": tx, "y": ty})
        continue

    # Buildings / Houses / Towers / Landmarks
    box_m = re.search(r'geometry\s+Box\s*\{\s*size\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
    cyl_m = re.search(r'geometry\s+Cylinder\s*\{\s*height\s+([\d\.\-]+)\s+radius\s+([\d\.\-]+)', node_str)
    if box_m:
        sx, sy = float(box_m.group(1)), float(box_m.group(2))
        buildings.append({"name": name, "x": tx, "y": ty, "sx": sx, "sy": sy, "rot": rot_z})
    elif cyl_m:
        r = float(cyl_m.group(2))
        buildings.append({"name": name, "x": tx, "y": ty, "r": r})

print(f"Parsed summary:")
print(f"  Trees: {len(trees)}")
print(f"  Road OBBs: {len(road_obbs)}")
print(f"  Road Circles: {len(road_circles)}")
print(f"  Signals: {len(signals)}")
print(f"  Vehicles: {len(vehicles)}")
print(f"  Buildings: {len(buildings)}")
print(f"  River: {river}")

# 2D Geometry Helper Functions
def point_to_obb_distance(px, py, cx, cy, sx, sy, rot):
    """
    Returns signed distance from point (px, py) to OBB centered at (cx, cy) with size (sx, sy) rotated by rot.
    Distance <= 0 means point is inside the OBB.
    """
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
        # Inside box: return negative distance to closest edge
        return max(dx_bound, dy_bound)
    
    # Outside box
    out_x = max(0.0, dx_bound)
    out_y = max(0.0, dy_bound)
    return math.hypot(out_x, out_y)

def point_to_circle_distance(px, py, cx, cy, radius):
    d = math.hypot(px - cx, py - cy)
    return d - radius

# Check tree collisions
# Clearance requirement:
# Tree canopy/branches or trunk should have a safety distance from road edges.
# Trunk distance to road edge should be >= trunk_r + margin (e.g., at least 2.5m - 3.5m from road center/edge)
CLEARANCE_MARGIN = 2.0  # safe clearance from road edge in meters

on_road_trees = []
safe_trees = []

for t in trees:
    tx, ty = t['x'], t['y']
    # Check against all road OBBs and Circles
    min_dist = float('inf')
    colliding_road = None
    
    for r in road_obbs:
        d = point_to_obb_distance(tx, ty, r['x'], r['y'], r['sx'], r['sy'], r['rot'])
        if d < min_dist:
            min_dist = d
            colliding_road = r['name']
            
    for c in road_circles:
        d = point_to_circle_distance(tx, ty, c['x'], c['y'], c['r'])
        if d < min_dist:
            min_dist = d
            colliding_road = c['name']

    # Also check river
    if river:
        d_river = point_to_obb_distance(tx, ty, river['x'], river['y'], river['sx'], river['sy'], 0.0)
        if d_river < min_dist:
            min_dist = d_river
            colliding_road = "city_river"

    # If min_dist < CLEARANCE_MARGIN (i.e. tree trunk is within 2.0m of road edge or inside road), tree is violating rules!
    if min_dist < CLEARANCE_MARGIN:
        on_road_trees.append((t, min_dist, colliding_road))
    else:
        safe_trees.append(t)

print(f"\nTree collision check results (CLEARANCE_MARGIN={CLEARANCE_MARGIN}m):")
print(f"  Trees on road or within {CLEARANCE_MARGIN}m of road: {len(on_road_trees)}")
print(f"  Trees strictly safe: {len(safe_trees)}")

print("\nFirst 20 trees violating road clearance:")
for t, d, rname in on_road_trees[:20]:
    print(f"  {t['name']:<20} at ({t['x']:6.1f}, {t['y']:6.1f}) dist_to_road={d:5.2f}m (Road: {rname})")
