"""
SWIFT SYSTEM - Webots Junction Controller
Module 2: Reusable Realistic Traffic Signal Controller System.

Controls 4-approach traffic light signals (NORTH, SOUTH, EAST, WEST) per intersection
with safety phase transitions, configurable timing, and future emergency priority interfaces.
"""

import sys
import math
import logging
from enum import Enum, auto
from typing import Dict, Optional, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (JunctionController) %(message)s")
logger = logging.getLogger("JunctionController")

try:
    from controller import Robot, LED
    WEBOTS_AVAILABLE = True
except ImportError:
    WEBOTS_AVAILABLE = False


class LampState(Enum):
    RED = 0
    YELLOW = 1
    GREEN = 2
    ALL_OFF = 3


class SignalPhase(Enum):
    NS_GREEN = 1
    NS_YELLOW = 2
    ALL_RED_NS_TO_EW = 3
    EW_GREEN = 4
    EW_YELLOW = 5
    ALL_RED_EW_TO_NS = 6
    EMERGENCY_OVERRIDE = 7


class Approach(Enum):
    NORTH = "NORTH"
    SOUTH = "SOUTH"
    EAST = "EAST"
    WEST = "WEST"


# Centralized Signal Timing Configuration
SIGNAL_CONFIG = {
    "green_duration": 15.0,     # seconds
    "yellow_duration": 3.0,     # seconds
    "all_red_duration": 1.0     # seconds
}


class ApproachSignalHead:
    """
    Manages the 3 physical LED lamps (RED, YELLOW, GREEN) for a single approach direction.
    """
    def __init__(self, junction_id: str, approach: Approach, robot: Optional[Any] = None):
        self.junction_id = junction_id
        self.approach = approach
        self.robot = robot
        self.current_state = LampState.RED

        self.led_red = None
        self.led_yellow = None
        self.led_green = None

        if self.robot and WEBOTS_AVAILABLE:
            app_str = approach.value
            # Try junction-prefixed device name first, then fallback to relative name
            names_red = [f"{junction_id}_{app_str}_RED", f"{app_str}_RED"]
            names_yellow = [f"{junction_id}_{app_str}_YELLOW", f"{app_str}_YELLOW"]
            names_green = [f"{junction_id}_{app_str}_GREEN", f"{app_str}_GREEN"]

            self.led_red = self._get_device(names_red)
            self.led_yellow = self._get_device(names_yellow)
            self.led_green = self._get_device(names_green)

        # Initialize to RED state
        self.set_state(LampState.RED)

    def _get_device(self, candidate_names: list) -> Optional[Any]:
        for name in candidate_names:
            try:
                device = self.robot.getDevice(name)
                if device is not None:
                    return device
            except Exception:
                pass
        return None

    def set_state(self, state: LampState):
        self.current_state = state
        red_val = 1 if state == LampState.RED else 0
        yellow_val = 1 if state == LampState.YELLOW else 0
        green_val = 1 if state == LampState.GREEN else 0

        if self.led_red:
            self.led_red.set(red_val)
        if self.led_yellow:
            self.led_yellow.set(yellow_val)
        if self.led_green:
            self.led_green.set(green_val)


import os
import json

STATE_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "traffic_signal_states.json")
EMERGENCY_REQUESTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "emergency_requests.json")
SHARED_EMERGENCY_REQUESTS: Dict[str, dict] = {}


