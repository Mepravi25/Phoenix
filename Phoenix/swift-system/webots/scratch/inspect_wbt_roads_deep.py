import re
import os

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"
with open(wbt_path, "r", encoding="utf-8") as f:
    text = f.read()

print(f"Total size of swift_city.wbt: {len(text):,} bytes")

# Find all named objects
name_matches = list(re.finditer(r'name\s*"([^"]+)"', text))
print(f"Total 'name' fields found: {len(name_matches)}")

categories = {}
for m in name_matches:
    name = m.group(1)
    start_pos = max(0, m.start() - 400)
    end_pos = min(len(text), m.end() + 400)
    snippet = text[start_pos:end_pos]
    
    trans = re.search(r'translation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', snippet)
    rot = re.search(r'rotation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', snippet)
    size = re.search(r'size\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', snippet)
    
    t_val = [float(x) for x in trans.groups()] if trans else None
    r_val = [float(x) for x in rot.groups()] if rot else None
    s_val = [float(x) for x in size.groups()] if size else None
    
    prefix = name.split("_")[0] if "_" in name else name
    if prefix not in categories:
        categories[prefix] = []
    categories[prefix].append((name, t_val, s_val, r_val))

print("\n=== CATEGORY BREAKDOWN ===")
for cat, items in categories.items():
    print(f"Category '{cat}': {len(items)} items")

print("\n=== ROAD / JUNCTION / GROUND / TERRAIN OBJECTS ===")
for cat, items in categories.items():
    if any(k in cat.upper() for k in ["ROAD", "JUNC", "GROUND", "TERRAIN", "BASE", "ASPHALT", "STREET", "LANE", "NODE", "SIGNAL", "TRAFFIC"]):
        print(f"\n--- Category: {cat} ({len(items)} items) ---")
        for name, t, s, r in items:
            t_str = f"({t[0]:7.1f}, {t[1]:7.1f}, {t[2]:5.2f})" if t else "(None)"
            s_str = f"({s[0]:7.1f}, {s[1]:7.1f}, {s[2]:5.2f})" if s else "(None)"
            print(f"  {name:35s} Trans: {t_str} Size: {s_str} Rot: {r}")

print("\n=== ALL OBJECTS THAT HAVE 'ROAD' OR 'JUNCTION' IN NAME ===")
for m in name_matches:
    name = m.group(1)
    if "ROAD" in name.upper() or "JUNCTION" in name.upper() or "STREET" in name.upper() or "ASPHALT" in name.upper():
        start_pos = max(0, m.start() - 400)
        end_pos = min(len(text), m.end() + 400)
        snippet = text[start_pos:end_pos]
        trans = re.search(r'translation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', snippet)
        size = re.search(r'size\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', snippet)
        rot = re.search(r'rotation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', snippet)
        t_val = [float(x) for x in trans.groups()] if trans else None
        s_val = [float(x) for x in size.groups()] if size else None
        r_val = [float(x) for x in rot.groups()] if rot else None
        print(f"Name: {name:35s} Trans: {t_val} Size: {s_val} Rot: {r_val}")
