# Mini Urban District Architecture Specification — Module 1

## Overview
This specification outlines the architecture, layout, road hierarchy, landmark distribution, signal infrastructure, and 3D label system for the Webots simulation world (`swift_city.wbt`) built for **Module 1: Complete Mini Urban District**.

---

## 1. District Layout & Scale
- **Ground Area**: `450m x 450m` (centered at `0, 0, 0`).
- **Coordinate System**: ENU (`+X` East, `+Y` North, `+Z` Up).
- **Design Paradigm**: Irregular, organic urban locality layout avoiding uniform grid patterns or simple square loops.
- **Density**: High coverage of roads, sidewalks, civic facilities, and building landmarks occupying the majority of the simulation grid.

---

## 2. Junction Infrastructure
- **Total Signalized Junctions**: 6
  - `JUNCTION_01`: North 4-Way Signalized Junction `(-80.0, 100.0)`
  - `JUNCTION_02`: East T-Junction `(100.0, 80.0)`
  - `JUNCTION_03`: Central 4-Way Irregular Hub `(-20.0, 10.0)`
  - `JUNCTION_04`: South-East Offset Intersection `(80.0, -50.0)`
  - `JUNCTION_05`: Hospital Gateway Junction `(30.0, -120.0)`
  - `JUNCTION_06`: South-West Residential/Local Junction `(-70.0, -130.0)`
- **Signal Poles**: Named `J1_SIGNAL`, `J2_SIGNAL`, `J3_SIGNAL`, `J4_SIGNAL`, `J5_SIGNAL`, `J6_SIGNAL` with directional lamp boxes.
- **Approaches**: Stop lines (`0.5m x 4.0m` white bars) and pedestrian crosswalks at each entry arm.

---

## 3. Road Hierarchy & Traffic Rules
1. **Main Arterials (10.0m wide)**: 4 lanes with yellow median divider lines. Connect main hubs (`J1-J2`, `J3-J5`).
2. **Secondary Roads (7.5m - 8.0m wide)**: 2 lanes connecting commercial, educational, and medical hubs.
3. **Local Roads (5.0m - 7.5m wide)**: Connecting residential zones, city park, and emergency dispatch depot.
4. **Traffic Rule**: Indian Left-Hand Traffic (LHT) (`← ← | → →`).

---

## 4. Required Destinations & Landmarks
- **Government Hospital (`GOVT_HOSPITAL_01`)**: `(-45.0, -120.0, 12.0)` with ambulance bay canopy and red cross tower emblem.
- **Private Hospital (`PRIVATE_HOSPITAL_01`)**: `(115.0, -120.0, 10.0)` with modern glass facade and cyan cross emblem.
- **School (`SCHOOL_01`)**: `(-160.0, 120.0, 7.0)` brick complex with adjacent athletic field `(-160, 60)`.
- **Mall (`MALL_01`)**: `(160.0, 110.0, 15.0)` multi-story retail mall.
- **Research Center (`RESEARCH_CENTER_01`)**: `(165.0, -50.0, 18.0)` corporate R&D complex.
- **Bank 01 (`BANK_01`)**: `(60.0, 105.0, 9.0)` classical bank building with columns.
- **Bank 02 (`BANK_02`)**: `(20.0, -45.0, 8.0)` modern financial branch.
- **Residential Area**: Housing blocks and apartment towers in the West Sector `(-140.0, 10.0)`.
- **Commercial Area**: Glass office towers and retail plaza in the East Sector `(120.0, 40.0)`.
- **Civic Area**: Municipal office building in the North-Central Sector `(-50.0, 60.0)`.
- **City Park**: 90m x 80m green park with central pond and trees in the South-West Sector `(-140.0, -100.0)`.
- **Emergency Source Depot (`EMERGENCY_SOURCE_01`)**: Dispatch station at `(-70.0, -190.0)`.

---

## 5. 3D Building Label System
Every landmark features an elevated 3D readable text label positioned above the building facing the Viewpoint camera:
- `GOVERNMENT HOSPITAL`
- `PRIVATE HOSPITAL`
- `SCHOOL`
- `MALL`
- `RESEARCH CENTER`
- `BANK 01`
- `BANK 02`
- `RESIDENTIAL AREA`
- `COMMERCIAL AREA`
- `CIVIC AREA`
- `CITY PARK`
- `EMERGENCY SOURCE 01`

---

## 6. Road Name Signboards
Green street name signboards positioned at key road entrances:
- `MAIN ARTERIAL ROAD`
- `SCHOOL ROAD`
- `HOSPITAL ROAD`
- `COMMERCIAL ROAD`
- `RESEARCH ROAD`
- `RESIDENTIAL ROAD`
