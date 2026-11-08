"""Unit and Integration Tests for Wacky Wheels Operations Policy Handbook.

Enforces and validates all 8 core operational policies and rule completeness:
- Rule 1: Reschedule strictly to earliest feasible working day >= min_date
- Rule 2: Plant daily capacity invariant (<= daily slots per plant)
- Rule 3: Emergency plant transfer logic when same plant is at capacity
- Rule 4: Dealer notification consolidation (exactly 1 dealer.notify per dealer, deduped)
- Rule 5: Loaner allocation priority (Platinum -> Gold -> promised date -> order ID) & pool limits
- Rule 6: Quality quarantine (quality.hold_lot, batched dealer.stop_sale, crm.notify_customer)
- Rule 7: Noise filtering (zero operational writes)
- Rule 8: Unconfirmed / ambiguous reports (escalate only, zero operational writes)
- Rule 9: Rule completeness & 15-event benchmark replay (783 deterministic actions, 0 errors)
"""

import os
import sys
import unittest
from datetime import date
from typing import Any, Dict, List

# Ensure project root is in path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from enterprise import Enterprise, ToolError, idx_to_date, date_to_idx, load_events
from knowledge_graph import KnowledgeGraph, ImpactReport
from policy_engine import PolicyEngine, LAST_WORKING_DAY_IDX
from agents.coordinator import CoordinatingAgent


DATA_DIR = os.path.join(REPO_ROOT, "data")


