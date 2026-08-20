import re

wbt_path = r"d:\REC\hack\Phoenix\swift-system\webots\worlds\swift_city.wbt"
with open(wbt_path, "r", encoding="utf-8") as f:
    content = f.read()

def_matches = list(re.finditer(r'DEF\s+([A-Za-z0-9_]+)\s+Robot\s*\{', content))
print(f"Total Robot DEF nodes in wbt: {len(def_matches)}")

for m in def_matches:
    def_name = m.group(1)
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
    
    trans = re.search(r'translation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
    rot = re.search(r'rotation\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', block)
    ctrl = re.search(r'controller\s+"([^"]+)"', block)
    supervisor = re.search(r'supervisor\s+([A-Za-z]+)', block)
    
    t_val = trans.groups() if trans else ("?", "?", "?")
    r_val = rot.groups() if rot else ("?", "?", "?", "?")
    c_val = ctrl.group(1) if ctrl else "NONE"
    s_val = supervisor.group(1) if supervisor else "FALSE"
    
    print(f"DEF: {def_name:18s} Trans: ({t_val[0]:>7s}, {t_val[1]:>7s}, {t_val[2]:>5s}) Rot: {r_val[3]:>7s} Ctrl: {c_val:22s} Sup: {s_val}")

