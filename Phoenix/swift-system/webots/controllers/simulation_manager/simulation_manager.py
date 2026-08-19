"""
Webots Simulation Manager Supervisor
Controls global tick synchronization, vehicle spawner, and dynamic incident injection.
"""
try:
    from controller import Supervisor
    WEBOTS_AVAILABLE = True
except ImportError:
    WEBOTS_AVAILABLE = False


import os
import sys

# Ensure traffic_monitor can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "traffic_monitor")))
try:
    from traffic_monitor import TrafficMonitor
    MONITOR_AVAILABLE = True
except ImportError:
    MONITOR_AVAILABLE = False


class SimulationManager:
    def __init__(self):
        if WEBOTS_AVAILABLE:
            self.supervisor = Supervisor()
            self.time_step = int(self.supervisor.getBasicTimeStep())
        else:
            self.supervisor = None
            self.time_step = 32

        if MONITOR_AVAILABLE and self.supervisor:
            self.monitor = TrafficMonitor(self.supervisor, report_interval=5.0)
        else:
            self.monitor = None

    def run(self):
        print("[SimulationManager Supervisor] Global step coordinator and Traffic Monitor active.")
        if self.supervisor:
            while self.supervisor.step(self.time_step) != -1:
                dt = self.time_step / 1000.0
                if self.monitor:
                    self.monitor.generate_report(dt)


if __name__ == "__main__":
    manager = SimulationManager()
    manager.run()
