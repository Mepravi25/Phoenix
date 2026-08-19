"""
SWIFT SYSTEM - Multi-Objective Optimization Engine
Ranks strategy candidates combining route selection and signal corridor plans.
Minimizes emergency ETA and traffic disruption while maximizing emergency priority.
"""

from typing import Dict, List, Any
import logging

logger = logging.getLogger("Optimizer")


class StrategyOptimizer:
    def __init__(
        self,
        w_eta: float = 1.5,
        w_congestion: float = 0.8,
        w_disruption: float = 0.5,
        w_signal: float = 0.4,
        w_priority: float = 2.0
    ):
        self.w_eta = w_eta
        self.w_congestion = w_congestion
        self.w_disruption = w_disruption
        self.w_signal = w_signal
        self.w_priority = w_priority

    def evaluate_strategy(
        self,
        candidate_route: Dict[str, Any],
        signal_plan: Dict[str, str],
        urgency_level: str = "LEVEL_3"
    ) -> Dict[str, Any]:
        """
        Computes composite cost for a route + signal strategy pair.
        """
        eta = candidate_route.get("est_total_eta_sec", 60.0)

        # Estimate disruption to normal traffic from priority holds
        priority_junctions_count = sum(1 for mode in signal_plan.values() if mode == "PRIORITY")
        traffic_disruption = priority_junctions_count * 15.0

        # Urgency multiplier
        priority_weight = {"LEVEL_1": 1.0, "LEVEL_2": 2.5, "LEVEL_3": 5.0}.get(urgency_level, 3.0)

        # Incident penalty
        incident_penalty = 500.0 if candidate_route.get("has_incident", False) else 0.0

        cost = (
            self.w_eta * eta
            + self.w_congestion * candidate_route.get("est_congestion_delay_sec", 0.0)
            + self.w_disruption * traffic_disruption
            + self.w_signal * (len(candidate_route.get("path", [])) * 3.0)
            - self.w_priority * (priority_weight * 10.0)
            + incident_penalty
        )

        return {
            "strategy_id": f"STRAT_{candidate_route.get('route_id')}",
            "route": candidate_route.get("path", []),
            "estimated_eta": round(eta, 1),
            "congestion_cost": round(candidate_route.get("est_congestion_delay_sec", 0.0), 1),
            "disruption_cost": round(traffic_disruption, 1),
            "signal_delay": round(len(candidate_route.get("path", [])) * 3.0, 1),
            "incident_penalty": incident_penalty,
            "composite_cost": round(cost, 1),
            "corridor_plan": signal_plan
        }


optimizer = StrategyOptimizer()
