import math

# Road segment data from generate_urban_world.py
roads = [
    # Corridor 1: East-West Upper Central (Y = 250)
    ("ROAD_EW_WEST_UPPER", -549.5, 250.0, 577.0, 20.0), # X: [-838, -261]
    ("ROAD_J1_J2_MAIN", 0.0, 250.0, 478.0, 20.0),        # X: [-239, 239]
    ("ROAD_EW_EAST_MAIN", 350.0, 250.0, 178.0, 20.0),    # X: [261, 439]
    ("ROAD_EW_EAST_OUTER", 650.0, 250.0, 378.0, 20.0),   # X: [461, 839]

    # Corridor 2: North-South West Central (X = -250)
    ("ROAD_RESEARCH_ACCESS_MAIN", -250.0, 293.0, 20.0, 64.0), # Y: [261, 325]
    ("ROAD_RESEARCH_NORTH_LINK", -250.0, 507.5, 20.0, 325.0), # Y: [345, 670]
    ("ROAD_J1_J4_MAIN", -250.0, 0.0, 20.0, 478.0),          # Y: [-239, 239]
    ("ROAD_J4_SOUTH_CONNECTOR", -293.0, -250.0, 64.0, 20.0), # X: [-325, -261]
    ("ROAD_GOVT_HOSP_WEST_ACCESS", -522.5, -250.0, 355.0, 20.0), # X: [-700, -345]
    ("ROAD_GOVT_HOSP_NS_LINK", -335.0, -349.5, 20.0, 179.0), # Y: [-439, -260]

    # Corridor 3: Commercial East-West Cross (Y = -50)
    ("ROAD_COMMERCIAL_CROSS_WEST", -24.0, -50.0, 432.0, 18.0), # X: [-240, 192]
    ("ROAD_COMMERCIAL_CROSS_EAST", 543.5, -50.0, 591.0, 18.0), # X: [248, 839]

    # Corridor 4: South Highway Main (Y = -450)
    ("ROAD_SOUTH_HIGHWAY_WEST", -599.5, -450.0, 479.0, 22.0), # X: [-839, -360]
    ("ROAD_SOUTH_HIGHWAY_MID", -100.5, -450.0, 479.0, 22.0),  # X: [-340, 139]
    ("ROAD_SOUTH_HIGHWAY_EAST", 500.0, -450.0, 678.0, 22.0),  # X: [161, 839]

    # Corridor 5: Avenue J2 -> J3 -> J5 (X = 250 & X = 150)
    ("ROAD_PARK_MALL_NS_LINK", 250.0, 305.5, 18.0, 89.0),    # Y: [261, 350]
    ("ROAD_PARK_MALL_TOP_LINK", 250.0, 530.0, 18.0, 320.0),  # Y: [370, 690]
    ("ROAD_J2_J3_AVENUE", 250.0, 108.5, 18.0, 261.0),       # Y: [-22, 239]
    ("ROAD_J3_J5_AVENUE", 150.0, -258.5, 18.0, 361.0),       # Y: [-439, -78]

    # Corridor 6: North Highway Main (Y = 850)
    ("ROAD_NORTH_HIGHWAY_WEST", -351.0, 850.0, 678.0, 22.0), # X: [-690, -12]
    ("ROAD_NORTH_HIGHWAY_EAST", 351.0, 850.0, 678.0, 22.0),  # X: [12, 690]

    # Corridor 7: North-South Arterial North (X = 0)
    ("ROAD_NS_ARTERIAL_NORTH_LOWER", 0.0, 360.5, 22.0, 199.0), # Y: [261, 460]
    ("ROAD_NS_ARTERIAL_NORTH_UPPER", 0.0, 659.0, 22.0, 358.0), # Y: [480, 838]
    ("ROAD_NORTH_INNOVATION_ACCESS", 0.0, 906.0, 18.0, 88.0),   # Y: [862, 950]

    # Corridor 8: West Highway Main (X = -850) & EW Main (Y = 0)
    ("ROAD_WEST_HIGHWAY_SOUTH", -850.0, -356.0, 22.0, 688.0),  # Y: [-700, -12]
    ("ROAD_WEST_HIGHWAY_NORTH", -850.0, 356.0, 22.0, 688.0),   # Y: [12, 700]
    ("ROAD_EW_WEST_MAIN", -549.5, 0.0, 577.0, 22.0),          # X: [-838, -261]
    ("ROAD_WEST_COMMUNITY_ACCESS", -906.0, 0.0, 88.0, 18.0), # X: [-950, -862]

    # Corridor 9: East Highway Main (X = 850) & River Bridge Mid (Y = 0)
    ("ROAD_EAST_HIGHWAY_SOUTH", 850.0, -356.0, 22.0, 688.0),  # Y: [-700, -12]
    ("ROAD_EAST_HIGHWAY_NORTH", 850.0, 356.0, 22.0, 688.0),   # Y: [12, 700]
    ("ROAD_RIVER_BRIDGE_MID", 549.5, 0.0, 577.0, 22.0),       # X: [261, 838]
    ("ROAD_EAST_CORPORATE_ACCESS", 906.0, 0.0, 88.0, 18.0),  # X: [862, 950]

    # Corridor 10: South Outer Highway (Y = -850) & NS Arterial South (X = 0)
    ("ROAD_SOUTH_OUTER_HIGHWAY_WEST", -356.0, -850.0, 688.0, 22.0), # X: [-700, -12]
    ("ROAD_SOUTH_OUTER_HIGHWAY_EAST", 356.0, -850.0, 688.0, 22.0),  # X: [12, 700]
    ("ROAD_NS_ARTERIAL_SOUTH", 0.0, -649.5, 22.0, 377.0),           # Y: [-838, -461]
    ("ROAD_SOUTH_STADIUM_ACCESS", 0.0, -906.0, 18.0, 88.0),         # Y: [-950, -862]

    # Corridor 11: Outer District Links & Roundabouts
    ("ROAD_J7_NORTH_LINK", -700.0, 784.5, 20.0, 109.0),    # Y: [730, 839]
    ("ROAD_J7_WEST_LINK", -784.0, 700.0, 108.0, 20.0),     # X: [-838, -730]
    ("ROAD_J9_NORTH_LINK", 700.0, 781.5, 20.0, 115.0),     # Y: [724, 839]
    ("ROAD_J9_EAST_LINK", 775.0, 700.0, 126.0, 20.0),      # X: [712, 838]
    ("ROAD_J12_SOUTH_LINK", -700.0, -775.5, 20.0, 127.0),  # Y: [-839, -712]
    ("ROAD_J12_WEST_LINK", -775.0, -700.0, 126.0, 20.0),   # X: [-838, -712]
    ("ROAD_J14_SOUTH_LINK", 700.0, -784.5, 20.0, 109.0),   # Y: [-839, -730]
    ("ROAD_J14_EAST_LINK", 784.0, -700.0, 108.0, 20.0),    # X: [730, 838]

    # Corridor 12: East District J15 & Hospital Access Links
    ("ROAD_J15_NS_CONNECTOR_NORTH", 450.0, 575.5, 20.0, 229.0), # Y: [461, 690]
    ("ROAD_J15_NS_CONNECTOR_SOUTH", 450.0, 350.0, 20.0, 178.0),   # Y: [261, 439]
    ("ROAD_J15_EW_CONNECTOR_WEST", 350.0, 450.0, 178.0, 20.0),    # X: [261, 439]
    ("ROAD_J15_EW_CONNECTOR_EAST", 649.5, 450.0, 377.0, 20.0),    # X: [461, 838]
    ("ROAD_PRIV_HOSP_WEST_LINK", 217.0, -250.0, 116.0, 20.0),     # X: [159, 275]
    ("ROAD_PRIV_HOSP_EAST_LINK", 567.0, -250.0, 544.0, 20.0),     # X: [295, 839]

    # T-Junction Connector Link Roads
    ("ROAD_SCHOOL_EW_LINK_WEST", -124.5, 470.0, 229.0, 18.0), # X: [-239, -10]
    ("ROAD_SCHOOL_EW_LINK_EAST", 124.5, 470.0, 229.0, 18.0),  # X: [10, 239]
    ("ROAD_PARK_MALL_EW_LINK", 350.0, 360.0, 180.0, 18.0), # Connects Park Mall T-junction (260 to 440)
    ("ROAD_RESEARCH_EW_LINK", -350.0, 335.0, 180.0, 18.0),# Connects Research T-junction (-440 to -260)

    # Perimeter North Ring Corridors at Y=700 (Connecting J7 -> NS Arterial -> J15 Link -> J9)
    ("ROAD_NORTH_RING_MID_WEST", -340.5, 700.0, 659.0, 20.0), # X: [-670, -11]
    ("ROAD_NORTH_RING_MID_EAST", 349.5, 700.0, 677.0, 20.0),  # X: [11, 688]
]

