"""Hack the Highway: Control Tower Coordinating Agent.

Orchestrates event intake, NLU parsing, knowledge graph traversal, policy enforcement,
and task dispatching across the three specialist agents:
1. MESPlannerSpecialist (Production & Transfers)
2. DealerNetworkSpecialist (Dealer Communications & Stop-Sales)
3. CustomerCareQualitySpecialist (CRM Loaners, Recalls & Lot Quarantines)
"""

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from agents.dealer_specialist import DealerNetworkAgent
from agents.event_parser import EventParser, ParsedIncident
from agents.mes_specialist import MESPlannerAgent
from agents.crm_quality_specialist import CustomerCareQualityAgent
from knowledge_graph import ImpactReport, KnowledgeGraph
from policy_engine import PolicyEngine


@dataclass
class EventProcessingResult:
    """Full deliverable structure for an event execution with audited metrics."""
    event_id: str
    category: str
    what_happened: str
    impact_summary: str
    graph_paths: List[str]
    reasoning_trace: List[str]
    actions_taken: List[Dict[str, Any]]
    audit_trail: List[Dict[str, Any]]
    total_actions: int
    unconfirmed: bool = False
    is_noise: bool = False
    # Audited Timing & Telemetry
    llm_perception_time_ms: float = 0.0
    deterministic_time_ms: float = 0.0
    prompt_tokens: int = 0
    output_tokens: int = 0
    model_name: str = "deterministic_rule_engine"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "category": self.category,
            "what_happened": self.what_happened,
            "impact_summary": self.impact_summary,
            "graph_paths": self.graph_paths,
            "reasoning_trace": self.reasoning_trace,
            "actions_taken": self.actions_taken,
            "audit_trail": self.audit_trail,
            "total_actions": self.total_actions,
            "unconfirmed": self.unconfirmed,
            "is_noise": self.is_noise,
            "telemetry": {
                "llm_perception_time_ms": round(self.llm_perception_time_ms, 2),
                "deterministic_time_ms": round(self.deterministic_time_ms, 2),
                "prompt_tokens": self.prompt_tokens,
                "output_tokens": self.output_tokens,
                "model_name": self.model_name
            }
        }


