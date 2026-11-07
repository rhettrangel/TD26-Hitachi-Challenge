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

1. **Perception Layer (`gemini-1.5-flash`):** Ingests raw text, maps colloquial terms via `data/aliases.csv`, converts relative dates into ISO weekdays via `data/calendar.csv`, and requests structured JSON outputs.
2. **Knowledge Graph Engine (`knowledge_graph.py`):** Models the enterprise domain (Plants, Models, Parts, Lots, Orders, VINs) and performs runtime breadth-first traversals to identify impacted records.
3. **Deterministic Policy Solver (`policy_engine.py`):** Enforces handbook rules (slot caps, single dealer notifications, loaner priority) with mathematical guarantees.
4. **Specialist Dispatcher (`agents/`):** A 1 Coordinator + 3 Specialist agent structure interfacing with enterprise systems.
5. **Control Tower UI (`dashboard/`):** An executive dark-mode industrial dashboard featuring dynamic traversal cascade animations, customer-facing action cards, and escalation review queues.

---

### 📊 Verified Performance & Metrics

All metrics trace directly to `runs/cached_run/timing_summary.json` and `docs/timing_audit.md`:

* **Benchmark Accuracy:** **100% Policy Adherence (783 / 783 tool calls executed with 0 errors)** against the 15 benchmark events evaluated on the enterprise simulator.
* **Deterministic Pipeline Wall-Clock Latency:** **0.0396 seconds** for the full 15-event benchmark run (0.0352s planning + 0.0043s state execution).
* **Perception Latency:** 0.00s in cached/deterministic baseline mode. Live LLM perception latency depends on external API round-trip times.
* **Model Attribution:** `gemini-1.5-flash` (Perception) + Deterministic Policy Engine.
* **Computed Efficiency & Cost:**
  * Google AI Studio published rates (https://ai.google.dev/pricing, Nov 2024 / current): \$0.075 / 1M input tokens, \$0.30 / 1M output tokens.
  * Estimated Volume (15 events): 10,200 prompt tokens + 1,500 output tokens.
  * Computed Inference Cost: **\$0.001215** per full 15-event run.

---

### ⚠️ Limitations

1. **Benchmark Scope:** The 15 test events were provided as part of the challenge scenario. The ground-truth policy rules reflect the challenge specification.
2. **Perception Generalization:** LLM perception accuracy on messy text outside the provided 15 events and `aliases.csv` mappings has not been independently evaluated on unseen external datasets.
3. **Latency Benchmarking:** The 0.0396s figure represents local in-memory graph traversal and simulator execution. It does not measure external internet latency or live cloud API round trips (detailed in `docs/timing_audit.md`).

---

### 🎥 2-Minute Demo Video Walkthrough Script

* **[0:00 - 0:30] Context:** Open dashboard. *"Welcome to the Hitachi Lumada Control Tower. Wacky Wheels Co. builds vehicles Just-In-Time with zero parts inventory. A late shipment, factory blackout, or defective lot causes an immediate domino effect. Here is how our 1 Coordinator + 3 Specialist agents handle it."*
* **[0:30 - 1:00] Supplier Delay:** Click **E-12 (Supplier Delay)**. Show the Knowledge Graph traversing `Shipment SH-0182 → CAM-360 → Summit → PO-0316 → Customer Orders → Dealer D07`. In **Executive & Actions**, show the rescheduled build slot, the consolidated dealer alert, and the VIP loaner deployment.
* **[1:00 - 1:30] Quality Containment:** Click **E-15 (Quality Hold)**. Show how defective Lot LOT-0191 is held, triggering showroom stop-sale orders across 25 dealerships and safety recall notifications to owners of sold vehicles.
* **[1:30 - 2:00] Guardrails & Telemetry:** Click **E-05 (Noise)** to demonstrate zero write actions, and **E-02 (Rumor)** to show the Human-in-the-Loop escalation panel. Click **DevPost & Judging Brief** in the header to show the verified metrics: *"783 automated actions, 0 errors against the benchmark, and an audited deterministic pipeline latency of 0.0396s."*
