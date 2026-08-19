"""
SWIFT SYSTEM - Signal Plan Generator
Generates junction signal control instructions based on orchestration green corridor plan.
"""

from typing import Dict, Any


class SignalPlanGenerator:
    def generate_plan(self, active_route: list, raw_junctions: dict) -> dict:
        plan = {}
        for j_id in raw_junctions.keys():
            if j_id in active_route:
                idx = active_route.index(j_id)
                if idx == 0:
                    plan[j_id] = "PRIORITY_ACTIVE"
                else:
                    plan[j_id] = "PREPARE"
            else:
                plan[j_id] = "NORMAL"
        return plan


signal_plan_generator = SignalPlanGenerator()
