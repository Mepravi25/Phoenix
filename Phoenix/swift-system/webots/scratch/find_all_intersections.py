import re

wbt_path = r"d:\REC\Phoenix\swift-system\webots\worlds\swift_city.wbt"

with open(wbt_path, "r", encoding="utf-8") as f:
    content = f.read()

def get_top_level_blocks(text):
    blocks = []
    i = 0
    n = len(text)
    while i < n:
        # Find start of a block like 'Solid {' or 'Robot {'
        match = re.search(r'(Solid|Robot|Supervisor)\s*\{', text[i:])
        if not match:
            break
        start_idx = i + match.start()
        node_type = match.group(1)
        
        # Balance braces
        brace_count = 0
        end_idx = start_idx
        for j in range(start_idx, n):
            if text[j] == '{':
                brace_count += 1
            elif text[j] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = j + 1
                    break
        
        block_text = text[start_idx:end_idx]
        
        # Extract name
        name_match = re.search(r'name\s*"([^"]+)"', block_text)
        name = name_match.group(1) if name_match else "UNNAMED"
        
        # Extract translation
        trans_match = re.search(r'translation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block_text)
        trans = (float(trans_match.group(1)), float(trans_match.group(2)), float(trans_match.group(3))) if trans_match else (0.0, 0.0, 0.0)
        
        # Extract controller if any
        ctrl_match = re.search(r'controller\s*"([^"]+)"', block_text)
        ctrl = ctrl_match.group(1) if ctrl_match else None
        
        blocks.append({
            'type': node_type,
            'name': name,
            'trans': trans,
            'controller': ctrl,
            'text': block_text
        })
        
        i = end_idx
    return blocks

blocks = get_top_level_blocks(content)
print(f"Total top-level VRML blocks extracted: {len(blocks)}")

junctions = [b for b in blocks if "JUNCTION" in b['name'] or "T_JUNCTION" in b['name']]
print(f"\nJunction Nodes ({len(junctions)}):")
for j in junctions:
    print(f" - {j['name']:25s} @ ({j['trans'][0]:7.1f}, {j['trans'][1]:7.1f}, {j['trans'][2]:4.2f})")

robots = [b for b in blocks if b['type'] in ['Robot', 'Supervisor'] or b['controller'] is not None]
print(f"\nRobot/Controller Nodes ({len(robots)}):")
for r in robots:
    print(f" - Kind: {r['type']:10s} | Name: {r['name']:25s} | Controller: {r['controller']}")

signals = [b for b in blocks if "_SIGNAL" in b['name']]
print(f"\nTraffic Signal Solid Nodes ({len(signals)}):")
for s in signals:
    print(f" - Name: {s['name']:25s} @ ({s['trans'][0]:7.1f}, {s['trans'][1]:7.1f})")

roads = [b for b in blocks if b['name'].startswith("ROAD_")]
print(f"\nRoad Segment Nodes ({len(roads)}):")
for rd in roads:
    print(f" - Name: {rd['name']:30s} @ ({rd['trans'][0]:7.1f}, {rd['trans'][1]:7.1f})")
