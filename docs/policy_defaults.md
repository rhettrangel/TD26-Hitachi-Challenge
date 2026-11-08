# Policy Defaults & Fail-Safe Routing Specification

**Date:** 2026-11-07  
**Module:** `agents/event_parser.py`, `agents/coordinator.py`  
**Governing Policy:** Policy Rule 7 (Noise Restraint) & Policy Rule 8 (Unconfirmed Rumors / Human Escalation)

---

## 1. The Policy Principle: Escalation Over Silence

In a high-stakes Just-In-Time (JIT) manufacturing environment with zero inventory buffers:
* **Silently ignoring a real but oddly phrased disruption** (treating it as Noise) can halt lines downstream, stall shipments, and lead to unmitigated delivery failures.
* **Executing unauthorized writes on unclear reports** corrupts scheduling queues and triggers false dealer alerts.
* **The Fail-Safe Rule:** Any event that the perception system cannot positively classify, or any message whose operational intent is ambiguous, **must default to Human Escalation (`Unconfirmed Report` / TC6 path)**, resulting in **zero operational write actions and exactly one `escalate` tool call**.

---

## 2. Classification Rules

1. **Noise (TC4):**
   * **Condition:** Assigned **only upon positive identification** of non-manufacturing, non-operational content (e.g. dealership sales inquiries for PDF marketing brochures, irrelevant external weather far away).
   * **Action:** Zero write actions, logged with non-operational justification.
2. **Unconfirmed Report / Ambiguous Fallback (TC6):**
   * **Condition:** Assigned when:
     - The report is a vague rumor lacking confirmed dates, lot IDs, or part numbers.
     - The parser (LLM or deterministic) fails to classify the message into a confirmed category.
     - Parsing or validation error occurs.
   * **Action:** Exactly one call to `escalate(reason=...)`, zero operational writes.
3. **Confirmed Incidents (TC1, TC2, TC3):**
   * **Condition:** Positively identified operational disruptions with verifiable dates and entity identifiers (plants, parts, lots, shipments).
   * **Action:** Dynamic knowledge graph traversal followed by policy-compliant execution across MES, Dealer Portals, and CRM.

---

## 3. Verification Test

A dedicated unit test in `tests/test_unrecognized_fallback.py` verifies this policy:
* Input: Ambiguous message: `"Floor supervisor says something unusual happened near building 4 yesterday afternoon."`
* Expected Category: `Unconfirmed Report`
* Operational Write Actions: 0
* Escalations: 1 (`escalate` tool invoked)
