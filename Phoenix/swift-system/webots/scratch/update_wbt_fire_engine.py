import os

wbt_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "worlds", "swift_city.wbt"))
with open(wbt_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace FIRE_ENGINE_001 header
old_header = "DEF FIRE_ENGINE_001 Solid {\n  translation 150.0 -350.0 0.10\n  rotation 0 0 1 1.5708"
new_header = "DEF FIRE_ENGINE_001 Robot {\n  translation 170.95 -350.60 0.10\n  rotation 0 0 1 -1.7453"

if old_header in content:
    content = content.replace(old_header, new_header)

old_footer = "  name \"FIRE_ENGINE_001\"\n}"
new_footer = "  name \"FIRE_ENGINE_001\"\n  controller \"fire_engine_controller\"\n  supervisor TRUE\n}"

if old_footer in content:
    content = content.replace(old_footer, new_footer)

with open(wbt_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated swift_city.wbt successfully!")
