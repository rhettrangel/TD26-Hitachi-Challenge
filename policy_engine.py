"""Hack the Highway: Deterministic Enterprise Policy Engine.

Translates Knowledge Graph Impact Reports into strictly compliant,
zero-error enterprise tool calls following Wacky Wheels Co. Operations Policy Handbook.

Rules enforced:
1. Rescheduling: Move affected orders to earliest feasible working day >= min_date
   at same plant; fallback to transfer if same plant full.
2. Dealer Notification: Exactly one notification per affected dealer listing only
   its affected customer orders.
3. Loaner Allocation: Platinum before Gold, earlier promised date, lower order ID.
   Standard tier gets 0 loaners. Dealer pool limits strictly enforced.
4. Quality Quarantine: Hold lot, batch stop_sale by dealer for in_stock, notify owners for sold.
5. Guardrails: Zero write actions on noise; escalate only on unconfirmed rumors.
"""

from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from knowledge_graph import ImpactReport, KnowledgeGraph, date_to_idx, idx_to_date


LAST_WORKING_DAY_IDX = 19  # Planning window ends 2027-04-02


class PolicyEngine:
    """Enforces operations policy handbook rules and generates validated tool actions."""

    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg

    def build_initial_slot_tracker(self) -> Dict[Tuple[str, int], List[str]]:
        """Maps (plant_id, day_idx) -> list of production_order_ids currently scheduled."""
        tracker = defaultdict(list)
        for po_id, o in self.kg.production_orders.items():
            try:
                idx = date_to_idx(date.fromisoformat(o["build_date"]))
                if 0 <= idx <= LAST_WORKING_DAY_IDX:
                    tracker[(o["plant_id"], idx)].append(po_id)
            except ValueError:
                continue
        return tracker

    def plan_rescheduling(
        self,
        affected_pos: List[Dict[str, Any]],
        min_date_str: str,
        slot_tracker: Dict[Tuple[str, int], List[str]],
    ) -> List[Dict[str, Any]]:
        """
        Moves affected production orders to earliest feasible slot >= min_date_str.
        Prefers same plant; falls back to transfer if same plant is full.
        """
        actions = []
        min_d = date.fromisoformat(min_date_str)
        min_idx = max(0, date_to_idx(min_d))

        # Sort affected orders chronologically to preserve fair scheduling order
        sorted_pos = sorted(
            affected_pos,
            key=lambda x: (x["build_date"], x["production_order_id"])
        )

        for po in sorted_pos:
            po_id = po["production_order_id"]
            orig_plant = po["plant_id"]
            model = po["model"]
            orig_idx = date_to_idx(date.fromisoformat(po["build_date"]))

            assigned_plant = None
            assigned_idx = None
            is_transfer = False

            # 1. Try same plant first from min_idx onwards
            plant_cap = self.kg.plants[orig_plant]["slots_per_day"]
            for idx in range(min_idx, LAST_WORKING_DAY_IDX + 1):
                cur_orders = slot_tracker[(orig_plant, idx)]
                # If po_id is already here, it doesn't count against free slots
                count = len([p for p in cur_orders if p != po_id])
                if count < plant_cap:
                    assigned_plant = orig_plant
                    assigned_idx = idx
                    is_transfer = False
                    break

            # 2. If same plant full, find alternate plant that builds this model
            if assigned_plant is None:
                candidate_plants = [
                    p_id for p_id, p_info in self.kg.plants.items()
                    if p_id != orig_plant and model in p_info["models"]
                ]
                for idx in range(min_idx, LAST_WORKING_DAY_IDX + 1):
                    for alt_plant in candidate_plants:
                        alt_cap = self.kg.plants[alt_plant]["slots_per_day"]
                        cur_orders = slot_tracker[(alt_plant, idx)]
                        if len(cur_orders) < alt_cap:
                            assigned_plant = alt_plant
                            assigned_idx = idx
                            is_transfer = True
                            break
                    if assigned_plant is not None:
                        break

            if assigned_plant is None:
                raise RuntimeError(f"Capacity exhaustion: unable to find slot for {po_id} ({model})")

            # Remove from old slot in tracker
            if po_id in slot_tracker[(orig_plant, orig_idx)]:
                slot_tracker[(orig_plant, orig_idx)].remove(po_id)
            # Add to new slot in tracker
            slot_tracker[(assigned_plant, assigned_idx)].append(po_id)

            new_date = idx_to_date(assigned_idx).isoformat()
            if is_transfer:
                actions.append({
                    "tool": "mes.transfer",
                    "args": {
                        "production_order_id": po_id,
                        "to_plant_id": assigned_plant,
                        "new_date": new_date,
                    },
                    "reasoning": f"Same plant {orig_plant} at capacity; transferred {po_id} ({model}) to {assigned_plant} on {new_date}."
                })
            else:
                actions.append({
                    "tool": "mes.reschedule",
                    "args": {
                        "production_order_id": po_id,
                        "new_date": new_date,
                    },
                    "reasoning": f"Rescheduled {po_id} at {orig_plant} to earliest feasible slot on {new_date}."
                })

        return actions

    def plan_dealer_notifications(
        self,
        affected_dealers: Dict[str, List[str]],
        reason: str = "Production disruption",
    ) -> List[Dict[str, Any]]:
        """
        Emits exactly one dealer.notify per affected dealer with the exact list
        of affected customer orders.
        """
        actions = []
        for dealer_id, co_ids in sorted(affected_dealers.items()):
            unique_ids = sorted(list(set(co_ids)))
            if not unique_ids:
                continue
            actions.append({
                "tool": "dealer.notify",
                "args": {
                    "dealer_id": dealer_id,
                    "customer_order_ids": unique_ids,
                    "message": f"Operational notification: {len(unique_ids)} customer order(s) affected due to {reason}. Affected IDs: {', '.join(unique_ids)}",
                },
                "reasoning": f"Notifying dealer {dealer_id} of {len(unique_ids)} delayed customer orders."
            })
        return actions

    def plan_loaner_allocations(
        self,
        affected_customers: List[Dict[str, Any]],
        loaner_pool: Dict[str, int],
    ) -> List[Dict[str, Any]]:
        """
        Allocates loaner cars according to policy priority:
        1. Platinum (0) before Gold (1).
        2. Earlier promised_date.
        3. Lower customer_order_id.
        Standard tier customers are excluded (0 loaners).
        Dealer pool limits are strictly respected.
        """
        actions = []
        tier_ranks = {"Platinum": 0, "Gold": 1}

        # Filter only eligible customers (Platinum or Gold)
        eligible = [
            c for c in affected_customers
            if c.get("tier") in tier_ranks
        ]

        # Deduplicate by customer_order_id in case customer appears multiple times
        dedup_eligible = {}
        for c in eligible:
            co_id = c["customer_order_id"]
            if co_id not in dedup_eligible:
                dedup_eligible[co_id] = c

        # Sort according to policy rules
        sorted_candidates = sorted(
            dedup_eligible.values(),
            key=lambda c: (
                tier_ranks[c["tier"]],
                c["promised_date"],
                c["customer_order_id"],
            )
        )

        for cand in sorted_candidates:
            dealer_id = cand["dealer_id"]
            co_id = cand["customer_order_id"]
            avail = loaner_pool.get(dealer_id, 0)
            if avail > 0:
                actions.append({
                    "tool": "crm.assign_loaner",
                    "args": {"customer_order_id": co_id},
                    "reasoning": f"Assigned loaner from {dealer_id} pool to {cand['tier']} customer {cand['customer_id']} for order {co_id} (remaining pool: {avail - 1})."
                })
                loaner_pool[dealer_id] -= 1

        return actions

    def plan_quality_quarantines(
        self,
        affected_lots: List[str],
        vehicles_in_stock: Dict[str, List[str]],
        vehicles_sold: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Executes quality containment:
        1. quality.hold_lot for each defective lot.
        2. dealer.stop_sale batch per dealer for unsold vehicles.
        3. crm.notify_customer for sold vehicles.
        """
        actions = []

        # 1. Hold Lot
        for lot_id in affected_lots:
            actions.append({
                "tool": "quality.hold_lot",
                "args": {"lot_id": lot_id},
                "reasoning": f"Quarantine defective part lot {lot_id}."
            })

        # 2. Stop Sale (batch by dealer)
        for dealer_id, vins in sorted(vehicles_in_stock.items()):
            unique_vins = sorted(list(set(vins)))
            if unique_vins:
                actions.append({
                    "tool": "dealer.stop_sale",
                    "args": {
                        "dealer_id": dealer_id,
                        "vins": unique_vins,
                    },
                    "reasoning": f"Stop sale for {len(unique_vins)} unsold vehicle(s) at dealer {dealer_id}."
                })

        # 3. Notify Customers (sold vehicles)
        notified_custs = set()
        for v in sorted(vehicles_sold, key=lambda x: x["customer_id"]):
            cid = v["customer_id"]
            if cid not in notified_custs:
                actions.append({
                    "tool": "crm.notify_customer",
                    "args": {
                        "customer_id": cid,
                        "message": f"Safety campaign: Please contact authorized service regarding safety inspection for VIN {v['vin']}.",
                    },
                    "reasoning": f"Notify owner {cid} of safety recall for VIN {v['vin']}."
                })
                notified_custs.add(cid)

        return actions

    def plan_escalation(self, reason: str) -> List[Dict[str, Any]]:
        """Policy Rule 8: Unconfirmed/unclear reports require escalation without write actions."""
        return [{
            "tool": "escalate",
            "args": {"reason": reason},
            "reasoning": f"Unconfirmed report escalated to human supervisor: {reason}"
        }]

    # -------------------------------------------------------------------------
    # Master Plan Generator from ImpactReport
    # -------------------------------------------------------------------------
    def generate_action_plan(
        self,
        report: ImpactReport,
        min_reschedule_date: Optional[str] = None,
        slot_tracker: Optional[Dict[Tuple[str, int], List[str]]] = None,
        loaner_pool: Optional[Dict[str, int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Takes an ImpactReport and returns the complete, ordered list of policy-compliant
        enterprise tool actions.
        """
        if report.is_noise:
            # Policy Rule 7: Zero write actions on noise
            return []

        if report.unconfirmed:
            # Policy Rule 8: Escalate only
            return self.plan_escalation(report.reasoning_trace[0])

        actions = []
        if slot_tracker is None:
            slot_tracker = self.build_initial_slot_tracker()
        if loaner_pool is None:
            loaner_pool = dict(self.kg.loaners)

        if report.category == "Supplier Delay":
            if not min_reschedule_date:
                raise ValueError("Supplier Delay requires min_reschedule_date (new ETA)")
            # 1. Reschedule / Transfer
            actions.extend(self.plan_rescheduling(report.affected_production_orders, min_reschedule_date, slot_tracker))
            # 2. Dealer notifications
            actions.extend(self.plan_dealer_notifications(report.affected_dealers, "supplier delivery delay"))
            # 3. Loaners
            actions.extend(self.plan_loaner_allocations(report.affected_customers, loaner_pool))

        elif report.category == "Plant Outage":
            if not min_reschedule_date:
                raise ValueError("Plant Outage requires min_reschedule_date (reopen date)")
            # 1. Reschedule / Transfer
            actions.extend(self.plan_rescheduling(report.affected_production_orders, min_reschedule_date, slot_tracker))
            # 2. Dealer notifications
            actions.extend(self.plan_dealer_notifications(report.affected_dealers, "plant outage"))
            # 3. Loaners
            actions.extend(self.plan_loaner_allocations(report.affected_customers, loaner_pool))

        elif report.category == "Quality Hold":
            # 1. Hold lot, stop sale, notify customers
            actions.extend(self.plan_quality_quarantines(
                report.affected_lots,
                report.affected_vehicles_in_stock,
                report.affected_vehicles_sold,
            ))

        return actions
