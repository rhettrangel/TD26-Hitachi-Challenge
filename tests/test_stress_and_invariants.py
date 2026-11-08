"""Industrial-Grade Stress & Invariant Test Suite for Wacky Wheels Control Tower.

Rigorous validation and property-based invariant testing:
1. Fuzzing & High Volume: 100 diverse synthetic events (Outages, Delays, Holds, Noise, Rumors)
2. Extreme Capacity Saturation: Resolving orders when 5/6 plants are saturated at 100% capacity
3. Loaner Pool Saturation & Invariants: 100 mixed customer orders against limited pool of 5 loaners
4. Dealer Notification Consolidation & Deduplication: High-volume duplicated order inputs
5. Quality Containment Invariants: Simultaneous multi-lot quarantine across dealers and owners
6. Temporal Boundary Stress: Weekend bridging, Day 0 start, Day 19 planning window boundary
7. 100% Alias Catalog Entity Resolution: Testing all 61 aliases in data/aliases.csv
8. Idempotency & Deterministic Shuffled Replays: 5 random benchmark permutations yielding 783 calls
9. Full Live HTTP Server End-to-End Stress: Replaying all 15 events over real TCP sockets via enterprise_server.py
"""

import json
import os
import random
import sys
import threading
import time
import unittest
from datetime import date, timedelta
from typing import Any, Dict, List

# Ensure project root is in path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from enterprise import Enterprise, ToolError, idx_to_date, date_to_idx, load_events
from enterprise_server import Server, make_handler
from knowledge_graph import KnowledgeGraph, ImpactReport
from policy_engine import PolicyEngine, LAST_WORKING_DAY_IDX
from runner import InstrumentedHttpClient
from agents.coordinator import CoordinatingAgent


DATA_DIR = os.path.join(REPO_ROOT, "data")


