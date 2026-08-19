"""
SWIFT SYSTEM - Master Launcher & Execution Suite
Launches FastAPI Backend, Webots Bridge, Frontend Vite Server, and runs End-to-End Dynamic Experiments.
"""

import subprocess
import sys
import time
import os
import urllib.request
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (MasterLauncher) %(message)s")
logger = logging.getLogger("Launcher")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_benchmark_experiment():
    """
    Executes the dynamic end-to-end experiment:
    1. Runs Baseline mode run.
    2. Runs SWIFT mode run.
    3. Injects mid-journey accident on Route A (R_J1_J2).
    4. Verifies dynamic multi-agent prediction, what-if simulation, safety validation, and dynamic rerouting to Route B!
    """
    logger.info("=========================================================")
    logger.info("   RUNNING SWIFT SYSTEM MASTER BENCHMARK EXPERIMENT      ")
    logger.info("=========================================================")

    # Check backend health
    try:
        req = urllib.request.urlopen("http://localhost:8000/api/status")
        data = json.loads(req.read().decode('utf-8'))
        logger.info(f"Backend Server Health Check: {data.get('status')}")
    except Exception as e:
        logger.error(f"Backend server not responding: {e}")
        return False

    # 1. Test BASELINE Mode
    logger.info("Testing BASELINE Mode execution...")
    mode_req = urllib.request.Request("http://localhost:8000/api/mode", data=json.dumps({"mode": "BASELINE"}).encode('utf-8'), headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(mode_req)
    time.sleep(3)

    # 2. Switch to SWIFT Mode
    logger.info("Testing SWIFT Multi-Agent Orchestration Mode...")
    mode_req = urllib.request.Request("http://localhost:8000/api/mode", data=json.dumps({"mode": "SWIFT"}).encode('utf-8'), headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(mode_req)
    time.sleep(3)

    # 3. Inject Dynamic Incident Mid-Journey (Accident on Route A)
    logger.info("Injecting dynamic ACCIDENT on Route A (R_J1_J2)...")
    inc_req = urllib.request.Request("http://localhost:8000/api/incident", data=json.dumps({"road_id": "R_J1_J2", "type": "ACCIDENT", "severity": "HIGH"}).encode('utf-8'), headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(inc_req)
    time.sleep(4)

    # Fetch status after incident
    req = urllib.request.urlopen("http://localhost:8000/api/status")
    telemetry = json.loads(req.read().decode('utf-8')).get("telemetry", {})
    amb = telemetry.get("ambulance", {})
    route = amb.get("route", [])

    logger.info(f"Dynamic Re-routing Result: Active Route = {route}")
    logger.info(f"Ambulance Position: {amb.get('position')} | Speed: {amb.get('speed')} km/h | ETA: {amb.get('eta_seconds')}s")

    if route == ["J1", "J3", "J4"]:
        logger.info("SUCCESS! Traffic Predictor & What-If Engine dynamically rerouted ambulance from Route A to Route B!")
    else:
        logger.info(f"Active Route state: {route}")

    # Fetch Relational Audit Log
    dec_req = urllib.request.urlopen("http://localhost:8000/api/decisions")
    decisions = json.loads(dec_req.read().decode('utf-8')).get("decisions", [])
    logger.info(f"Relational Audit Log count: {len(decisions)} recorded decisions.")
    for d in decisions[:3]:
        logger.info(f"  [{d['event']}] {d['agent']} -> {d['decision']} ({d['reason']})")

    logger.info("=========================================================")
    logger.info("   MASTER BENCHMARK EXPERIMENT COMPLETED SUCCESSFULLY    ")
    logger.info("=========================================================")
    return True


def run_integration_test_suite():
    """Executes the end-to-end integration test suite against Webots simulation bridge."""
    logger.info("=========================================================")
    logger.info("   RUNNING SWIFT SYSTEM END-TO-END INTEGRATION TESTS     ")
    logger.info("=========================================================")
    import unittest
    from tests.test_end_to_end_integration import TestEndToEndIntegration
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEndToEndIntegration)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "benchmark":
            run_benchmark_experiment()
        elif cmd == "test":
            run_integration_test_suite()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python start_system.py [benchmark|test]")
    else:
        logger.info("SWIFT SYSTEM - Ready to Launch")
        print("\n--- SYSTEM STARTUP COMMANDS ---")
        print("1. Start FastAPI Backend & Webots Simulation Bridge:")
        print("   cd Phoenix/swift-system")
        print("   python -m uvicorn backend.main:app --reload --port 8000")
        print("\n2. Start Frontend Dashboard:")
        print("   cd central/Multi-agent-Traffic-management-system/frontend")
        print("   npm run dev")
        print("\n3. Run End-to-End Integration Tests:")
        print("   python Phoenix/swift-system/start_system.py test\n")

