import os
import re

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"
with open(wbt_path, "r", encoding="utf-8") as f:
    content = f.read()

print(f"Loaded {wbt_path}, total length: {len(content)} chars")

# Find all Solid blocks with name TREE_
tree_matches = list(re.finditer(r'Solid\s*\{\s*translation\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)[\s\S]*?name\s+\"(TREE_[^\"]+)\"', content))
print(f"Total TREE matches found: {len(tree_matches)}")

if tree_matches:
    print("Sample tree match 0:", tree_matches[0].groups())
    print("Sample tree match -1:", tree_matches[-1].groups())

# Check for all Solid objects with 'road', 'junction', 'intersection', 'lane', 'street', etc. in name
all_solids = re.findall(r'Solid\s*\{\s*translation\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)[\s\S]*?name\s+\"([^\"]+)\"', content)
print(f"Total Solid matches found: {len(all_solids)}")

road_solids = [s for s in all_solids if 'road' in s[3].lower() or 'junc' in s[3].lower() or 'roundabout' in s[3].lower() or 'street' in s[3].lower() or 'avenue' in s[3].lower()]
print(f"Road/Junction solids found: {len(road_solids)}")

print("\nFirst 20 road/junction solids:")
for r in road_solids[:20]:
    print(f"  Name: {r[3]}, translation: ({r[0]}, {r[1]}, {r[2]})")
