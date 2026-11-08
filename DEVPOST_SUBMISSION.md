# DevPost Submission: Hitachi Lumada Autonomous JIT Control Tower

**Project Title:** Hitachi Lumada: Autonomous JIT Operations Control Tower  
**Tagline:** Autonomous, neuro-symbolic multi-agent operations control tower resolving supply chain disruptions and factory outages in under 40ms with zero errors.  
**Track:** Hitachi Track / Challenge: Industrial AI / Supply Chain Resilience  
**Built With:** `python`, `gemini-flash`, `multi-agent-systems`, `knowledge-graph`, `constraint-programming`, `autonomous-agents`, `just-in-time`, `supply-chain`, `neuro-symbolic-ai`, `html5`, `css3`, `javascript`  
**GitHub Repository:** [https://github.com/rhettrangel/TD26-Hitachi-Challenge](https://github.com/rhettrangel/TD26-Hitachi-Challenge)  
**Demo Video:** [https://www.youtube.com/watch?v=nwJWi1T06o0](https://www.youtube.com/watch?v=nwJWi1T06o0)  

[![Watch the Demo Video](https://img.youtube.com/vi/nwJWi1T06o0/maxresdefault.jpg)](https://www.youtube.com/watch?v=nwJWi1T06o0)

---

### 💡 Inspiration
Hitachi focuses on **Industrial AI and IT/OT convergence**—bridging physical industrial operations (assembly plants, inbound logistics, supply chains) with enterprise platforms.

In automotive manufacturing, **Just-In-Time (JIT) production operates with zero parts inventory**. Components arrive on the day of assembly. While cost-efficient, JIT makes manufacturing fragile: a delayed shipment of infotainment chips, a plant power outage, or a contaminated wiring harness ripples immediately across production schedules, 50 regional dealerships, and hundreds of customer deliveries.

Human supply chain planners are overwhelmed with fragmented emails, chat messages, and PDF bulletins, spending hours manually cross-referencing Bills of Materials (BOMs), assembly lines, and customer orders. We built the **Hitachi Lumada Autonomous Operations Control Tower** to evaluate how an event-driven multi-agent architecture can automate disruption mitigation and maintain policy compliance under strict operational constraints in real time.

---

### ⚙️ What It Does

The Control Tower autonomously manages the end-to-end operational lifecycle for Wacky Wheels Co. across 6 assembly plants, 6 vehicle models, 50 dealerships, and thousands of customer orders:

1. **Operational Feed Intake:** Ingests unstructured operational communications (chat messages, plant alerts, supplier emails, digests) containing informal phrasing and relative dates.
2. **Noise Filtering & Human-in-the-Loop Escalation:** Ignores non-operational inquiries (e.g. dealership brochure requests) with **zero write actions** (Rule 7), and routes unconfirmed rumors to supervisors via the `escalate` tool (Rule 8).
3. **Knowledge Graph Traversal (16,955 Nodes):** Computes the exact operational blast radius across plants, bills of materials (BOM), part lots, and customer orders, generating verifiable citation paths:
   $$\text{Shipment} \to \text{Part} \to \text{Model (BOM)} \to \text{ProductionOrder} \to \text{CustomerOrder} \to \text{Dealer / Customer}$$
4. **Autonomous Action Execution Across 3 Specialist Agents:**
   * **MES Planner Specialist:** Reschedules builds to the earliest feasible slot ($\le 5$ slots/day) or transfers orders to authorized sister plants when factories reach 100% capacity.
   * **Dealer Network Specialist:** Consolidates delayed customer orders into **exactly one notification per affected dealership** and issues stop-sale holds on quarantined vehicles.
   * **Customer Care & Quality Specialist:** Quarantines defective part lots, alerts owners of sold vehicles for safety recalls, and executes loaner car triage (Platinum $\to$ Gold $\to$ promised date $\to$ order ID) within strict dealer pool limits.

---

### 🧠 System Architecture & Implementation

The platform uses a hybrid **Neuro-Symbolic architecture** to avoid pure-LLM pitfalls (hallucinated identifiers, slot overbooking, and calendar math errors):

1. **Perception Layer (`gemini-3-flash-preview`):** Ingests raw text, maps colloquial terms via `data/aliases.csv`, converts relative dates into ISO weekdays via `data/calendar.csv`, and requests structured JSON outputs via strict schemas (`response_schema`).
2. **Entity Grounding Layer (`agents/event_parser.py`):** Automatically grounds colloquial model extractions (`Orbit` $\to$ `SUP-11`, `surround-view cameras` $\to$ `CAM-360`, `Huntsville` $\to$ `P_AL`) to canonical enterprise IDs.
3. **Knowledge Graph Engine (`knowledge_graph.py`):** Models the enterprise domain (Plants, Models, Parts, Lots, Orders, VINs) and performs runtime breadth-first traversals to identify impacted records.
4. **Deterministic Policy Solver (`policy_engine.py`):** Enforces handbook rules (slot caps, single dealer notifications, loaner priority) with mathematical guarantees.
5. **Specialist Dispatcher (`agents/`):** A 1 Coordinator + 3 Specialist agent structure interfacing with enterprise systems.
6. **Control Tower UI (`dashboard/`):** An executive industrial dashboard featuring dynamic traversal cascade animations, customer-facing action cards, and escalation review queues.

---

### 📊 Verified Performance & Metrics

All metrics trace directly to `runs/live_run/timing_summary.json`, `runs/cached_run/timing_summary.json`, `docs/parser_agreement.md`, and `docs/pricing_source.md`:

* **Benchmark Accuracy:** Scoped across the 15 team-authored ground-truth events:
  * Deterministic Layer: **783 / 783 tool calls executed with 0 errors** in the deterministic baseline against the enterprise simulator (`runs/cached_run/action_log.jsonl`).
  * LLM Perception Agreement: 14 of 15 live calls succeeded (HTTP 200) in the initial full run; E-15 returned HTTP 429 (free-tier daily quota) and fell back to deterministic parsing. Across the 14 successful calls (100%), the model agreed on event category with the deterministic baseline parser.
  * Field-level extraction resolution: Following our prompt update and entity grounding layer, a live rerun of E-09 against `gemini-3-flash-preview` (`runs/live_run_e09_fix/raw/E-09.json`, HTTP 200 OK) successfully extracted `supplier_id: "Orbit"` and `part_id: "surround-view cameras"`, resolved them to canonical IDs `SUP-11` and `CAM-360`, and executed all 42 operational actions with 0 errors.
* **Timing Breakdown:**
  * **Live Gemini Run (`runs/live_run/`):** **53.3218 s** total wall-clock time (37.33s LLM round-trip perception time summed from `runs/live_run/timing_summary.json`, 0.0523s deterministic pipeline, 0.0087s action execution).
  * **Deterministic Baseline (`runs/cached_run/`):** **0.0357 s** total wall-clock time (deterministic only, zero LLM calls, zero network calls).
* **Automated Verification:** **19 / 19 unit & stress tests passing** in under 1.7 seconds (`tests/test_policy_rules.py` and `tests/test_stress_and_invariants.py`), including 100 synthetic fuzzed events, 100% capacity saturation across 5 plants, and live TCP execution against `enterprise_server.py`.
* **Model Attribution:** `gemini-3-flash-preview` (Perception) + Deterministic Policy Engine.
* **Computed Commercial Efficiency & Cost:**
  * Google AI Studio published rates (`https://ai.google.dev/pricing`, retrieved 2026-11-07): $0.50 / 1M input tokens, $3.00 / 1M output tokens.
  * Measured Volume (15 events): 14,445 prompt tokens + 751 output tokens (+ 7,715 thinking tokens) = 22,911 total billed tokens.
  * Computed Commercial Inference Cost: **$0.033** (computed as $(14{,}445 \times \$0.0000005) + ((751 + 7{,}715) \times \$0.000003) = \$0.03262$ per full 15-event run).

---

### ⚠️ Limitations

1. **Benchmark Scope:** The 15 test events were hand-written by the team; the ground truth was built by the same team.
2. **Perception Generalization:** LLM perception accuracy on messy real-world text outside the 15 team-authored events has not been measured independently.
3. **Latency Benchmarking:** The 0.0357s figure represents local in-memory deterministic processing only. Real API calls are subject to external network latency (37.33s total LLM perception time summed from `runs/live_run/timing_summary.json`).
4. **Pricing Citation:** Commercial pricing rates were retrieved from Google AI Studio on 2026-11-07 ($0.50/1M input, $3.00/1M output).

---

### 🎥 2-Minute Demo Video

Watch the complete autonomous control tower walkthrough:  
▶️ **[Hitachi Lumada JIT Control Tower Demo Video](https://www.youtube.com/watch?v=nwJWi1T06o0)**  
URL: `https://www.youtube.com/watch?v=nwJWi1T06o0`
