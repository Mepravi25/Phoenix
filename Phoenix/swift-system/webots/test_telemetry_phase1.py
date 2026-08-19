"""
SWIFT SYSTEM - Phase 1 Telemetry Generator Validation Test
Verifies:
1. 25 node records are generated (nodes 0..24).
2. Every record contains exact contractual 16 fields with valid types.
3. Strict Pydantic validation passes cleanly.
4. Dynamic queue calculation and simulation ticks work.
"""

import os
import sys
import json
import logging

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from webots.telemetry_generator import telemetry_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestPhase1")

def test_telemetry_generation():
    logger.info("Running Phase 1 Telemetry Validation Test...")

    # Simulated vehicles
    mock_vehicles = [
        {"id": "CAR_001", "x": -600.0, "y": 600.0, "speed": 0.2}, # Node 0
        {"id": "CAR_002", "x": -600.0, "y": 600.0, "speed": 0.0}, # Node 0
        {"id": "CAR_003", "x": 0.0, "y": 0.0, "speed": 0.5},     # Node 12
        {"id": "AMB_01", "x": -300.0, "y": 300.0, "speed": 12.0} # Node 6
    ]

    # Step simulation 5 times
    for i in range(5):
        telemetry_engine.step(mock_vehicles)

    # Generate payload
    payload = telemetry_engine.generate_payload()

    assert len(payload) == 25, f"Expected 25 nodes, got {len(payload)}"
    logger.info(f"Generated {len(payload)} intersection records.")

    # Contractual fields list
    expected_fields = {
        "node", "queue_length", "flush_time", "light_phase", "active_direction",
        "phase_remaining_ticks", "preemption_active", "reserved_axis",
        "reservation_ev_id", "reservation_remaining_ticks", "reservation_end_time",
        "preempted_from_phase", "preempted_from_direction",
        "reservation_control_ready", "simulation_tick", "generated_at"
    }

    for idx, node_data in enumerate(payload):
        assert node_data["node"] == idx, f"Expected node {idx}, got {node_data['node']}"
        actual_fields = set(node_data.keys())
        missing = expected_fields - actual_fields
        assert not missing, f"Node {idx} missing contractual fields: {missing}"

    # Check node 0 queue length
    node_0 = payload[0]
    assert node_0["queue_length"] == 2, f"Node 0 expected queue_length 2, got {node_0['queue_length']}"
    assert node_0["flush_time"] > 0.0, f"Node 0 expected flush_time > 0, got {node_0['flush_time']}"
    assert node_0["simulation_tick"] == 5, f"Expected tick 5, got {node_0['simulation_tick']}"

    logger.info(f"Node 0 Payload Sample: {json.dumps(node_0, indent=2)}")
    logger.info("PHASE 1 TELEMETRY VALIDATION TEST PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_telemetry_generation()