class MockTrackingClient:
    """Mock client that records all calls and tracks per-tool call counts."""
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def call(self, event_id: str, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append({"event_id": event_id, "tool": tool, "args": args})
        return {"ok": True}


class StressAndInvariantsTestSuite(unittest.TestCase):
    """Stress testing suite validating mathematical invariants, throughput, and robustness."""

    @classmethod
    def setUpClass(cls):
        cls.kg = KnowledgeGraph(DATA_DIR)
        cls.pe = PolicyEngine(cls.kg)
        cls.benchmark_events = load_events(os.path.join(DATA_DIR, "events.json"))

    def test_stress_100_synthetic_events_fuzzing(self):
        """Stress Test 1: Generate and execute 100 diverse synthetic operational events."""
        random.seed(42)
        plants = list(self.kg.plants.keys())
        parts = list(self.kg.parts.keys())
        suppliers = list(self.kg.suppliers.keys())
        lots = list(self.kg.lots.keys())

        synthetic_events = []
        for i in range(1, 101):
            eid = f"SYNTH-{i:03d}"
            evt_type = i % 5

            if evt_type == 0:  # Noise
                ev = {
                    "event_id": eid,
                    "received_at": "2027-03-08T10:00:00",
                    "source": "dealer newsletter",
                    "text": f"Dealer marketing query: where to find the brochure pdf for synthetic event {eid}?"
                }
            elif evt_type == 1:  # Unconfirmed Rumor
                ev = {
                    "event_id": eid,
                    "received_at": "2027-03-08T10:00:00",
                    "source": "rumor mill",
                    "text": f"Rumor circulating on plant floor {i}: nothing confirmed by anyone, just chatter."
                }
            elif evt_type == 2:  # Plant Outage
                p = plants[i % len(plants)]
                ev = {
                    "event_id": eid,
                    "received_at": "2027-03-08T10:00:00",
                    "source": "plant alert",
                    "text": f"Plant outage: {p} shutdown from next Friday through Monday Mar 22 due to synthetic test {i}."
                }
            elif evt_type == 3:  # Supplier Delay
                p = plants[i % len(plants)]
                part = parts[i % len(parts)]
                ev = {
                    "event_id": eid,
                    "received_at": "2027-03-08T10:00:00",
                    "source": "carrier alert",
                    "text": f"Supplier shipment for {part} at {p} due next Monday and will now arrive next Friday."
                }
            else:  # Quality Hold
                lot = lots[i % len(lots)]
                lot_info = self.kg.lots[lot]
                p = lot_info["plant_id"]
                part = lot_info["part_id"]
                ev = {
                    "event_id": eid,
                    "received_at": "2027-03-08T10:00:00",
                    "source": "quality bulletin",
                    "text": f"Quality bulletin: defective lot {lot} of {part} at {p} built Monday Feb 22 through Wednesday Feb 24."
                }
            synthetic_events.append(ev)

        coordinator = CoordinatingAgent(DATA_DIR, use_live_llm=False)
        ent = Enterprise(DATA_DIR)

        total_actions = 0
        errors = 0
        write_tools = {"mes.reschedule", "mes.transfer", "dealer.notify", "dealer.stop_sale", "crm.assign_loaner", "crm.notify_customer", "quality.hold_lot"}

        for ev in synthetic_events:
            res = coordinator.process_event(ev, ent)
            total_actions += res.total_actions

            for act in res.actions_taken:
                if not act.get("ok", True):
                    errors += 1

            if res.is_noise:
                # Rule 7 invariant: 0 writes
                writes = [a for a in res.actions_taken if a["tool"] in write_tools]
                self.assertEqual(len(writes), 0, f"Noise event {ev['event_id']} had writes: {writes}")
            elif res.unconfirmed:
                # Rule 8 invariant: 1 escalate, 0 writes
                writes = [a for a in res.actions_taken if a["tool"] in write_tools]
                self.assertEqual(len(writes), 0, f"Unconfirmed event {ev['event_id']} had writes: {writes}")
                self.assertEqual(res.total_actions, 1)

        self.assertEqual(errors, 0, f"Zero simulator errors expected across 100 synthetic events (got {errors})")
        self.assertGreater(total_actions, 0, "Synthetic operational events must generate valid actions")

    def test_stress_extreme_capacity_saturation(self):
        """Stress Test 2: Saturate 5 out of 6 plants at 100% capacity; verify transfer to remaining plant."""
        slot_tracker = self.pe.build_initial_slot_tracker()
        all_plants = list(self.kg.plants.keys())

        # Select target plant P_NC to stay open; saturate the other 5 plants
        target_plant = "P_NC"
        saturated_plants = [p for p in all_plants if p != target_plant]

        for p in saturated_plants:
            cap = self.kg.plants[p]["slots_per_day"]
            for idx in range(0, LAST_WORKING_DAY_IDX + 1):
                slot_tracker[(p, idx)] = [f"SAT_{p}_{idx}_{k}" for k in range(cap)]

        # Find 5 unbuilt orders belonging to the saturated plants
        test_pos = []
        for po_id, po in self.kg.production_orders.items():
            if po["plant_id"] in saturated_plants and po["build_date"] >= "2027-03-08":
                # Ensure target_plant builds this model
                if po["model"] in self.kg.plants[target_plant]["models"]:
                    test_pos.append(po)
                    if len(test_pos) == 5:
                        break

        self.assertEqual(len(test_pos), 5, "Must find 5 eligible unbuilt orders")

        actions = self.pe.plan_rescheduling(test_pos, "2027-03-08", slot_tracker)
        self.assertEqual(len(actions), 5)

        for act in actions:
            # Must transfer to target_plant because all others are 100% saturated
            self.assertEqual(act["tool"], "mes.transfer")
            self.assertEqual(act["args"]["to_plant_id"], target_plant)

        # Invariant check: target plant slot count never exceeds slots_per_day
        target_cap = self.kg.plants[target_plant]["slots_per_day"]
        for idx in range(0, LAST_WORKING_DAY_IDX + 1):
            count = len(slot_tracker[(target_plant, idx)])
            self.assertLessEqual(count, target_cap, f"Target plant {target_plant} exceeded capacity on day {idx}")

    def test_stress_loaner_pool_saturation_and_invariants(self):
        """Stress Test 3: Flood 100 customer orders (30 Plat, 30 Gold, 40 Standard) into dealer pool of 5 loaners."""
        random.seed(123)
        dealer_pool = {"D01": 5}

        candidates = []
        # 40 Standard customers
        for i in range(1, 41):
            candidates.append({
                "customer_order_id": f"CO-STD-{i:03d}",
                "customer_id": f"C-STD-{i:03d}",
                "dealer_id": "D01",
                "tier": "Standard",
                "promised_date": (date(2027, 3, 9) + timedelta(days=i % 10)).isoformat()
            })

        # 30 Gold customers
        for i in range(1, 31):
            candidates.append({
                "customer_order_id": f"CO-GLD-{i:03d}",
                "customer_id": f"C-GLD-{i:03d}",
                "dealer_id": "D01",
                "tier": "Gold",
                "promised_date": (date(2027, 3, 9) + timedelta(days=i % 5)).isoformat()
            })

        # 30 Platinum customers
        for i in range(1, 31):
            candidates.append({
                "customer_order_id": f"CO-PLT-{i:03d}",
                "customer_id": f"C-PLT-{i:03d}",
                "dealer_id": "D01",
                "tier": "Platinum",
                "promised_date": (date(2027, 3, 9) + timedelta(days=i % 4)).isoformat()
            })

        random.shuffle(candidates)

        actions = self.pe.plan_loaner_allocations(candidates, dealer_pool)

        # Invariant 1: Exactly 5 loaners assigned
        self.assertEqual(len(actions), 5)
        # Invariant 2: Remaining pool is exactly 0 (never negative)
        self.assertEqual(dealer_pool["D01"], 0)

        # Invariant 3: All 5 recipients must be Platinum customers
        allocated_ids = [a["args"]["customer_order_id"] for a in actions]
        for co_id in allocated_ids:
            self.assertTrue(co_id.startswith("CO-PLT-"), f"Recipient {co_id} must be Platinum")

        # Invariant 4: No Standard customer ever received a loaner
        self.assertFalse(any(cid.startswith("CO-STD-") for cid in allocated_ids))

        # Invariant 5: Deduplication (no order receives more than 1 loaner)
        self.assertEqual(len(allocated_ids), len(set(allocated_ids)))

    def test_stress_dealer_notification_deduplication(self):
        """Stress Test 4: Heavy duplicate order IDs across multiple dealers consolidated into 1 notify per dealer."""
        heavy_duplicates = {
            "D01": ["CO-0100", "CO-0101", "CO-0100", "CO-0102", "CO-0101", "CO-0100"],
            "D02": ["CO-0200", "CO-0200", "CO-0200"],
            "D03": ["CO-0301", "CO-0302", "CO-0303", "CO-0301"],
            "D04": []  # Dealer with no affected orders
        }

        actions = self.pe.plan_dealer_notifications(heavy_duplicates, "high-volume disruption")

        # Invariant 1: Exactly 3 dealer notifications (D01, D02, D03; D04 excluded)
        self.assertEqual(len(actions), 3)

        notified_dealers = [a["args"]["dealer_id"] for a in actions]
        self.assertEqual(notified_dealers, ["D01", "D02", "D03"])

        # Invariant 2: Deduplication and sorting
        d01_action = next(a for a in actions if a["args"]["dealer_id"] == "D01")
        self.assertEqual(d01_action["args"]["customer_order_ids"], ["CO-0100", "CO-0101", "CO-0102"])

        d02_action = next(a for a in actions if a["args"]["dealer_id"] == "D02")
        self.assertEqual(d02_action["args"]["customer_order_ids"], ["CO-0200"])

    def test_stress_quality_containment_invariants(self):
        """Stress Test 5: Multi-lot simultaneous quarantine across dealers and sold owners."""
        lots = list(self.kg.lots.keys())[:3]
        dealers = list(self.kg.dealers.keys())[:2]

        vehicles_in_stock = {
            dealers[0]: ["VIN-STOCK-01", "VIN-STOCK-02", "VIN-STOCK-01"],  # Duplicate VIN
            dealers[1]: ["VIN-STOCK-03"]
        }

        vehicles_sold = [
            {"customer_id": "C-001", "vin": "VIN-SOLD-01"},
            {"customer_id": "C-001", "vin": "VIN-SOLD-02"},  # Same customer, second vehicle
            {"customer_id": "C-002", "vin": "VIN-SOLD-03"}
        ]

        actions = self.pe.plan_quality_quarantines(lots, vehicles_in_stock, vehicles_sold)

        tools = [a["tool"] for a in actions]
        # Invariant 1: All 3 lots held
        self.assertEqual(tools.count("quality.hold_lot"), 3)

        # Invariant 2: Exactly 2 stop_sale actions (one per dealer with in-stock vehicles)
        self.assertEqual(tools.count("dealer.stop_sale"), 2)

        # Invariant 3: VIN deduplication at dealer 0
        d0_stop = next(a for a in actions if a["tool"] == "dealer.stop_sale" and a["args"]["dealer_id"] == dealers[0])
        self.assertEqual(d0_stop["args"]["vins"], ["VIN-STOCK-01", "VIN-STOCK-02"])

        # Invariant 4: Customer notification deduplication (C-001 notified exactly once)
        cust_notifies = [a for a in actions if a["tool"] == "crm.notify_customer"]
        self.assertEqual(len(cust_notifies), 2)
        notified_cust_ids = [a["args"]["customer_id"] for a in cust_notifies]
        self.assertEqual(notified_cust_ids, ["C-001", "C-002"])

    def test_stress_temporal_boundary_conditions(self):
        """Stress Test 6: Temporal boundary conditions (Day 0, Day 19 planning end, weekend bridging)."""
        slot_tracker = self.pe.build_initial_slot_tracker()

        # Boundary 1: Day 0 (Today: 2027-03-08)
        day0_idx = date_to_idx(date(2027, 3, 8))
        self.assertEqual(day0_idx, 0)
        self.assertEqual(idx_to_date(0).isoformat(), "2027-03-08")

        # Boundary 2: Day 19 (End of planning window: 2027-04-02)
        day19_idx = date_to_idx(date(2027, 4, 2))
        self.assertEqual(day19_idx, LAST_WORKING_DAY_IDX)
        self.assertEqual(idx_to_date(19).isoformat(), "2027-04-02")

        # Boundary 3: Weekend bridging (Friday 2027-03-12 -> Monday 2027-03-15)
        fri_idx = date_to_idx(date(2027, 3, 12))
        mon_idx = date_to_idx(date(2027, 3, 15))
        self.assertEqual(mon_idx, fri_idx + 1)  # Next working day index is exactly +1

        # Invariant: date_to_idx rejects weekends
        with self.assertRaises(ValueError):
            date_to_idx(date(2027, 3, 13))  # Saturday
        with self.assertRaises(ValueError):
            date_to_idx(date(2027, 3, 14))  # Sunday

    def test_stress_alias_catalog_100_percent_resolution(self):
        """Stress Test 7: Verify 100% resolution of all 61 aliases in data/aliases.csv."""
        self.assertEqual(len(self.kg.aliases), 61, "Expected exactly 61 aliases in aliases.csv")

        for alias, (etype, target_id) in self.kg.aliases.items():
            resolved_type, resolved_id = self.kg.resolve_entity(alias)
            self.assertEqual(
                resolved_id, target_id,
                f"Alias '{alias}' resolved to '{resolved_id}', expected '{target_id}'"
            )
            self.assertEqual(
                resolved_type, etype,
                f"Alias '{alias}' resolved type '{resolved_type}', expected '{etype}'"
            )

    def test_stress_idempotency_and_shuffled_replays(self):
        """Stress Test 8: Replay 15 benchmark events across 5 randomized shuffles; verify identical determinism."""
        coordinator = CoordinatingAgent(DATA_DIR, use_live_llm=False)

        base_event_actions = {}
        # First deterministic baseline run
        ent_base = Enterprise(DATA_DIR)
        for ev in self.benchmark_events:
            eid = ev["event_id"]
            res = coordinator.process_event(ev, ent_base)
            base_event_actions[eid] = len(res.actions_taken)

        self.assertEqual(sum(base_event_actions.values()), 783)

        # Run 5 shuffled permutations
        random.seed(999)
        shuffled = list(self.benchmark_events)
        for trial in range(1, 6):
            random.shuffle(shuffled)
            ent_trial = Enterprise(DATA_DIR)
            trial_total = 0
            for ev in shuffled:
                eid = ev["event_id"]
                res = coordinator.process_event(ev, ent_trial)
                trial_total += res.total_actions
                self.assertEqual(
                    len(res.actions_taken), base_event_actions[eid],
                    f"Trial {trial}: Event {eid} produced {len(res.actions_taken)} actions, expected {base_event_actions[eid]}"
                )
            self.assertEqual(trial_total, 783, f"Trial {trial}: Expected exactly 783 total actions, got {trial_total}")

    def test_stress_live_http_server_end_to_end(self):
        """Stress Test 9: Replay all 15 benchmark events through enterprise_server.py over live HTTP sockets."""
        port = random.randint(20000, 35000)
        out_log = os.path.join(REPO_ROOT, "runs", "test_http_stress_suite.jsonl")
        os.makedirs(os.path.dirname(out_log), exist_ok=True)
        if os.path.exists(out_log):
            os.remove(out_log)

        ent = Enterprise(DATA_DIR)
        server_lock = threading.Lock()
        handler = make_handler(ent, self.benchmark_events, out_log, server_lock)
        server = Server(("127.0.0.1", port), handler)

        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        time.sleep(0.3)

        try:
            http_client = InstrumentedHttpClient(f"http://127.0.0.1:{port}")
            coordinator = CoordinatingAgent(DATA_DIR, use_live_llm=False)

            total_actions = 0
            for ev in self.benchmark_events:
                res = coordinator.process_event(ev, http_client)
                total_actions += res.total_actions

            self.assertEqual(total_actions, 783, f"Expected 783 HTTP calls, executed {total_actions}")

            # Verify server-side written action log
            with open(out_log, "r", encoding="utf-8") as f:
                logged_calls = [json.loads(line) for line in f]

            self.assertEqual(len(logged_calls), 783, f"Expected 783 logged HTTP calls, found {len(logged_calls)}")
            failed_http_calls = [c for c in logged_calls if not c.get("ok")]
            self.assertEqual(len(failed_http_calls), 0, f"Expected 0 failed HTTP calls, got {len(failed_http_calls)}")

        finally:
            server.shutdown()
            server.server_close()
            if os.path.exists(out_log):
                os.remove(out_log)


if __name__ == "__main__":
    unittest.main()
