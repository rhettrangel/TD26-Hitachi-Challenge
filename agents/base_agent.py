"""Hack the Highway: Base Agent interface and message definitions."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseAgent(ABC):
    """Abstract Base Agent for Control Tower specialists."""

    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.audit_log: List[Dict[str, Any]] = []

    def log_action(self, tool: str, args: Dict[str, Any], result: Any, reasoning: str):
        self.audit_log.append({
            "agent": self.name,
            "role": self.role,
            "tool": tool,
            "args": args,
            "result": result,
            "reasoning": reasoning,
        })

    @abstractmethod
    def execute_plan(
        self,
        event_id: str,
        actions: List[Dict[str, Any]],
        client: Any,
    ) -> List[Dict[str, Any]]:
        """Executes a list of assigned tool actions through client or simulator."""
        pass
