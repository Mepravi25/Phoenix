import re
import json

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"
with open(wbt_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find all Robot/Solid/DEF blocks
def_matches = re.finditer(r'DEF\s+([A-Za-z0-9_]+)\s+(Robot|Solid|Car|Vehicle|Motorcycle)\s*\{', content)
print("=== DEF ROBOT / VEHICLE NODES IN WBT ===")
for m in def_matches:
    def_name = m.group(1)
    node_type = m.group(2)
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
    trans_m = re.search(r'translation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
    rot_m = re.search(r'rotation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
    ctrl_m = re.search(r'controller\s+"([^"]+)"', block)
    trans = trans_m.groups() if trans_m else ("?", "?", "?")
    rot = rot_m.groups() if rot_m else ("?", "?", "?", "?")
    ctrl = ctrl_m.group(1) if ctrl_m else "NONE"
    print(f"DEF: {def_name:20s} Type: {node_type:10s} Translation: ({trans[0]}, {trans[1]}, {trans[2]}) Rot: {rot[3]} Ctrl: {ctrl}")
