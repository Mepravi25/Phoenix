import math

wbt_path = r"d:\REC\Phoenix\swift-system\webots\worlds\swift_city.wbt"

with open(wbt_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

signals = []
for i in range(len(lines)):
    line = lines[i]
    if 'name "' in line and '_SIGNAL"' in line:
        name = line.split('"')[1]
        # scan backwards to find the outer Solid starting line
        # The outer Solid starts before any child Transform
        solid_idx = -1
        for j in range(i, max(-1, i-150), -1):
            if lines[j].strip().startswith('Solid {'):
                solid_idx = j
                break
        
        trans = [0.0, 0.0, 0.0]
        rot = [0.0, 0.0, 1.0, 0.0]
        if solid_idx != -1:
            for j in range(solid_idx, i):
                l = lines[j].strip()
                if l.startswith('translation ') and trans == [0.0, 0.0, 0.0]:
                    parts = l.split()
                    trans = [float(parts[1]), float(parts[2]), float(parts[3])]
                if l.startswith('rotation ') and rot == [0.0, 0.0, 1.0, 0.0]:
                    parts = l.split()
                    rot = [float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])]
        
        signals.append({
            'name': name,
            'line': solid_idx + 1 if solid_idx != -1 else i + 1,
            'trans': trans,
            'rot': rot
        })

print(f"Total signals extracted: {len(signals)}\n")

for s in signals:
    tx, ty, tz = s['trans']
    rx, ry, rz, angle = s['rot']
    eff_angle = angle if rz >= 0 else -angle
    dx = math.sin(eff_angle)
    dy = -math.cos(eff_angle)
    
    facing = ""
    if abs(dy - 1.0) < 0.1: facing = "FACING NORTH (+Y)"
    elif abs(dy - (-1.0)) < 0.1: facing = "FACING SOUTH (-Y)"
    elif abs(dx - 1.0) < 0.1: facing = "FACING EAST (+X)"
    elif abs(dx - (-1.0)) < 0.1: facing = "FACING WEST (-X)"
    else: facing = f"dx={dx:.2f}, dy={dy:.2f}, rot={angle:.4f}"

    print(f"Line {s['line']:5d} | {s['name']:25s} | Pos: ({tx:7.1f}, {ty:7.1f}, {tz:4.2f}) | Rot Z: {angle:6.3f} | {facing}")
