import os
import re

wbt_path = r"d:\REC\Phoenix\swift-system\webots\worlds\swift_city.wbt"

with open(wbt_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

signals = []
current_block = []
in_solid = False

i = 0
while i < len(lines):
    line = lines[i]
    if 'name "' in line and '_SIGNAL"' in line:
        name = line.split('"')[1]
        # Look backwards for translation and rotation
        trans = None
        rot = None
        for j in range(max(0, i-60), i):
            if 'translation ' in lines[j]:
                parts = lines[j].strip().split()
                trans = [float(parts[1]), float(parts[2]), float(parts[3])]
            if 'rotation ' in lines[j]:
                parts = lines[j].strip().split()
                rot = [float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])]
        signals.append((name, trans, rot, i))
    i += 1

print(f"Total signals found: {len(signals)}")
for name, trans, rot, line_no in signals:
    t_str = f"{trans[0]:7.1f}, {trans[1]:7.1f}, {trans[2]:5.2f}" if trans else "None"
    r_str = f"{rot[0]:.1f} {rot[1]:.1f} {rot[2]:.1f} {rot[3]:6.3f}" if rot else "None"
    print(f"Line {line_no:5d} | {name:25s} | Trans: {t_str} | Rot: {r_str}")
