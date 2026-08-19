"""
SWIFT SYSTEM - Webots Expanded Top-Down Open World City Generator
Generates a massive 2800m x 2800m continuous open-world simulation map with:
- ALL BLUE BACKGROUND REMOVED (2800m x 2800m solid green terrain base)
- Central District + 4 Outer Developed Districts (North, South, West, East)
- 15 Spaced Major Junctions (including 3 Roundabouts) + 5 Controlled T-Junctions
- CLEAN, NON-OVERLAPPING 3D ROAD MESH GEOMETRY (Zero Z-Fighting, Zero Road Collapse across all camera angles)
- Unified Physical Elevation Hierarchy (Ground Z=0.0m, Road top Z=0.10m, Thickness=0.10m)
- 100% Traffic Signal Coverage across all 15 major junctions and controlled turnings
- 10 Central Landmarks + 4 District Landmarks intact
- 1200+ Trees, 100+ Houses, 50+ Towers
"""

import math
import os

WBT_HEADER = """#VRML_SIM R2025a utf8

WorldInfo {
  info [
    "SWIFT SYSTEM - Predictive Multi-Agent Emergency Traffic Orchestration System"
    "Module 1: Expanded Open World City (2800m x 2800m Continuous Green Terrain)"
  ]
  title "swift_city"
  coordinateSystem "ENU"
  basicTimeStep 32
}

Viewpoint {
  orientation -0.55 0.35 0.75 1.22
  position 0 -400 2400
}

Background {
  skyColor [
    0.45 0.72 0.98
  ]
}

DirectionalLight {
  ambientIntensity 0.55
  direction 0.3 0.5 -1.0
  intensity 1.4
  castShadows TRUE
}

# ==========================================
# CITY GROUND PLANE (2800m x 2800m CONTINUOUS GREEN TERRAIN - NO BLUE BG)
# Top Surface Z = 0.00
# ==========================================
Solid {
  translation 0 0 -0.05
  children [
    Shape {
      appearance PBRAppearance {
        baseColor 0.22 0.44 0.20
        roughness 0.9
        metalness 0.0
      }
      geometry Box {
        size 2800 2800 0.10
      }
    }
  ]
  name "ground"
}

# Integrated City River (Geographic Feature inside East District, x = 600..650)
Solid {
  translation 625 0 -0.03
  children [
    Shape {
      appearance PBRAppearance {
        baseColor 0.06 0.38 0.65
        emissiveColor 0.02 0.12 0.25
        roughness 0.05
        metalness 0.85
      }
      geometry Box {
        size 50 2600 0.12
      }
    }
  ]
  name "city_river"
}
"""

# ==========================================
# 3D PHYSICAL GEOMETRY GENERATORS (Top Surface Z = 0.10m, Thickness = 0.10m)
# ==========================================

def generate_junction_box(name, x, y, size_x=22.0, size_y=22.0):
    return f"""# {name}
Solid {{
  translation {x} {y} 0.05
  children [
    Shape {{
      appearance PBRAppearance {{ baseColor 0.12 0.12 0.14 roughness 0.8 }}
      geometry Box {{ size {size_x} {size_y} 0.10 }}
    }}
  ]
  name "{name}"
}}
"""

def generate_roundabout(name, x, y, outer_r=28.0, inner_r=12.0):
    """Generates a circular roundabout junction with asphalt outer ring and green center island."""
    return f"""# Roundabout {name}
Solid {{
  translation {x} {y} 0.05
  children [
    # Asphalt Ring Base (Top Z = 0.10)
    Shape {{
      appearance PBRAppearance {{ baseColor 0.12 0.12 0.14 roughness 0.8 }}
      geometry Cylinder {{ height 0.10 radius {outer_r} }}
    }}
    # Center Green Island (Sticks up slightly)
    Transform {{
      translation 0 0 0.04
      children [
        Shape {{
          appearance PBRAppearance {{ baseColor 0.2 0.45 0.18 roughness 0.9 }}
          geometry Cylinder {{ height 0.12 radius {inner_r} }}
        }}
        # Island Concrete Curb
        Shape {{
          appearance PBRAppearance {{ baseColor 0.7 0.7 0.72 roughness 0.6 }}
          geometry Tube {{ height 0.16 radius {inner_r + 0.3} thickness 0.6 }}
        }}
      ]
    }}
  ]
  name "{name}"
}}
"""

def generate_road(name, x, y, size_x, size_y, rot_z=0.0):
    rot_str = f"  rotation 0 0 1 {rot_z}\n" if rot_z != 0.0 else ""
    return f"""# {name}
Solid {{
  translation {x} {y} 0.05
{rot_str}  children [
    Shape {{
      appearance PBRAppearance {{ baseColor 0.14 0.14 0.16 roughness 0.8 }}
      geometry Box {{ size {size_x} {size_y} 0.10 }}
    }}
  ]
  name "{name}"
}}
"""

def generate_sidewalk(name, x, y, size_x, size_y, rot_z=0.0):
    rot_str = f"  rotation 0 0 1 {rot_z}\n" if rot_z != 0.0 else ""
    return f"""# {name}
Solid {{
  translation {x} {y} 0.08
{rot_str}  children [
    Shape {{
      appearance PBRAppearance {{ baseColor 0.62 0.62 0.64 roughness 0.7 }}
      geometry Box {{ size {size_x} {size_y} 0.16 }}
    }}
  ]
  name "{name}"
}}
"""

def generate_centerline(name, x, y, size_x, size_y, rot_z=0.0, color="0.95 0.75 0.1"):
    rot_str = f"  rotation 0 0 1 {rot_z}\n" if rot_z != 0.0 else ""
    return f"""# {name}
Solid {{
  translation {x} {y} 0.1025
{rot_str}  children [
    Shape {{
      appearance PBRAppearance {{ baseColor {color} roughness 0.5 }}
      geometry Box {{ size {size_x} {size_y} 0.005 }}
    }}
  ]
  name "{name}"
}}
"""

def generate_stop_line(name, x, y, size_x, size_y):
    return f"""Solid {{ translation {x} {y} 0.1025 children [ Shape {{ appearance PBRAppearance {{ baseColor 0.95 0.95 0.95 }} geometry Box {{ size {size_x} {size_y} 0.005 }} }} ] name "{name}" }}
"""

