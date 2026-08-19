import math

# Load roads and junctions defined in generate_urban_world.py
# Let's inspect where road bounding boxes overlap or meet

# List of junction nodes currently defined in generate_urban_world.py:
junction_nodes = [
    # Major 4-way & roundabouts (J1..J15)
    ("JUNCTION_01", -250.0, 250.0, 22.0, 22.0, "4-way"),
    ("JUNCTION_02", 250.0, 250.0, 22.0, 22.0, "4-way"),
    ("JUNCTION_03", 220.0, -50.0, 56.0, 56.0, "Roundabout 1"), # Roundabout: outer_r=28
    ("JUNCTION_04", -250.0, -250.0, 22.0, 22.0, "4-way"),
    ("JUNCTION_05", 150.0, -450.0, 22.0, 22.0, "4-way"),
    ("JUNCTION_06", -350.0, -450.0, 20.0, 20.0, "4-way"),
    ("JUNCTION_07", -700.0, 700.0, 60.0, 60.0, "Roundabout 2"), # Roundabout: outer_r=30
    ("JUNCTION_08", 0.0, 850.0, 24.0, 24.0, "4-way"),
    ("JUNCTION_09", 700.0, 700.0, 24.0, 24.0, "4-way"),
    ("JUNCTION_10", -850.0, 0.0, 24.0, 24.0, "4-way"),
    ("JUNCTION_11", 850.0, 0.0, 24.0, 24.0, "4-way"),
    ("JUNCTION_12", -700.0, -700.0, 24.0, 24.0, "4-way"),
    ("JUNCTION_13", 0.0, -850.0, 24.0, 24.0, "4-way"),
    ("JUNCTION_14", 700.0, -700.0, 60.0, 60.0, "Roundabout 3"), # Roundabout: outer_r=30
    ("JUNCTION_15", 450.0, 450.0, 22.0, 22.0, "4-way"),

    # T-Junctions defined with junction boxes
    ("GOVT_HOSP_T_JUNCTION", -335.0, -250.0, 20.0, 20.0, "T-Junction"),
    ("PRIV_HOSP_T_JUNCTION", 285.0, -250.0, 20.0, 20.0, "T-Junction"),
    ("RESEARCH_T_JUNCTION", -250.0, 335.0, 20.0, 20.0, "T-Junction"),
    ("SCHOOL_T_JUNCTION", 0.0, 470.0, 20.0, 20.0, "T-Junction"),
    ("PARK_MALL_T_JUNCTION", 250.0, 360.0, 20.0, 20.0, "T-Junction"),
]

# Let's also check all road intersections where roads cross each other or meet at T-intersections without explicit junction boxes!
# Let's check all roads from generate_urban_world.py
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

print("Scanning for all intersections where roads meet...")

# Let's find all T-junctions or 4-way intersections where perpendicular roads meet!
# A road meeting another road perpendicularly forms a T-junction or 4-way intersection.
intersections = []

# First, check explicit junction nodes
for j in junction_nodes:
    name, jx, jy, sx, sy, jtype = j
    intersections.append({
        'name': name,
        'x': jx,
        'y': jy,
        'type': jtype,
        'source': 'explicit_node'
    })

# Now check for any implicit intersections where a road T-intersects or crosses another road without an explicit junction box!
# Let's test all pairs of horizontal and vertical roads:
for r1 in roads:
    n1, x1, y1, sx1, sy1 = r1
    is_r1_h = sx1 > sy1
    b1_minx, b1_maxx = x1 - sx1/2.0, x1 + sx1/2.0
    b1_miny, b1_maxy = y1 - sy1/2.0, y1 + sy1/2.0
    
    for r2 in roads:
        n2, x2, y2, sx2, sy2 = r2
        if n1 >= n2: continue
        is_r2_h = sx2 > sy2
        
        # Check if perpendicular
        if is_r1_h != is_r2_h:
            h_road = r1 if is_r1_h else r2
            v_road = r2 if is_r1_h else r1
            
            hx, hy, hsx, hsy = h_road[1], h_road[2], h_road[3], h_road[4]
            vx, vy, vsx, vsy = v_road[1], v_road[2], v_road[3], v_road[4]
            
            h_minx, h_maxx = hx - hsx/2.0, hx + hsx/2.0
            v_miny, v_maxy = vy - vsy/2.0, vy + vsy/2.0
            
            # Intersection point would be at (vx, hy)
            if h_minx - 1.0 <= vx <= h_maxx + 1.0 and v_miny - 1.0 <= hy <= v_maxy + 1.0:
                # Check if this point (vx, hy) is already covered by an explicit junction node!
                covered = False
                for j in intersections:
                    if math.hypot(j['x'] - vx, j['y'] - hy) < 25.0:
                        covered = True
                        break
                if not covered:
                    intersections.append({
                        'name': f"IMPLICIT_INTERSECTION_{len(intersections)+1:02d}",
                        'x': vx,
                        'y': hy,
                        'type': 'T-Junction/Cross',
                        'source': f"{h_road[0]} x {v_road[0]}"
                    })

print(f"\nTotal Controlled Intersections Identified: {len(intersections)}")
for i, j in enumerate(intersections, 1):
    print(f"{i:2d}. {j['name']:28s} @ ({j['x']:7.1f}, {j['y']:7.1f}) | Type: {j['type']:15s} | Source: {j['source']}")
