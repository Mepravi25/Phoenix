"""
SWIFT SYSTEM - Orchestration Agent
Central coordinator managing end-to-end multi-agent orchestration workflow:
TRAFFIC → PREDICT → ROUTE → OPTIMIZE → WHAT-IF SIMULATE → SAFETY VALIDATE → EXECUTE → RE-PLAN
"""

from typing import Dict, List, Any
import logging

from backend.agents.traffic_agent import traffic_agent
from backend.agents.route_agent import route_agent
from backend.prediction.traffic_predictor import traffic_predictor
from backend.optimization.optimizer import optimizer
from backend.what_if.simulator import what_if_simulator
from backend.safety.safety_validator import safety_validator
from backend.storage.relational_db import relational_db

logger = logging.getLogger("OrchestrationAgent")


class OrchestrationAgent:
    def __init__(self):
        self.active_route: List[str] = ["J1", "J2", "J4"]
        self.active_corridor_plan: Dict[str, str] = {}
        self.last_decision_reason: str = "Initialization"

    def orchestrate(
        self,
        telemetry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Main orchestration loop execution step.
        """
        mode = telemetry.get("mode", "SWIFT")
        raw_junctions = telemetry.get("junctions", {})
        ambulance = telemetry.get("ambulance", {})
        incidents = telemetry.get("incidents", {})

        if mode == "BASELINE":
            # Baseline Mode: static route, default signals, no green corridor
            default_route = ["J1", "J2", "J4"]
            self.active_route = default_route
            corridor_plan = {j_id: "NORMAL" for j_id in raw_junctions.keys()}
            return {
                "mode": "BASELINE",
                "active_route": default_route,
                "corridor_plan": corridor_plan,
                "decision_reason": "Baseline mode active (no prediction or green corridor)",
                "safety_passed": True
            }

        # --- SWIFT MULTI-AGENT WORKFLOW ---

        # Step 1: Traffic Monitoring
        traffic_insights = traffic_agent.analyze_traffic(raw_junctions, incidents)

        # Step 2: Prediction Engine
        predictions = {}
        for j_id, j_state in raw_junctions.items():
            has_inc = any(j_id in road_id for road_id in incidents.keys())
            pred = traffic_predictor.predict_junction(j_id, j_state, horizon_seconds=30.0, incident_present=has_inc)
            predictions[j_id] = pred

        # Step 3: Route Candidate Generation
        curr_j = ambulance.get("current_junction", "J1")
        dest_j = ambulance.get("dest_junction", "J4")

        candidate_routes = route_agent.generate_candidate_routes(
            start_junction=curr_j,
            dest_junction=dest_j,
            junction_states=raw_junctions,
            predictions=predictions,
            incidents=incidents
        )

        if not candidate_routes:
            candidate_routes = [{
                "route_id": "ROUTE_FALLBACK",
                "path": [curr_j, dest_j],
                "distance_meters": 400.0,
                "est_free_flow_time_sec": 30.0,
                "est_congestion_delay_sec": 0.0,
                "est_total_eta_sec": 30.0,
                "has_incident": False,
                "score": 30.0
            }]

        # Step 4: What-If Analytical Simulation Engine
        what_if_results = what_if_simulator.simulate_strategies(
            candidate_routes=candidate_routes,
            junction_states=raw_junctions,
            predictions=predictions,
            urgency_level=ambulance.get("urgency_level", "LEVEL_3")
        )

        best_strategy = what_if_results[0]
        selected_route = best_strategy["path"]
        raw_signal_plan = best_strategy["signal_plan"]

        # Step 5: Construct Dynamic Green Corridor Commands
        corridor_commands = {}
        for j_id in raw_junctions.keys():
            if j_id in selected_route:
                if j_id == curr_j or (len(selected_route) > 1 and j_id == selected_route[1]):
                    cmd = {
                        "junction_id": j_id,
                        "signal_state": "GREEN_EW" if j_id in ["J1", "J3"] else "GREEN_NS",
                        "green_duration": 20.0,
                        "priority": True
                    }
                else:
                    cmd = {
                        "junction_id": j_id,
                        "signal_state": "GREEN_EW" if j_id in ["J1", "J3"] else "GREEN_NS",
                        "green_duration": 15.0,
                        "priority": True
                    }
            else:
                cmd = {
                    "junction_id": j_id,
                    "signal_state": raw_junctions[j_id]["signal_state"],
                    "green_duration": 15.0,
                    "priority": False
                }
            corridor_commands[j_id] = cmd

        # Step 6: Dedicated Safety Validation
        safety_passed, safety_reasons = safety_validator.validate_corridor_plan(corridor_commands, raw_junctions)

        if not safety_passed:
            logger.warning(f"Safety validator rejected plan! Falling back to safe cycles. Reasons: {safety_reasons}")
            decision_reason = f"Safety Override Triggered: {safety_reasons}"
            corridor_plan = {j_id: "NORMAL" for j_id in raw_junctions.keys()}
        else:
            self.active_route = selected_route
            corridor_plan = {j_id: ("PRIORITY" if j_id in selected_route else "NORMAL") for j_id in raw_junctions.keys()}
            self.active_corridor_plan = corridor_plan
            decision_reason = f"Selected {best_strategy['strategy_name']} (ETA: {best_strategy['simulated_eta_sec']}s) via {selected_route}"

        self.last_decision_reason = decision_reason

        # Log decision in relational audit database
        relational_db.log_decision(
            agent="OrchestrationAgent",
            event="DYNAMIC_ORCHESTRATION",
            junction=curr_j,
            decision=f"ROUTE={selected_route}",
            reason=decision_reason
        )

        return {
            "mode": "SWIFT",
            "active_route": selected_route,
            "corridor_plan": corridor_plan,
            "corridor_commands": corridor_commands,
            "decision_reason": decision_reason,
            "safety_passed": safety_passed,
            "predictions": predictions,
            "what_if_top_3": what_if_results[:3]
        }


orchestration_agent = OrchestrationAgent()
