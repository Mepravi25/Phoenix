import re
import math

wbt_path = r"d:\REC\Phoenix\swift-system\webots\worlds\swift_city.wbt"

with open(wbt_path, "r", encoding="utf-8") as f:
    text = f.read()

# Parse all Solid blocks with name "*_SIGNAL"
pattern = re.compile(
    r'Solid\s*\{[^}]*?translation\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)[^}]*?rotation\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)[^}]*?name\s+"([^"]+_SIGNAL)"',
    re.DOTALL
)

matches = pattern.findall(text)
print(f"Parsed {len(matches)} signals:")
for m in matches:
    tx, ty, tz = float(m[0]), float(m[1]), float(m[2])
    rx, ry, rz, angle = float(m[3]), float(m[4]), float(m[5]), float(m[6])
    name = m[7]
    # Calculate facing vector (in local frame, LEDs face -Y, i.e. (0, -1, 0))
    # Rotated around Z by angle:
    # local -Y (0, -1) rotated by angle around Z (0,0,1):
    # dx = 0*cos - (-1)*sin = sin(angle)
    # dy = 0*sin + (-1)*cos = -cos(angle)
    dx = math.sin(angle)
    dy = -math.cos(angle)
    print(f"{name:25s} | Pos: ({tx:7.1f}, {ty:7.1f}) | Rot Z: {angle:6.3f} rad | Facing Vec: ({dx:5.2f}, {dy:5.2f})")
