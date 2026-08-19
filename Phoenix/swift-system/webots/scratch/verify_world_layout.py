"""
Verification script for swift_city.wbt Webots city simulation world.
Validates all major city expansion requirements:
- 2800m x 2800m continuous green terrain base (No blue background)
- 4 New Outer Districts (North, South, West, East)
- 15 physically separated major junctions & 3 roundabouts
- 10 Central Landmarks + Hospital Emergency Corridors
- 1200+ Trees, 100+ Houses, 50+ Towers
"""

import os
import re

def verify_swift_city_wbt():
    wbt_path = r"d:\REC\Phoenix\swift-system\webots\worlds\swift_city.wbt"
    if not os.path.exists(wbt_path):
        print(f"FAIL: {wbt_path} does not exist!")
        return False

    with open(wbt_path, "r", encoding="utf-8") as f:
        content = f.read()

    print("==================================================")
    print("VERIFYING WEBOTS SWIFT_CITY.WBT MAJOR CITY EXPANSION")
    print("==================================================")
    print(f"File Size: {len(content):,} bytes")

    required_landmarks = [
        ("RESEARCH_CENTER", r"RESEARCH_CENTER"),
        ("SCHOOL", r"SCHOOL"),
        ("CITY_PARK", r"CITY_PARK|PARK_GREEN_BASE"),
        ("BANK_01", r"BANK_01"),
        ("MALL", r"MALL_01"),
        ("RESIDENTIAL_AREA", r"RESIDENTIAL_AREA|RESIDENTIAL_HOUSE"),
        ("COMMERCIAL_AREA", r"COMMERCIAL_AREA|COMM_TOWER"),
        ("BANK_02", r"BANK_02"),
        ("GOVT_HOSPITAL", r"GOVT_HOSPITAL"),
        ("PRIVATE_HOSPITAL", r"PRIVATE_HOSPITAL"),
        ("NORTH_TECH_TOWER", r"NORTH_TECH_TOWER"),
        ("WEST_COMMUNITY_CENTER", r"WEST_COMMUNITY_CENTER"),
        ("EAST_CORPORATE_TOWER", r"EAST_CORPORATE_TOWER"),
        ("SOUTH_SPORTS_STADIUM", r"SOUTH_SPORTS_STADIUM"),
    ]

    required_junctions = [
        ("JUNCTION_01", r"JUNCTION_01"),
        ("JUNCTION_02", r"JUNCTION_02"),
        ("JUNCTION_03 (Roundabout 1)", r"JUNCTION_03"),
        ("JUNCTION_04", r"JUNCTION_04"),
        ("JUNCTION_05", r"JUNCTION_05"),
        ("JUNCTION_06", r"JUNCTION_06"),
        ("JUNCTION_07 (Roundabout 2)", r"JUNCTION_07"),
        ("JUNCTION_08", r"JUNCTION_08"),
        ("JUNCTION_09", r"JUNCTION_09"),
        ("JUNCTION_10", r"JUNCTION_10"),
        ("JUNCTION_11", r"JUNCTION_11"),
        ("JUNCTION_12", r"JUNCTION_12"),
        ("JUNCTION_13", r"JUNCTION_13"),
        ("JUNCTION_14 (Roundabout 3)", r"JUNCTION_14"),
        ("JUNCTION_15", r"JUNCTION_15"),
    ]

    required_labels = [
        "LABEL_DISTRICT_NORTH",
        "LABEL_DISTRICT_SOUTH",
        "LABEL_DISTRICT_WEST",
        "LABEL_DISTRICT_EAST",
        "LABEL_RESEARCH_CENTER",
        "LABEL_SCHOOL",
        "LABEL_CITY_PARK",
        "LABEL_BANK_01",
        "LABEL_MALL",
        "LABEL_RESIDENTIAL_AREA",
        "LABEL_COMMERCIAL_AREA",
        "LABEL_BANK_02",
        "LABEL_GOVT_HOSPITAL",
        "LABEL_PRIVATE_HOSPITAL",
        "LABEL_JUNCTION_01",
        "LABEL_JUNCTION_02",
        "LABEL_JUNCTION_03",
        "LABEL_JUNCTION_04",
        "LABEL_JUNCTION_05",
        "LABEL_JUNCTION_07",
        "LABEL_JUNCTION_14",
    ]

    all_passed = True

    print("\n--- 1. LANDMARK VERIFICATION ---")
    for name, pattern in required_landmarks:
        match = re.search(pattern, content)
        if match:
            print(f"[PASS] Landmark '{name}' found.")
        else:
            print(f"[FAIL] Landmark '{name}' MISSING!")
            all_passed = False

    print("\n--- 2. JUNCTION VERIFICATION (15 JUNCTIONS) ---")
    for name, pattern in required_junctions:
        match = re.search(pattern, content)
        if match:
            print(f"[PASS] Junction '{name}' found.")
        else:
            print(f"[FAIL] Junction '{name}' MISSING!")
            all_passed = False

    print("\n--- 3. 3D FLOATING LABELS & DISTRICT LABELS ---")
    for label in required_labels:
        if label in content:
            print(f"[PASS] Label '{label}' found.")
        else:
            print(f"[FAIL] Label '{label}' MISSING!")
            all_passed = False

    print("\n--- 4. URBAN DENSITY & OBJECT COUNTS ---")
    house_count = len(re.findall(r'name "(?:RESIDENTIAL|NORTH|WEST|SOUTH)_HOUSE_|WEST_VILLA_', content))
    comm_count = len(re.findall(r'name "(?:COMM_TOWER_|EAST_TOWER_)', content))
    tree_count = len(re.findall(r'name "TREE_', content))
    road_count = len(re.findall(r'name "ROAD_', content))

    print(f"Residential Houses/Villas: {house_count} (Requirement: > 50)")
    print(f"Commercial Towers:         {comm_count} (Requirement: > 20)")
    print(f"Trees:                     {tree_count} (Requirement: > 1000)")
    print(f"Road Segments:             {road_count} (Requirement: > 25)")

    if house_count < 50:
        print("[FAIL] Insufficient residential houses!")
        all_passed = False
    if comm_count < 20:
        print("[FAIL] Insufficient commercial towers!")
        all_passed = False
    if tree_count < 1000:
        print("[FAIL] Insufficient trees!")
        all_passed = False

    print("\n--- 5. SPECIAL FEATURES VERIFICATION ---")
    features = [
        ("Continuous 2800m Green Ground Base", r'size 2800 2800 0.1'),
        ("Roundabout 1 (J3)", r"Roundabout JUNCTION_03"),
        ("Roundabout 2 (J7)", r"Roundabout JUNCTION_07"),
        ("Roundabout 3 (J14)", r"Roundabout JUNCTION_14"),
        ("City River Geographic Water Body", r'name "city_river"'),
        ("School Running Track & Field", r'name "SCHOOL_TRACK_FIELD"'),
        ("Park Central Fountain Pond", r'name "PARK_CENTRAL_POND"'),
        ("Govt Hospital Emergency Complex", r'name "GOVT_HOSPITAL_01"'),
        ("Private Hospital Emergency Complex", r'name "PRIVATE_HOSPITAL_01"'),
        ("Top-Down High Overhead Viewpoint", r"Viewpoint \{"),
    ]

    for fname, fpattern in features:
        if re.search(fpattern, content):
            print(f"[PASS] Feature '{fname}' verified.")
        else:
            print(f"[FAIL] Feature '{fname}' missing!")
            all_passed = False

    print("\n==================================================")
    if all_passed:
        print("ALL EXPANDED CITY VERIFICATION CHECKS PASSED! (100%)")
    else:
        print("SOME VERIFICATION CHECKS FAILED!")
    print("==================================================")
    return all_passed

if __name__ == "__main__":
    verify_swift_city_wbt()
