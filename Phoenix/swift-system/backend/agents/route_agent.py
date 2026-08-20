"""
SWIFT SYSTEM - Route Agent
Constructs road network graph using NetworkX. Generates candidate ambulance routes
and computes multi-objective route cost based on distance, predicted queue, signals, and road closures.
"""

import networkx as nx
from typing import Dict, List, Any
import logging

logger = logging.getLogger("RouteAgent")


class RouteAgent:
    def __init__(self):
        self.graph = nx.DiGraph()
        self._build_initial_graph()

    def _build_initial_graph(self):
        self.graph.clear()
        # Add 4 grid junctions
        self.graph.add_node("J1", pos=(-100, -100))
        self.graph.add_node("J2", pos=(100, -100))
        self.graph.add_node("J3", pos=(-100, 100))
        self.graph.add_node("J4", pos=(100, 100))

        # Add road edges (bidirectional for ambulance access)
        edges = [
            ("J1", "J2", {"road_id": "R_J1_J2", "distance": 200.0, "speed_limit": 50.0}),
            ("J2", "J1", {"road_id": "R_J1_J2", "distance": 200.0, "speed_limit": 50.0}),
            ("J2", "J4", {"road_id": "R_J2_J4", "distance": 200.0, "speed_limit": 50.0}),
            ("J4", "J2", {"road_id": "R_J2_J4", "distance": 200.0, "speed_limit": 50.0}),
            ("J1", "J3", {"road_id": "R_J1_J3", "distance": 200.0, "speed_limit": 50.0}),
            ("J3", "J1", {"road_id": "R_J1_J3", "distance": 200.0, "speed_limit": 50.0}),
            ("J3", "J4", {"road_id": "R_J3_J4", "distance": 200.0, "speed_limit": 50.0}),
            ("J4", "J3", {"road_id": "R_J3_J4", "distance": 200.0, "speed_limit": 50.0}),
        ]
        for u, v, data in edges:
            self.graph.add_edge(u, v, **data)

    def generate_candidate_routes(
        self,
        start_junction: str,
        dest_junction: str,
        junction_states: Dict[str, Dict[str, Any]],
        predictions: Dict[str, Dict[str, Any]],
        incidents: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generates and ranks all candidate routes between start and dest junction.
        Calculates multi-objective cost for each route.
        """
        try:
            simple_paths = list(nx.all_simple_paths(self.graph, source=start_junction, target=dest_junction))
        except nx.NetworkXNoPath:
            return []

        candidates = []
        for path_idx, path in enumerate(simple_paths):
            total_dist = 0.0
            free_flow_time = 0.0
            congestion_delay = 0.0
            signal_delay = 0.0
            has_incident = False

            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                edge_data = self.graph[u][v]
                dist = edge_data["distance"]
                speed_kmh = edge_data["speed_limit"]

                total_dist += dist
                free_flow_time += (dist / (speed_kmh * 1000 / 3600))

                # Check road key for incident
                rk1 = f"R_{u}_{v}"
                rk2 = f"R_{v}_{u}"
                if rk1 in incidents or rk2 in incidents:
                    has_incident = True
                    congestion_delay += 120.0  # Massive 2-min penalty for incident road

                # Node congestion & predicted queue delay
                v_state = junction_states.get(v, {})
                v_pred = predictions.get(v, {})

                curr_q = v_state.get("queue_length", 0)
                pred_q = v_pred.get("predicted_queue", curr_q)

                # Queue delay: approx 3s per vehicle queued
                congestion_delay += (curr_q * 2.0 + pred_q * 1.5)

                # Signal delay if non-priority
                if not v_state.get("priority_active", False):
                    signal_delay += 5.0

            total_eta = free_flow_time + congestion_delay + signal_delay

            # Multi-objective composite cost score
            composite_score = total_eta + (1000.0 if has_incident else 0.0)

            candidates.append({
                "route_id": f"ROUTE_{chr(65 + path_idx)}",
                "path": path,
                "distance_meters": total_dist,
                "est_free_flow_time_sec": round(free_flow_time, 1),
                "est_congestion_delay_sec": round(congestion_delay, 1),
                "est_total_eta_sec": round(total_eta, 1),
                "has_incident": has_incident,
                "score": round(composite_score, 1)
            })

        # Sort candidate routes by lowest composite cost score
        candidates.sort(key=lambda c: c["score"])
        
        best_path_str = candidates[0]['path'] if candidates else "N/A"
        best_eta_str = candidates[0]['est_total_eta_sec'] if candidates else "N/A"
        logger.info(f"Generated {len(candidates)} candidate routes. Best: {best_path_str} (ETA: {best_eta_str}s)")

        logger.info(
            f"\n[ROUTE DEBUG]\n"
            f"current junction: {start_junction}\n"
            f"destination: {dest_junction}\n"
            f"available graph nodes: {list(self.graph.nodes())}\n"
            f"incidents: {list(incidents.keys())}\n"
            f"blocked nodes: []\n"
            f"candidate route count: {len(candidates)}\n"
            f"candidate routes: {candidates}\n"
        )

        return candidates


route_agent = RouteAgent()
