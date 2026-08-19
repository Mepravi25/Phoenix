"""
SWIFT SYSTEM - Webots Simulator Bridge
Bridges physical Webots simulation telemetry and central Python server via WebSockets.
Runs continuously, supporting both full Webots controller IPC and realistic simulation fallback engine.
"""

import asyncio
import json
import logging
import math
import random
import time
import time
from typing import Dict, List, Any, Optional

from webots.telemetry_generator import telemetry_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (WebotsBridge) %(message)s")
logger = logging.getLogger("WebotsBridge")


class SwiftWebotsSimulator:
    def __init__(self, mode: str = "MEDIUM"):
        self.mode = mode.upper()
        self.simulation_time = 0.0
        self.time_step = 0.5  # seconds per tick
        self.is_running = True

        # Junctions state (J1..J25 for 5x5 grid)
        self.junctions: Dict[str, Dict[str, Any]] = {}
        for node_id in range(25):
            r, c = node_id // 5, node_id % 5
            j_id = f"J{node_id + 1}"
            self.junctions[j_id] = {
                "id": j_id,
                "pos": {"x": round((c - 2) * 100.0, 2), "y": round((r - 2) * 100.0, 2)},
                "signal_state": "GREEN_NS" if (r + c) % 2 == 0 else "GREEN_EW",
                "queue_length": 3,
                "vehicle_count": 8,
                "avg_speed": 40.0,
                "lane_occupancy": 0.35,
                "traffic_density": 0.40,
                "congestion_level": "LOW",
                "priority_active": False,
                "remaining_green": 12.0
            }

        # Ambulance physical state
        self.ambulance = {
            "id": "AMB_01",
            "urgency_level": "LEVEL_3",
            "start_junction": "J1",
            "destination": "HOSPITAL_CENTRAL",
            "dest_junction": "J8",
            "current_junction": "J1",
            "current_road": "R_J1_J2",
            "position": {"x": -200.0, "y": -200.0},
            "speed": 0.0,  # km/h
            "target_speed": 60.0,
            "heading": 0.0,  # degrees
            "route": ["J1", "J2", "J3", "J8"],
            "route_progress": 0.0,  # 0.0 to 1.0 along current road
            "current_segment_index": 0,
            "stopped_in_traffic": False,
            "cumulative_waiting_time": 0.0,
            "stops_count": 0,
            "active": True,
            "has_arrived": False
        }

        # Dynamic Incidents / Accidents
        self.active_incidents: Dict[str, Dict[str, Any]] = {}

        # Road segments geometry & distance across 5x5 grid
        self.roads: Dict[str, Dict[str, Any]] = {}
        for node_id in range(25):
            r, c = node_id // 5, node_id % 5
            j_curr = f"J{node_id + 1}"
            if c < 4:
                j_east = f"J{node_id + 2}"
                self.roads[f"R_{j_curr}_{j_east}"] = {"from": j_curr, "to": j_east, "length": 200.0}
                self.roads[f"R_{j_east}_{j_curr}"] = {"from": j_east, "to": j_curr, "length": 200.0}
            if r < 4:
                j_south = f"J{node_id + 6}"
                self.roads[f"R_{j_curr}_{j_south}"] = {"from": j_curr, "to": j_south, "length": 200.0}
                self.roads[f"R_{j_south}_{j_curr}"] = {"from": j_south, "to": j_curr, "length": 200.0}

        # System Mode: BASELINE vs SWIFT
        self.orchestration_mode = "SWIFT"

    def set_orchestration_mode(self, mode: str):
        self.orchestration_mode = mode.upper()
        logger.info(f"Orchestration mode set to {self.orchestration_mode}")

    def inject_incident(self, road_id: str, incident_type: str = "ACCIDENT", severity: str = "HIGH"):
        self.active_incidents[road_id] = {
            "type": incident_type,
            "severity": severity,
            "timestamp": self.simulation_time
        }
        logger.info(f"INCIDENT INJECTED: {incident_type} on {road_id} (Severity: {severity})")

    def clear_incidents(self):
        self.active_incidents.clear()
        logger.info("All incidents cleared")

    def apply_signal_command(self, junction_id: str, command: Dict[str, Any]):
        if junction_id not in self.junctions:
            return
        j = self.junctions[junction_id]
        new_state = command.get("signal_state", j["signal_state"])
        duration = command.get("green_duration", 15.0)
        is_priority = command.get("priority", False)

        j["signal_state"] = new_state
        j["remaining_green"] = duration
        j["priority_active"] = is_priority
        logger.info(f"Signal update applied to {junction_id}: {new_state} (Priority: {is_priority})")

    def update_ambulance_route(self, new_route: List[str]):
        if self.ambulance["route"] != new_route:
            logger.info(f"AMBULANCE ROUTE UPDATED: {self.ambulance['route']} -> {new_route}")
            self.ambulance["route"] = new_route
            self.ambulance["has_arrived"] = False
            self.ambulance["active"] = True
            curr_j = self.ambulance["current_junction"]
            if curr_j in new_route:
                idx = new_route.index(curr_j)
                if idx < len(new_route) - 1:
                    self.ambulance["current_segment_index"] = idx
                    next_j = new_route[idx + 1]
                    self.ambulance["current_road"] = f"R_{curr_j}_{next_j}"
                else:
                    self.ambulance["current_segment_index"] = max(0, len(new_route) - 1)
            else:
                if len(new_route) > 0:
                    self.ambulance["current_junction"] = new_route[0]
                    self.ambulance["current_segment_index"] = 0
                    if new_route[0] in self.junctions:
                        self.ambulance["position"] = dict(self.junctions[new_route[0]]["pos"])
                    if len(new_route) > 1:
                        self.ambulance["current_road"] = f"R_{new_route[0]}_{new_route[1]}"

    def step(self):
        """Advance physical simulation state by self.time_step seconds"""
        if not self.is_running:
            return

        self.simulation_time += self.time_step

        # 1. Update junction traffic signals & green timers
        for j_id, j in self.junctions.items():
            j["remaining_green"] -= self.time_step
            if j["remaining_green"] <= 0:
                if not j["priority_active"]:
                    # Toggle signal phase normally
                    j["signal_state"] = "GREEN_NS" if j["signal_state"] == "GREEN_EW" else "GREEN_EW"
                    j["remaining_green"] = 15.0

            # Incident effect on junction queue/speed
            road_affected = False
            for road_id, inc in self.active_incidents.items():
                if j_id in road_id:
                    road_affected = True
                    break

            if road_affected:
                j["queue_length"] = min(25, j["queue_length"] + random.choice([1, 2]))
                j["avg_speed"] = max(5.0, j["avg_speed"] - 2.0)
                j["congestion_level"] = "HIGH"
                j["lane_occupancy"] = 0.90
            else:
                # Normal fluctuations depending on traffic mode
                base_spawn = {"LOW": 0.1, "MEDIUM": 0.3, "HIGH": 0.6}[self.mode]
                if random.random() < base_spawn:
                    # Dissipate queue if signal green
                    if j["signal_state"] in ["GREEN_EW", "GREEN_NS", "PRIORITY"] and j["queue_length"] > 0:
                        j["queue_length"] = max(0, j["queue_length"] - 1)
                j["lane_occupancy"] = round(min(1.0, max(0.1, j["queue_length"] * 0.08)), 2)
                j["congestion_level"] = "HIGH" if j["queue_length"] > 10 else ("MEDIUM" if j["queue_length"] > 5 else "LOW")

        # 2. Update ambulance physical movement
        amb = self.ambulance
        if amb["active"] and not amb["has_arrived"]:
            route = amb["route"]
            seg_idx = amb["current_segment_index"]

            if seg_idx < len(route) - 1:
                curr_j_id = route[seg_idx]
                next_j_id = route[seg_idx + 1]
                road_key = f"R_{curr_j_id}_{next_j_id}"
                if road_key not in self.roads:
                    road_key = f"R_{next_j_id}_{curr_j_id}"

                road_len = self.roads.get(road_key, {}).get("length", 200.0)

                # Check downstream junction traffic condition & signal
                next_j = self.junctions[next_j_id]
                has_green_priority = (next_j["priority_active"] and self.orchestration_mode == "SWIFT") or (next_j["signal_state"] in ["GREEN_EW", "GREEN_NS"])

                # Incident impact on current road
                has_incident = road_key in self.active_incidents

                if has_incident and self.orchestration_mode == "BASELINE":
                    # In BASELINE mode, ambulance gets trapped in incident queue
                    max_speed = 10.0
                    queue_delay = 5.0
                elif has_incident and self.orchestration_mode == "SWIFT":
                    max_speed = 25.0
                    queue_delay = 2.0
                elif has_green_priority:
                    max_speed = 65.0
                    queue_delay = 0.0
                else:
                    max_speed = 20.0
                    queue_delay = 1.5

                # Adjust speed with smooth acceleration/deceleration
                if amb["speed"] < max_speed:
                    amb["speed"] = min(max_speed, amb["speed"] + 10.0 * self.time_step)
                elif amb["speed"] > max_speed:
                    amb["speed"] = max(max_speed, amb["speed"] - 15.0 * self.time_step)

                if amb["speed"] < 5.0:
                    if not amb["stopped_in_traffic"]:
                        amb["stopped_in_traffic"] = True
                        amb["stops_count"] += 1
                    amb["cumulative_waiting_time"] += self.time_step
                else:
                    amb["stopped_in_traffic"] = False

                # Distance covered in this step
                dist_step = (amb["speed"] * 1000.0 / 3600.0) * self.time_step
                progress_step = dist_step / road_len

                amb["route_progress"] += progress_step

                # Interpolate coordinate position
                p1 = self.junctions[curr_j_id]["pos"]
                p2 = self.junctions[next_j_id]["pos"]
                amb["position"]["x"] = round(p1["x"] + (p2["x"] - p1["x"]) * min(1.0, amb["route_progress"]), 2)
                amb["position"]["y"] = round(p1["y"] + (p2["y"] - p1["y"]) * min(1.0, amb["route_progress"]), 2)

                if amb["route_progress"] >= 1.0:
                    # Reached next junction
                    amb["current_junction"] = next_j_id
                    amb["current_segment_index"] += 1
                    amb["route_progress"] = 0.0
                    logger.info(f"AMBULANCE REACHED JUNCTION {next_j_id}")

                    if amb["current_segment_index"] >= len(route) - 1:
                        amb["has_arrived"] = True
                        amb["active"] = False
                        logger.info(f"AMBULANCE ARRIVED AT HOSPITAL! Total travel time: {self.simulation_time:.1f}s")
            else:
                amb["has_arrived"] = True
                amb["active"] = False

        # Step 25-node telemetry generator engine
        v_states = [{"id": "AMB_01", "x": amb["position"]["x"], "y": amb["position"]["y"], "speed": amb["speed"]}]
        telemetry_engine.step(v_states)

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns snapshot of current Webots field telemetry"""
        # Calculate ETA
        amb = self.ambulance
        remaining_dist = 0.0
        route = amb["route"]
        seg_idx = amb["current_segment_index"]

        for i in range(seg_idx, len(route) - 1):
            rk = f"R_{route[i]}_{route[i+1]}"
            if rk not in self.roads:
                rk = f"R_{route[i+1]}_{route[i]}"
            road_len = self.roads.get(rk, {}).get("length", 200.0)
            if i == seg_idx:
                remaining_dist += road_len * (1.0 - amb["route_progress"])
            else:
                remaining_dist += road_len

        eff_speed = max(10.0, amb["speed"])
        eta_seconds = round((remaining_dist / (eff_speed * 1000.0 / 3600.0)), 1) if not amb["has_arrived"] else 0.0

        nodes_25_payload = telemetry_engine.generate_payload()

        return {
            "timestamp": self.simulation_time,
            "mode": self.orchestration_mode,
            "junctions": self.junctions,
            "nodes_25": nodes_25_payload,
            "ambulance": {
                **amb,
                "eta_seconds": eta_seconds,
                "remaining_distance_m": round(remaining_dist, 1)
            },
            "incidents": self.active_incidents
        }
