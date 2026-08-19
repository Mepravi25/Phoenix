"""
SWIFT SYSTEM - 5x5 Grid Routing & Green Corridor Signal Preemption Engine
Generates optimal node route sequences and signal priority actions for emergency vehicles.
"""

from typing import List, Tuple, Dict, Any
from backend.models.telemetry_schema import SignalAction, CentralDecision, HospitalInfo


class RoutingService:
    def __init__(self, rows: int = 5, cols: int = 5):
        self.rows = rows
        self.cols = cols

    def _node_to_rc(self, node: int) -> Tuple[int, int]:
        return node // self.cols, node % self.cols

    def _rc_to_node(self, r: int, c: int) -> int:
        return r * self.cols + c

    def plan_route(self, start_node: int, target_node: int) -> List[int]:
        """
        Generates deterministic Manhattan grid path from start_node to target_node.
        """
        r1, c1 = self._node_to_rc(start_node)
        r2, c2 = self._node_to_rc(target_node)

        route = [start_node]
        curr_r, curr_c = r1, c1

        # Move horizontally first (east/west)
        step_c = 1 if c2 >= c1 else -1
        while curr_c != c2:
            curr_c += step_c
            route.append(self._rc_to_node(curr_r, curr_c))

        # Move vertically second (north/south)
        step_r = 1 if r2 >= r1 else -1
        while curr_r != r2:
            curr_r += step_r
            route.append(self._rc_to_node(curr_r, curr_c))

        return route

    def generate_signal_actions(self, route: List[int]) -> List[SignalAction]:
        """
        Determines target signal priority axis (NS or EW) for each intersection along the route.
        """
        actions = []
        if not route:
            return actions

        for i in range(len(route)):
            curr_node = route[i]
            if i < len(route) - 1:
                next_node = route[i + 1]
                r1, c1 = self._node_to_rc(curr_node)
                r2, c2 = self._node_to_rc(next_node)
                axis = "EW" if c1 != c2 else "NS"
            else:
                # Last node: use axis of previous step or default NS
                prev_node = route[i - 1] if i > 0 else curr_node
                r1, c1 = self._node_to_rc(prev_node)
                r2, c2 = self._node_to_rc(curr_node)
                axis = "EW" if c1 != c2 else "NS"

            actions.append(SignalAction(node=curr_node, axis=axis, action="GREEN_PRIORITY"))

        return actions

    def create_decision(self, ambulance_id: str, current_node: int, hospital: HospitalInfo) -> CentralDecision:
        """
        Builds complete CentralDecision output structure matching prompt requirements.
        """
        route = self.plan_route(current_node, hospital.node)
        signal_actions = self.generate_signal_actions(route)
        eta_minutes = max(3, len(route) * 2)

        return CentralDecision(
            status="ROUTE_AUTHORIZED",
            ambulance_id=ambulance_id,
            selected_hospital=hospital,
            route=route,
            estimated_time_minutes=eta_minutes,
            signal_actions=signal_actions
        )


routing_service = RoutingService()
