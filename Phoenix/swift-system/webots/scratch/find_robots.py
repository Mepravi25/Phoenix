wbt_path = r"d:\REC\Phoenix\swift-system\webots\worlds\swift_city.wbt"

with open(wbt_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if any(k in line for k in ["Robot", "Supervisor", "controller"]):
        print(f"Line {i+1:5d}: {line.strip()}")
