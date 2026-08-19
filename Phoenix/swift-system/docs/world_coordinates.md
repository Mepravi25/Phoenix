# Urban World Coordinate Documentation — SWIFT SYSTEM (Module 1 Rebuild)

This document defines the exact physical parameters, 3D world coordinates, road network hierarchy, Indian Left-Hand Traffic (LHT) rules, traffic signal infrastructure, and landmark positions for the complete mini urban district in Webots R2025a.

---

## 1. World Geometry Overview

* **District Dimensions**: `450m x 450m` (`X: -225.0 to 225.0`, `Y: -225.0 to 225.0`)
* **Coordinate System**: ENU (`+X` = East, `+Y` = North, `+Z` = Up)
* **Ground Elevation**: Asphalt road surface at `Z = 0.01m`, Sidewalks at `Z = 0.04m`
* **Road Hierarchy**:
  * **Main Arterial Corridor**: 10.0m width (4-lane / 2-way with median)
  * **Secondary Corridors**: 7.5m - 8.0m width (2-lane directional)
  * **Local Access Roads**: 5.0m - 7.5m width (residential, park, emergency depot)

---

## 2. Major Signalized Junction Registry

| Junction ID | Name / Type | Center Coordinates (X, Y, Z) | Size (L x W) | Controlled Signals | Connected Junctions |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`JUNCTION_01`** | North Hub (4-Way Signalized w/ Median) | `(-80.0, 100.0, 0.01)` | 18m x 18m | `J1_NORTH_SIGNAL`<br>`J1_SOUTH_SIGNAL`<br>`J1_EAST_SIGNAL`<br>`J1_WEST_SIGNAL` | `JUNCTION_02`, `JUNCTION_03` |
| **`JUNCTION_02`** | East Hub (T-Junction on Main Arterial) | `(100.0, 80.0, 0.01)` | 16m x 16m | `J2_WEST_SIGNAL`<br>`J2_EAST_SIGNAL`<br>`J2_SOUTH_SIGNAL` | `JUNCTION_01`, `JUNCTION_04` |
| **`JUNCTION_03`** | Central Hub (Irregular 4-Way Junction) | `(-20.0, 10.0, 0.01)` | 16m x 16m | `J3_NORTH_SIGNAL`<br>`J3_SOUTH_SIGNAL`<br>`J3_WEST_SIGNAL`<br>`J3_EAST_SIGNAL` | `JUNCTION_01`, `JUNCTION_04`, `JUNCTION_05`, `JUNCTION_06` |
| **`JUNCTION_04`** | South-East Offset Commercial & R&D | `(80.0, -50.0, 0.01)` | 16m x 16m | `J4_NORTH_SIGNAL`<br>`J4_SOUTH_SIGNAL`<br>`J4_EAST_SIGNAL`<br>`J4_WEST_SIGNAL` | `JUNCTION_02`, `JUNCTION_03`, `JUNCTION_05` |
| **`JUNCTION_05`** | Hospital Gateway Junction (Medical Hub) | `(30.0, -120.0, 0.01)` | 16m x 16m | `J5_NORTH_SIGNAL`<br>`J5_SOUTH_SIGNAL`<br>`J5_EAST_SIGNAL`<br>`J5_WEST_SIGNAL` | `JUNCTION_03`, `JUNCTION_04`, `JUNCTION_06` |
| **`JUNCTION_06`** | South-West Local Hub (Residential & Depot) | `(-70.0, -130.0, 0.01)` | 16m x 16m | `J6_NORTH_SIGNAL`<br>`J6_SOUTH_SIGNAL`<br>`J6_EAST_SIGNAL`<br>`J6_WEST_SIGNAL` | `JUNCTION_03`, `JUNCTION_05` |

---

## 3. Civic & Commercial Destinations Registry

