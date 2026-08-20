import re

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"
with open(wbt_path, "r", encoding="utf-8") as f:
    content = f.read()

idx = content.find("FIRE_ENGINE_001")
if idx != -1:
    print(content[idx-100:idx+600])
else:
    print("Not found")