class CoordinatingAgent:
    """Master Control Tower Coordinator orchestrating the specialist agent team."""

    def __init__(self, data_dir: str, use_live_llm: bool = False, api_key: Optional[str] = None):
        self.kg = KnowledgeGraph(data_dir)
        self.parser = EventParser(self.kg, use_live_llm=use_live_llm, api_key=api_key)
        self.policy = PolicyEngine(self.kg)

        # 3 Specialist Agents
        self.mes_agent = MESPlannerAgent()
        self.dealer_agent = DealerNetworkAgent()
        self.crm_quality_agent = CustomerCareQualityAgent()

    def process_event(self, event_dict: Dict[str, Any], client: Any) -> EventProcessingResult:
        eid = event_dict["event_id"]

        # 1. Perception Step (LLM or Deterministic Fallback)
        incidents, p_metrics = self.parser.parse_event(event_dict)

        t_det_start = time.time()

        combined_what_happened = []
        combined_impact = []
        combined_paths = []
        combined_reasoning = [
            f"Coordinator received event {eid} ({event_dict.get('source', 'unknown')}).",
            f"Perception parsed {len(incidents)} operational incident(s) [Mode: {p_metrics.get('model')}]."
        ]
        all_actions = []
        all_audit = []

        # Shared state for compound events to avoid resource contention
        slot_tracker = self.policy.build_initial_slot_tracker()
        loaner_pool = dict(self.kg.loaners)

        categories = set()
        is_noise = False
        is_unconfirmed = False

        for inc in incidents:
            categories.add(inc.category)
            if inc.category == "Noise":
                is_noise = True
                report = self.kg.traverse_noise(eid, inc.reason or "Non-operational query")
                combined_what_happened.append(report.what_happened)
                combined_impact.append(report.impact_summary)
                combined_paths.extend(report.graph_paths)
                combined_reasoning.extend(report.reasoning_trace)
                continue

            if inc.category == "Unconfirmed Report":
                is_unconfirmed = True
                report = self.kg.traverse_unconfirmed(eid, inc.reason or "Unconfirmed operational rumor")
                combined_what_happened.append(report.what_happened)
                combined_impact.append(report.impact_summary)
                combined_paths.extend(report.graph_paths)
                combined_reasoning.extend(report.reasoning_trace)
                try:
                    res = client.call(eid, "escalate", {"reason": inc.reason or "Unconfirmed report"})
                    all_actions.append({"tool": "escalate", "args": {"reason": inc.reason}, "ok": True})
                    all_audit.append({
                        "agent": "ControlTowerCoordinator",
                        "role": "Coordinator / Safety Officer",
                        "tool": "escalate",
                        "args": {"reason": inc.reason},
                        "ok": True,
                        "reasoning": "Escalated unconfirmed report to human operator per Policy Rule 8."
                    })
                except Exception as e:
                    all_actions.append({"tool": "escalate", "args": {"reason": inc.reason}, "ok": False, "error": str(e)})
                continue

            # Real incidents: traverse graph
            if inc.category == "Supplier Delay":
                report = self.kg.traverse_supplier_delay(
                    event_id=eid,
                    plant_id=inc.plant_id,
                    part_id=inc.part_id,
                    orig_eta=inc.start_date,
                    new_eta=inc.end_date,
                    shipment_id=inc.shipment_id,
                    supplier_id=inc.supplier_id,
                )
                min_reschedule_date = inc.min_reschedule_date

            elif inc.category == "Plant Outage":
                report = self.kg.traverse_plant_outage(
                    event_id=eid,
                    plant_id=inc.plant_id,
                    start_date=inc.start_date,
                    end_date=inc.end_date,
                )
                min_reschedule_date = inc.min_reschedule_date

            elif inc.category == "Quality Hold":
                report = self.kg.traverse_quality_hold(
                    event_id=eid,
                    plant_id=inc.plant_id,
                    part_id=inc.part_id,
                    start_date=inc.start_date,
                    end_date=inc.end_date,
                    lot_id=inc.lot_id,
                    supplier_id=inc.supplier_id,
                )
                min_reschedule_date = None

            combined_what_happened.append(report.what_happened)
            combined_impact.append(report.impact_summary)
            combined_paths.extend(report.graph_paths)
            combined_reasoning.extend(report.reasoning_trace)

            # Generate plan using policy engine
            planned_actions = self.policy.generate_action_plan(
                report=report,
                min_reschedule_date=min_reschedule_date,
                slot_tracker=slot_tracker,
                loaner_pool=loaner_pool,
            )

            # Dispatch to Specialist Agents
            mes_results = self.mes_agent.execute_plan(eid, planned_actions, client)
            dealer_results = self.dealer_agent.execute_plan(eid, planned_actions, client)
            crm_results = self.crm_quality_agent.execute_plan(eid, planned_actions, client)

            all_actions.extend(mes_results)
            all_actions.extend(dealer_results)
            all_actions.extend(crm_results)

            for act in planned_actions:
                all_audit.append({
                    "event_id": eid,
                    "tool": act["tool"],
                    "args": act["args"],
                    "reasoning": act.get("reasoning", "")
                })

        cat_label = " & ".join(sorted(categories)) if categories else "Unknown"
        det_time_ms = (time.time() - t_det_start) * 1000.0

        return EventProcessingResult(
            event_id=eid,
            category=cat_label,
            what_happened=" | ".join(combined_what_happened),
            impact_summary=" | ".join(combined_impact),
            graph_paths=combined_paths if combined_paths else ["None"],
            reasoning_trace=combined_reasoning,
            actions_taken=all_actions,
            audit_trail=all_audit,
            total_actions=len(all_actions),
            unconfirmed=is_unconfirmed,
            is_noise=is_noise,
            llm_perception_time_ms=p_metrics.get("perception_time_ms", 0.0),
            deterministic_time_ms=det_time_ms,
            prompt_tokens=p_metrics.get("prompt_tokens", 0),
            output_tokens=p_metrics.get("output_tokens", 0),
            model_name=p_metrics.get("model", "deterministic_rule_engine")
        )
