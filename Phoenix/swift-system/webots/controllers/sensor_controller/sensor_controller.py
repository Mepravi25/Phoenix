"""
Webots Sensor Controller
Reads virtual camera & induction loop traffic sensor telemetry.
"""
try:
    from controller import Supervisor
    WEBOTS_AVAILABLE = True
except ImportError:
    WEBOTS_AVAILABLE = False


class SensorController:
    def __init__(self):
        if WEBOTS_AVAILABLE:
            self.supervisor = Supervisor()
            self.time_step = int(self.supervisor.getBasicTimeStep())
        else:
            self.supervisor = None
            self.time_step = 32

    def run(self):
        print("[SensorController] Monitoring junction cameras & sensors.")
        if self.supervisor:
            while self.supervisor.step(self.time_step) != -1:
                pass


if __name__ == "__main__":
    controller = SensorController()
    controller.run()
