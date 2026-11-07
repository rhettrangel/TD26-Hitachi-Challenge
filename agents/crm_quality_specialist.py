"""Hack the Highway: Customer Care & Quality Control Specialist Agent.

Manages customer notifications, VIP loaner car triage, and part lot quality containment.
"""

from typing import Any, Dict, List
from agents.base_agent import BaseAgent


class CustomerCareQualityAgent(BaseAgent):
    """Specialist agent responsible for CRM loaner dispatch, owner alerts, and lot holds."""

    def __init__(self):
        super().__init__(
            name="CustomerCareQualitySpecialist",
            role="Customer Experience & Quality Assurance Specialist"
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
            if tool not in ("crm.assign_loaner", "crm.notify_customer", "quality.hold_lot"):
                continue

            args = act["args"]
            reasoning = act.get("reasoning", "Customer care / Quality containment action")
            try:
                res = client.call(event_id, tool, args)
                self.log_action(tool, args, res, reasoning)
                results.append({"tool": tool, "args": args, "ok": True, "result": res, "agent": self.name})
            except Exception as e:
                self.log_action(tool, args, {"error": str(e)}, f"FAILED: {reasoning}")
                results.append({"tool": tool, "args": args, "ok": False, "error": str(e), "agent": self.name})
        return results
