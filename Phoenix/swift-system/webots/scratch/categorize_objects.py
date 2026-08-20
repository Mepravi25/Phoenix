import os
import re
from parse_top_vrml import get_top_nodes

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"

with open(wbt_path, "r", encoding="utf-8") as f:
    text = f.read()

nodes = get_top_nodes(text)

non_tree_solids = []
trees = []
robots = []

for node_type, start_pos, end_pos, node_str in nodes:
    nm_match = re.search(r'name\s+\"([^\"]+)\"', node_str)
    name = nm_match.group(1) if nm_match else "UNNAMED"
    
    # Extract translation
    tr_match = re.search(r'translation\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
    if tr_match:
        tx, ty, tz = float(tr_match.group(1)), float(tr_match.group(2)), float(tr_match.group(3))
    else:
        tx, ty, tz = 0.0, 0.0, 0.0
        
    # Extract rotation if any
    rot_match = re.search(r'rotation\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
    if rot_match:
        rx, ry, rz, angle = float(rot_match.group(1)), float(rot_match.group(2)), float(rot_match.group(3)), float(rot_match.group(4))
    else:
        rx, ry, rz, angle = 0.0, 0.0, 1.0, 0.0

    # Extract geometry info (Box size, Cylinder radius/height, Tube, etc.)
    box_match = re.search(r'geometry\s+Box\s*\{\s*size\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)', node_str)
    cyl_match = re.search(r'geometry\s+Cylinder\s*\{\s*height\s+([\d\.\-]+)\s+radius\s+([\d\.\-]+)', node_str)
    
    geom = None
    if box_match:
        geom = ("Box", float(box_match.group(1)), float(box_match.group(2)), float(box_match.group(3)))
    elif cyl_match:
        geom = ("Cylinder", float(cyl_match.group(1)), float(cyl_match.group(2)))

    obj = {
        "type": node_type,
        "name": name,
        "x": tx, "y": ty, "z": tz,
        "rot": (rx, ry, rz, angle),
        "geom": geom,
        "str": node_str
    }
    
    if name.startswith("TREE_"):
        trees.append(obj)
    elif node_type == "Robot":
        robots.append(obj)
    else:
        non_tree_solids.append(obj)

print(f"Trees count: {len(trees)}")
print(f"Robots count: {len(robots)}")
print(f"Non-tree solids count: {len(non_tree_solids)}")

print("\nNon-tree solids list:")
for s in non_tree_solids:
    print(f"Name: {s['name']:<30} Type: {s['type']} Pos: ({s['x']:7.1f}, {s['y']:7.1f}) Geom: {s['geom']}")
