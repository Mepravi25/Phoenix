"""
SWIFT SYSTEM - WebSocket Communication Hub
Handles real-time bi-directional messaging between Python Server, Webots bridge, and Frontend Dashboard.
"""

from fastapi import WebSocket
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger("WebSocketManager")


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        payload = json.dumps(message)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.error(f"Error broadcasting WS message: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)


ws_manager = ConnectionManager()
