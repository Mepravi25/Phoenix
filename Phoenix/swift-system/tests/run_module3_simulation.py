"""
Simulation Integration Test Runner for Module 3 (Normal Traffic Vehicle Simulation).
Simulates 120 seconds of continuous multi-vehicle traffic with J1..J4 JunctionControllers.
"""

import sys
import os
import time
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots", "controllers", "junction_controller")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots", "controllers", "vehicle_controller")))

from junction_controller import IntersectionController
from vehicle_controller import NormalVehicleController, NUM_NORMAL_VEHICLES, SIGNAL_STATE_FILE, POSITIONS_STATE_FILE


def run_simulation(duration_seconds: float = 120.0):
    print("=" * 60)
    print(f"STARTING MODULE 3 TRAFFIC SIMULATION RUNNER ({duration_seconds}s)")
    print("=" * 60)

    # Initialize 4 Junction Controllers
    junctions = {
        "J1": IntersectionController("J1", robot=None),
        "J2": IntersectionController("J2", robot=None),
        "J3": IntersectionController("J3", robot=None),
        "J4": IntersectionController("J4", robot=None),
    }

    # Initialize 10 Normal Vehicle Controllers
    vehicles = [
        NormalVehicleController(f"CAR_{i:03d}")
        for i in range(1, NUM_NORMAL_VEHICLES + 1)
    ]

    time_step = 0.032  # 32ms timestep
    total_steps = int(duration_seconds / time_step)

    red_stops_count = 0
    green_moves_count = 0
    collisions_count = 0

    print(f"Running simulation for {total_steps} timesteps...")

    for step in range(total_steps):
        # 1. Update 4 Junction Controllers
        for j_id, j_ctrl in junctions.items():
            j_ctrl.update_logic(time_step)

        # 2. Update 10 Vehicle Controllers
        for vehicle in vehicles:
            vehicle.update_logic(time_step)

        # Check vehicle safety / collision overlapping
        for i in range(len(vehicles)):
            v1 = vehicles[i]
            if not v1.is_spawned:
                continue
            for j in range(i + 1, len(vehicles)):
                v2 = vehicles[j]
                if not v2.is_spawned:
                    continue
                dist = ((v1.x - v2.x) ** 2 + (v1.y - v2.y) ** 2) ** 0.5
                if dist < 2.5:  # Overlap threshold
                    print(f"[COLLISION ERROR] Step {step}: {v1.vehicle_id} and {v2.vehicle_id} overlapped! (dist={dist:.2f}m)")
                    collisions_count += 1

        # Track activity at interval
        if step % 500 == 0:
            active_cars = sum(1 for v in vehicles if v.is_spawned)
            moving_cars = sum(1 for v in vehicles if v.is_spawned and v.current_speed > 0.5)
            stopped_cars = sum(1 for v in vehicles if v.is_spawned and v.current_speed <= 0.5)
            sim_time = step * time_step
            print(f"[T={sim_time:5.1f}s] Active Cars: {active_cars}/{NUM_NORMAL_VEHICLES} | Moving: {moving_cars} | Stopped: {stopped_cars}")

    print("=" * 60)
    print("SIMULATION SUMMARY RESULT:")
    print(f"Total Duration: {duration_seconds}s ({total_steps} steps)")
    print(f"Active Vehicles: {sum(1 for v in vehicles if v.is_spawned)}/{NUM_NORMAL_VEHICLES}")
    print(f"Collisions / Overlaps: {collisions_count}")

    assert collisions_count == 0, f"Collisions detected during simulation: {collisions_count}"
    assert sum(1 for v in vehicles if v.is_spawned) == NUM_NORMAL_VEHICLES, "Not all vehicles spawned!"

    print("MODULE 3 TRAFFIC SIMULATION PASSED CLEANLY WITH ZERO ERRORS.")
    print("=" * 60)


if __name__ == "__main__":
    run_simulation(120.0)