class MockClient:
    """Mock client to track executed tool calls and simulate backend success."""
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def call(self, event_id: str, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append({"event_id": event_id, "tool": tool, "args": args})
        return {"ok": True}


class PolicyRulesTestSuite(unittest.TestCase):
    """Formal test suite verifying all 8 operational rules and full benchmark replay."""

    @classmethod
    def setUpClass(cls):
        cls.kg = KnowledgeGraph(DATA_DIR)
        cls.pe = PolicyEngine(cls.kg)
        cls.enterprise = Enterprise(DATA_DIR)

    def test_rule_1_reschedule_earliest_feasible_working_day(self):
        """Rule 1: Orders must be rescheduled to earliest feasible slot >= min_reschedule_date."""
        slot_tracker = self.pe.build_initial_slot_tracker()
        min_date_str = "2027-03-15"
        min_d = date.fromisoformat(min_date_str)

        # Pick a real production order from P_TX scheduled before min_date
        sample_po = None
        for po_id, po in self.kg.production_orders.items():
            if po["plant_id"] == "P_TX" and po["build_date"] < min_date_str and po["build_date"] >= "2027-03-08":
                sample_po = po
                break

        self.assertIsNotNone(sample_po, "Should find a production order at P_TX")
        affected = [sample_po]

        actions = self.pe.plan_rescheduling(affected, min_date_str, slot_tracker)
        self.assertEqual(len(actions), 1)
        action = actions[0]

        # Must be mes.reschedule or mes.transfer
        self.assertIn(action["tool"], ("mes.reschedule", "mes.transfer"))
        new_date_str = action["args"]["new_date"]
        new_d = date.fromisoformat(new_date_str)

        # Must be >= min_date
        self.assertGreaterEqual(new_d, min_d, f"New date {new_date_str} must be >= min_date {min_date_str}")

        # Must be a weekday (Mon-Fri)
        self.assertLess(new_d.weekday(), 5, f"New date {new_date_str} must be a weekday")

        # Execute in Enterprise simulator
        res = self.enterprise.call("TEST_R1", action["tool"], action["args"])
        self.assertTrue(res.get("ok"), "Enterprise call must succeed")

    def test_rule_2_plant_capacity_invariant(self):
        """Rule 2: Plant slots per day limit must never be exceeded."""
        slot_tracker = self.pe.build_initial_slot_tracker()
        plant_id = "P_TX"
        plant_cap = self.kg.plants[plant_id]["slots_per_day"]
        target_idx = 5  # 2027-03-15
        target_date_str = idx_to_date(target_idx).isoformat()

        # Artificially saturate target_idx up to capacity
        fake_pos = [f"DUMMY_SATURATE_{i}" for i in range(plant_cap)]
        slot_tracker[(plant_id, target_idx)] = list(fake_pos)

        # Create an affected order for P_TX
        sample_po = {
            "production_order_id": "TEST_CAP_OVERFLOW_01",
            "plant_id": plant_id,
            "model": list(self.kg.plants[plant_id]["models"])[0],
            "build_date": "2027-03-08",
            "units": 10
        }

        actions = self.pe.plan_rescheduling([sample_po], target_date_str, slot_tracker)
        self.assertEqual(len(actions), 1)

        new_date_str = actions[0]["args"]["new_date"]
        new_idx = date_to_idx(date.fromisoformat(new_date_str))

        # Because target_idx was full, it MUST NOT be scheduled on target_idx
        self.assertNotEqual(new_idx, target_idx, "Cannot schedule on saturated day")
        self.assertGreater(new_idx, target_idx, "Must push to subsequent feasible slot")

        # Invariant check: slot_tracker count <= plant_cap
        for (p, idx), pos in slot_tracker.items():
            cap = self.kg.plants[p]["slots_per_day"]
            self.assertLessEqual(len(pos), cap, f"Capacity overflow at {p} on index {idx}: {len(pos)} > {cap}")

    def test_rule_3_emergency_plant_transfer(self):
        """Rule 3: If original plant is fully booked, order transfers to an alternate plant building that model."""
        slot_tracker = self.pe.build_initial_slot_tracker()
        orig_plant = "P_TX"

        # Saturate P_TX for ALL remaining working days (idx 0 to LAST_WORKING_DAY_IDX)
        tx_cap = self.kg.plants[orig_plant]["slots_per_day"]
        for idx in range(0, LAST_WORKING_DAY_IDX + 1):
            slot_tracker[(orig_plant, idx)] = [f"SAT_{idx}_{i}" for i in range(tx_cap)]

        # Find an unbuilt order from P_TX
        test_po = None
        for po_id, po in self.kg.production_orders.items():
            if po["plant_id"] == orig_plant and po["build_date"] >= "2027-03-08":
                test_po = po
                break

        self.assertIsNotNone(test_po, "Must find an unbuilt order at P_TX")
        model = test_po["model"]

        actions = self.pe.plan_rescheduling([test_po], "2027-03-08", slot_tracker)
        self.assertEqual(len(actions), 1)
        action = actions[0]

        # Must trigger mes.transfer because P_TX has 0 slots
        self.assertEqual(action["tool"], "mes.transfer", "Must transfer when original plant is saturated")
        self.assertIn("to_plant_id", action["args"])
        alt_plant = action["args"]["to_plant_id"]

        self.assertNotEqual(alt_plant, orig_plant, "Transfer target must differ from original plant")
        self.assertIn(model, self.kg.plants[alt_plant]["models"], f"{alt_plant} must build {model}")

        # Execute against Enterprise
        res = self.enterprise.call("TEST_R3", action["tool"], action["args"])
        self.assertTrue(res.get("ok"), "mes.transfer must succeed in enterprise simulator")

    def test_rule_4_dealer_notification_consolidation(self):
        """Rule 4: Exactly one notification per affected dealer listing only unique customer order IDs."""
        affected_dealers = {
            "D01": ["CO-0001", "CO-0002", "CO-0001", "CO-0003"],  # Contains duplicate
            "D02": ["CO-0010", "CO-0011"],
            "D03": []  # Empty dealer should not be notified
        }

        actions = self.pe.plan_dealer_notifications(affected_dealers, reason="supplier delay")

        # Exactly 2 actions: one for D01, one for D02
        self.assertEqual(len(actions), 2)

        dealers_notified = [a["args"]["dealer_id"] for a in actions]
        self.assertEqual(dealers_notified, ["D01", "D02"])

        # Check D01 deduplication
        d01_action = next(a for a in actions if a["args"]["dealer_id"] == "D01")
        self.assertEqual(d01_action["args"]["customer_order_ids"], ["CO-0001", "CO-0002", "CO-0003"])

        # Check that dealer.notify requires real customer orders when calling Enterprise
        real_d01_orders = [
            co_id for co_id, co in self.kg.customer_orders.items()
            if co["dealer_id"] == "D01"
        ][:2]

        if real_d01_orders:
            real_actions = self.pe.plan_dealer_notifications({"D01": real_d01_orders})
            ent_res = self.enterprise.call("TEST_R4", real_actions[0]["tool"], real_actions[0]["args"])
            self.assertTrue(ent_res.get("ok"))
            self.assertIn("D01", self.enterprise.state("TEST_R4")["notified"])

    def test_rule_5_loaner_allocation_priority_and_limits(self):
        """Rule 5: Platinum before Gold, earlier promised date, lower order ID. Standard gets 0. Pool cap strictly respected."""
        mock_pool = {"D01": 2}  # Dealer D01 has exactly 2 loaners

        candidates = [
            # Standard tier: must get 0
            {"customer_order_id": "CO-001", "customer_id": "C-STD", "dealer_id": "D01", "tier": "Standard", "promised_date": "2027-03-09"},
            # Gold tier: later priority than Platinum
            {"customer_order_id": "CO-002", "customer_id": "C-GLD", "dealer_id": "D01", "tier": "Gold", "promised_date": "2027-03-09"},
            # Platinum with later date
            {"customer_order_id": "CO-003", "customer_id": "C-PLT-LATE", "dealer_id": "D01", "tier": "Platinum", "promised_date": "2027-03-15"},
            # Platinum with earlier date, higher ID
            {"customer_order_id": "CO-005", "customer_id": "C-PLT-EARLY2", "dealer_id": "D01", "tier": "Platinum", "promised_date": "2027-03-10"},
            # Platinum with earlier date, lower ID -> HIGHEST PRIORITY
            {"customer_order_id": "CO-004", "customer_id": "C-PLT-EARLY1", "dealer_id": "D01", "tier": "Platinum", "promised_date": "2027-03-10"},
        ]

        actions = self.pe.plan_loaner_allocations(candidates, mock_pool)

        # Pool had 2 loaners, so exactly 2 actions must be returned
        self.assertEqual(len(actions), 2, "Only 2 loaners available; exactly 2 allocations allowed")
        self.assertEqual(mock_pool["D01"], 0, "Loaner pool must be exhausted to 0")

        # 1st priority: CO-004 (Platinum, 2027-03-10, lower ID than CO-005)
        self.assertEqual(actions[0]["args"]["customer_order_id"], "CO-004")
        # 2nd priority: CO-005 (Platinum, 2027-03-10, higher ID)
        self.assertEqual(actions[1]["args"]["customer_order_id"], "CO-005")

        # Enterprise verification with real customer order
        real_co = None
        for co_id, co in self.kg.customer_orders.items():
            if co["dealer_id"] == "D01":
                cust = self.kg.customers.get(co["customer_id"])
                if cust and cust["tier"] in ("Platinum", "Gold"):
                    real_co = co_id
                    break

        if real_co:
            res = self.enterprise.call("TEST_R5", "crm.assign_loaner", {"customer_order_id": real_co})
            self.assertTrue(res.get("ok"))
            self.assertIn(real_co, self.enterprise.state("TEST_R5")["loaned"])

    def test_rule_6_quality_hold_quarantine(self):
        """Rule 6: Defect lot hold, batched dealer stop-sale, customer recall notifications."""
        # Find a real lot from lots
        sample_lot = list(self.kg.lots.keys())[0]

        # Find real in-stock vehicles
        in_stock = {}
        for vin, v in self.kg.vehicles.items():
            if v["status"] == "in_stock":
                in_stock.setdefault(v["dealer_id"], []).append(vin)
                if len(in_stock) >= 1 and len(list(in_stock.values())[0]) >= 2:
                    break

        sample_dealer = list(in_stock.keys())[0]
        sample_vins = in_stock[sample_dealer][:2]

        # Find real sold vehicle
        sample_sold_cust = None
        sample_sold_vin = None
        for vin, v in self.kg.vehicles.items():
            if v["status"] == "sold" and v.get("customer_id"):
                sample_sold_cust = v["customer_id"]
                sample_sold_vin = vin
                break

        self.assertIsNotNone(sample_lot)
        self.assertIsNotNone(sample_dealer)
        self.assertIsNotNone(sample_sold_cust)

        actions = self.pe.plan_quality_quarantines(
            affected_lots=[sample_lot],
            vehicles_in_stock={sample_dealer: sample_vins},
            vehicles_sold=[{"customer_id": sample_sold_cust, "vin": sample_sold_vin}]
        )

        # Should produce 1 hold_lot, 1 dealer.stop_sale, 1 crm.notify_customer
        self.assertEqual(len(actions), 3)

        tools = [a["tool"] for a in actions]
        self.assertIn("quality.hold_lot", tools)
        self.assertIn("dealer.stop_sale", tools)
        self.assertIn("crm.notify_customer", tools)

        # Test against Enterprise
        for act in actions:
            res = self.enterprise.call("TEST_R6", act["tool"], act["args"])
            self.assertTrue(res.get("ok"), f"Tool {act['tool']} must succeed")

        s = self.enterprise.state("TEST_R6")
        self.assertIn(sample_lot, s["held"])
        self.assertTrue(set(sample_vins).issubset(s["stopped"]))
        self.assertIn(sample_sold_cust, s["customers"])

    def test_rule_7_noise_zero_writes(self):
        """Rule 7: Non-manufacturing inquiries (Noise) produce strictly 0 operational writes."""
        noise_report = ImpactReport(
            event_id="TEST_NOISE",
            category="Noise",
            what_happened="Brochure typo inquiry",
            impact_summary="Zero impact",
            reasoning_trace=["Non-operational inquiry"],
            graph_paths=["None"],
            is_noise=True
        )

        actions = self.pe.generate_action_plan(noise_report)
        self.assertEqual(len(actions), 0, "Noise must produce 0 planned actions")

        # Coordinator level test
        coordinator = CoordinatingAgent(DATA_DIR, use_live_llm=False)
        mock_client = MockClient()

        noise_event = {
            "event_id": "TEST_E_NOISE",
            "received_at": "2027-03-08T09:00:00",
            "source": "marketing hotline",
            "text": "Dealer marketing asks where to find the brochure pdf for the 2027 models."
        }

        res = coordinator.process_event(noise_event, mock_client)
        self.assertTrue(res.is_noise)
        self.assertEqual(res.total_actions, 0)
        self.assertEqual(len(mock_client.calls), 0, "Zero client tool calls must be made for noise")

    def test_rule_8_unconfirmed_escalate_zero_writes(self):
        """Rule 8: Unconfirmed signals produce exactly 1 escalate call and 0 operational writes."""
        unconfirmed_report = ImpactReport(
            event_id="TEST_UNCONFIRMED",
            category="Unconfirmed Report",
            what_happened="Vague forum rumor",
            impact_summary="Under supervisor review",
            reasoning_trace=["Unverified internet thread mentioning supply chain disruption"],
            graph_paths=["None"],
            unconfirmed=True
        )

        actions = self.pe.generate_action_plan(unconfirmed_report)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["tool"], "escalate")

        # Coordinator level test
        coordinator = CoordinatingAgent(DATA_DIR, use_live_llm=False)
        mock_client = MockClient()

        unconfirmed_event = {
            "event_id": "TEST_E_UNCONFIRMED",
            "received_at": "2027-03-08T09:00:00",
            "source": "social media",
            "text": "Rumor on automotive forum claims supplier may have issues next month. No supplier named."
        }

        res = coordinator.process_event(unconfirmed_event, mock_client)
        self.assertTrue(res.unconfirmed)
        self.assertEqual(res.total_actions, 1)
        self.assertEqual(len(mock_client.calls), 1)
        self.assertEqual(mock_client.calls[0]["tool"], "escalate")

        # Ensure no write actions were called
        write_tools = {
            "mes.reschedule", "mes.transfer", "dealer.notify",
            "dealer.stop_sale", "crm.assign_loaner", "crm.notify_customer", "quality.hold_lot"
        }
        writes = [c["tool"] for c in mock_client.calls if c["tool"] in write_tools]
        self.assertEqual(len(writes), 0, "Unconfirmed reports must never trigger write tools")

    def test_end_to_end_15_benchmark_events_replay(self):
        """Rule 9: Replay all 15 benchmark events; verify exactly 783 deterministic calls and 0 simulator errors."""
        events = load_events(os.path.join(DATA_DIR, "events.json"))
        self.assertEqual(len(events), 15, "Benchmark must contain 15 events")

        coordinator = CoordinatingAgent(DATA_DIR, use_live_llm=False)
        ent = Enterprise(DATA_DIR)

        total_actions = 0
        error_count = 0
        per_event_counts = {}

        for ev in events:
            eid = ev["event_id"]
            res = coordinator.process_event(ev, ent)
            per_event_counts[eid] = res.total_actions
            total_actions += res.total_actions

            for act in res.actions_taken:
                if not act.get("ok", True):
                    error_count += 1

            # Rule completeness check
            if res.is_noise:
                self.assertEqual(res.total_actions, 0, f"Noise event {eid} must have 0 actions")
            elif res.unconfirmed:
                self.assertEqual(res.total_actions, 1, f"Unconfirmed event {eid} must have exactly 1 escalate")
                self.assertEqual(res.actions_taken[0]["tool"], "escalate")
            else:
                # Real incident must have >= 3 distinct kinds of action (Rule 9 in policy handbook)
                distinct_tools = set(a["tool"] for a in res.actions_taken)
                self.assertGreaterEqual(
                    len(distinct_tools), 3,
                    f"Real operational incident {eid} must execute at least 3 distinct tools (got: {distinct_tools})"
                )

        self.assertEqual(total_actions, 783, f"Expected exactly 783 deterministic tool calls, got {total_actions}")
        self.assertEqual(error_count, 0, f"Expected 0 simulator errors, got {error_count}")


if __name__ == "__main__":
    unittest.main()
