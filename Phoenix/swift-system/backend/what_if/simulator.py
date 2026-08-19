"""
SWIFT SYSTEM - What-If Simulation Engine
Evaluates multiple strategy combinations (Route + Signal Plan) analytically prior to physical execution.
Forecasts ambulance ETA, queue impact, disruption score, and safety compliance.
"""

from typing import Dict, List, Any
import logging

logger = logging.getLogger("WhatIfSimulator")


class WhatIfSimulator:
    def __init__(self):
        pass

    def simulate_strategies(
        self,
        candidate_routes: List[Dict[str, Any]],
        junction_states: Dict[str, Dict[str, Any]],
        predictions: Dict[str, Dict[str, Any]],
        urgency_level: str = "LEVEL_3"
    ) -> List[Dict[str, Any]]:
        """
        Runs fast analytical What-If simulations for each route with matching signal strategies.
        """
        results = []

        for route in candidate_routes:
            path = route.get("path", [])
            # Option 1: Full Green Corridor Strategy for this route
            plan_full_corridor = {}
            for j_id in junction_states.keys():
                if j_id in path:
                    plan_full_corridor[j_id] = "PRIORITY"
                else:
                    plan_full_corridor[j_id] = "NORMAL"

            # Option 2: Partial/Standard Signal Plan Strategy
            plan_standard = {j_id: "NORMAL" for j_id in junction_states.keys()}

            for strat_name, signal_plan in [("GREEN_CORRIDOR", plan_full_corridor), ("STANDARD_CYCLES", plan_standard)]:
                eta = route.get("est_free_flow_time_sec", 30.0)
                queue_impact = 0.0

                for node in path:
                    curr_q = junction_states.get(node, {}).get("queue_length", 0)
                    pred_q = predictions.get(node, {}).get("predicted_queue", curr_q)

                    if signal_plan.get(node) == "PRIORITY":
                        # Green corridor clears queue rapidly
                        queue_impact += max(0, curr_q - 5)
                        eta += 2.0  # minimal junction slowdown
                    else:
                        queue_impact += curr_q
                        eta += (curr_q * 2.5 + pred_q * 1.5)

                disruption_score = sum(15.0 for mode in signal_plan.values() if mode == "PRIORITY")
                if route.get("has_incident", False):
                    eta += 120.0  # incident delay penalty

                composite_score = eta + disruption_score * 0.5

                results.append({
                    "strategy_name": f"{route.get('route_id')}_{strat_name}",
                    "route_id": route.get("route_id"),
                    "path": path,
                    "signal_plan": signal_plan,
                    "simulated_eta_sec": round(eta, 1),
                    "simulated_queue_impact": round(queue_impact, 1),
                    "disruption_score": round(disruption_score, 1),
                    "composite_score": round(composite_score, 1),
                    "has_incident": route.get("has_incident", False)
                })

        # Rank candidates by lowest composite score
        results.sort(key=lambda r: r["composite_score"])
        logger.info(f"What-If Simulation evaluated {len(results)} candidate strategies. Winner: {results[0]['strategy_name']} (ETA: {results[0]['simulated_eta_sec']}s)")

        return results


what_if_simulator = WhatIfSimulator()
