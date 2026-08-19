"""
SWIFT SYSTEM - Dedicated Safety Validator Engine
Enforces hard safety constraints on all AI / Orchestration decisions before dispatching commands.
Rejects conflicting green phases, improper yellow clearance, or invalid signal transitions.
"""

from typing import Dict, List, Tuple, Any
import logging

logger = logging.getLogger("SafetyValidator")


class SafetyValidator:
    def __init__(self, min_green_sec: float = 3.0, yellow_sec: float = 3.0):
        self.min_green_sec = min_green_sec
        self.yellow_sec = yellow_sec
        self.valid_signal_states = {"GREEN_NS", "GREEN_EW", "YELLOW", "RED_ALL", "PRIORITY"}
        self.valid_junction_ids = {"J1", "J2", "J3", "J4"}

    def validate_signal_command(
        self,
        command: Dict[str, Any],
        current_junction_state: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validates a proposed junction signal command against hard safety constraints.
        Returns (is_valid, list_of_violation_reasons).
        """
        reasons = []
        junction_id = command.get("junction_id")
        proposed_state = command.get("signal_state")
        proposed_duration = command.get("green_duration", 0.0)

        # Rule 1: Valid Junction ID
        if junction_id not in self.valid_junction_ids:
            reasons.append(f"Invalid junction ID: {junction_id}")

        # Rule 2: Valid Signal State
        if proposed_state not in self.valid_signal_states:
            reasons.append(f"Invalid signal state requested: {proposed_state}")

        # Rule 3: Conflicting Green Signal Enforcement
        # Check if payload attempts dual green conflict
        if command.get("conflicting_green_override") is True:
            reasons.append("CRITICAL: Conflicting green directions requested simultaneously!")

        # Rule 4: Minimum Green / Yellow Clearance Duration
        if proposed_duration < self.min_green_sec:
            reasons.append(f"Requested duration {proposed_duration}s is less than minimum safe duration {self.min_green_sec}s")

        # Rule 5: Safe Phase Transition (Yellow Clearance Check)
        curr_state = current_junction_state.get("signal_state")
        if curr_state and curr_state != proposed_state and curr_state != "YELLOW" and proposed_state != "PRIORITY":
            rem_green = current_junction_state.get("remaining_green", 0.0)
            if rem_green > 10.0 and not command.get("priority"):
                reasons.append(f"Abrupt transition requested with {rem_green}s remaining without yellow clearance")

        is_valid = len(reasons) == 0
        if not is_valid:
            logger.warning(f"SAFETY VALIDATION FAILED for {junction_id}: {reasons}")
        else:
            logger.info(f"SAFETY VALIDATION PASSED for {junction_id}: {proposed_state}")

        return is_valid, reasons

    def validate_corridor_plan(
        self,
        corridor_plan: Dict[str, Dict[str, Any]],
        current_junctions: Dict[str, Dict[str, Any]]
    ) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Validates a multi-junction corridor plan.
        """
        overall_valid = True
        all_reasons = {}

        for j_id, cmd in corridor_plan.items():
            curr_state = current_junctions.get(j_id, {})
            valid, reasons = self.validate_signal_command(cmd, curr_state)
            if not valid:
                overall_valid = False
                all_reasons[j_id] = reasons

        return overall_valid, all_reasons


safety_validator = SafetyValidator()