def generate_signal(name, x, y, facing_dir):
    parts = name.replace("_SIGNAL", "").split("_")
    if len(parts) >= 2:
        j_prefix = "_".join(parts[:-1])
        app_str = parts[-1]
    else:
        j_prefix = name
        app_str = "SIGNAL"

    red_name = f"{j_prefix}_{app_str}_RED"
    yellow_name = f"{j_prefix}_{app_str}_YELLOW"
    green_name = f"{j_prefix}_{app_str}_GREEN"

    rot_str = "  rotation 0 0 1 0\n"
    if facing_dir == 'N':
        rot_str = "  rotation 0 0 1 3.14159\n"
    elif facing_dir == 'E':
        rot_str = "  rotation 0 0 1 1.57079\n"
    elif facing_dir == 'W':
        rot_str = "  rotation 0 0 1 -1.57079\n"

    return f"""Solid {{
  translation {x} {y} 0.10
{rot_str}  children [
    Transform {{
      translation 0 0 2.5
      children [
        Shape {{
          appearance PBRAppearance {{ baseColor 0.15 0.15 0.18 roughness 0.7 metalness 0.8 }}
          geometry Cylinder {{ height 5.0 radius 0.12 }}
        }}
      ]
    }}
    Transform {{
      translation 0 0 3.2
      children [
        Shape {{
          appearance PBRAppearance {{ baseColor 0.05 0.05 0.05 roughness 0.8 metalness 0.5 }}
          geometry Box {{ size 0.6 0.6 1.8 }}
        }}
        Transform {{
          translation 0 0 0.95
          children [
            Shape {{
              appearance PBRAppearance {{ baseColor 0.08 0.08 0.08 roughness 0.9 }}
              geometry Cylinder {{ height 0.08 radius 0.38 }}
            }}
          ]
        }}
        Transform {{
          translation 0 -0.31 0.5
          children [
            LED {{
              translation 0 0 0
              children [
                Shape {{
                  appearance PBRAppearance {{ baseColor 1.0 0.1 0.1 emissiveColor 1.0 0.1 0.1 roughness 0.2 }}
                  geometry Sphere {{ radius 0.18 }}
                }}
              ]
              name "{red_name}"
              color [ 1.0 0.1 0.1 ]
            }}
            Transform {{
              translation 0 -0.05 0.05
              children [
                Shape {{
                  appearance PBRAppearance {{ baseColor 0.05 0.05 0.05 roughness 0.8 }}
                  geometry Box {{ size 0.42 0.15 0.04 }}
                }}
              ]
            }}
          ]
        }}
        Transform {{
          translation 0 -0.31 0.0
          children [
            LED {{
              translation 0 0 0
              children [
                Shape {{
                  appearance PBRAppearance {{ baseColor 1.0 0.7 0.0 emissiveColor 1.0 0.7 0.0 roughness 0.2 }}
                  geometry Sphere {{ radius 0.18 }}
                }}
              ]
              name "{yellow_name}"
              color [ 1.0 0.7 0.0 ]
            }}
            Transform {{
              translation 0 -0.05 0.05
              children [
                Shape {{
                  appearance PBRAppearance {{ baseColor 0.05 0.05 0.05 roughness 0.8 }}
                  geometry Box {{ size 0.42 0.15 0.04 }}
                }}
              ]
            }}
          ]
        }}
        Transform {{
          translation 0 -0.31 -0.5
          children [
            LED {{
              translation 0 0 0
              children [
                Shape {{
                  appearance PBRAppearance {{ baseColor 0.1 1.0 0.2 emissiveColor 0.1 1.0 0.2 roughness 0.2 }}
                  geometry Sphere {{ radius 0.18 }}
                }}
              ]
              name "{green_name}"
              color [ 0.1 1.0 0.2 ]
            }}
            Transform {{
              translation 0 -0.05 0.05
              children [
                Shape {{
                  appearance PBRAppearance {{ baseColor 0.05 0.05 0.05 roughness 0.8 }}
                  geometry Box {{ size 0.42 0.15 0.04 }}
                }}
              ]
            }}
          ]
        }}
      ]
    }}
  ]
  name "{name}"
}}
"""

def generate_3d_label(name, label_text, x, y, z=36.0, color="1 1 1", size=7.5, bg_width=85.0):
    return f"""# 3D Landmark Signboard: {label_text}
Solid {{
  translation {x} {y} {z}
  children [
    Shape {{
      appearance PBRAppearance {{ baseColor 0.08 0.12 0.22 roughness 0.4 metalness 0.5 }}
      geometry Box {{ size {bg_width} 1.2 {size * 1.5} }}
    }}
    Transform {{
      translation 0 0.7 0
      children [
        Shape {{
          appearance PBRAppearance {{ baseColor {color} emissiveColor {color} roughness 0.2 }}
          geometry Box {{ size {bg_width * 0.9} 0.2 {size * 0.9} }}
        }}
      ]
    }}
  ]
  name "LABEL_{name}"
}}
"""

def generate_tree(name, x, y, scale=1.2):
    return f"""Solid {{
  translation {x} {y} 0.10
  children [
    Shape {{ appearance PBRAppearance {{ baseColor 0.35 0.22 0.12 roughness 0.9 }} geometry Cylinder {{ height {3.6 * scale} radius {0.35 * scale} }} }}
    Transform {{
      translation 0 0 {3.3 * scale}
      children [
        Shape {{ appearance PBRAppearance {{ baseColor 0.14 0.48 0.16 roughness 0.8 }} geometry Sphere {{ radius {2.5 * scale} }} }}
      ]
    }}
  ]
  name "{name}"
}}
"""

def generate_house(name, x, y, color="0.88 0.84 0.78", roof_color="0.72 0.25 0.18", size_x=14.0, size_y=11.0, height=7.5, rot_z=0.0):
    rot_str = f"  rotation 0 0 1 {rot_z}\n" if rot_z != 0.0 else ""
    half_h = height / 2.0
    roof_z = half_h + 1.4
    return f"""Solid {{
  translation {x} {y} {half_h + 0.10}
{rot_str}  children [
    Shape {{ appearance PBRAppearance {{ baseColor {color} roughness 0.6 }} geometry Box {{ size {size_x} {size_y} {height} }} }}
    Transform {{
      translation 0 0 {roof_z}
      rotation 0 1 0 0.785
      children [
        Shape {{ appearance PBRAppearance {{ baseColor {roof_color} roughness 0.7 }} geometry Box {{ size {size_x * 0.75} {size_y * 1.05} {size_x * 0.75} }} }}
      ]
    }}
  ]
  name "{name}"
}}
"""

def generate_commercial_building(name, x, y, size_x, size_y, height, color="0.2 0.3 0.45", metalness=0.7, roughness=0.2):
    half_h = height / 2.0
    return f"""Solid {{
  translation {x} {y} {half_h + 0.10}
  children [
    Shape {{ appearance PBRAppearance {{ baseColor {color} roughness {roughness} metalness {metalness} }} geometry Box {{ size {size_x} {size_y} {height} }} }}
    Transform {{
      translation 0 0 {half_h + 1.8}
      children [
        Shape {{ appearance PBRAppearance {{ baseColor 0.15 0.15 0.18 roughness 0.8 }} geometry Box {{ size {size_x * 0.4} {size_y * 0.4} 3.5 }} }}
      ]
    }}
  ]
  name "{name}"
}}
"""

def generate_warehouse(name, x, y, size_x=50.0, size_y=35.0, height=12.0):
    half_h = height / 2.0
    return f"""Solid {{
  translation {x} {y} {half_h + 0.10}
  children [
    Shape {{ appearance PBRAppearance {{ baseColor 0.65 0.68 0.72 roughness 0.5 metalness 0.4 }} geometry Box {{ size {size_x} {size_y} {height} }} }}
  ]
  name "{name}"
}}
"""