| Landmark ID | Visible 3D Label | Center Position (X, Y, Z) | Dimensions / Features | Connected Road / Junction |
| :--- | :--- | :--- | :--- | :--- |
| **`GOVT_HOSPITAL_01`** | `GOVERNMENT HOSPITAL` | `(-45.0, -120.0, 12.0)` | 40m x 28m x 24m, Red Cross emblem tower, Emergency Bay `(-20, -120)` | `ROAD_GOVT_HOSPITAL` -> `JUNCTION_05` |
| **`PRIVATE_HOSPITAL_01`** | `PRIVATE HOSPITAL` | `(115.0, -120.0, 10.0)` | 36m x 26m x 20m, Modern glass facade, Cyan cross, Dropoff Bay `(95, -120)` | `ROAD_PRIVATE_HOSPITAL` -> `JUNCTION_05` |
| **`SCHOOL_01`** | `SCHOOL` | `(-160.0, 120.0, 7.0)` | 44m x 24m x 14m Brick school, Athletic field `(-160, 60)` | `ROAD_SCHOOL_01` -> `JUNCTION_01` |
| **`MALL_01`** | `MALL` | `(160.0, 110.0, 15.0)` | 50m x 40m x 30m Multi-story retail mall & atrium | `ROAD_COMMERCIAL_EAST` -> `JUNCTION_02` |
| **`RESEARCH_CENTER_01`** | `RESEARCH CENTER` | `(165.0, -50.0, 18.0)` | 36m x 32m x 36m Tech R&D building with roof antenna | `ROAD_RESEARCH_01` -> `JUNCTION_04` |
| **`BANK_01`** | `BANK 01` | `(60.0, 105.0, 9.0)` | 24m x 18m x 18m Classical banking entrance w/ columns | Main Arterial -> `JUNCTION_01` / `JUNCTION_02` |
| **`BANK_02`** | `BANK 02` | `(20.0, -45.0, 8.0)` | 22m x 16m x 16m Commercial banking branch | `ROAD_COMMERCIAL_WEST` -> `JUNCTION_04` |
| **`RESIDENTIAL_AREA`** | `RESIDENTIAL AREA` | `(-140.0, 10.0, 10.0)` | Multiple housing blocks (`-140,30`, `-140,-10`, `-100,10`) | Local residential access roads -> `JUNCTION_03` |
| **`COMMERCIAL_AREA`** | `COMMERCIAL AREA` | `(120.0, 40.0, 20.0)` | Glass office tower `(130,40,25)` & plaza `(110,20,12)` | `ROAD_COMMERCIAL_SOUTH` -> `JUNCTION_02` / `JUNCTION_04` |
| **`CIVIC_AREA`** | `CIVIC AREA` | `(-50.0, 60.0, 8.0)` | Municipal government building (28m x 20m x 16m) | `ROAD_CIVIC_PARK` -> `JUNCTION_03` |
| **`CITY_PARK`** | `CITY PARK` | `(-140.0, -100.0, 0.02)`| 90m x 80m green park, central pond (r=9m), trees | `ROAD_CIVIC_PARK` -> `JUNCTION_03` / `JUNCTION_06` |
| **`EMERGENCY_SOURCE_01`**| `EMERGENCY SOURCE 01` | `(-70.0, -190.0, 4.0)` | 24m x 18m x 8m Emergency response dispatch station | `ROAD_EMERGENCY_SOURCE` -> `JUNCTION_06` |

---

## 4. Road Hierarchy & Segment Registry

| Road ID | Hierarchy Class | Width | Length | Connected Nodes |
| :--- | :--- | :--- | :--- | :--- |
| **`ROAD_ARTERIAL_MAIN_A/B`** | Main Arterial | 10.0m | 172.0m | `JUNCTION_01` <-> `JUNCTION_02` |
| **`ROAD_ARTERIAL_NORTH`** | Expressway | 10.0m | 91.0m | `JUNCTION_01` North Corridor |
| **`ROAD_SCHOOL_01`** | Secondary | 7.5m | 71.0m | `JUNCTION_01` <-> `SCHOOL_01` |
| **`ROAD_RESIDENTIAL_NORTH`**| Secondary | 7.5m | 111.0m | `JUNCTION_01` <-> `JUNCTION_03` |
| **`ROAD_COMMERCIAL_EAST`** | Secondary | 8.0m | 82.0m | `JUNCTION_02` <-> `MALL_01` |
| **`ROAD_COMMERCIAL_SOUTH`**| Secondary | 8.0m | 116.0m | `JUNCTION_02` <-> `JUNCTION_04` |
| **`ROAD_COMMERCIAL_WEST`** | Secondary | 8.0m | 110.0m | `JUNCTION_04` <-> `JUNCTION_03` |
| **`ROAD_RESEARCH_01`** | Secondary | 7.5m | 69.0m | `JUNCTION_04` <-> `RESEARCH_CENTER_01` |
| **`ROAD_HOSPITAL_ARTERIAL`**| Main Arterial | 10.0m | 138.0m | `JUNCTION_03` <-> `JUNCTION_05` |
| **`ROAD_GOVT_HOSPITAL`** | Emergency Dedicated | 8.0m | 59.0m | `JUNCTION_05` <-> `GOVT_HOSPITAL_01` |
| **`ROAD_PRIVATE_HOSPITAL`** | Emergency Dedicated | 8.0m | 72.0m | `JUNCTION_05` <-> `PRIVATE_HOSPITAL_01` |
| **`ROAD_CIVIC_PARK`** | Secondary / Local | 7.5m | 92.0m | `JUNCTION_03` <-> `CITY_PARK` / `CIVIC_AREA` |
| **`ROAD_RESIDENTIAL_SOUTH`**| Secondary | 7.5m | 142.0m | `JUNCTION_03` <-> `JUNCTION_06` |
| **`ROAD_HOSPITAL_RESIDENTIAL_LOOP`**| Local | 7.5m | 84.0m | `JUNCTION_06` <-> `JUNCTION_05` |
| **`ROAD_EMERGENCY_SOURCE`**| Emergency Access | 8.0m | 42.0m | `JUNCTION_06` <-> `EMERGENCY_SOURCE_01` |

---

## 5. Indian Left-Hand Traffic (LHT) Rules & Markings

- Driving occurs strictly on the **LEFT** side of the road in the direction of motion (`← ← ← | → → →`).
- Double yellow solid lines mark central medians on 4-lane arterials (`Z = 0.035m`).
- Single yellow lines mark centerlines on secondary and local roads.
- White solid stop bars (`0.5m x 4.0m`) mark junction approach boundaries.
- White zebra crosswalks mark pedestrian crossings at all signalized junctions.
