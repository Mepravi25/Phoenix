import re

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"
with open(wbt_path, "r", encoding="utf-8") as f:
    content = f.read()

tree_count = len(re.findall(r'name\s+\"TREE_', content))
print(f"Tree count in swift_city.wbt: {tree_count}")
assert tree_count > 1000, "Insufficient trees!"
print("Layout requirement (> 1000 trees) satisfied!")
