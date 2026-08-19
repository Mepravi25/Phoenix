"""
SWIFT SYSTEM - Road Network Graph Connectivity Validator
Verifies that all road segments and junctions form exactly ONE connected component.
Checks physical geometric overlap between road boxes/cylinders and junctions.
"""

import math
from typing import Dict, List, Tuple, Set

def boxes_overlap(b1: Tuple[float, float, float, float], b2: Tuple[float, float, float, float], eps: float = 1.0) -> bool:
    """Returns True if box 1 (minx, miny, maxx, maxy) overlaps or touches box 2 within eps meters."""
    minx1, miny1, maxx1, maxy1 = b1
    minx2, miny2, maxx2, maxy2 = b2
    return not (maxx1 + eps < minx2 or minx1 - eps > maxx2 or maxy1 + eps < miny2 or miny1 - eps > maxy2)

def box_circle_overlap(box: Tuple[float, float, float, float], circle_center: Tuple[float, float], radius: float, eps: float = 1.0) -> bool:
    """Returns True if box overlaps circle of radius r within eps meters."""
    minx, miny, maxx, maxy = box
    cx, cy = circle_center
    closest_x = max(minx, min(cx, maxx))
    closest_y = max(miny, min(cy, maxy))
    dx = cx - closest_x
    dy = cy - closest_y
    return (dx*dx + dy*dy) <= (radius + eps) * (radius + eps)

def check_network_connectivity(nodes: Dict[str, Dict]):
    """
    Given a dict of nodes with geometry ('box' or 'circle'),
    builds an adjacency list based on geometric overlap and runs BFS to count connected components.
    """
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

    # Compute connected components using BFS
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

    return adj, components
