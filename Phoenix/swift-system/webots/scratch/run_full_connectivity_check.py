"""
SWIFT SYSTEM - Full World Graph Connectivity Test
Parses swift_city.wbt and computes physical geometric connectivity across all roads and junctions.
Ensures connected components == 1.
"""

import os
import re
import math
from typing import Dict, List, Tuple, Set

def parse_wbt_nodes(wbt_path: str) -> Dict[str, Dict]:
    with open(wbt_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find all Solid blocks with name "JUNCTION_*" or "ROAD_*"
    # Regex pattern to capture name, translation, geometry type and size/radius
    nodes = {}
    
    # Extract Solids
    solid_blocks = re.findall(r'Solid\s*\{[^}]*?name\s*"([^"]+)"[^}]*?\}', content, re.DOTALL)
    
    # We will search each Solid declaration manually in content
    # Find all occurrences of name "..."
    matches = re.finditer(r'Solid\s*\{', content)
    for m in matches:
        start_idx = m.start()
        # Find closing brace balance
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
        if not (name.startswith("JUNCTION_") or name.startswith("ROAD_")):
            continue

        # Get translation
        trans_match = re.search(r'translation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
        if not trans_match:
            continue
        tx, ty, tz = float(trans_match.group(1)), float(trans_match.group(2)), float(trans_match.group(3))

        # Check geometry type
        if "Cylinder" in block:
            rad_match = re.search(r'radius\s+([-\d.]+)', block)
            r = float(rad_match.group(1)) if rad_match else 28.0
            nodes[name] = {
                'type': 'circle',
                'geom': ((tx, ty), r)
            }
        elif "Box" in block:
            size_match = re.search(r'size\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
            if size_match:
                sx, sy = float(size_match.group(1)), float(size_match.group(2))
                minx, maxx = tx - sx/2.0, tx + sx/2.0
                miny, maxy = ty - sy/2.0, ty + sy/2.0
                nodes[name] = {
                    'type': 'box',
                    'geom': (minx, miny, maxx, maxy)
                }

    return nodes

def boxes_overlap(b1, b2, eps=1.0):
    minx1, miny1, maxx1, maxy1 = b1
    minx2, miny2, maxx2, maxy2 = b2
    return not (maxx1 + eps < minx2 or minx1 - eps > maxx2 or maxy1 + eps < miny2 or miny1 - eps > maxy2)

def box_circle_overlap(box, circle_center, radius, eps=1.0):
    minx, miny, maxx, maxy = box
    cx, cy = circle_center
    closest_x = max(minx, min(cx, maxx))
    closest_y = max(miny, min(cy, maxy))
    dx = cx - closest_x
    dy = cy - closest_y
    return (dx*dx + dy*dy) <= (radius + eps) * (radius + eps)

def run_connectivity_test():
    wbt_path = r"d:\REC\Phoenix\swift-system\webots\worlds\swift_city.wbt"
    nodes = parse_wbt_nodes(wbt_path)
    print(f"Parsed {len(nodes)} road/junction nodes from swift_city.wbt.")

    node_keys = list(nodes.keys())
    adj: Dict[str, Set[str]] = {k: set() for k in node_keys}

    for i in range(len(node_keys)):
        k1 = node_keys[i]
        n1 = nodes[k1]
        for j in range(i + 1, len(node_keys)):
            k2 = node_keys[j]
            n2 = nodes[k2]

            overlap = False
            if n1['type'] == 'box' and n2['type'] == 'box':
                overlap = boxes_overlap(n1['geom'], n2['geom'])
            elif n1['type'] == 'circle' and n2['type'] == 'circle':
                c1, r1 = n1['geom']
                c2, r2 = n2['geom']
                dist = math.hypot(c1[0]-c2[0], c1[1]-c2[1])
                overlap = dist <= (r1 + r2 + 1.0)
            elif n1['type'] == 'box' and n2['type'] == 'circle':
                overlap = box_circle_overlap(n1['geom'], n2['geom'][0], n2['geom'][1])
            elif n1['type'] == 'circle' and n2['type'] == 'box':
                overlap = box_circle_overlap(n2['geom'], n1['geom'][0], n1['geom'][1])

            if overlap:
                adj[k1].add(k2)
                adj[k2].add(k1)

    visited: Set[str] = set()
    components: List[List[str]] = []

    for k in node_keys:
        if k not in visited:
            comp = []
            queue = [k]
            visited.add(k)
            while queue:
                curr = queue.pop(0)
                comp.append(curr)
                for nbr in adj[curr]:
                    if nbr not in visited:
                        visited.add(nbr)
                        queue.append(nbr)
            components.append(comp)

    print("\n==================================================")
    print(f"ROAD NETWORK CONNECTIVITY TEST RESULTS")
    print(f"Total Nodes (Roads + Junctions): {len(nodes)}")
    print(f"Total Connected Components:      {len(components)}")
    print("==================================================")

    for idx, comp in enumerate(components, 1):
        print(f"Component {idx}: {len(comp)} nodes -> {comp[:5]}{'...' if len(comp) > 5 else ''}")

    # Check for any zero-degree isolated nodes
    isolated = [k for k, nbrs in adj.items() if len(nbrs) == 0]
    if isolated:
        print(f"\n[FAIL] Found {len(isolated)} completely ISOLATED nodes: {isolated}")
    else:
        print("\n[PASS] No isolated floating nodes!")

    if len(components) == 1:
        print("\n[SUCCESS] ENTIRE ROAD NETWORK IS ONE SINGLE CONNECTED GRAPH! (Connected components = 1)")
        return True
    else:
        print(f"\n[FAIL] ROAD NETWORK IS DISCONNECTED! Connected components = {len(components)}")
        return False

if __name__ == "__main__":
    run_connectivity_test()
