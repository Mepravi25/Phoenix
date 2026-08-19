"""
SWIFT SYSTEM - Full End-to-End Pipeline Integration Test (Phases 1 - 5)
Tests:
1. 25-Node Telemetry Generation & Schema Validation
2. Telemetry ingestion API logic
3. Emergency request -> Hospital selection -> Route generation -> Green corridor
4. Chennai Government Hospitals evaluation
5. Full system live state with 25 active intersections
"""

import sys
import os
import json
import logging
import asyncio

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from webots.telemetry_generator import telemetry_engine
from backend.models.telemetry_schema import IntersectionTelemetry, EmergencyRequest
from backend.services.hospital_service import hospital_service
from backend.services.routing_service import routing_service
from backend.api.endpoints import (
    ingest_telemetry, handle_emergency_request, get_government_hospitals, get_full_system_state
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestPipeline")


async def run_async_tests():
    logger.info("=========================================================")
    logger.info("   STARTING SWIFT SYSTEM PIPELINE INTEGRATION TEST       ")
    logger.info("=========================================================")

    # Step 1: Generate 25-node Telemetry Payload
    telemetry_engine.step([{"id": "CAR_001", "x": -600.0, "y": 600.0, "speed": 0.0}])
    payload_dicts = telemetry_engine.generate_payload()
    assert len(payload_dicts) == 25, f"Expected 25 nodes, got {len(payload_dicts)}"
    logger.info("STEP 1 PASSED: 25-node telemetry generated successfully.")

    # Step 2: Test Telemetry Ingestion Endpoint Logic
    telemetry_models = [IntersectionTelemetry(**d) for d in payload_dicts]
    res_tel = await ingest_telemetry(telemetry_models)
    assert res_tel["status"] == "ACCEPTED"
    assert res_tel["count"] == 25
    logger.info("STEP 2 PASSED: Telemetry Ingestion accepted 25-node payload.")

    # Step 3: Test Government Hospitals Service & Endpoint
    hospitals = await get_government_hospitals(current_node=12)
    assert len(hospitals) >= 4, f"Expected at least 4 hospitals, got {len(hospitals)}"
    logger.info(f"STEP 3 PASSED: Retrieved Chennai Government Hospitals. Nearest: {hospitals[0]['name']}")

    # Step 4: Test Emergency Request & Green Corridor Route Authorization
    req = EmergencyRequest(
        event="EMERGENCY_REQUEST",
        ambulance_id="AMB_01",
        emergency_level="CRITICAL",
        current_node=12
    )
    decision = await handle_emergency_request(req)

    assert decision["status"] == "ROUTE_AUTHORIZED"
    assert decision["ambulance_id"] == "AMB_01"
    assert decision["selected_hospital"]["type"] == "Government"
    assert len(decision["route"]) > 0
    assert len(decision["signal_actions"]) == len(decision["route"])
    logger.info(f"STEP 4 PASSED: Decision Authorized. Selected Hospital: {decision['selected_hospital']['name']}")
    logger.info(f"Route: {decision['route']} | Signal Actions Count: {len(decision['signal_actions'])}")

    # Step 5: Test Full System Live State Endpoint
    state = await get_full_system_state()
    assert state["active_intersections"] == 25
    assert state["decision"] is not None
    assert state["decision"]["status"] == "ROUTE_AUTHORIZED"
    logger.info("STEP 5 PASSED: Full system live state verified with 25 active intersections.")

    logger.info("=========================================================")
    logger.info("   ALL PIPELINE INTEGRATION TESTS PASSED SUCCESSFULLY!   ")
    logger.info("=========================================================")


if __name__ == "__main__":
    asyncio.run(run_async_tests())
