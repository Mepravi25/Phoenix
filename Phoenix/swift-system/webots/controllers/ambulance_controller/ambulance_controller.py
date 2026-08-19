"""
Webots Ambulance Controller
Physically controls emergency vehicle in Webots world and reports telemetry to simulation bridge.
"""
import sys
import os

try:
    from controller import Robot, GPS, InertialUnit
    WEBOTS_AVAILABLE = True
except ImportError:
    WEBOTS_AVAILABLE = False


class AmbulanceController:
    def __init__(self):
        if WEBOTS_AVAILABLE:
            self.robot = Robot()
            self.time_step = int(self.robot.getBasicTimeStep())
            self.gps = self.robot.getDevice("gps")
            if self.gps:
                self.gps.enable(self.time_step)
        else:
            self.robot = None
            self.time_step = 32

    def run(self):
        print("[AmbulanceController] Initialized.")
        if self.robot:
            while self.robot.step(self.time_step) != -1:
                pos = self.gps.getValues() if self.gps else [0, 0, 0]
                # Send frame telemetry
                pass


if __name__ == "__main__":
    controller = AmbulanceController()
    controller.run()
