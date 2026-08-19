"""
SWIFT SYSTEM - Traffic Agent
Monitors all junctions, analyzes queue build-up, speed drops, traffic density, and flags bottlenecks.
"""

from typing import Dict, List, Any
import logging

logger = logging.getLogger("TrafficAgent")


class TrafficAgent:
    def __init__(self):
        self.last_junction_states: Dict[str, Dict[str, Any]] = {}

    def analyze_traffic(
        self,
        raw_junctions: Dict[str, Dict[str, Any]],
        incidents: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyzes field telemetry and outputs standardized junction insights.
        """
        junction_insights = {}
        congested_junctions = []

        for j_id, j_data in raw_junctions.items():
            queue = j_data.get("queue_length", 0)
            avg_speed = j_data.get("avg_speed", 40.0)

            # Check if junction connected road has incident
            has_incident = any(j_id in road_id for road_id in incidents.keys())

            if queue > 8 or has_incident:
                congestion = "HIGH"
                congested_junctions.append(j_id)
            elif queue > 4:
                congestion = "MEDIUM"
            else:
                congestion = "LOW"

            junction_insights[j_id] = {
                **j_data,
                "congestion_level": congestion,
                "has_incident": has_incident
            }

        self.last_junction_states = junction_insights

        return {
            "junctions": junction_insights,
            "congested_count": len(congested_junctions),
            "congested_junctions": congested_junctions,
            "has_active_incidents": len(incidents) > 0
        }


traffic_agent = TrafficAgent()
