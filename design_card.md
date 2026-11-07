# Design Card: Autonomous Event-Driven Multi-Agent Control Tower

**Challenge:** Hitachi — Hack the Highway: Event-Driven Multi-Agent Control Tower (TAMU Datathon 2026)  
**System Type:** Hybrid Neuro-Symbolic Multi-Agent System  
**Model Cited:** `gemini-1.5-flash` (Perception) + Deterministic Policy Solver  

---

### 1. Architecture Overview (1 Coordinating Agent + 3 Specialist Agents)

The system uses a modular multi-agent architecture designed to process operational disruptions in a zero-inventory Just-In-Time (JIT) manufacturing environment:

```
                          [ Operational Event Feed ]
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │    COORDINATING AGENT     │
                        │  • Intent Classification  │
                        │  • Entity & Date Resolver │
                        │  • Incident Decomposition │
                        │  • Guardrail Gatekeeper   │
                        └─────────────┬─────────────┘
                                      │
               ┌──────────────────────┼──────────────────────┐
               ▼                      ▼                      ▼
    ┌──────────────────────┐┌──────────────────────┐┌──────────────────────┐
    │   MES PLANNER AGENT  ││ DEALER NETWORK AGENT ││  CRM & QUALITY AGENT │
    │ • mes.get_schedule   ││ • dealer.notify      ││ • quality.hold_lot   │
    │ • mes.reschedule     ││ • dealer.stop_sale   ││ • crm.assign_loaner  │
    │ • mes.transfer       ││                      ││ • crm.notify_customer│
    └──────────┬───────────┘└──────────┬───────────┘└──────────┬───────────┘
               └──────────────────────┼──────────────────────┘
                                      ▼
                     ┌──────────────────────────────────┐
                     │     ENTERPRISE SYSTEM STATE      │
                     │  (Wacky Wheels Co. Operations)   │
                     └──────────────────────────────────┘
```

1. **Coordinating Agent (`ControlTowerCoordinator`):**
   * Manages intake and perception. Ingests operational text, resolves aliases via `data/aliases.csv`, converts colloquial calendar dates to ISO weekdays via `data/calendar.csv`, and routes actionable incidents to specialists.
   * Enforces safety guardrails: suppresses write actions on noise events and dispatches unconfirmed rumors to human supervisors via the `escalate` tool.
2. **MES & Production Planner Agent (`MESPlannerSpecialist`):**
   * Manages assembly schedules across the 6 regional plants. Reschedules affected builds to the earliest feasible slot $\ge$ disruption resolution without exceeding daily slot capacity (`slots_per_day = 5`). Dynamically transfers orders to authorized alternate plants via `plant_models.csv` when same-plant capacity is exhausted.
3. **Dealer Network Agent (`DealerNetworkSpecialist`):**
   * Consolidates affected customer orders into **exactly one notification per affected dealer** (`dealer.notify`).
   * Issues batch stop-sale orders (`dealer.stop_sale`) for unsold vehicles (`in_stock`) caught in quality holds.
4. **CRM & Quality Specialist Agent (`CustomerCareQualitySpecialist`):**
   * Quarantines defective part lots (`quality.hold_lot`).
   * Allocates courtesy loaner vehicles following policy tier prioritization: **Platinum $\to$ Gold $\to$ earliest promised date $\to$ lowest order ID**. Standard tier customers are excluded. Dealer loaner pool limits are strictly observed.
   * Dispatches direct safety notifications to owners of sold vehicles (`crm.notify_customer`).

---

### 2. Division of Labor: LLM Perception vs Deterministic Code

| Component | Implementation | Rationale |
| :--- | :--- | :--- |
| **Perception & Entity Grounding** | `gemini-1.5-flash` / Hybrid Rule Engine | Ingests free-text messages and resolves colloquial phrasing (*"the Texas plant"*, *"harness B"*, *"dark from next Friday through Monday Mar 22"*). |
| **Ontology & Blast Radius Traversal** | In-Memory Graph (`knowledge_graph.py`) | Traverses 16,955 nodes in $< 0.01$s per event to compute exact downstream entity dependencies without hallucinating IDs. |
| **Policy Constraint Satisfaction** | Deterministic Solver (`policy_engine.py`) | Enforces calendar rules, slot limits, notification batching, and loaner priority with mathematical guarantees. |
| **Tool Execution & Logging** | Enterprise Client | Generates validated JSONL logs matching the required enterprise simulator protocol. |

