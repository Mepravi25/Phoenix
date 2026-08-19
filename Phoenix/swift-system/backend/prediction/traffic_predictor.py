"""
SWIFT SYSTEM - Predictive ML Engine
Predicts future queue length, traffic density, and congestion levels across prediction horizons.
Features abstract predictor interface and transparent model implementation with ML extension points.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import numpy as np


class ITrafficPredictor(ABC):
    @abstractmethod
    def predict_junction(
        self,
        junction_id: str,
        current_state: Dict[str, Any],
        horizon_seconds: float = 30.0,
        incident_present: bool = False
    ) -> Dict[str, Any]:
        pass


class DynamicFlowTrafficPredictor(ITrafficPredictor):
    """
    Transparent, explainable dynamic flow predictor.
    Predicts future queue = current_queue + (inflow_rate - outflow_rate) * horizon + incident_factor
    """

    def predict_junction(
        self,
        junction_id: str,
        current_state: Dict[str, Any],
        horizon_seconds: float = 30.0,
        incident_present: bool = False
    ) -> Dict[str, Any]:
        curr_queue = float(current_state.get("queue_length", 0))
        signal_state = current_state.get("signal_state", "GREEN_NS")

        # Dynamic rate calculation
        if signal_state in ["GREEN_NS", "GREEN_EW", "PRIORITY"]:
            outflow_rate = 0.4  # vehicles/sec leaving
        else:
            outflow_rate = 0.05

        inflow_rate = 0.35  # vehicles/sec arriving

        if incident_present:
            inflow_rate += 0.4
            outflow_rate *= 0.2

        net_rate = inflow_rate - outflow_rate
        predicted_queue = max(0.0, curr_queue + net_rate * horizon_seconds)

        # Estimate density and congestion
        predicted_density = min(1.0, round(predicted_queue * 0.05, 2))

        if predicted_queue > 12.0 or incident_present:
            predicted_congestion = "HIGH"
        elif predicted_queue > 6.0:
            predicted_congestion = "MEDIUM"
        else:
            predicted_congestion = "LOW"

        return {
            "junction_id": junction_id,
            "horizon_seconds": horizon_seconds,
            "current_queue": curr_queue,
            "predicted_queue": round(predicted_queue, 1),
            "predicted_density": predicted_density,
            "predicted_congestion": predicted_congestion,
            "growth_rate_per_sec": round(net_rate, 2),
            "incident_impact": incident_present
        }


# Global Predictor Instance
traffic_predictor = DynamicFlowTrafficPredictor()
