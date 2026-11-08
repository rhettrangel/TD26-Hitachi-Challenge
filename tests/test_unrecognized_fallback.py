"""Test to verify that ambiguous or unrecognized events route to escalation, never Noise."""

import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.coordinator import CoordinatingAgent
from enterprise import Enterprise


class MockClient:
    def __init__(self):
        self.calls = []

    def call(self, event_id, tool, args):
        self.calls.append({"event_id": event_id, "tool": tool, "args": args})
        return {"ok": True}


def test_unrecognized_event_routes_to_escalate():
    coordinator = CoordinatingAgent("data", use_live_llm=False)
    client = MockClient()

    # Ambiguous event that cannot be positively matched to delay, outage, quality, or brochure noise
    ambiguous_event = {
        "event_id": "TEST-AMBIGUOUS-01",
        "received_at": "2027-03-08T12:00:00",
        "source": "floor whisper",
        "text": "Floor supervisor says something unusual happened near building 4 yesterday afternoon. Unclear if anything stopped."
    }

    res = coordinator.process_event(ambiguous_event, client)

    print(f"Processed ambiguous event:")
    print(f"  Category: {res.category}")
    print(f"  Unconfirmed: {res.unconfirmed}")
    print(f"  Is Noise: {res.is_noise}")
    print(f"  Total Actions: {res.total_actions}")
    print(f"  Client Calls: {client.calls}")

    # Assertions
    assert res.category == "Unconfirmed Report", f"Expected 'Unconfirmed Report', got '{res.category}'"
    assert res.unconfirmed is True, "Expected unconfirmed flag to be True"
    assert res.is_noise is False, "Expected is_noise flag to be False (must NOT default to Noise)"
    assert len(client.calls) == 1, f"Expected exactly 1 tool call, got {len(client.calls)}"
    assert client.calls[0]["tool"] == "escalate", f"Expected tool 'escalate', got '{client.calls[0]['tool']}'"

    # Verify zero operational write actions
    write_tools = {"mes.reschedule", "mes.transfer", "dealer.notify", "dealer.stop_sale", "crm.assign_loaner", "crm.notify_customer", "quality.hold_lot"}
    executed_write_tools = [c["tool"] for c in client.calls if c["tool"] in write_tools]
    assert len(executed_write_tools) == 0, f"Expected 0 write actions, got: {executed_write_tools}"

    print("TEST PASSED: Ambiguous event correctly routed to escalation with zero write actions!")


if __name__ == "__main__":
    test_unrecognized_event_routes_to_escalate()
