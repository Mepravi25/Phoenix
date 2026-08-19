"""
Unit tests for SWIFT Route Agent, Predictor, and Optimizer
"""
import pytest
from backend.agents.route_agent import route_agent
from backend.prediction.traffic_predictor import traffic_predictor
from backend.optimization.optimizer import optimizer


def test_route_candidate_generation():
    junction_states = {
        "J1": {"queue_length": 2},
        "J2": {"queue_length": 4},
        "J3": {"queue_length": 1},
        "J4": {"queue_length": 3}
    }
    predictions = {
        "J1": {"predicted_queue": 2},
        "J2": {"predicted_queue": 5},
        "J3": {"predicted_queue": 1},
        "J4": {"predicted_queue": 3}
    }
    incidents = {}

    candidates = route_agent.generate_candidate_routes(
        start_junction="J1",
        dest_junction="J4",
        junction_states=junction_states,
        predictions=predictions,
        incidents=incidents
    )
    assert len(candidates) >= 2
    paths = [c["path"] for c in candidates]
    assert ["J1", "J2", "J4"] in paths
    assert ["J1", "J3", "J4"] in paths


test_route_candidate_generation()


def test_incident_rerouting():
    junction_states = {j: {"queue_length": 2} for j in ["J1", "J2", "J3", "J4"]}
    predictions = {j: {"predicted_queue": 2} for j in ["J1", "J2", "J3", "J4"]}
    # Inject accident on Route A (R_J1_J2)
    incidents = {"R_J1_J2": {"type": "ACCIDENT", "severity": "HIGH"}}

    candidates = route_agent.generate_candidate_routes(
        start_junction="J1",
        dest_junction="J4",
        junction_states=junction_states,
        predictions=predictions,
        incidents=incidents
    )
    assert len(candidates) >= 2
    # Best route should now be Route B (J1 -> J3 -> J4)
    assert candidates[0]["path"] == ["J1", "J3", "J4"]


test_incident_rerouting()


def test_traffic_prediction():
    curr_state = {"queue_length": 5, "signal_state": "GREEN_NS"}
    pred = traffic_predictor.predict_junction("J1", curr_state, horizon_seconds=30.0)
    assert pred["junction_id"] == "J1"
    assert "predicted_queue" in pred
    assert pred["predicted_congestion"] in ["LOW", "MEDIUM", "HIGH"]


test_traffic_prediction()
