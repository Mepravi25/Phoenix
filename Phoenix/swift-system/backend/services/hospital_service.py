"""
SWIFT SYSTEM - Government Hospital Selection Service
Maintains real Chennai Government Hospitals dataset and evaluates the nearest suitable hospital
for an emergency ambulance based on simulation grid node distance.
"""

import math
from typing import List, Dict, Any, Optional
from backend.models.telemetry_schema import HospitalInfo

# Real Chennai Government Hospitals Dataset mapped to 5x5 simulation grid
CHENNAI_GOVT_HOSPITALS = [
    {
        "id": "GOVT_HOSP_01",
        "name": "Rajiv Gandhi Government General Hospital",
        "type": "Government",
        "node": 19,  # Row 3, Col 4
        "latitude": 13.0817,
        "longitude": 80.2778,
    },
    {
        "id": "GOVT_HOSP_02",
        "name": "Government Royapettah Hospital",
        "type": "Government",
        "node": 24,  # Row 4, Col 4
        "latitude": 13.0535,
        "longitude": 80.2621,
    },
    {
        "id": "GOVT_HOSP_03",
        "name": "Stanley Government Medical College Hospital",
        "type": "Government",
        "node": 4,   # Row 0, Col 4
        "latitude": 13.1070,
        "longitude": 80.2874,
    },
    {
        "id": "GOVT_HOSP_04",
        "name": "Government Kilpauk Medical College Hospital",
        "type": "Government",
        "node": 9,   # Row 1, Col 4
        "latitude": 13.0784,
        "longitude": 80.2427,
    }
]


class HospitalService:
    def __init__(self):
        self.hospitals = CHENNAI_GOVT_HOSPITALS

    def _calculate_node_distance_km(self, start_node: int, end_node: int) -> float:
        """Calculates Manhattan grid distance in kilometers (approx 0.8 km per grid cell)."""
        r1, c1 = start_node // 5, start_node % 5
        r2, c2 = end_node // 5, end_node % 5
        grid_dist = abs(r1 - r2) + abs(c1 - c2)
        return round(max(0.5, grid_dist * 0.8), 1)

    def get_all_hospitals(self, current_node: int = 0) -> List[HospitalInfo]:
        """Returns all government hospitals with evaluated distance from current_node."""
        results = []
        for h in self.hospitals:
            dist = self._calculate_node_distance_km(current_node, h["node"])
            info = HospitalInfo(
                id=h["id"],
                name=h["name"],
                type="Government",
                node=h["node"],
                latitude=h["latitude"],
                longitude=h["longitude"],
                distance_km=dist
            )
            results.append(info)
        return sorted(results, key=lambda x: x.distance_km)

    def select_nearest_hospital(self, current_node: int) -> HospitalInfo:
        """Evaluates and selects the nearest suitable government hospital."""
        evaluated = self.get_all_hospitals(current_node)
        return evaluated[0]


hospital_service = HospitalService()
