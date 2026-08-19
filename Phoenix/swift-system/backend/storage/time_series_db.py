"""
SWIFT SYSTEM - Time-Series Storage Abstraction
Stores time-series traffic metrics (queue, speed, density, signal state) for analytics & prediction.
"""

from collections import deque
import time
from typing import Dict, List, Any


class TimeSeriesDB:
    def __init__(self, max_points: int = 1000):
        self.max_points = max_points
        self._series: Dict[str, deque] = {}

    def record(self, metric_name: str, value: Any, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        if metric_name not in self._series:
            self._series[metric_name] = deque(maxlen=self.max_points)
        self._series[metric_name].append({"timestamp": timestamp, "value": value})

    def get_recent(self, metric_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        if metric_name not in self._series:
            return []
        return list(self._series[metric_name])[-limit:]

    def get_average(self, metric_name: str, window_seconds: float = 60.0) -> float:
        if metric_name not in self._series or not self._series[metric_name]:
            return 0.0
        now = time.time()
        vals = [item["value"] for item in self._series[metric_name] if isinstance(item["value"], (int, float))]
        if not vals:
            return 0.0
        return sum(vals) / len(vals)


# Global Singleton Instance
ts_db = TimeSeriesDB()