---

### 3. Structured Output Schema & Malformed Response Handling

Perception calls request structured JSON using the following schema:

```json
{
  "type": "OBJECT",
  "properties": {
    "incidents": {
      "type": "ARRAY",
      "items": {
        "type": "OBJECT",
        "properties": {
          "category": {"type": "STRING", "enum": ["Supplier Delay", "Plant Outage", "Quality Hold", "Noise", "Unconfirmed Report"]},
          "plant_id": {"type": "STRING"},
          "part_id": {"type": "STRING"},
          "supplier_id": {"type": "STRING"},
          "shipment_id": {"type": "STRING"},
          "lot_id": {"type": "STRING"},
          "start_date": {"type": "STRING"},
          "end_date": {"type": "STRING"},
          "min_reschedule_date": {"type": "STRING"},
          "reason": {"type": "STRING"}
        },
        "required": ["category"]
      }
    }
  },
  "required": ["incidents"]
}
```

**Real Sample Parsed Output (Event E-12):**
```json
{
  "incidents": [
    {
      "category": "Supplier Delay",
      "plant_id": "P_IN",
      "part_id": "CAM-360",
      "shipment_id": "SH-0182",
      "start_date": "2027-03-15",
      "end_date": "2027-03-18",
      "min_reschedule_date": "2027-03-18",
      "reason": "Shipment SH-0182 delayed due to port congestion"
    }
  ]
}
```

**Failure Handling Code Path:** In `agents/llm_client.py`, API requests are wrapped in `try...except (urllib.error.HTTPError, json.JSONDecodeError, Exception)`. When an API call fails or produces malformed JSON, the client logs the error and returns `None`. `agents/event_parser.py` detects `incidents_raw is None`, records `fallback_used = True`, and seamlessly triggers the deterministic rule-based parser. If the rule parser encounters completely unrecognized text, it classifies the incident as `Noise`, preventing accidental writes.

---

### 4. Verified Performance Metrics

All figures below trace directly to `runs/cached_run/timing_summary.json` and `docs/timing_audit.md`:

* **Event Set:** 15 benchmark events (`data/events.json`).
* **Deterministic Policy Replay Accuracy:** **100% (783 / 783 valid tool calls, 0 tool errors)** against the ground-truth enterprise simulator.
* **Deterministic Pipeline Wall-Clock Latency:** **0.0396 seconds** for the full 15-event run (comprising 0.0352s deterministic planning and 0.0043s state mutation).
* **Perception Latency:** 0.00s in cached/deterministic mode; live LLM network latency is external and subject to API round-trip times.
* **Token & Cost Accounting:**
  * Model String: `gemini-1.5-flash`
  * Pricing: \$0.075 / 1M input tokens, \$0.30 / 1M output tokens (Source: Google AI Studio pricing, https://ai.google.dev/pricing, verified Nov 2024 / current).
  * Estimated Volume (15 events): 10,200 prompt tokens + 1,500 candidate tokens = 11,700 total tokens.
  * Computed Cost per Full 15-Event Run: **\$0.001215** ($10,200 \times 7.5\times 10^{-8} + 1,500 \times 3.0\times 10^{-7}$).

---

### 5. Limitations

1. **Benchmark Scope:** The 15 test events were provided by the challenge organizers. Ground-truth expectations are based on the policy handbook rules.
2. **Perception Generalization:** LLM perception accuracy on unstructured text outside the provided 15 benchmark events and `aliases.csv` mappings has not been independently measured on external real-world production datasets.
3. **Execution Latency Sourcing:** The 0.0396s figure reflects in-memory deterministic graph traversal and local simulator updates. It does not reflect external internet latency or live cloud API round-trip times, as detailed in `docs/timing_audit.md`.
