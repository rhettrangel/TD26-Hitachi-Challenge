"""Hack the Highway: MES & Production Planning Specialist Agent.

Manages assembly line schedules, slot allocations, and inter-plant transfers
across Wacky Wheels Co.'s 6 manufacturing plants.
"""

from typing import Any, Dict, List
from agents.base_agent import BaseAgent


class MESPlannerAgent(BaseAgent):
    """Specialist agent responsible for plant scheduling, slot tracking, and transfers."""

    def __init__(self):
        super().__init__(
            name="MESPlannerSpecialist",
            role="Supply Chain & Production Scheduling Specialist"
        )

    def execute_plan(
        self,
        event_id: str,
        actions: List[Dict[str, Any]],
        client: Any,
    ) -> List[Dict[str, Any]]:
        results = []
        for act in actions:
            tool = act["tool"]
            if tool not in ("mes.reschedule", "mes.transfer", "mes.get_schedule"):
                continue

            args = act["args"]
            reasoning = act.get("reasoning", "Production schedule adjustment")
            try:
                res = client.call(event_id, tool, args)
                self.log_action(tool, args, res, reasoning)
                results.append({"tool": tool, "args": args, "ok": True, "result": res, "agent": self.name})
            except Exception as e:
                self.log_action(tool, args, {"error": str(e)}, f"FAILED: {reasoning}")
                results.append({"tool": tool, "args": args, "ok": False, "error": str(e), "agent": self.name})
        return results