# Let's list all junctions:
junctions = [
    {"id": "INTERSECTION_CONTROLLER_001", "name": "JUNCTION_01", "x": -250.0, "y": 250.0, "type": "4-WAY", "approaches": ["NORTH", "SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_002", "name": "JUNCTION_02", "x": 250.0, "y": 250.0, "type": "4-WAY", "approaches": ["NORTH", "SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_003", "name": "JUNCTION_03", "x": 220.0, "y": -50.0, "type": "ROUNDABOUT", "approaches": []}, # Uncontrolled Roundabout
    {"id": "INTERSECTION_CONTROLLER_004", "name": "JUNCTION_04", "x": -250.0, "y": -250.0, "type": "4-WAY", "approaches": ["NORTH", "SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_005", "name": "JUNCTION_05", "x": 150.0, "y": -450.0, "type": "4-WAY", "approaches": ["NORTH", "SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_006", "name": "JUNCTION_06", "x": -350.0, "y": -450.0, "type": "4-WAY", "approaches": ["NORTH", "SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_007", "name": "JUNCTION_07", "x": -700.0, "y": 700.0, "type": "ROUNDABOUT", "approaches": []}, # Uncontrolled Roundabout
    {"id": "INTERSECTION_CONTROLLER_008", "name": "JUNCTION_08", "x": 0.0, "y": 850.0, "type": "4-WAY", "approaches": ["NORTH", "SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_009", "name": "JUNCTION_09", "x": 700.0, "y": 700.0, "type": "4-WAY", "approaches": ["NORTH", "SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_010", "name": "JUNCTION_10", "x": -850.0, "y": 0.0, "type": "4-WAY", "approaches": ["NORTH", "SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_011", "name": "JUNCTION_11", "x": 850.0, "y": 0.0, "type": "4-WAY", "approaches": ["NORTH", "SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_012", "name": "JUNCTION_12", "x": -700.0, "y": -700.0, "type": "4-WAY", "approaches": ["NORTH", "SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_013", "name": "JUNCTION_13", "x": 0.0, "y": -850.0, "type": "4-WAY", "approaches": ["NORTH", "SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_014", "name": "JUNCTION_14", "x": 700.0, "y": -700.0, "type": "ROUNDABOUT", "approaches": []}, # Uncontrolled Roundabout
    {"id": "INTERSECTION_CONTROLLER_015", "name": "JUNCTION_15", "x": 450.0, "y": 450.0, "type": "4-WAY", "approaches": ["NORTH", "SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_016", "name": "GOVT_HOSP_T_JUNCTION", "x": -335.0, "y": -250.0, "type": "3-WAY_T", "approaches": ["NORTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_017", "name": "PRIV_HOSP_T_JUNCTION", "x": 285.0, "y": -250.0, "type": "3-WAY_T", "approaches": ["NORTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_018", "name": "RESEARCH_T_JUNCTION", "x": -250.0, "y": 335.0, "type": "3-WAY_T", "approaches": ["NORTH", "SOUTH", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_019", "name": "SCHOOL_T_JUNCTION", "x": 0.0, "y": 470.0, "type": "3-WAY_T", "approaches": ["SOUTH", "EAST", "WEST"]},
    {"id": "INTERSECTION_CONTROLLER_020", "name": "PARK_MALL_T_JUNCTION", "x": 250.0, "y": 360.0, "type": "3-WAY_T", "approaches": ["NORTH", "SOUTH", "EAST"]},
]

controlled_intersections = [j for j in junctions if j['type'] != 'ROUNDABOUT']
print(f"Total Road Intersections Detected: {len(junctions)}")
print(f"Controlled Intersections Required: {len(controlled_intersections)}")
print(f"Uncontrolled Roundabouts:          {len(junctions) - len(controlled_intersections)}")

print("\n--- DETAILED CONTROLLED INTERSECTION LIST ---")
for idx, j in enumerate(controlled_intersections, 1):
    num_str = f"{idx:03d}"
    print(f"Intersection {idx:2d}: Controller ID = INTERSECTION_CONTROLLER_{num_str} | Name = {j['name']:22s} @ ({j['x']:6.1f}, {j['y']:6.1f}) | Type = {j['type']:8s} | Approaches = {j['approaches']}")
