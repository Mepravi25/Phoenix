"""
SWIFT SYSTEM - Webots Traffic Monitor Controller
Module 2: Traffic & Junction Simulation Baseline Monitoring.

Monitors traffic density, queue lengths, approaching vehicles, average speeds,
waiting times, and congestion levels across all 4 junctions (J1-J4).
Outputs formatted telemetry to the Webots console periodically.
"""

import os
import sys
import math
import time
import json
from typing import Dict, List, Tuple, Optional, Any

try:
    from controller import Supervisor
    WEBOTS_AVAILABLE = True
except ImportError:
    WEBOTS_AVAILABLE = False

STATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

JUNCTIONS = {
    "J1": {"name": "North-West", "x": -46.5, "y": 46.5},
    "J2": {"name": "North-East", "x": 46.5,  "y": 46.5},
    "J3": {"name": "South-West", "x": -46.5, "y": -46.5},
    "J4": {"name": "South-East", "x": 46.5,  "y": -46.5},
}

DETECTION_RADIUS = 35.0  # meters from junction center
QUEUE_RADIUS = 15.0      # meters from junction center for queue check
STOP_SPEED_THRESHOLD = 0.5  # m/s below which a vehicle is considered waiting/queued


class TrafficMonitor:
    """
    Traffic Monitor that extracts live junction metrics and simulation statistics.
    Can be run as a standalone controller or integrated into SimulationManager.
    """
    def __init__(self, supervisor: Optional[Any] = None, report_interval: float = 5.0):
        self.supervisor = supervisor
        self.report_interval = report_interval
        self.last_report_time = 0.0
        self.elapsed_time = 0.0
        self.time_step = int(self.supervisor.getBasicTimeStep()) if (self.supervisor and WEBOTS_AVAILABLE) else 32

        # Waiting time tracker per vehicle: {vehicle_id: wait_start_timestamp}
        self.waiting_start_times: Dict[str, float] = {}

    def _get_vehicle_states(self) -> Dict[str, Dict[str, Any]]:
        """Fetch position, speed, and status of all active vehicles."""
        vehicles = {}
        v_ids = ["CAR_001", "CAR_002", "CAR_003", "CAR_004", "AMBULANCE_001"]

        if self.supervisor and WEBOTS_AVAILABLE:
            for v_id in v_ids:
                node = self.supervisor.getFromDef(v_id)
                if node:
                    t_field = node.getField("translation")
                    v_field = node.getVelocity() if hasattr(node, "getVelocity") else None
                    if t_field:
                        pos = t_field.getSFVec3f()
                        if v_field and len(v_field) >= 3:
                            speed = math.hypot(v_field[0], v_field[1])
                        else:
                            speed = 0.0
                        vehicles[v_id] = {
                            "vehicle_id": v_id,
                            "x": pos[0],
                            "y": pos[1],
                            "z": pos[2],
                            "speed": speed
                        }

        # Fallback / merge with state files if Supervisor API didn't return all
        for v_id in v_ids:
            if v_id not in vehicles:
                s_file = os.path.join(STATE_DIR, f"vehicle_pos_{v_id}.json")
                if os.path.exists(s_file):
                    try:
                        with open(s_file, "r") as f:
                            data = json.load(f)
                        if abs(self.elapsed_time - data.get("timestamp", 0.0)) <= 3.0:
                            vehicles[v_id] = {
                                "vehicle_id": v_id,
                                "x": data.get("x", 0.0),
                                "y": data.get("y", 0.0),
                                "z": data.get("z", 0.42),
                                "speed": data.get("speed", 0.0)
                            }
                    except Exception:
                        pass

        return vehicles

    def _calculate_junction_metrics(self, vehicles: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Calculate per-junction traffic statistics."""
        junction_data = {}

        for j_id, j_info in JUNCTIONS.items():
            jx, jy = j_info["x"], j_info["y"]
            in_zone = []
            approaching = []
            queue = []
            waiting_times = []

            for v_id, v_data in vehicles.items():
                vx, vy = v_data["x"], v_data["y"]
                speed = v_data["speed"]
                dist = math.hypot(vx - jx, vy - jy)

                if dist <= DETECTION_RADIUS:
                    in_zone.append(v_id)

                    if dist <= 25.0:
                        approaching.append(v_id)

                    if dist <= QUEUE_RADIUS and speed <= STOP_SPEED_THRESHOLD:
                        queue.append(v_id)

                        # Update waiting time
                        if v_id not in self.waiting_start_times:
                            self.waiting_start_times[v_id] = self.elapsed_time
                        wait_dur = self.elapsed_time - self.waiting_start_times[v_id]
                        waiting_times.append(wait_dur)
                    else:
                        if v_id in self.waiting_start_times:
                            del self.waiting_start_times[v_id]

            queue_len = len(queue)
            avg_wait = (sum(waiting_times) / len(waiting_times)) if waiting_times else 0.0

            # Deterministic Congestion Classification
            if queue_len == 0 or queue_len == 1:
                congestion = "LOW"
            elif queue_len <= 3:
                congestion = "MEDIUM"
            elif queue_len <= 5:
                congestion = "HIGH"
            else:
                congestion = "CRITICAL"

            junction_data[j_id] = {
                "name": j_info["name"],
                "vehicle_count": len(in_zone),
                "approaching_count": len(approaching),
                "queue_length": queue_len,
                "waiting_count": queue_len,
                "avg_waiting_time": avg_wait,
                "congestion": congestion
            }

        return junction_data

    def generate_report(self, dt: float):
        """Update elapsed time and print report if report interval reached."""
        self.elapsed_time += dt

        if (self.elapsed_time - self.last_report_time) >= self.report_interval:
            self.last_report_time = self.elapsed_time
            vehicles = self._get_vehicle_states()
            j_metrics = self._calculate_junction_metrics(vehicles)

            # Network level metrics
            total_active = len(vehicles)
            speeds = [v["speed"] for v in vehicles.values()]
            avg_speed = (sum(speeds) / len(speeds)) if speeds else 0.0
            max_q = max([m["queue_length"] for m in j_metrics.values()]) if j_metrics else 0
            avg_q = (sum([m["queue_length"] for m in j_metrics.values()]) / len(j_metrics)) if j_metrics else 0.0

            print("\n====================================", flush=True)
            print("SWIFT SYSTEM TRAFFIC MONITOR", flush=True)
            print(f"Simulation Time: {self.elapsed_time:.1f}s | Active Vehicles: {total_active}", flush=True)
            print("====================================", flush=True)

            for j_id, m in j_metrics.items():
                print(f"Junction: {j_id} ({m['name']})", flush=True)
                print(f"  Vehicles: {m['vehicle_count']} | Approaching: {m['approaching_count']} | Queue: {m['queue_length']} | Waiting: {m['waiting_count']}", flush=True)
                print(f"  Avg Wait: {m['avg_waiting_time']:.1f}s | Congestion: {m['congestion']}", flush=True)

            print("------------------------------------", flush=True)
            print(f"Network Summary -> Avg Speed: {avg_speed:.1f} m/s | Max Queue: {max_q} | Avg Queue: {avg_q:.1f}", flush=True)
            print("====================================\n", flush=True)

    def run(self):
        """Standalone supervisor execution loop."""
        print("[TrafficMonitor] Started monitoring Webots traffic flow...", flush=True)
        if self.supervisor and WEBOTS_AVAILABLE:
            while self.supervisor.step(self.time_step) != -1:
                self.generate_report(self.time_step / 1000.0)


if __name__ == "__main__":
    if WEBOTS_AVAILABLE:
        supervisor = Supervisor()
        monitor = TrafficMonitor(supervisor)
        monitor.run()
    else:
        print("[TrafficMonitor] Webots API not available. Running headless mode.")
        monitor = TrafficMonitor()
        for step in range(50):
            monitor.generate_report(0.1)
            time.sleep(0.1)
