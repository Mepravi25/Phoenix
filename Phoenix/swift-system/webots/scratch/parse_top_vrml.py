import os
import re

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"

with open(wbt_path, "r", encoding="utf-8") as f:
    text = f.read()

# Let's parse top-level blocks or Solid blocks in text.
# In VRML, blocks start with TypeName { ... }
# We can match Solid { ... } blocks by keeping track of brace depth.

def parse_blocks(vrml_text):
    blocks = []
    i = 0
    n = len(vrml_text)
    while i < n:
        # find next word followed by {
        m = re.search(r'([A-Za-z0-9_]+)\s*\{', vrml_text[i:])
        if not m:
            break
        start_idx = i + m.start()
        block_type = m.group(1)
        brace_start = i + m.end() - 1
        
        # Balance braces to find matching }
        depth = 0
        j = brace_start
        while j < n:
            if vrml_text[j] == '{':
                depth += 1
            elif vrml_text[j] == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        
        end_idx = j + 1
        block_str = vrml_text[start_idx:end_idx]
        blocks.append((block_type, start_idx, end_idx, block_str))
        i = end_idx
    return blocks

# Let's test top-level blocks parse
top_blocks = []
# Top level VRML objects in swift_city.wbt:
# WorldInfo, Viewpoint, Background, DirectionalLight, Solid, etc.
# Note: Solid children contain nested Solid/Shape/Transform. We only want top-level nodes in WorldInfo context.

def get_top_nodes(text):
    nodes = []
    i = 0
    n = len(text)
    # Skip comments and header lines like #VRML_SIM ...
    while i < n:
        # skip whitespace and comments
        while i < n and (text[i].isspace() or text[i] == '#'):
            if text[i] == '#':
                while i < n and text[i] != '\n':
                    i += 1
            else:
                i += 1
        if i >= n:
            break
        # Match node name
        m = re.match(r'([A-Za-z0-9_]+)\s*\{', text[i:])
        if not m:
            # Maybe some unrecognized text or trailing lines
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
print(f"Total top-level VRML nodes found: {len(nodes)}")

type_counts = {}
for nt, sp, ep, ns in nodes:
    type_counts[nt] = type_counts.get(nt, 0) + 1

print("Top-level node counts by type:")
for k, v in type_counts.items():
    print(f"  {k}: {v}")

# Find names of top-level Solids
solids = [n for n in nodes if n[0] == 'Solid']
print(f"\nTotal top-level Solids: {len(solids)}")

names = []
for _, _, _, ns in solids:
    nm = re.search(r'name\s+\"([^\"]+)\"', ns)
    if nm:
        names.append(nm.group(1))

print(f"Sample names (first 30): {names[:30]}")
print(f"Tree solids count: {sum(1 for nm in names if nm.startswith('TREE_'))}")
