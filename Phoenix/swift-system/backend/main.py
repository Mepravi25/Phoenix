"""
SWIFT SYSTEM - Central FastAPI Server Entrypoint
Integrates Data Ingestion, Multi-Agent Orchestration, Predictor, Optimizer, Safety Validator,
WebSocket real-time Hub, and REST API Services.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging
import json

from webots.simulator_bridge import SwiftWebotsSimulator
from backend.agents.orchestration_agent import orchestration_agent
from backend.execution.command_dispatcher import command_dispatcher
from backend.execution.replanning_manager import replanning_manager
from backend.websocket.ws_manager import ws_manager
from backend.api.endpoints import router as api_router, set_sim_bridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (Backend) %(message)s")
logger = logging.getLogger("SwiftServer")

# Global simulation instance
sim_bridge = SwiftWebotsSimulator(mode="MEDIUM")
set_sim_bridge(sim_bridge)

# Background orchestration task reference
orchestration_task = None


async def run_orchestration_loop():
    """Background task executing the continuous field-predict-optimize-orchestrate-execute loop"""
    logger.info("Starting background SWIFT Orchestration Loop...")
    while True:
        try:
            # 1. Step physical simulation
            sim_bridge.step()
            telemetry = sim_bridge.get_telemetry()
            
            # Sync 25-node telemetry array to API store
            from backend.api.endpoints import latest_decision
            if "nodes_25" in telemetry:
                import backend.api.endpoints as api_endpoints
                api_endpoints.latest_telemetry = telemetry["nodes_25"]

            # 2. Check if replanning triggered
            should_replan, replan_reason = replanning_manager.should_trigger_replan(
                current_route=sim_bridge.ambulance["route"],
                incidents=sim_bridge.active_incidents,
                junctions=sim_bridge.junctions
            )

            # 3. Run multi-agent orchestrator loop
            orch_result = orchestration_agent.orchestrate(telemetry)

            # Update ambulance route if orchestrator switched path
            new_route = orch_result.get("active_route")
            if new_route:
                sim_bridge.update_ambulance_route(new_route)

            # 4. Dispatch signal commands to Webots junction controllers
            corridor_cmds = orch_result.get("corridor_commands")
            if corridor_cmds:
                command_dispatcher.dispatch(sim_bridge, corridor_cmds)

            # 5. Broadcast complete real-time telemetry frame to WebSocket clients
            frame = {
                "type": "TELEMETRY",
                "telemetry": telemetry,
                "orchestration": orch_result,
                "decision": latest_decision.model_dump() if latest_decision else None
            }
            await ws_manager.broadcast(frame)

            await asyncio.sleep(0.5)  # 2 Hz update rate
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in orchestration loop: {e}", exc_info=True)
            await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestration_task
    logger.info("Starting SWIFT System Central Server...")
    orchestration_task = asyncio.create_task(run_orchestration_loop())
    yield
    logger.info("Shutting down SWIFT System Central Server...")
    if orchestration_task:
        orchestration_task.cancel()


app = FastAPI(
    title="SWIFT SYSTEM - Emergency Traffic Orchestration Central Server",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "system": "SWIFT SYSTEM",
        "version": "1.0.0",
        "description": "Predictive Multi-Agent Emergency Traffic Orchestration System",
        "status": "ONLINE"
    }


@app.post("/login")
async def root_login():
    return {
        "access_token": "swift_demo_token_12345",
        "token_type": "bearer"
    }


@app.post("/register")
async def root_register():
    return {
        "access_token": "swift_demo_token_12345",
        "token_type": "bearer"
    }


@app.websocket("/ws")
@app.websocket("/ws/traffic")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming WebSocket commands from dashboard or Webots
            try:
                msg = json.loads(data)
                cmd_type = msg.get("type")
                if cmd_type == "TOGGLE_MODE":
                    sim_bridge.set_orchestration_mode(msg.get("mode", "SWIFT"))
                elif cmd_type == "INJECT_INCIDENT":
                    sim_bridge.inject_incident(msg.get("road_id", "R_J1_J2"))
                elif cmd_type == "CLEAR_INCIDENTS":
                    sim_bridge.clear_incidents()
            except Exception as parse_err:
                logger.warning(f"Malformed WS payload received: {parse_err}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