class IntersectionController:
    """
    Reusable 4-approach Traffic Signal Controller for a single intersection.
    Controls signal phases, handles safe transitions, and provides emergency override hooks.
    """
    def __init__(self, junction_id: str = "J1", robot: Optional[Any] = None, config: Optional[dict] = None):
        self.junction_id = junction_id
        self.robot = robot
        self.config = config or SIGNAL_CONFIG

        self.time_step = int(self.robot.getBasicTimeStep()) if (self.robot and WEBOTS_AVAILABLE) else 32
        
        # Initialize 4 approach signals
        self.signals: Dict[Approach, ApproachSignalHead] = {
            Approach.NORTH: ApproachSignalHead(junction_id, Approach.NORTH, robot),
            Approach.SOUTH: ApproachSignalHead(junction_id, Approach.SOUTH, robot),
            Approach.EAST: ApproachSignalHead(junction_id, Approach.EAST, robot),
            Approach.WEST: ApproachSignalHead(junction_id, Approach.WEST, robot),
        }

        self.current_phase = SignalPhase.NS_GREEN
        self.last_phase: Optional[SignalPhase] = None
        self.phase_elapsed_time = 0.0

        # Emergency priority override interface state
        self.priority_active = False
        self.priority_direction: Optional[str] = None
        self.priority_remaining_time = 0.0

        # Module 5A J1 Emergency Priority State Machine
        self.emergency_state: str = "IDLE"  # "IDLE", "INIT", "CLEARING", "ALL_RED", "GREEN", "RESTORE_YELLOW", "RESTORE_ALL_RED"
        self.emergency_request: Optional[dict] = None
        self.emergency_timer: float = 0.0
        self.max_emergency_green: float = 8.0  # Section 15: MAX_EMERGENCY_GREEN = 8 seconds
        self.ambulance_entered_j1: bool = False
        self.ambulance_cleared_j1: bool = False
        self.signal_conflicts_count: int = 0

        self._apply_phase_lamps(self.current_phase)
        self._export_signal_state()
        logger.info(f"[{self.junction_id}] IntersectionController initialized. Initial Phase: {self.current_phase.name}")

    def _export_signal_state(self):
        try:
            data = {}
            if os.path.exists(STATE_FILE_PATH):
                try:
                    with open(STATE_FILE_PATH, "r") as f:
                        data = json.load(f)
                except Exception:
                    data = {}

            data[self.junction_id] = {
                app.value: self.signals[app].current_state.name
                for app in Approach
            }

            tmp_path = STATE_FILE_PATH + f".{self.junction_id}.tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f)
            os.replace(tmp_path, STATE_FILE_PATH)
        except Exception:
            pass

    def request_priority(self, direction: str, duration: float = 20.0) -> bool:
        """
        Future Emergency Priority Override Interface.
        Called by future ambulance orchestration modules to grant green corridor.
        """
        logger.info(f"[{self.junction_id}] Emergency priority requested for direction '{direction}' (duration: {duration}s)")
        self.priority_direction = direction.upper()
        self.priority_active = True
        self.priority_remaining_time = duration
        self.current_phase = SignalPhase.EMERGENCY_OVERRIDE
        self._apply_emergency_lamps(self.priority_direction)
        return True

    def clear_priority(self):
        """
        Clears emergency priority override and resumes normal signal cycle.
        """
        logger.info(f"[{self.junction_id}] Emergency priority cleared. Resuming normal cycle.")
        self.priority_active = False
        self.priority_direction = None
        self.priority_remaining_time = 0.0
        self.current_phase = SignalPhase.ALL_RED_NS_TO_EW
        self.phase_elapsed_time = 0.0
        self._apply_phase_lamps(self.current_phase)

    def _log_phase_transition(self, phase: SignalPhase):
        if phase == self.last_phase:
            return
        self.last_phase = phase
        phase_str = "ALL_RED" if phase in (SignalPhase.ALL_RED_NS_TO_EW, SignalPhase.ALL_RED_EW_TO_NS) else phase.name
        
        ns_lamp = self.signals[Approach.NORTH].current_state.name
        ew_lamp = self.signals[Approach.EAST].current_state.name
        
        print(f"[{self.junction_id}] NORMAL_PHASE={phase_str}", flush=True)
        print(f"[{self.junction_id}] PHASE {phase_str}", flush=True)
        print(f"[{self.junction_id}] NS = {ns_lamp} | EW = {ew_lamp}", flush=True)

    def _validate_safety(self):
        ns_green = (self.signals[Approach.NORTH].current_state == LampState.GREEN or 
                    self.signals[Approach.SOUTH].current_state == LampState.GREEN)
        ew_green = (self.signals[Approach.EAST].current_state == LampState.GREEN or 
                    self.signals[Approach.WEST].current_state == LampState.GREEN)
        if ns_green and ew_green:
            self.signal_conflicts_count += 1
            print(f"[{self.junction_id}_SIGNAL_CONFLICT_ERROR]", flush=True)
            print(f"[{self.junction_id}] ERROR: Safety conflict detected! Both NS and EW are GREEN. Forcing ALL RED.", flush=True)
            self.signals[Approach.NORTH].set_state(LampState.RED)
            self.signals[Approach.SOUTH].set_state(LampState.RED)
            self.signals[Approach.EAST].set_state(LampState.RED)
            self.signals[Approach.WEST].set_state(LampState.RED)

    def _apply_phase_lamps(self, phase: SignalPhase):
        if phase == SignalPhase.NS_GREEN:
            self.signals[Approach.NORTH].set_state(LampState.GREEN)
            self.signals[Approach.SOUTH].set_state(LampState.GREEN)
            self.signals[Approach.EAST].set_state(LampState.RED)
            self.signals[Approach.WEST].set_state(LampState.RED)
        elif phase == SignalPhase.NS_YELLOW:
            self.signals[Approach.NORTH].set_state(LampState.YELLOW)
            self.signals[Approach.SOUTH].set_state(LampState.YELLOW)
            self.signals[Approach.EAST].set_state(LampState.RED)
            self.signals[Approach.WEST].set_state(LampState.RED)
        elif phase in (SignalPhase.ALL_RED_NS_TO_EW, SignalPhase.ALL_RED_EW_TO_NS):
            self.signals[Approach.NORTH].set_state(LampState.RED)
            self.signals[Approach.SOUTH].set_state(LampState.RED)
            self.signals[Approach.EAST].set_state(LampState.RED)
            self.signals[Approach.WEST].set_state(LampState.RED)
        elif phase == SignalPhase.EW_GREEN:
            self.signals[Approach.NORTH].set_state(LampState.RED)
            self.signals[Approach.SOUTH].set_state(LampState.RED)
            self.signals[Approach.EAST].set_state(LampState.GREEN)
            self.signals[Approach.WEST].set_state(LampState.GREEN)
        elif phase == SignalPhase.EW_YELLOW:
            self.signals[Approach.NORTH].set_state(LampState.RED)
            self.signals[Approach.SOUTH].set_state(LampState.RED)
            self.signals[Approach.EAST].set_state(LampState.YELLOW)
            self.signals[Approach.WEST].set_state(LampState.YELLOW)
            
        self._validate_safety()
        self._log_phase_transition(phase)
        self._export_signal_state()

    def _apply_emergency_lamps(self, priority_dir: Optional[str]):
        # Default all RED
        for app in Approach:
            self.signals[app].set_state(LampState.RED)

        if priority_dir in ("NORTH", "SOUTH", "NS"):
            self.signals[Approach.NORTH].set_state(LampState.GREEN)
            self.signals[Approach.SOUTH].set_state(LampState.GREEN)
        elif priority_dir in ("EAST", "WEST", "EW"):
            self.signals[Approach.EAST].set_state(LampState.GREEN)
            self.signals[Approach.WEST].set_state(LampState.GREEN)

        self._validate_safety()
        self._export_signal_state()

    def _check_emergency_requests(self):
        if self.junction_id != "J1":
            return

        req = None
        if "J1" in SHARED_EMERGENCY_REQUESTS:
            req = SHARED_EMERGENCY_REQUESTS["J1"]
        elif os.path.exists(EMERGENCY_REQUESTS_FILE):
            try:
                with open(EMERGENCY_REQUESTS_FILE, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("junction_id") == "J1":
                    req = data
            except Exception:
                pass

        if req and req.get("active", False) and req.get("request_type") == "EMERGENCY_PRIORITY":
            if self.emergency_state == "IDLE":
                self.emergency_request = req
                self.emergency_state = "INIT"
                print(f"[{self.junction_id}] EMERGENCY_REQUESTED", flush=True)

    def _get_ambulance_pos(self) -> Optional[Tuple[float, float]]:
        # In-memory registry check
        try:
            from car_001_controller import SHARED_MEMORY_REGISTRY
            if "AMBULANCE_001" in SHARED_MEMORY_REGISTRY:
                pos = SHARED_MEMORY_REGISTRY["AMBULANCE_001"]
                return (pos[0], pos[1])
        except Exception:
            pass

        # State file check
        amb_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "vehicle_pos_AMBULANCE_001.json"))
        if os.path.exists(amb_file):
            try:
                with open(amb_file, "r") as f:
                    data = json.load(f)
                return (data["x"], data["y"])
            except Exception:
                pass
        return None

    def update_logic(self, dt: float):
        """
        Advances signal timer and transitions between phases safely.
        """
        self._validate_safety()

        if self.priority_active:
            self.priority_remaining_time -= dt
            if self.priority_remaining_time <= 0:
                self.clear_priority()
            return

        # Check for J1 Emergency Requests
        if self.junction_id == "J1":
            self._check_emergency_requests()

            if self.emergency_state != "IDLE":
                self._update_emergency_logic(dt)
                return

        self.phase_elapsed_time += dt

        green_dur = self.config["green_duration"]
        yellow_dur = self.config["yellow_duration"]
        all_red_dur = self.config["all_red_duration"]

        if self.current_phase == SignalPhase.NS_GREEN:
            if self.phase_elapsed_time >= green_dur:
                self.current_phase = SignalPhase.NS_YELLOW
                self.phase_elapsed_time = 0.0
                self._apply_phase_lamps(self.current_phase)

        elif self.current_phase == SignalPhase.NS_YELLOW:
            if self.phase_elapsed_time >= yellow_dur:
                self.current_phase = SignalPhase.ALL_RED_NS_TO_EW
                self.phase_elapsed_time = 0.0
                self._apply_phase_lamps(self.current_phase)

        elif self.current_phase == SignalPhase.ALL_RED_NS_TO_EW:
            if self.phase_elapsed_time >= all_red_dur:
                self.current_phase = SignalPhase.EW_GREEN
                self.phase_elapsed_time = 0.0
                self._apply_phase_lamps(self.current_phase)

        elif self.current_phase == SignalPhase.EW_GREEN:
            if self.phase_elapsed_time >= green_dur:
                self.current_phase = SignalPhase.EW_YELLOW
                self.phase_elapsed_time = 0.0
                self._apply_phase_lamps(self.current_phase)

        elif self.current_phase == SignalPhase.EW_YELLOW:
            if self.phase_elapsed_time >= yellow_dur:
                self.current_phase = SignalPhase.ALL_RED_EW_TO_NS
                self.phase_elapsed_time = 0.0
                self._apply_phase_lamps(self.current_phase)

        elif self.current_phase == SignalPhase.ALL_RED_EW_TO_NS:
            if self.phase_elapsed_time >= all_red_dur:
                self.current_phase = SignalPhase.NS_GREEN
                self.phase_elapsed_time = 0.0
                self._apply_phase_lamps(self.current_phase)

    def _update_emergency_logic(self, dt: float):
        yellow_dur = self.config["yellow_duration"]
        all_red_dur = self.config["all_red_duration"]
        app_dir = self.emergency_request.get("approach_direction", "SOUTH") if self.emergency_request else "SOUTH"

        if self.emergency_state == "INIT":
            # Check if current phase is ALREADY green for ambulance approach direction
            is_ns_app = app_dir in ("NORTH", "SOUTH", "NS")
            is_ew_app = app_dir in ("EAST", "WEST", "EW")

            already_green = (is_ns_app and self.current_phase == SignalPhase.NS_GREEN) or \
                            (is_ew_app and self.current_phase == SignalPhase.EW_GREEN)

            if already_green:
                self.emergency_state = "GREEN"
                self.emergency_timer = 0.0
                self.ambulance_entered_j1 = False
                self.ambulance_cleared_j1 = False
                self._apply_emergency_lamps(app_dir)
                print(f"[J1_EMERGENCY_GREEN]\nvehicle=AMBULANCE_001\napproach={app_dir}", flush=True)
            elif self.current_phase in (SignalPhase.ALL_RED_NS_TO_EW, SignalPhase.ALL_RED_EW_TO_NS):
                print(f"[{self.junction_id}] ALL_RED", flush=True)
                self.emergency_state = "ALL_RED"
                self.phase_elapsed_time = 0.0
                self._apply_emergency_lamps(None)  # ALL RED
            elif self.current_phase in (SignalPhase.NS_YELLOW, SignalPhase.EW_YELLOW):
                print(f"[{self.junction_id}] CLEARING_CURRENT_PHASE", flush=True)
                self.emergency_state = "CLEARING"
            else:
                print(f"[{self.junction_id}] CLEARING_CURRENT_PHASE", flush=True)
                self.current_phase = SignalPhase.EW_YELLOW if self.current_phase == SignalPhase.EW_GREEN else SignalPhase.NS_YELLOW
                self.phase_elapsed_time = 0.0
                self.emergency_state = "CLEARING"
                self._apply_phase_lamps(self.current_phase)

        elif self.emergency_state == "CLEARING":
            self.phase_elapsed_time += dt
            if self.phase_elapsed_time >= yellow_dur:
                print(f"[{self.junction_id}] ALL_RED", flush=True)
                self.emergency_state = "ALL_RED"
                self.phase_elapsed_time = 0.0
                self.current_phase = SignalPhase.ALL_RED_NS_TO_EW
                self._apply_emergency_lamps(None)  # ALL RED

        elif self.emergency_state == "ALL_RED":
            self.phase_elapsed_time += dt
            if self.phase_elapsed_time >= all_red_dur:
                self.emergency_state = "GREEN"
                self.emergency_timer = 0.0
                self.ambulance_entered_j1 = False
                self.ambulance_cleared_j1 = False
                self._apply_emergency_lamps(app_dir)
                print(f"[J1_EMERGENCY_GREEN]\nvehicle=AMBULANCE_001\napproach={app_dir}", flush=True)

        elif self.emergency_state == "GREEN":
            self.emergency_timer += dt

            # Track Ambulance clearance
            pos = self._get_ambulance_pos()
            if pos:
                ax, ay = pos[0], pos[1]
                dist_center = math.hypot(ax - (-46.5), ay - 46.5)

                # Entry check (clearance zone: dist <= 6.0m or inside J1 box)
                if dist_center <= 6.0 and not self.ambulance_entered_j1:
                    self.ambulance_entered_j1 = True
                    print(f"[{self.junction_id}] AMBULANCE_ENTERED", flush=True)

                # Exit check (clearance zone exit: dist > 6.0m moving away, e.g. ax > -43.0 or ay > 51.0)
                if self.ambulance_entered_j1 and not self.ambulance_cleared_j1:
                    if dist_center > 6.0 or ax > -43.0 or ay > 51.0:
                        self.ambulance_cleared_j1 = True
                        print(f"[{self.junction_id}] AMBULANCE_CLEARED", flush=True)

            # Check if request was cancelled externally
            req_active = True
            if "J1" in SHARED_EMERGENCY_REQUESTS:
                req_active = SHARED_EMERGENCY_REQUESTS["J1"].get("active", True)

            if not req_active and not self.ambulance_cleared_j1:
                print("[SWIFT_EMERGENCY_CANCELLED]", flush=True)

            # Check restoration trigger
            if self.ambulance_cleared_j1 or self.emergency_timer >= self.max_emergency_green or not req_active:
                print(f"[{self.junction_id}] RESTORING_NORMAL_CYCLE", flush=True)
                self.emergency_state = "RESTORE_YELLOW"
                self.phase_elapsed_time = 0.0
                # Apply Yellow to emergency approach direction
                if app_dir in ("NORTH", "SOUTH", "NS"):
                    self.current_phase = SignalPhase.NS_YELLOW
                else:
                    self.current_phase = SignalPhase.EW_YELLOW
                self._apply_phase_lamps(self.current_phase)

        elif self.emergency_state == "RESTORE_YELLOW":
            self.phase_elapsed_time += dt
            if self.phase_elapsed_time >= yellow_dur:
                self.emergency_state = "RESTORE_ALL_RED"
                self.phase_elapsed_time = 0.0
                self.current_phase = SignalPhase.ALL_RED_NS_TO_EW
                self._apply_emergency_lamps(None)  # ALL RED
                print(f"[{self.junction_id}] ALL_RED", flush=True)

        elif self.emergency_state == "RESTORE_ALL_RED":
            self.phase_elapsed_time += dt
            if self.phase_elapsed_time >= all_red_dur:
                # Resume normal cycle: next phase EW_GREEN
                self.current_phase = SignalPhase.EW_GREEN
                self.phase_elapsed_time = 0.0
                self._apply_phase_lamps(self.current_phase)
                
                # Clear request state
                SHARED_EMERGENCY_REQUESTS.pop("J1", None)
                if os.path.exists(EMERGENCY_REQUESTS_FILE):
                    try:
                        os.remove(EMERGENCY_REQUESTS_FILE)
                    except Exception:
                        pass

                self.emergency_state = "IDLE"
                self.emergency_request = None

    def run(self):
        print(f"[JunctionController {self.junction_id}] Active and running signal cycle.")
        if self.robot:
            while self.robot.step(self.time_step) != -1:
                dt = self.time_step / 1000.0
                self.update_logic(dt)
        else:
            print(f"[JunctionController {self.junction_id}] Running in headless/standalone mode.")


class TrafficSignalController:
    """
    Top-level manager class wrapping intersection controllers for multi-junction instantiation.
    """
    def __init__(self, junction_id: Optional[str] = None):
        if WEBOTS_AVAILABLE:
            self.robot = Robot()
            self.junction_id = junction_id or self.robot.getName()
        else:
            self.robot = None
            self.junction_id = junction_id or "J1"

        self.intersection = IntersectionController(self.junction_id, self.robot)

    def run(self):
        self.intersection.run()


if __name__ == "__main__":
    controller = TrafficSignalController()
    controller.run()


