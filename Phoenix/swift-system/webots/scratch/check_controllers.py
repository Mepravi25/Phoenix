import re

wbt_path = r"d:\REC\Phoenix\swift-system\webots\worlds\swift_city.wbt"

with open(wbt_path, "r", encoding="utf-8") as f:
    text = f.read()

controllers = set(re.findall(r'controller\s+"([^"]+)"', text))
print("Controllers referenced in swift_city.wbt:")
for c in controllers:
    print(f" - {c}")

# Also check Robot nodes in swift_city.wbt
robots = re.findall(r'(Robot|Supervisor)\s*\{[^}]*?name\s+"([^"]+)"[^}]*?controller\s+"([^"]+)"', text)
print("\nRobot/Supervisor nodes:")
for r in robots:
    print(f" - Kind: {r[0]}, Name: {r[1]}, Controller: {r[2]}")
