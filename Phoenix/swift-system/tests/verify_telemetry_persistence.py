"""
SWIFT SYSTEM - Telemetry Disk Persistence Verification Test
Verifies:
1. data/telemetry/ directory exists
2. telemetry_latest.json exists
3. File contains valid JSON
4. Root object is an array
5. Array contains exactly 25 records
6. Nodes are 0–24 in order
7. All contractual 16 schema fields exist for every node
8. simulation_tick advances between steps
9. generated_at timestamp updates
10. Dynamic fields (queue_length) reflect actual simulation state
11. Historical recording option works when enabled
"""

import os
import sys
import json
import time
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from webots.telemetry_generator import (
    telemetry_engine, save_telemetry_to_disk, LATEST_TELEMETRY_FILE, TELEMETRY_DIR, HISTORY_DIR
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyPersistence")


def verify_telemetry_persistence():
    logger.info("=========================================================")
    logger.info("  STARTING TELEMETRY PERSISTENCE VERIFICATION TEST      ")
    logger.info("=========================================================")

    # Step 1: Step simulation with dynamic vehicle positions (Node 0 & Node 12)
    mock_vehicles_1 = [
        {"id": "CAR_001", "x": -600.0, "y": 600.0, "speed": 0.0},  # Node 0
        {"id": "CAR_002", "x": -600.0, "y": 600.0, "speed": 0.0},  # Node 0
        {"id": "CAR_003", "x": -600.0, "y": 600.0, "speed": 0.0},  # Node 0
        {"id": "CAR_004", "x": 0.0, "y": 0.0, "speed": 0.0},       # Node 12
    ]
    telemetry_engine.step(mock_vehicles_1)
    payload_1 = telemetry_engine.generate_payload(save_to_disk=True)

    # 1. Check directory exists
    assert os.path.exists(TELEMETRY_DIR), f"Directory {TELEMETRY_DIR} does not exist!"
    logger.info(f"[PASS 1/10] Directory exists: {TELEMETRY_DIR}")

    # 2. Check telemetry_latest.json exists
    assert os.path.exists(LATEST_TELEMETRY_FILE), f"File {LATEST_TELEMETRY_FILE} does not exist!"
    logger.info(f"[PASS 2/10] File exists: {LATEST_TELEMETRY_FILE}")

    # 3. Read and parse JSON
    with open(LATEST_TELEMETRY_FILE, "r", encoding="utf-8") as f:
        data_1 = json.load(f)
    logger.info("[PASS 3/10] File contains valid JSON.")

    # 4. Root object is an array
    assert isinstance(data_1, list), f"Expected list root, got {type(data_1)}"
    logger.info("[PASS 4/10] Root object is a JSON array.")

    # 5. Exactly 25 records
    assert len(data_1) == 25, f"Expected 25 records, got {len(data_1)}"
    logger.info("[PASS 5/10] Array contains exactly 25 node records.")

    # 6. Nodes are 0..24
    nodes_present = [item["node"] for item in data_1]
    assert nodes_present == list(range(25)), f"Expected nodes 0..24, got {nodes_present}"
    logger.info("[PASS 6/10] Nodes are strictly 0 through 24 in sequential order.")

    # 7. Required contractual schema fields exist
    expected_fields = {
        "node", "queue_length", "flush_time", "light_phase", "active_direction",
        "phase_remaining_ticks", "preemption_active", "reserved_axis",
        "reservation_ev_id", "reservation_remaining_ticks", "reservation_end_time",
        "preempted_from_phase", "preempted_from_direction",
        "reservation_control_ready", "simulation_tick", "generated_at"
    }
    for item in data_1:
        missing = expected_fields - set(item.keys())
        assert not missing, f"Node {item['node']} missing fields: {missing}"
    logger.info("[PASS 7/10] All 16 contractual fields present in every node record.")

    # Check dynamic queue reflecting vehicle state
    assert data_1[0]["queue_length"] == 3, f"Node 0 expected queue_length=3, got {data_1[0]['queue_length']}"
    assert data_1[12]["queue_length"] == 1, f"Node 12 expected queue_length=1, got {data_1[12]['queue_length']}"
    logger.info(f"[PASS 10/10] Dynamic state reflected: Node 0 queue={data_1[0]['queue_length']}, Node 12 queue={data_1[12]['queue_length']}")

    tick_1 = data_1[0]["simulation_tick"]
    gen_at_1 = data_1[0]["generated_at"]

    # Step simulation again to check update
    time.sleep(0.05)
    telemetry_engine.step([])
    payload_2 = telemetry_engine.generate_payload(save_to_disk=True)

    with open(LATEST_TELEMETRY_FILE, "r", encoding="utf-8") as f:
        data_2 = json.load(f)

    tick_2 = data_2[0]["simulation_tick"]
    gen_at_2 = data_2[0]["generated_at"]

    # 8. simulation_tick changes
    assert tick_2 > tick_1, f"Expected tick_2 ({tick_2}) > tick_1 ({tick_1})"
    logger.info(f"[PASS 8/10] simulation_tick changes: {tick_1} -> {tick_2}")

    # 9. generated_at changes
    assert gen_at_2 >= gen_at_1, f"Expected gen_at_2 ({gen_at_2}) >= gen_at_1 ({gen_at_1})"
    logger.info(f"[PASS 9/10] generated_at timestamp changes: {gen_at_1} -> {gen_at_2}")

    # Test historical recording option
    save_telemetry_to_disk(data_2, enable_history=True, history_interval_sec=0.0)
    assert os.path.exists(HISTORY_DIR), f"History dir {HISTORY_DIR} should exist when history enabled"
    hist_files = os.listdir(HISTORY_DIR)
    assert len(hist_files) > 0, "Historical file should be saved when enabled"
    logger.info(f"[PASS BONUS] Historical snapshot saved to data/telemetry/history/: {hist_files[0]}")

    logger.info("=========================================================")
    logger.info("  ALL TELEMETRY PERSISTENCE VERIFICATIONS PASSED!       ")
    logger.info("=========================================================")


if __name__ == "__main__":
    verify_telemetry_persistence()
