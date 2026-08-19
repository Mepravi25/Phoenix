"""
VRML / WBT file parser and validator for Webots.
Checks bracket balance, named nodes, and required Module 1 elements.
"""
import sys

def verify_wbt(filepath):
    print(f"Verifying {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    brace_stack = []
    bracket_stack = []
    line_num = 0
    named_nodes = set()

    for line in lines:
        line_num += 1
        stripped = line.strip()
        if stripped.startswith("name "):
            parts = stripped.split('"')
            if len(parts) >= 2:
                named_nodes.add(parts[1])

        for char in line:
            if char == '{':
                brace_stack.append(line_num)
            elif char == '}':
                if not brace_stack:
                    print(f"Error: Unmatched closing brace '}}' at line {line_num}")
                    return False
                brace_stack.pop()
            elif char == '[':
                bracket_stack.append(line_num)
            elif char == ']':
                if not bracket_stack:
                    print(f"Error: Unmatched closing bracket ']' at line {line_num}")
                    return False
                bracket_stack.pop()

    if brace_stack:
        print(f"Error: Unclosed braces '{{' opened at lines: {brace_stack[:10]}")
        return False
    if bracket_stack:
        print(f"Error: Unclosed brackets '[' opened at lines: {bracket_stack[:10]}")
        return False

    print("[OK] VRML Syntax & Brackets balanced successfully!")
    print(f"Total lines: {line_num}")
    print(f"Found {len(named_nodes)} named nodes.")

    required_nodes = [
        "JUNCTION_01", "JUNCTION_02", "JUNCTION_03", "JUNCTION_04", "JUNCTION_05", "JUNCTION_06",
        "JUNCTION_07", "JUNCTION_08", "JUNCTION_09", "JUNCTION_10", "JUNCTION_11", "JUNCTION_12",
        "JUNCTION_13", "JUNCTION_14", "JUNCTION_15",
        "GOVT_HOSPITAL_01", "PRIVATE_HOSPITAL_01", "SCHOOL_01", "MALL_01", "RESEARCH_CENTER_01",
        "BANK_01", "BANK_02", "EMERGENCY_SOURCE_01", "PARK_GREEN_BASE", "COMMERCIAL_TOWER_01",
        "RESIDENTIAL_BLOCK_01", "CIVIC_BUILDING_01",
        "J1_NORTH_SIGNAL", "J2_WEST_SIGNAL", "J3_NORTH_SIGNAL", "J4_NORTH_SIGNAL", "J5_NORTH_SIGNAL", "J6_NORTH_SIGNAL",
        "LABEL_GOVT_HOSPITAL", "LABEL_PRIVATE_HOSPITAL", "LABEL_SCHOOL", "LABEL_MALL", "LABEL_RESEARCH_CENTER",
        "LABEL_BANK_01", "LABEL_BANK_02", "LABEL_RESIDENTIAL_AREA", "LABEL_COMMERCIAL_AREA", "LABEL_CIVIC_AREA",
        "LABEL_CITY_PARK", "LABEL_EMERGENCY_SOURCE",
        "LABEL_DISTRICT_NORTH", "LABEL_DISTRICT_SOUTH", "LABEL_DISTRICT_WEST", "LABEL_DISTRICT_EAST",
        "LABEL_JUNCTION_01", "LABEL_JUNCTION_02", "LABEL_JUNCTION_03", "LABEL_JUNCTION_04", "LABEL_JUNCTION_05",
        "LABEL_JUNCTION_07", "LABEL_JUNCTION_14"
    ]

    missing = [req for req in required_nodes if req not in named_nodes]
    if missing:
        print(f"[FAIL] Missing required named nodes: {missing}")
        return False

    print("[OK] All required named nodes are present!")
    return True

if __name__ == "__main__":
    wbt_path = r"d:\REC\Phoenix\swift-system\webots\worlds\swift_city.wbt"
    if not verify_wbt(wbt_path):
        sys.exit(1)