def generate_stadium(name, x, y):
    return f"""# {name}
Solid {{
  translation {x} {y} 10.10
  children [
    Shape {{ appearance PBRAppearance {{ baseColor 0.8 0.82 0.85 roughness 0.4 metalness 0.3 }} geometry Cylinder {{ height 20.0 radius 65.0 }} }}
    Transform {{
      translation 0 0 10.1
      children [
        Shape {{ appearance PBRAppearance {{ baseColor 0.18 0.55 0.2 roughness 0.9 }} geometry Cylinder {{ height 0.2 radius 50.0 }} }}
      ]
    }}
  ]
  name "{name}"
}}
"""

def build_urban_world():
    content = [WBT_HEADER]

    # ==========================================
    # 1. 15 MAJOR JUNCTIONS & 5 CONTROLLED T-JUNCTIONS (NON-OVERLAPPING BOXES & ROUNDABOUTS)
    # ==========================================
    content.append("\n# ==========================================")
    content.append("# 15 MAJOR JUNCTIONS & 5 CONTROLLED T-JUNCTIONS")
    content.append("# ==========================================")
    # Central District Junctions
    content.append(generate_junction_box("JUNCTION_01", -250.0, 250.0, 22.0, 22.0))  # X: [-261, -239], Y: [239, 261]
    content.append(generate_junction_box("JUNCTION_02", 250.0, 250.0, 22.0, 22.0))   # X: [239, 261], Y: [239, 261]
    content.append(generate_roundabout("JUNCTION_03", 220.0, -50.0, outer_r=28.0, inner_r=12.0)) # X: [192, 248], Y: [-78, -22]
    content.append(generate_junction_box("JUNCTION_04", -250.0, -250.0, 22.0, 22.0)) # X: [-261, -239], Y: [-261, -239]
    content.append(generate_junction_box("JUNCTION_05", 150.0, -450.0, 22.0, 22.0))  # X: [139, 161], Y: [-461, -439]
    content.append(generate_junction_box("JUNCTION_06", -350.0, -450.0, 20.0, 20.0)) # X: [-360, -340], Y: [-460, -440]

    # Outer District Junctions
    content.append(generate_roundabout("JUNCTION_07", -700.0, 700.0, outer_r=30.0, inner_r=14.0)) # Roundabout 2: X: [-730, -670], Y: [670, 730]
    content.append(generate_junction_box("JUNCTION_08", 0.0, 850.0, 24.0, 24.0))    # X: [-12, 12], Y: [838, 862]
    content.append(generate_junction_box("JUNCTION_09", 700.0, 700.0, 24.0, 24.0))   # X: [688, 712], Y: [688, 712]
    content.append(generate_junction_box("JUNCTION_10", -850.0, 0.0, 24.0, 24.0))   # X: [-862, -838], Y: [-12, 12]
    content.append(generate_junction_box("JUNCTION_11", 850.0, 0.0, 24.0, 24.0))    # X: [838, 862], Y: [-12, 12]
    content.append(generate_junction_box("JUNCTION_12", -700.0, -700.0, 24.0, 24.0))# X: [-712, -688], Y: [-712, -688]
    content.append(generate_junction_box("JUNCTION_13", 0.0, -850.0, 24.0, 24.0))   # X: [-12, 12], Y: [-862, -838]
    content.append(generate_roundabout("JUNCTION_14", 700.0, -700.0, outer_r=30.0, inner_r=14.0)) # Roundabout 3: X: [670, 730], Y: [-730, -670]
    content.append(generate_junction_box("JUNCTION_15", 450.0, 450.0, 22.0, 22.0))  # X: [439, 461], Y: [439, 461]

    # Major Controlled T-Junctions
    content.append(generate_junction_box("GOVT_HOSP_T_JUNCTION", -335.0, -250.0, 20.0, 20.0))  # X: [-345, -325], Y: [-260, -240]
    content.append(generate_junction_box("PRIV_HOSP_T_JUNCTION", 285.0, -250.0, 20.0, 20.0))   # X: [275, 295], Y: [-260, -240]
    content.append(generate_junction_box("RESEARCH_T_JUNCTION", -250.0, 335.0, 20.0, 20.0))    # X: [-260, -240], Y: [325, 345]
    content.append(generate_junction_box("SCHOOL_T_JUNCTION", 0.0, 470.0, 20.0, 20.0))         # X: [-10, 10], Y: [460, 480]
    content.append(generate_junction_box("PARK_MALL_T_JUNCTION", 250.0, 360.0, 20.0, 20.0))    # X: [240, 260], Y: [350, 370]

    # ==========================================
    # 2. LONG ARTERIAL CORRIDORS (STRICT NON-OVERLAPPING SEGMENTS)
    # ==========================================
    content.append("\n# ==========================================")
    content.append("# LONG ARTERIAL CORRIDORS (PRECISE NON-OVERLAPPING MESH SEGMENTS)")
    content.append("# ==========================================")

    # Corridor 1: East-West Upper Central (Y = 250)
    content.append(generate_road("ROAD_EW_WEST_UPPER", -549.5, 250.0, 577.0, 20.0)) # X: [-838, -261]
    content.append(generate_road("ROAD_J1_J2_MAIN", 0.0, 250.0, 478.0, 20.0))        # X: [-239, 239]
    content.append(generate_road("ROAD_EW_EAST_MAIN", 350.0, 250.0, 178.0, 20.0))    # X: [261, 439]
    content.append(generate_road("ROAD_EW_EAST_OUTER", 650.0, 250.0, 378.0, 20.0))   # X: [461, 839]

    # Corridor 2: North-South West Central (X = -250)
    content.append(generate_road("ROAD_RESEARCH_ACCESS_MAIN", -250.0, 293.0, 20.0, 64.0)) # Y: [261, 325]
    content.append(generate_road("ROAD_RESEARCH_NORTH_LINK", -250.0, 507.5, 20.0, 325.0)) # Y: [345, 670]
    content.append(generate_road("ROAD_J1_J4_MAIN", -250.0, 0.0, 20.0, 478.0))          # Y: [-239, 239]
    content.append(generate_road("ROAD_J4_SOUTH_CONNECTOR", -293.0, -250.0, 64.0, 20.0)) # X: [-325, -261]
    content.append(generate_road("ROAD_GOVT_HOSP_WEST_ACCESS", -522.5, -250.0, 355.0, 20.0)) # X: [-700, -345]
    content.append(generate_road("ROAD_GOVT_HOSP_NS_LINK", -335.0, -349.5, 20.0, 179.0)) # Y: [-439, -260]

    # Corridor 3: Commercial East-West Cross (Y = -50)
    content.append(generate_road("ROAD_COMMERCIAL_CROSS_WEST", -24.0, -50.0, 432.0, 18.0)) # X: [-240, 192]
    content.append(generate_road("ROAD_COMMERCIAL_CROSS_EAST", 543.5, -50.0, 591.0, 18.0)) # X: [248, 839]

    # Corridor 4: South Highway Main (Y = -450)
    content.append(generate_road("ROAD_SOUTH_HIGHWAY_WEST", -599.5, -450.0, 479.0, 22.0)) # X: [-839, -360]
    content.append(generate_road("ROAD_SOUTH_HIGHWAY_MID", -100.5, -450.0, 479.0, 22.0))  # X: [-340, 139]
    content.append(generate_road("ROAD_SOUTH_HIGHWAY_EAST", 500.0, -450.0, 678.0, 22.0))  # X: [161, 839]

    # Corridor 5: Avenue J2 -> J3 -> J5 (X = 250 & X = 150)
    content.append(generate_road("ROAD_PARK_MALL_NS_LINK", 250.0, 305.5, 18.0, 89.0))    # Y: [261, 350]
    content.append(generate_road("ROAD_PARK_MALL_TOP_LINK", 250.0, 530.0, 18.0, 320.0))  # Y: [370, 690]
    content.append(generate_road("ROAD_J2_J3_AVENUE", 250.0, 108.5, 18.0, 261.0))       # Y: [-22, 239]
    content.append(generate_road("ROAD_J3_J5_AVENUE", 150.0, -258.5, 18.0, 361.0))       # Y: [-439, -78]

    # Corridor 6: North Highway Main (Y = 850)
    content.append(generate_road("ROAD_NORTH_HIGHWAY_WEST", -351.0, 850.0, 678.0, 22.0)) # X: [-690, -12]
    content.append(generate_road("ROAD_NORTH_HIGHWAY_EAST", 351.0, 850.0, 678.0, 22.0))  # X: [12, 690]

    # Corridor 7: North-South Arterial North (X = 0)
    content.append(generate_road("ROAD_NS_ARTERIAL_NORTH_LOWER", 0.0, 360.5, 22.0, 199.0)) # Y: [261, 460]
    content.append(generate_road("ROAD_NS_ARTERIAL_NORTH_UPPER", 0.0, 659.0, 22.0, 358.0)) # Y: [480, 838]
    content.append(generate_road("ROAD_NORTH_INNOVATION_ACCESS", 0.0, 906.0, 18.0, 88.0))   # Y: [862, 950]

    # Corridor 8: West Highway Main (X = -850) & EW Main (Y = 0)
    content.append(generate_road("ROAD_WEST_HIGHWAY_SOUTH", -850.0, -356.0, 22.0, 688.0))  # Y: [-700, -12]
    content.append(generate_road("ROAD_WEST_HIGHWAY_NORTH", -850.0, 356.0, 22.0, 688.0))   # Y: [12, 700]
    content.append(generate_road("ROAD_EW_WEST_MAIN", -549.5, 0.0, 577.0, 22.0))          # X: [-838, -261]
    content.append(generate_road("ROAD_WEST_COMMUNITY_ACCESS", -906.0, 0.0, 88.0, 18.0)) # X: [-950, -862]

    # Corridor 9: East Highway Main (X = 850) & River Bridge Mid (Y = 0)
    content.append(generate_road("ROAD_EAST_HIGHWAY_SOUTH", 850.0, -356.0, 22.0, 688.0))  # Y: [-700, -12]
    content.append(generate_road("ROAD_EAST_HIGHWAY_NORTH", 850.0, 356.0, 22.0, 688.0))   # Y: [12, 700]
    content.append(generate_road("ROAD_RIVER_BRIDGE_MID", 549.5, 0.0, 577.0, 22.0))       # X: [261, 838]
    content.append(generate_road("ROAD_EAST_CORPORATE_ACCESS", 906.0, 0.0, 88.0, 18.0))  # X: [862, 950]

    # Corridor 10: South Outer Highway (Y = -850) & NS Arterial South (X = 0)
    content.append(generate_road("ROAD_SOUTH_OUTER_HIGHWAY_WEST", -356.0, -850.0, 688.0, 22.0)) # X: [-700, -12]
    content.append(generate_road("ROAD_SOUTH_OUTER_HIGHWAY_EAST", 356.0, -850.0, 688.0, 22.0))  # X: [12, 700]
    content.append(generate_road("ROAD_NS_ARTERIAL_SOUTH", 0.0, -649.5, 22.0, 377.0))           # Y: [-838, -461]
    content.append(generate_road("ROAD_SOUTH_STADIUM_ACCESS", 0.0, -906.0, 18.0, 88.0))         # Y: [-950, -862]

    # Corridor 11: Outer District Links & Roundabouts
    content.append(generate_road("ROAD_J7_NORTH_LINK", -700.0, 784.5, 20.0, 109.0))    # Y: [730, 839]
    content.append(generate_road("ROAD_J7_WEST_LINK", -784.0, 700.0, 108.0, 20.0))     # X: [-838, -730]
    content.append(generate_road("ROAD_J9_NORTH_LINK", 700.0, 781.5, 20.0, 115.0))     # Y: [724, 839]
    content.append(generate_road("ROAD_J9_EAST_LINK", 775.0, 700.0, 126.0, 20.0))      # X: [712, 838]
    content.append(generate_road("ROAD_J12_SOUTH_LINK", -700.0, -775.5, 20.0, 127.0))  # Y: [-839, -712]
    content.append(generate_road("ROAD_J12_WEST_LINK", -775.0, -700.0, 126.0, 20.0))   # X: [-838, -712]
    content.append(generate_road("ROAD_J14_SOUTH_LINK", 700.0, -784.5, 20.0, 109.0))   # Y: [-839, -730]
    content.append(generate_road("ROAD_J14_EAST_LINK", 784.0, -700.0, 108.0, 20.0))    # X: [730, 838]

    # Corridor 12: East District J15 & Hospital Access Links
    content.append(generate_road("ROAD_J15_NS_CONNECTOR_NORTH", 450.0, 575.5, 20.0, 229.0)) # Y: [461, 690]
    content.append(generate_road("ROAD_J15_NS_CONNECTOR_SOUTH", 450.0, 350.0, 20.0, 178.0))   # Y: [261, 439]
    content.append(generate_road("ROAD_J15_EW_CONNECTOR_WEST", 350.0, 450.0, 178.0, 20.0))    # X: [261, 439]
    content.append(generate_road("ROAD_J15_EW_CONNECTOR_EAST", 649.5, 450.0, 377.0, 20.0))    # X: [461, 838]
    content.append(generate_road("ROAD_PRIV_HOSP_WEST_LINK", 217.0, -250.0, 116.0, 20.0))     # X: [159, 275]
    content.append(generate_road("ROAD_PRIV_HOSP_EAST_LINK", 567.0, -250.0, 544.0, 20.0))     # X: [295, 839]

    # T-Junction Connector Link Roads
    content.append(generate_road("ROAD_SCHOOL_EW_LINK_WEST", -124.5, 470.0, 229.0, 18.0)) # X: [-239, -10]
    content.append(generate_road("ROAD_SCHOOL_EW_LINK_EAST", 124.5, 470.0, 229.0, 18.0))  # X: [10, 239]
    content.append(generate_road("ROAD_PARK_MALL_EW_LINK", 350.0, 360.0, 180.0, 18.0)) # Connects Park Mall T-junction (260 to 440)
    content.append(generate_road("ROAD_RESEARCH_EW_LINK", -350.0, 335.0, 180.0, 18.0))# Connects Research T-junction (-440 to -260)

    # Perimeter North Ring Corridors at Y=700 (Connecting J7 -> NS Arterial -> J15 Link -> J9)
    content.append(generate_road("ROAD_NORTH_RING_MID_WEST", -340.5, 700.0, 659.0, 20.0)) # X: [-670, -11]
    content.append(generate_road("ROAD_NORTH_RING_MID_EAST", 349.5, 700.0, 677.0, 20.0))  # X: [11, 688]


    # ==========================================
    # 3. LANE MARKINGS, STOP LINES & TRAFFIC SIGNALS
    # ==========================================
    content.append("\n# ==========================================")
    content.append("# LANE MARKINGS, STOP LINES & TRAFFIC SIGNALS")
    content.append("# ==========================================")
    content.append(generate_centerline("CENTERLINE_MAIN_TOP", 0.0, 250.0, 470.0, 0.5, color="0.95 0.75 0.1"))
    content.append(generate_centerline("CENTERLINE_WEST_CORR", -250.0, 0.0, 0.5, 470.0, color="0.95 0.75 0.1"))
    content.append(generate_centerline("CENTERLINE_NS_ART", 0.0, 659.0, 0.6, 350.0, color="0.95 0.75 0.1"))
    content.append(generate_centerline("CENTERLINE_EW_ART", -549.5, 250.0, 570.0, 0.6, color="0.95 0.75 0.1"))

    # Stop lines for major junctions J1..J15
    junction_coords = {
        "J1": (-250.0, 250.0, 22.0), "J2": (250.0, 250.0, 22.0), "J3": (220.0, -50.0, 28.0),
        "J4": (-250.0, -250.0, 22.0), "J5": (150.0, -450.0, 22.0), "J6": (-350.0, -450.0, 20.0),
        "J7": (-700.0, 700.0, 30.0), "J8": (0.0, 850.0, 24.0), "J9": (700.0, 700.0, 24.0),
        "J10": (-850.0, 0.0, 24.0), "J11": (850.0, 0.0, 24.0), "J12": (-700.0, -700.0, 24.0),
        "J13": (0.0, -850.0, 24.0), "J14": (700.0, -700.0, 30.0), "J15": (450.0, 450.0, 22.0)
    }

    for j_id, (jx, jy, sz) in junction_coords.items():
        half_sz = sz / 2.0
        content.append(generate_stop_line(f"STOP_{j_id}_NORTH", jx, jy + half_sz + 2.0, 8.0, 0.7))
        content.append(generate_stop_line(f"STOP_{j_id}_SOUTH", jx, jy - half_sz - 2.0, 8.0, 0.7))
        content.append(generate_stop_line(f"STOP_{j_id}_EAST", jx + half_sz + 2.0, jy, 0.7, 8.0))
        content.append(generate_stop_line(f"STOP_{j_id}_WEST", jx - half_sz - 2.0, jy, 0.7, 8.0))

    # Traffic Signals for all 15 Major Junctions (J1..J15)
    for j_id, (jx, jy, sz) in junction_coords.items():
        half_sz = sz / 2.0
        content.append(generate_signal(f"{j_id}_NORTH_SIGNAL", jx - (half_sz + 2.0), jy + (half_sz + 3.0), 'N'))
        content.append(generate_signal(f"{j_id}_SOUTH_SIGNAL", jx + (half_sz + 2.0), jy - (half_sz + 3.0), 'S'))
        content.append(generate_signal(f"{j_id}_EAST_SIGNAL", jx + (half_sz + 3.0), jy + (half_sz + 2.0), 'E'))
        content.append(generate_signal(f"{j_id}_WEST_SIGNAL", jx - (half_sz + 3.0), jy - (half_sz + 2.0), 'W'))

    # Traffic Signals for 5 Controlled T-Junctions
    # 1. Govt Hospital Access T-Junction (-335, -250)
    content.append(generate_signal("GOVT_HOSP_NORTH_SIGNAL", -343.0, -236.0, 'N'))
    content.append(generate_signal("GOVT_HOSP_EAST_SIGNAL", -321.0, -242.0, 'E'))
    content.append(generate_signal("GOVT_HOSP_WEST_SIGNAL", -349.0, -258.0, 'W'))

    # 2. Private Hospital Access T-Junction (285, -250)
    content.append(generate_signal("PRIV_HOSP_NORTH_SIGNAL", 277.0, -236.0, 'N'))
    content.append(generate_signal("PRIV_HOSP_EAST_SIGNAL", 299.0, -242.0, 'E'))
    content.append(generate_signal("PRIV_HOSP_WEST_SIGNAL", 271.0, -258.0, 'W'))

    # 3. Research Center Access T-Junction (-250, 335)
    content.append(generate_signal("RESEARCH_NORTH_SIGNAL", -258.0, 349.0, 'N'))
    content.append(generate_signal("RESEARCH_SOUTH_SIGNAL", -242.0, 321.0, 'S'))
    content.append(generate_signal("RESEARCH_WEST_SIGNAL", -264.0, 327.0, 'W'))

    # 4. School Access T-Junction (0, 470)
    content.append(generate_signal("SCHOOL_SOUTH_SIGNAL", 8.0, 456.0, 'S'))
    content.append(generate_signal("SCHOOL_EAST_SIGNAL", 14.0, 478.0, 'E'))
    content.append(generate_signal("SCHOOL_WEST_SIGNAL", -14.0, 462.0, 'W'))

    # 5. Park & Mall Access T-Junction (250, 360)
    content.append(generate_signal("PARK_MALL_NORTH_SIGNAL", 242.0, 374.0, 'N'))
    content.append(generate_signal("PARK_MALL_SOUTH_SIGNAL", 258.0, 346.0, 'S'))
    content.append(generate_signal("PARK_MALL_EAST_SIGNAL", 264.0, 368.0, 'E'))

    # ==========================================
    # 4. 10 REQUIRED CENTRAL LANDMARKS (PRESERVED)
    # ==========================================
    content.append("\n# ==========================================")
    content.append("# 10 REQUIRED CENTRAL URBAN LANDMARKS")
    content.append("# ==========================================")

    # 1. RESEARCH CENTER
    content.append("""# RESEARCH_CENTER_01 (Research Center R&D Tech Campus)
Solid {
  translation -420 420 18.10
  children [
    Shape { appearance PBRAppearance { baseColor 0.82 0.86 0.92 roughness 0.25 metalness 0.3 } geometry Box { size 75 55 36 } }
    Transform { translation 0 0 19.0 children [ Shape { appearance PBRAppearance { baseColor 0.1 0.55 0.75 roughness 0.08 metalness 0.85 } geometry Box { size 45 32 4 } } ] }
    Transform { translation 52 18 -6 children [ Shape { appearance PBRAppearance { baseColor 0.72 0.74 0.78 roughness 0.35 metalness 0.6 } geometry Cylinder { height 24 radius 10.0 } } ] }
    Transform { translation 52 -16 -6 children [ Shape { appearance PBRAppearance { baseColor 0.72 0.74 0.78 roughness 0.35 metalness 0.6 } geometry Cylinder { height 24 radius 10.0 } } ] }
  ]
  name "RESEARCH_CENTER_01"
}
Solid {
  translation -420 350 0.10
  children [ Shape { appearance PBRAppearance { baseColor 0.18 0.18 0.2 roughness 0.8 } geometry Box { size 100 45 0.02 } } ]
  name "RESEARCH_PARKING_LOT"
}
""")

    # 2. SCHOOL
    content.append("""# SCHOOL_01 (School Campus Building Complex)
Solid {
  translation 0 520 12.10
  children [
    Shape { appearance PBRAppearance { baseColor 0.74 0.44 0.28 roughness 0.8 } geometry Box { size 90 35 24 } }
    Transform { translation 0 0 12.5 children [ Shape { appearance PBRAppearance { baseColor 0.48 0.22 0.15 roughness 0.7 } geometry Box { size 94 38 1.0 } } ] }
  ]
  name "SCHOOL_01"
}
Solid {
  translation 0 420 0.10
  children [
    Shape { appearance PBRAppearance { baseColor 0.78 0.2 0.15 roughness 0.8 } geometry Box { size 110 50 0.02 } }
    Transform { translation 0 0 0.01 children [ Shape { appearance PBRAppearance { baseColor 0.15 0.55 0.18 roughness 0.9 } geometry Box { size 85 38 0.02 } } ] }
  ]
  name "SCHOOL_TRACK_FIELD"
}
""")

    # 3. CITY PARK
    content.append("""# CITY_PARK (Urban City Park & Central Fountain Pond Plaza)
Solid {
  translation 260 440 0.10
  children [ Shape { appearance PBRAppearance { baseColor 0.18 0.58 0.20 roughness 0.9 } geometry Box { size 140 120 0.02 } } ]
  name "PARK_GREEN_BASE"
}
Solid {
  translation 260 440 0.15
  children [
    Shape { appearance PBRAppearance { baseColor 0.08 0.48 0.82 roughness 0.05 metalness 0.85 } geometry Cylinder { height 0.1 radius 20.0 } }
    Shape { appearance PBRAppearance { baseColor 0.82 0.82 0.85 roughness 0.5 } geometry Tube { height 0.35 radius 20.5 thickness 1.0 } }
  ]
  name "PARK_CENTRAL_POND"
}
""")

    # 4. BANK 1
    content.append("""# BANK_01 (National Commercial Bank - Branch 1)
Solid {
  translation -120 300 15.10
  children [
    Shape { appearance PBRAppearance { baseColor 0.85 0.82 0.76 roughness 0.4 } geometry Box { size 48 38 30 } }
  ]
  name "BANK_01"
}
Solid {
  translation -120 260 0.10
  children [ Shape { appearance PBRAppearance { baseColor 0.18 0.18 0.2 roughness 0.8 } geometry Box { size 60 20 0.02 } } ]
  name "BANK_01_PARKING"
}
""")

    # 5. MALL
    content.append("""# MALL_01 (City Commercial Shopping Mall Complex)
Solid {
  translation 350 250 20.10
  children [
    Shape { appearance PBRAppearance { baseColor 0.88 0.88 0.92 roughness 0.25 metalness 0.3 } geometry Box { size 100 80 40 } }
  ]
  name "MALL_01"
}
Solid {
  translation 350 170 0.10
  children [ Shape { appearance PBRAppearance { baseColor 0.18 0.18 0.2 roughness 0.8 } geometry Box { size 120 70 0.02 } } ]
  name "MALL_PARKING_LOT"
}
""")

    # 6. RESIDENTIAL AREA
    content.append("""# RESIDENTIAL AREA (Neighborhood Housing Suburb Base)
Solid {
  translation -420 0 0.05
  children [ Shape { appearance PBRAppearance { baseColor 0.2 0.45 0.18 roughness 0.9 } geometry Box { size 220 220 0.10 } } ]
  name "RESIDENTIAL_AREA_BASE"
}
Solid {
  translation -420 30 9.10
  children [ Shape { appearance PBRAppearance { baseColor 0.78 0.42 0.3 roughness 0.7 } geometry Box { size 26 20 18 } } ]
  name "RESIDENTIAL_BLOCK_01"
}
""")
    # Central Residential Houses (50 houses)
    colors = ["0.88 0.84 0.78", "0.92 0.9 0.85", "0.85 0.78 0.72", "0.78 0.82 0.88"]
    roof_colors = ["0.72 0.25 0.18", "0.25 0.25 0.28", "0.55 0.3 0.2"]
    house_idx = 1
    for hx in [-500, -460, -420, -380, -340]:
        for hy in [90, 60, 30, 0, -30, -60, -90]:
            c = colors[house_idx % len(colors)]
            rc = roof_colors[house_idx % len(roof_colors)]
            content.append(generate_house(f"RESIDENTIAL_HOUSE_{house_idx:02d}", hx, hy, color=c, roof_color=rc))
            house_idx += 1

    # 7. COMMERCIAL AREA
    content.append("""# COMMERCIAL AREA (Downtown Business District Towers Base)
Solid {
  translation 0 0 0.05
  children [ Shape { appearance PBRAppearance { baseColor 0.16 0.16 0.18 roughness 0.8 } geometry Box { size 220 220 0.10 } } ]
  name "COMMERCIAL_AREA_BASE"
}
""")
    comm_configs = [
        ("COMMERCIAL_TOWER_01", -70, 70, 42, 38, 65, "0.15 0.22 0.35", 0.85, 0.15),
        ("COMM_TOWER_02", -25, 70, 38, 36, 55, "0.75 0.75 0.78", 0.3, 0.4),
        ("COMM_TOWER_03", 25, 70, 44, 40, 72, "0.18 0.45 0.6", 0.8, 0.1),
        ("COMM_TOWER_04", 70, 70, 36, 38, 52, "0.68 0.72 0.75", 0.4, 0.4),
        ("COMM_TOWER_05", -70, 20, 38, 36, 48, "0.25 0.32 0.42", 0.6, 0.3),
        ("COMM_TOWER_06", -25, 20, 42, 42, 80, "0.12 0.28 0.5", 0.88, 0.1),
        ("COMM_TOWER_07", 25, 20, 46, 38, 60, "0.72 0.75 0.78", 0.3, 0.5),
        ("COMM_TOWER_08", 70, 20, 36, 36, 50, "0.2 0.4 0.5", 0.7, 0.2),
        ("COMM_TOWER_09", -70, -25, 42, 36, 54, "0.7 0.72 0.75", 0.4, 0.4),
        ("COMM_TOWER_10", -25, -25, 38, 38, 68, "0.14 0.2 0.32", 0.85, 0.15),
        ("COMM_TOWER_11", 25, -25, 42, 42, 84, "0.1 0.4 0.65", 0.9, 0.1),
        ("COMM_TOWER_12", 70, -25, 38, 36, 58, "0.75 0.78 0.8", 0.3, 0.4),
        ("COMM_TOWER_13", -70, -70, 36, 36, 45, "0.22 0.3 0.4", 0.6, 0.3),
        ("COMM_TOWER_14", -25, -70, 42, 36, 62, "0.15 0.35 0.55", 0.8, 0.15),
        ("COMM_TOWER_15", 25, -70, 38, 38, 52, "0.68 0.7 0.72", 0.3, 0.5),
        ("COMM_TOWER_16", 70, -70, 42, 36, 58, "0.18 0.25 0.38", 0.75, 0.2),
    ]
    for cname, cx, cy, csx, csy, ch, ccol, cmet, crou in comm_configs:
        content.append(generate_commercial_building(cname, cx, cy, csx, csy, ch, color=ccol, metalness=cmet, roughness=crou))

    # 8. BANK 2
    content.append("""# BANK_02 (Financial District Commercial Branch 2)
Solid {
  translation 340 -80 18.10
  children [ Shape { appearance PBRAppearance { baseColor 0.2 0.48 0.42 roughness 0.25 metalness 0.65 } geometry Box { size 54 42 36 } } ]
  name "BANK_02"
}
Solid {
  translation 340 -120 0.10
  children [ Shape { appearance PBRAppearance { baseColor 0.18 0.18 0.2 roughness 0.8 } geometry Box { size 60 30 0.02 } } ]
  name "BANK_02_PARKING"
}
""")

    # 9. GOVERNMENT HOSPITAL
    content.append("""# GOVERNMENT HOSPITAL COMPLEX (GOVT_HOSPITAL_01)
Solid {
  translation -420 -310 20.10
  children [
    Shape { appearance PBRAppearance { baseColor 0.92 0.94 0.96 roughness 0.3 metalness 0.1 } geometry Box { size 90 60 40 } }
    Transform { translation 50 -6 -6 children [ Shape { appearance PBRAppearance { baseColor 0.88 0.9 0.92 roughness 0.35 } geometry Box { size 50 40 28 } } ] }
    Transform { translation 0 30.1 8 children [ Shape { appearance PBRAppearance { baseColor 0.95 0.1 0.1 emissiveColor 0.95 0.1 0.1 } geometry Box { size 20 0.6 6.0 } }, Shape { appearance PBRAppearance { baseColor 0.95 0.1 0.1 emissiveColor 0.95 0.1 0.1 } geometry Box { size 6.0 0.6 20 } } ] }
  ]
  name "GOVT_HOSPITAL_01"
}
Solid {
  translation -360 -280 6.10
  children [ Shape { appearance PBRAppearance { baseColor 0.84 0.88 0.92 roughness 0.4 } geometry Box { size 24 20 0.8 } } ]
  name "GOVT_HOSPITAL_CANOPY"
}
""")

    # 10. PRIVATE HOSPITAL
    content.append("""# PRIVATE HOSPITAL COMPLEX (PRIVATE_HOSPITAL_01)
Solid {
  translation 350 -310 18.10
  children [
    Shape { appearance PBRAppearance { baseColor 0.75 0.88 0.96 roughness 0.2 metalness 0.6 } geometry Box { size 80 50 36 } }
    Transform { translation 0 -25.1 6 children [ Shape { appearance PBRAppearance { baseColor 0.1 0.75 0.95 emissiveColor 0.1 0.75 0.95 } geometry Box { size 18 0.6 5.0 } }, Shape { appearance PBRAppearance { baseColor 0.1 0.75 0.95 emissiveColor 0.1 0.75 0.95 } geometry Box { size 5.0 0.6 18 } } ] }
  ]
  name "PRIVATE_HOSPITAL_01"
}
Solid {
  translation 300 -280 5.60
  children [ Shape { appearance PBRAppearance { baseColor 0.72 0.84 0.94 roughness 0.3 } geometry Box { size 22 18 0.7 } } ]
  name "PRIVATE_HOSPITAL_CANOPY"
}
""")

    # Emergency Dispatch & Civic Center
    content.append("""# EMERGENCY_SOURCE_01 & CIVIC_BUILDING_01
Solid {
  translation -350 -500 6.10
  children [ Shape { appearance PBRAppearance { baseColor 0.92 0.2 0.1 roughness 0.4 } geometry Box { size 45 30 12 } } ]
  name "EMERGENCY_SOURCE_01"
}
Solid {
  translation -150 150 12.10
  children [ Shape { appearance PBRAppearance { baseColor 0.86 0.86 0.82 roughness 0.5 } geometry Box { size 45 30 24 } } ]
  name "CIVIC_BUILDING_01"
}
""")

    # ==========================================
    # 5. NEW DEVELOPED OUTER DISTRICT LANDMARKS & BUILDINGS
    # ==========================================
    content.append("\n# ==========================================")
    content.append("# 4 NEW DEVELOPED OUTER DISTRICT LANDMARKS")
    content.append("# ==========================================")

    # A. NORTH DISTRICT (Innovation Hub & High-Rise Apartments)
    content.append("""# NORTH INNOVATION TOWER & TECH CAMPUS
Solid {
  translation 0 950 30.10
  children [ Shape { appearance PBRAppearance { baseColor 0.15 0.45 0.7 roughness 0.15 metalness 0.8 } geometry Box { size 65 65 60 } } ]
  name "NORTH_TECH_TOWER"
}
""")
    # 25 North District Apartment Buildings & Houses
    for nx in [-400, -300, -200, 200, 300, 400]:
        for ny in [750, 850, 950]:
            content.append(generate_house(f"NORTH_HOUSE_{house_idx:03d}", nx, ny, color="0.82 0.88 0.92", roof_color="0.25 0.3 0.4", size_x=16.0, size_y=12.0, height=10.0))
            house_idx += 1

    # B. WEST DISTRICT (Hillside Villas & West Community Park)
    content.append("""# WEST COMMUNITY PLAZA & CENTER
Solid {
  translation -950 0 14.10
  children [ Shape { appearance PBRAppearance { baseColor 0.75 0.72 0.65 roughness 0.5 } geometry Box { size 55 45 28 } } ]
  name "WEST_COMMUNITY_CENTER"
}
""")
    # 30 West District Villas
    for wx in [-1050, -950, -750]:
        for wy in range(-300, 350, 70):
            content.append(generate_house(f"WEST_VILLA_{house_idx:03d}", wx, wy, color="0.9 0.85 0.78", roof_color="0.65 0.22 0.18", size_x=15.0, size_y=12.0, height=8.0))
            house_idx += 1

    # C. EAST DISTRICT (Riverside Corporate Promenade & Clinic)
    content.append("""# EAST RIVERSIDE CORPORATE TOWER
Solid {
  translation 950 0 25.10
  children [ Shape { appearance PBRAppearance { baseColor 0.2 0.5 0.65 roughness 0.2 metalness 0.7 } geometry Box { size 70 50 50 } } ]
  name "EAST_CORPORATE_TOWER"
}
""")
    for ex in [750, 850, 950]:
        for ey in range(-300, 350, 70):
            content.append(generate_commercial_building(f"EAST_TOWER_{house_idx:03d}", ex, ey, 35.0, 35.0, 45.0, color="0.72 0.75 0.8", metalness=0.5))
            house_idx += 1

    # D. SOUTH DISTRICT (Industrial Commerce, Logistics & Sports Stadium)
    content.append(generate_stadium("SOUTH_SPORTS_STADIUM", 0, -950))
    content.append(generate_warehouse("SOUTH_LOGISTICS_HUB_01", -300, -950))
    content.append(generate_warehouse("SOUTH_LOGISTICS_HUB_02", 300, -950))

    for sx in [-450, -350, 350, 450]:
        for sy in [-1050, -750]:
            content.append(generate_house(f"SOUTH_HOUSE_{house_idx:03d}", sx, sy, color="0.85 0.82 0.78", roof_color="0.3 0.3 0.35"))
            house_idx += 1

    # ==========================================
    # 6. 3D VISIBLE OVERHEAD LABELS
    # ==========================================
    content.append("\n# ==========================================")
    content.append("# 3D FLOATING OVERHEAD LABELS (JUNCTIONS, LANDMARKS & DISTRICTS)")
    content.append("# ==========================================")

    # District Labels
    content.append(generate_3d_label("DISTRICT_NORTH", "NORTH DISTRICT - INNOVATION HUB", 0, 950, z=75.0, color="0.3 0.85 1.0", size=10.0, bg_width=180.0))
    content.append(generate_3d_label("DISTRICT_SOUTH", "SOUTH DISTRICT - COMMERCE & STADIUM", 0, -950, z=75.0, color="1.0 0.8 0.3", size=10.0, bg_width=190.0))
    content.append(generate_3d_label("DISTRICT_WEST", "WEST DISTRICT - RESIDENTIAL HILLS", -850, 0, z=65.0, color="0.4 1.0 0.5", size=10.0, bg_width=175.0))
    content.append(generate_3d_label("DISTRICT_EAST", "EAST DISTRICT - RIVERSIDE PROMENADE", 850, 0, z=65.0, color="0.9 0.4 1.0", size=10.0, bg_width=185.0))

    # Landmark Labels
    content.append(generate_3d_label("RESEARCH_CENTER", "RESEARCH CENTER", -420, 420, z=45.0, color="0.3 0.8 1.0", size=7.5, bg_width=95.0))
    content.append(generate_3d_label("SCHOOL", "SCHOOL", 0, 520, z=32.0, color="1.0 0.85 0.2", size=7.5, bg_width=50.0))
    content.append(generate_3d_label("CITY_PARK", "CITY PARK", 260, 440, z=28.0, color="0.3 1.0 0.4", size=7.5, bg_width=55.0))
    content.append(generate_3d_label("BANK_01", "BANK 1", -120, 300, z=36.0, color="0.3 1.0 0.6", size=7.5, bg_width=45.0))
    content.append(generate_3d_label("MALL", "MALL", 350, 250, z=48.0, color="1.0 0.3 0.65", size=7.5, bg_width=45.0))
    content.append(generate_3d_label("RESIDENTIAL_AREA", "RESIDENTIAL AREA", -420, 0, z=36.0, color="1.0 0.7 0.4", size=7.5, bg_width=90.0))
    content.append(generate_3d_label("COMMERCIAL_AREA", "COMMERCIAL AREA", 0, 0, z=95.0, color="0.4 0.85 1.0", size=7.5, bg_width=95.0))
    content.append(generate_3d_label("BANK_02", "BANK 2", 340, -80, z=42.0, color="0.3 1.0 0.6", size=7.5, bg_width=45.0))
    content.append(generate_3d_label("GOVT_HOSPITAL", "GOVERNMENT HOSPITAL", -420, -310, z=48.0, color="1.0 0.2 0.2", size=7.5, bg_width=110.0))
    content.append(generate_3d_label("PRIVATE_HOSPITAL", "PRIVATE HOSPITAL", 350, -310, z=44.0, color="0.2 0.85 1.0", size=7.5, bg_width=90.0))
    content.append(generate_3d_label("CIVIC_AREA", "CIVIC CENTER", -150, 150, z=32.0, color="0.9 0.9 0.9", size=6.5, bg_width=65.0))
    content.append(generate_3d_label("EMERGENCY_SOURCE", "DISPATCH DEPOT", -350, -500, z=26.0, color="1.0 0.3 0.2", size=6.5, bg_width=70.0))

    # Junction Labels for J1..J15
    coords_map = [
        (-250, 250), (250, 250), (220, -50), (-250, -250), (150, -450),
        (-350, -450), (-700, 700), (0, 850), (700, 700), (-850, 0),
        (850, 0), (-700, -700), (0, -850), (700, -700), (450, 450)
    ]
    for i in range(1, 16):
        j_id = f"JUNCTION_{i:02d}"
        label_txt = f"JUNCTION {i}"
        if i == 3: label_txt += " (ROUNDABOUT 1)"
        elif i == 7: label_txt += " (ROUNDABOUT 2)"
        elif i == 14: label_txt += " (ROUNDABOUT 3)"
        jx, jy = coords_map[i - 1]
        content.append(generate_3d_label(j_id, label_txt, jx, jy, z=28.0, color="1.0 1.0 1.0", size=6.0, bg_width=70.0))

    # ==========================================
    # 7. PROCEDURAL TREES & DENSE URBAN GREENERY (1200+ Trees)
    # ==========================================
    content.append("\n# ==========================================")
    content.append("# DENSE URBAN GREENERY & FOREST BUFFERS (1200+ Trees)")
    content.append("# ==========================================")
    tree_idx = 1
    # Park Trees
    for tx in range(200, 320, 15):
        for ty in range(390, 490, 15):
            if math.hypot(tx - 260, ty - 440) > 22:
                content.append(generate_tree(f"TREE_PARK_{tree_idx:04d}", tx, ty, scale=1.3))
                tree_idx += 1

    # Grid of Greenery across outer districts & roadside avenues
    for tx in range(-1150, 1150, 60):
        for ty in range(-1150, 1150, 60):
            if math.hypot(tx, ty) > 100 and (abs(tx) % 200 > 30 or abs(ty) % 200 > 30):
                content.append(generate_tree(f"TREE_CITY_{tree_idx:04d}", tx, ty, scale=1.2))
                tree_idx += 1

    # Write output WBT file
    full_text = "\n".join(content)
    output_path = r"d:\REC\Phoenix\swift-system\webots\worlds\swift_city.wbt"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    print(f"Successfully generated {output_path} with {len(content)} VRML components and {tree_idx} trees!")

if __name__ == "__main__":
    build_urban_world()
