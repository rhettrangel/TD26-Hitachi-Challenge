"""Test to verify that ambiguous or unrecognized events route to escalation, never Noise."""

import os
import sys
import unittest

# Add project root to sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from agents.coordinator import CoordinatingAgent
from enterprise import Enterprise


class MockClient:
    def __init__(self):
        self.calls = []

    def call(self, event_id, tool, args):
        self.calls.append({"event_id": event_id, "tool": tool, "args": args})
        return {"ok": True}


class UnrecognizedFallbackTestCase(unittest.TestCase):
    def test_unrecognized_event_routes_to_escalate(self):
        data_dir = os.path.join(REPO_ROOT, "data")
        coordinator = CoordinatingAgent(data_dir, use_live_llm=False)
        client = MockClient()

        # Ambiguous event that cannot be positively matched to delay, outage, quality, or brochure noise
        ambiguous_event = {
            "event_id": "TEST-AMBIGUOUS-01",
            "received_at": "2027-03-08T12:00:00",
            "source": "floor whisper",
            "text": "Floor supervisor says something unusual happened near building 4 yesterday afternoon. Unclear if anything stopped."
        }

        res = coordinator.process_event(ambiguous_event, client)

        # Assertions
        self.assertEqual(res.category, "Unconfirmed Report")
        self.assertTrue(res.unconfirmed)
        self.assertFalse(res.is_noise)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["tool"], "escalate")

        # Verify zero operational write actions
        write_tools = {"mes.reschedule", "mes.transfer", "dealer.notify", "dealer.stop_sale", "crm.assign_loaner", "crm.notify_customer", "quality.hold_lot"}
        executed_write_tools = [c["tool"] for c in client.calls if c["tool"] in write_tools]
        self.assertEqual(len(executed_write_tools), 0)


def test_unrecognized_event_routes_to_escalate():
    runner = UnrecognizedFallbackTestCase()
    runner.test_unrecognized_event_routes_to_escalate()
    print("TEST PASSED: Ambiguous event correctly routed to escalation with zero write actions!")


if __name__ == "__main__":
    unittest.main()
