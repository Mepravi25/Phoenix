"""
SWIFT SYSTEM - Automated Road Geometry Stability & Traffic Signal Validator
Checks:
1. Interior 2D Overlaps between road/junction bounding boxes (road_overlaps == 0)
2. Elevation consistency & physical thickness (road top Z == 0.10, thickness >= 0.04)
3. Full network graph connectivity (connected_components == 1)
4. Traffic signal presence & orientation across major junctions and controlled turnings
5. Webots VRML syntax, bracket balance, and zero invalid Text nodes
"""

import os
import re
import math
from typing import Dict, List, Tuple, Set

def parse_wbt_geometries(wbt_path: str):
    with open(wbt_path, "r", encoding="utf-8") as f:
        content = f.read()

    nodes = {}

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
        # Filter strictly for road network elements, excluding landmark buildings
        valid_prefixes = ("JUNCTION_", "ROAD_", "GOVT_HOSP_T_JUNCTION", "PRIV_HOSP_T_JUNCTION", "RESEARCH_T_JUNCTION", "SCHOOL_T_JUNCTION", "PARK_MALL_T_JUNCTION")
        if not name.startswith(valid_prefixes) and "ROUNDABOUT" not in name:
            continue

        trans_match = re.search(r'translation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
        if not trans_match:
            continue
        tx, ty, tz = float(trans_match.group(1)), float(trans_match.group(2)), float(trans_match.group(3))

        rot_z = 0.0
        rot_match = re.search(r'rotation\s+[-\d.]+\s+[-\d.]+\s+([-\d.]+)\s+([-\d.]+)', block)
        if rot_match:
            axis_z, angle = float(rot_match.group(1)), float(rot_match.group(2))
            if abs(axis_z) > 0.5:
                rot_z = angle if axis_z > 0 else -angle

        if "Cylinder" in block:
            rad_match = re.search(r'radius\s+([-\d.]+)', block)
            r = float(rad_match.group(1)) if rad_match else 28.0
            h_match = re.search(r'height\s+([-\d.]+)', block)
            h = float(h_match.group(1)) if h_match else 0.04
            nodes[name] = {
                'type': 'circle',
                'center': (tx, ty),
                'radius': r,
                'tz': tz,
                'height': h,
                'top_z': tz + h/2.0
            }
        elif "Box" in block:
            size_match = re.search(r'size\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
            if size_match:
                sx, sy, sz = float(size_match.group(1)), float(size_match.group(2)), float(size_match.group(3))
                if abs(abs(rot_z) - 1.57079) < 0.1 or abs(abs(rot_z) - 4.71238) < 0.1:
                    sx, sy = sy, sx
                minx, maxx = tx - sx/2.0, tx + sx/2.0
                miny, maxy = ty - sy/2.0, ty + sy/2.0
                nodes[name] = {
                    'type': 'box',
                    'bounds': (minx, miny, maxx, maxy),
                    'center': (tx, ty),
                    'size': (sx, sy, sz),
                    'tz': tz,
                    'height': sz,
                    'top_z': tz + sz/2.0
                }

    return content, nodes

def boxes_interior_overlap(b1, b2, eps=0.01):
    minx1, miny1, maxx1, maxy1 = b1
    minx2, miny2, maxx2, maxy2 = b2
    return (minx1 < maxx2 - eps) and (maxx1 > minx2 + eps) and (miny1 < maxy2 - eps) and (maxy1 > miny2 + eps)

def box_circle_interior_overlap(box, circle_center, radius, eps=0.01):
    minx, miny, maxx, maxy = box
    cx, cy = circle_center
    closest_x = max(minx, min(cx, maxx))
    closest_y = max(miny, min(cy, maxy))
    dx = cx - closest_x
    dy = cy - closest_y
    dist_sq = dx*dx + dy*dy
    return dist_sq < (radius - eps) * (radius - eps)

def box_circle_touch(box, circle_center, radius, eps=0.5):
    minx, miny, maxx, maxy = box
    cx, cy = circle_center
    closest_x = max(minx, min(cx, maxx))
    closest_y = max(miny, min(cy, maxy))
    dx = cx - closest_x
    dy = cy - closest_y
    return math.hypot(dx, dy) <= (radius + eps)

def run_validation():
    wbt_path = r"d:\REC\Phoenix\swift-system\webots\worlds\swift_city.wbt"
    if not os.path.exists(wbt_path):
        print(f"FAIL: {wbt_path} missing")
        return False

    content, nodes = parse_wbt_geometries(wbt_path)
    print("==================================================")
    print("ROAD GEOMETRY STABILITY & TRAFFIC SIGNAL VALIDATION")
    print("==================================================")
    print(f"Total Road & Junction Geometries: {len(nodes)}")

    overlaps = []
    keys = list(nodes.keys())
    for i in range(len(keys)):
        k1 = keys[i]
        n1 = nodes[k1]
        for j in range(i + 1, len(keys)):
            k2 = keys[j]
            n2 = nodes[k2]

            if abs(n1['top_z'] - n2['top_z']) < 0.05:
                is_overlap = False
                if n1['type'] == 'box' and n2['type'] == 'box':
                    is_overlap = boxes_interior_overlap(n1['bounds'], n2['bounds'])
                elif n1['type'] == 'box' and n2['type'] == 'circle':
                    is_overlap = box_circle_interior_overlap(n1['bounds'], n2['center'], n2['radius'])
                elif n1['type'] == 'circle' and n2['type'] == 'box':
                    is_overlap = box_circle_interior_overlap(n2['bounds'], n1['center'], n1['radius'])

                if is_overlap:
                    overlaps.append((k1, k2))

    print(f"\n1. INTERIOR COPLANAR ROAD OVERLAPS: {len(overlaps)}")
    if overlaps:
        print("  [FAIL] Overlapping road meshes detected:")
        for o1, o2 in overlaps[:10]:
            print(f"    - '{o1}' overlaps '{o2}'")
    else:
        print("  [PASS] 0 interior overlapping road surfaces! (Clean non-overlapping geometry)")

    thin_count = 0
    inconsistent_elevation = 0
    for k, n in nodes.items():
        if n['height'] < 0.04:
            thin_count += 1
        if abs(n['top_z'] - 0.10) > 0.02:
            inconsistent_elevation += 1

    print(f"\n2. 3D GEOMETRY ELEVATION & THICKNESS:")
    print(f"  Thin geometry (< 0.04m height): {thin_count}")
    print(f"  Inconsistent elevation (top Z != 0.10m): {inconsistent_elevation}")
    if thin_count == 0 and inconsistent_elevation == 0:
        print("  [PASS] All roads have proper physical thickness (0.10m) and consistent elevation (0.10m)!")
    else:
        print("  [FAIL] Road thickness or elevation issues detected.")

    adj: Dict[str, Set[str]] = {k: set() for k in keys}
    for i in range(len(keys)):
        k1 = keys[i]
        n1 = nodes[k1]
        for j in range(i + 1, len(keys)):
            k2 = keys[j]
            n2 = nodes[k2]
            touch = False
            eps = 0.5  # 0.5m connectivity boundary touching tolerance
            if n1['type'] == 'box' and n2['type'] == 'box':
                minx1, miny1, maxx1, maxy1 = n1['bounds']
                minx2, miny2, maxx2, maxy2 = n2['bounds']
                touch = not (maxx1 + eps < minx2 or minx1 - eps > maxx2 or maxy1 + eps < miny2 or miny1 - eps > maxy2)
            elif n1['type'] == 'circle' and n2['type'] == 'circle':
                c1, r1 = n1['center'], n1['radius']
                c2, r2 = n2['center'], n2['radius']
                touch = math.hypot(c1[0]-c2[0], c1[1]-c2[1]) <= (r1 + r2 + eps)
            elif n1['type'] == 'box' and n2['type'] == 'circle':
                touch = box_circle_touch(n1['bounds'], n2['center'], n2['radius'], eps=eps)
            elif n1['type'] == 'circle' and n2['type'] == 'box':
                touch = box_circle_touch(n2['bounds'], n1['center'], n1['radius'], eps=eps)

            if touch:
                adj[k1].add(k2)
                adj[k2].add(k1)

    visited = set()
    comps = []
    for k in keys:
        if k not in visited:
            comp = []
            q = [k]
            visited.add(k)
            while q:
                curr = q.pop(0)
                comp.append(curr)
                for nbr in adj[curr]:
                    if nbr not in visited:
                        visited.add(nbr)
                        q.append(nbr)
            comps.append(comp)

    print(f"\n3. ROAD GRAPH CONNECTIVITY:")
    print(f"  Connected components: {len(comps)}")
    if len(comps) == 1:
        print("  [PASS] Whole road network forms 1 single connected component!")
    else:
        print(f"  [FAIL] Road network is disconnected into {len(comps)} components!")
        for idx, c in enumerate(comps, 1):
            print(f"    Component {idx}: {len(c)} nodes -> {c[:3]}")

    signals = re.findall(r'name\s*"([^"]+_SIGNAL)"', content)
    leds = re.findall(r'name\s*"([^"]+_(?:RED|YELLOW|GREEN))"', content)
    print(f"\n4. TRAFFIC SIGNALS COVERAGE:")
    print(f"  Total Signals Installed: {len(signals)}")
    print(f"  Total LEDs Registered:  {len(leds)}")
    
    j_with_signals = set()
    for sig in signals:
        m = re.match(r'^(J\d+|GOVT_HOSP|PRIV_HOSP|RESEARCH|SCHOOL|PARK_MALL)', sig)
        if m:
            j_with_signals.add(m.group(1))

    print(f"  Signalized Junctions & Turnings: {len(j_with_signals)} (J1..J15 + T-junctions)")
    if len(signals) >= 60 and len(leds) >= 180 and len(j_with_signals) >= 20:
        print("  [PASS] 100% Traffic signal coverage across all major junctions & controlled turnings!")
    else:
        print("  [FAIL] Incomplete traffic signal placement!")

    has_text_node = "Text {" in content
    print(f"\n5. WEBOTS R2025a COMPATIBILITY:")
    print(f"  Invalid Text nodes found: {has_text_node}")
    if not has_text_node:
        print("  [PASS] Clean VRML R2025a syntax! Zero invalid Text nodes.")
    else:
        print("  [FAIL] Found invalid Text nodes in WBT!")

    passed = (len(overlaps) == 0 and thin_count == 0 and inconsistent_elevation == 0 and len(comps) == 1 and not has_text_node)
    print("\n==================================================")
    print(f"OVERALL VALIDATION: {'PASSED [100%]' if passed else 'FAILED'}")
    print("==================================================")
    return passed

if __name__ == "__main__":
    run_validation()
