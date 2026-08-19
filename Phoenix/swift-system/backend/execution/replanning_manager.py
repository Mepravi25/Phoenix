"""
SWIFT SYSTEM - Re-planning Manager
Continuously monitors traffic conditions, incidents, and ETA drift.
Triggers RE-PREDICT → RE-OPTIMIZE → RE-SIMULATE → RE-DECIDE loop when active route is impacted.
"""

from typing import Dict, Any, List
import logging

logger = logging.getLogger("ReplanningManager")


class ReplanningManager:
    def __init__(self):
        self.last_active_route: List[str] = []
        self.last_incident_count: int = 0

    def should_trigger_replan(
        self,
        current_route: List[str],
        incidents: Dict[str, Any],
        junctions: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Determines whether a dynamic re-planning event should be triggered.
        """
        # Trigger condition 1: Incident count changed
        if len(incidents) != self.last_incident_count:
            self.last_incident_count = len(incidents)
            return True, "Incidents updated in simulation"

        # Trigger condition 2: Incident directly on current route
        for i in range(len(current_route) - 1):
            u, v = current_route[i], current_route[i + 1]
            rk1 = f"R_{u}_{v}"
            rk2 = f"R_{v}_{u}"
            if rk1 in incidents or rk2 in incidents:
                return True, f"Active route {current_route} blocked by incident on {rk1}"

        # Trigger condition 3: Severe queue build-up on active route junction
        for j_id in current_route:
            q = junctions.get(j_id, {}).get("queue_length", 0)
            if q > 12:
                return True, f"Severe queue congestion ({q} veh) at junction {j_id}"

        return False, "Traffic nominal"


replanning_manager = ReplanningManager()
