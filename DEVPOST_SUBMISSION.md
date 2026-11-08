# DevPost Submission: Hitachi Lumada Autonomous JIT Control Tower

**Project Title:** Hitachi Lumada: Autonomous JIT Operations Control Tower  
**Tagline:** A Multi-Agent Control Tower resolving supply chain delays, plant outages, and quality holds for zero-inventory automakers.

---

### 💡 Inspiration
Hitachi focuses on **Industrial AI and IT/OT convergence**—bridging physical industrial operations (assembly plants, inbound logistics, supply chains) with enterprise platforms.

In automotive manufacturing, **Just-In-Time (JIT) production operates with zero parts inventory**. Components arrive on the day of assembly. While cost-efficient, JIT makes manufacturing fragile: a delayed shipment of infotainment chips, a plant power outage, or a contaminated wiring harness ripples immediately across production schedules, 50 regional dealerships, and hundreds of customer deliveries.

We built the **Hitachi Lumada Autonomous Operations Control Tower** to evaluate how an event-driven multi-agent architecture can automate disruption mitigation and maintain policy compliance under strict operational constraints.

---

### ⚙️ What It Does

The system serves as an operational control tower for Wacky Wheels Co.:

1. **Operational Feed Intake:** Ingests unstructured operational communications (chat messages, plant alerts, supplier emails, digests) containing informal phrasing and relative dates.
2. **Noise Filtering & Human-in-the-Loop Escalation:** Ignores non-operational inquiries (e.g. dealership brochure requests) with **zero write actions**, and routes unconfirmed rumors to supervisors via the `escalate` tool.
3. **Knowledge Graph Traversal (16,955 Nodes):** Computes the exact operational blast radius across plants, bills of materials (BOM), part lots, and customer orders, generating verifiable citation paths:
   $$\text{Shipment} \to \text{Part} \to \text{Model (BOM)} \to \text{ProductionOrder} \to \text{CustomerOrder} \to \text{Dealer / Customer}$$
4. **Autonomous Action Execution Across 3 Specialist Agents:**
   * **MES Planner Specialist:** Reschedules builds to the earliest feasible slot ($\le 5$ slots/day) or transfers orders to authorized sister plants.
   * **Dealer Network Specialist:** Consolidates delayed customer orders into **exactly one notification per affected dealership** and issues stop-sale holds on quarantined vehicles.
   * **CRM & Quality Specialist:** Quarantines defective part lots, alerts owners of sold vehicles for safety recalls, and executes loaner car triage (Platinum $\to$ Gold $\to$ promised date $\to$ order ID) within dealer pool limits.

---

### 🧠 System Architecture & Implementation

The platform uses a hybrid **Neuro-Symbolic architecture** to avoid pure-LLM pitfalls (hallucinated identifiers, slot overbooking, and calendar math errors):

1. **Perception Layer (`gemini-3-flash-preview`):** Ingests raw text, maps colloquial terms via `data/aliases.csv`, converts relative dates into ISO weekdays via `data/calendar.csv`, and requests structured JSON outputs.
2. **Knowledge Graph Engine (`knowledge_graph.py`):** Models the enterprise domain (Plants, Models, Parts, Lots, Orders, VINs) and performs runtime breadth-first traversals to identify impacted records.
3. **Deterministic Policy Solver (`policy_engine.py`):** Enforces handbook rules (slot caps, single dealer notifications, loaner priority) with mathematical guarantees.
4. **Specialist Dispatcher (`agents/`):** A 1 Coordinator + 3 Specialist agent structure interfacing with enterprise systems.
5. **Control Tower UI (`dashboard/`):** An executive dark-mode industrial dashboard featuring dynamic traversal cascade animations, customer-facing action cards, and escalation review queues.

---

### 📊 Verified Performance & Metrics

All metrics trace directly to `runs/live_run/timing_summary.json`, `runs/cached_run/timing_summary.json`, `docs/parser_agreement.md`, and `docs/pricing_source.md`:

* **Benchmark Accuracy:** Scoped across the 15 team-authored ground-truth events:
  * Deterministic Layer: **783 / 783 tool calls executed with 0 errors** against the enterprise simulator (`runs/cached_run/action_log.jsonl`).
  * LLM Perception Agreement: **14 of 14 completed live calls (100%)** agreed on event category with the deterministic baseline parser. *Caveat on field-level extraction:* In event E-09, the live LLM classified the category as Supplier Delay but omitted the supplier ID and part number strings from text, resulting in 0 actions taken in live mode versus 42 actions in deterministic mode. 1 call (E-15) encountered Free Tier daily API rate limits and fell back to the deterministic path cleanly.
* **Timing Breakdown:**
  * **Live Gemini Run (`runs/live_run/`):** **53.3218 s** total wall-clock time (45.20s LLM round-trip perception time, 0.0523s deterministic pipeline, 0.0087s action execution).
  * **Deterministic Baseline (`runs/cached_run/`):** **0.0357 s** total wall-clock time (deterministic only, no LLM calls, no network).
* **Model Attribution:** `gemini-3-flash-preview` (Perception) + Deterministic Policy Engine.
* **Computed Commercial Efficiency & Cost:**
  * Google AI Studio published rates (`https://ai.google.dev/pricing`, retrieved 2026-11-07): $0.50 / 1M input tokens, $3.00 / 1M output tokens.
  * Measured Volume (15 events): 14,445 prompt tokens + 751 output tokens = 15,196 total tokens.
  * Computed Commercial Inference Cost: **$0.009475** (approx. 0.95 cents per full 15-event run).

---

### ⚠️ Limitations

1. **Benchmark Scope:** The 15 test events were hand-written by the team; the ground truth was built by the same team.
2. **Perception Generalization:** LLM perception accuracy on messy real-world text outside the 15 team-authored events has not been measured independently.
3. **Latency Benchmarking:** The 0.0357s figure represents local in-memory deterministic processing only. Real API calls are subject to external network latency (45.20s total across live calls).
4. **Pricing Citation:** Commercial pricing rates were retrieved from Google AI Studio on 2026-11-07 ($0.50/1M input, $3.00/1M output).

---

### 🎥 2-Minute Demo Video Walkthrough Script

* **[0:00 - 0:30] Context:** Open dashboard. *"Welcome to the Hitachi Lumada Control Tower. Wacky Wheels Co. builds vehicles Just-In-Time with zero parts inventory. A late shipment, factory blackout, or defective lot causes an immediate domino effect. Here is how our 1 Coordinator + 3 Specialist agents handle it."*
* **[0:30 - 1:00] Supplier Delay:** Click **E-12 (Supplier Delay)**. Show the Knowledge Graph traversing `Shipment SH-0182 → CAM-360 → Summit → PO-0316 → Customer Orders → Dealer D07`. In **Executive & Actions**, show the rescheduled build slot, the consolidated dealer alert, and the VIP loaner deployment.
* **[1:00 - 1:30] Quality Containment:** Click **E-15 (Quality Hold)**. Show how defective Lot LOT-0191 is held, triggering showroom stop-sale orders across 25 dealerships and safety recall notifications to owners of sold vehicles.
* **[1:30 - 2:00] Guardrails & Telemetry:** Click **E-05 (Noise)** to demonstrate zero write actions, and **E-02 (Rumor)** to show the Human-in-the-Loop escalation panel. Click **DevPost & Judging Brief** in the header to show the audited metrics: *"783 automated actions in the deterministic baseline, 0 simulator errors against the benchmark, and measured live run token usage of 15,196 tokens ($0.0095 across 15 events in `runs/live_run/timing_summary.json`)."*
