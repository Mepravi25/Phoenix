"""
SWIFT SYSTEM - Command Dispatcher
Dispatches validated signal commands to physical Webots simulator controllers.
"""

from typing import Dict, Any
import logging

logger = logging.getLogger("CommandDispatcher")


class CommandDispatcher:
    def __init__(self):
        self.last_dispatched_commands = {}

    def dispatch(self, bridge: Any, corridor_commands: Dict[str, Dict[str, Any]]):
        """
        Dispatches validated signal commands to Webots simulation bridge.
        """
        for j_id, cmd in corridor_commands.items():
            bridge.apply_signal_command(j_id, cmd)
        self.last_dispatched_commands = corridor_commands
        logger.info(f"Dispatched {len(corridor_commands)} junction commands to Webots bridge.")


command_dispatcher = CommandDispatcher()
