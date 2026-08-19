# Module 2 — Traffic & Junction Simulation Documentation

## Overview
Module 2 establishes the **Baseline Traffic & Junction Simulation** for the Swift System in Webots R2025a. It introduces standard normal traffic vehicles, lane/waypoint-following behaviors, 4-approach traffic light signals, junction controllers, signal compliance, configurable traffic density profiles, and live traffic monitoring metrics.

---

## Key Components

### 1. Reusable Normal Traffic Vehicles
- **Controllers**: `car_001_controller`, `car_002_controller`, `car_003_controller`, `car_004_controller`, `vehicle_controller`.
- **IDs**: `CAR_001`, `CAR_002`, `CAR_003`, `CAR_004`.
- **Navigation**: Closed waypoint loops (`J1` → `J2` → `J4` → `J3` → `J1`).
- **Safety**:
  - Enforces minimum 3.0m vehicle-to-vehicle clearance.
  - Strict asphalt road corridor boundary validation (`validate_road_corridor`).
  - Smooth target heading interpolation and progress watchdog timer.

### 2. Traffic Light & Junction Controller
- **Controller**: `junction_controller/junction_controller.py`.
- **Signal Phases**: `NS_GREEN` → `NS_YELLOW` → `ALL_RED` → `EW_GREEN` → `EW_YELLOW` → `ALL_RED`.
- **State Export**: Continuously exports current lamp states for all approaches to `traffic_signal_states.json`.
- **Signal Interaction**:
  - `GREEN`: Vehicles proceed through intersection.
  - `YELLOW`: Vehicles decelerate when approaching within 6.0m of stop line.
  - `RED`: Vehicles stop before stop line (<= 2.5m clearance).

### 3. Configurable Traffic Density
- **Configuration**: Defined in `config/traffic.json` and selectable via environment variable `TRAFFIC_DENSITY`.
- **Profiles**:
  - `LOW`: 2 active normal vehicles.
  - `MEDIUM`: 3 active normal vehicles (Default).
  - `HIGH`: 4 active normal vehicles.

### 4. Traffic Monitor & Metrics Logging
- **Controller**: `traffic_monitor/traffic_monitor.py` (integrated with `simulation_manager.py`).
- **Per-Junction Metrics**: Vehicle count, approaching count, queue length, waiting vehicle count, average waiting time, congestion level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **Global Telemetry**: Active vehicle count, network average speed, max queue length, average queue length, total simulation time.
- **Console Reports**: Formatted status reports printed every 5 seconds to Webots console.

---

## Verification & Test Results
- **TEST 1-2**: Waypoint following verified for single and multi-vehicle scenarios.
- **TEST 3-5**: Traffic light compliance (RED stop, YELLOW slow, GREEN proceed) verified.
- **TEST 6-7**: Queue formation and 3m safe clearance verified.
- **TEST 8**: 4 Junctions (`J1`-`J4`) running synchronized signal cycles.
- **TEST 9-11**: Configurable traffic density (`LOW`, `MEDIUM`, `HIGH`) verified.
- **TEST 12**: Continuous simulation stability without crashes or deadlocks verified.

---

## Execution Steps
1. Open Webots R2025a and open world file `webots/worlds/swift_city.wbt`.
2. To test different traffic density profiles before launching Webots, set `TRAFFIC_DENSITY`:
   ```bash
   $env:TRAFFIC_DENSITY="HIGH"   # Options: LOW, MEDIUM, HIGH
   ```
3. Press Play in Webots to view vehicles, traffic lights, and live console metrics.
