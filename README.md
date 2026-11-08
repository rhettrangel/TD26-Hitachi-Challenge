# Hitachi Lumada JIT Autonomous Operations Control Tower
### TAMU Datathon 2026 | Hitachi Challenge — Supply Chain Resilience & Industrial AI

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests: 19 Passing](https://img.shields.io/badge/tests-19%20passed-brightgreen.svg)](tests/)
[![Deterministic Latency](https://img.shields.io/badge/latency-0.035s-orange.svg)](docs/timing_audit.md)
[![Zero-Inventory Policy](https://img.shields.io/badge/policy%20adherence-100%25-success.svg)](data/policy_handbook.md)

An autonomous, **neuro-symbolic multi-agent operations control tower** engineered to resolve sudden factory disruptions, supplier delays, and defective component lots across lean automotive assembly plants in under **40 milliseconds** with **zero simulator errors**.

---

## 🚀 Live Demo & Visuals

- **Executive Industrial Dashboard:** Open [`dashboard/index.html`](dashboard/index.html) in any browser (zero web dependencies, self-contained standard HTML5/CSS/JS).
- **Architecture & System Design:** See [`design_card.md`](design_card.md) and [`ontology_diagram.md`](ontology_diagram.md).
- **Submission Narrative:** See [`DEVPOST_SUBMISSION.md`](DEVPOST_SUBMISSION.md).

---

## 💡 The Problem: Domino Effects in JIT Manufacturing

Modern automotive manufacturing operates on **Just-In-Time (JIT)** principles with lean parts buffers and virtually **zero parts inventory**. Each factory builds in daily production sequences with fixed daily slot limits. Parts arrive in inbound shipments from over 20 suppliers, and finished vehicles ship directly to 50 regional dealerships to fulfill pre-sold customer orders.

When an unexpected event occurs—such as a customs delay on a camera chip, an assembly line software outage, or a batch of defective steering components—it triggers an immediate, multi-tier operational cascade:
- Production lines stall because assembly cannot run without parts.
- Overdue customer promises accumulate at dealerships.
- VIP loaner vehicle fleets face sudden regional exhaustion.
- Quarantined parts require simultaneous showroom stop-sale orders and safety recall campaigns.

Human planners spend hours manually cross-referencing Bills of Materials (BOMs), plant models, and customer orders. **Hitachi Lumada Control Tower automates this entire lifecycle autonomously with mathematical guarantees.**

---

## 🧠 System Architecture: Neuro-Symbolic Multi-Agent Design

To avoid pure-LLM pitfalls (hallucinated part identifiers, calendar arithmetic errors, and assembly slot overbooking), we designed a **Hybrid Neuro-Symbolic Architecture**:

```
[ Unstructured Disruption Feeds ] (Emails, chats, plant alerts, wire reports)
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 1. Perception Layer (Gemini 3 Flash Preview)           │
│    - Strict JSON Schema extraction (`response_schema`) │
│    - Temporal ISO normalization via `calendar.csv`     │
└────────────────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 2. Entity Grounding Layer (`resolve_entity`)           │
│    - Translates colloquial aliases to canonical IDs    │
│    - "Orbit" ➔ SUP-11 | "surround-view cameras" ➔ CAM-360
└────────────────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 3. Enterprise Knowledge Graph (`knowledge_graph.py`)   │
│    - 16,955 nodes (Plants, Models, Parts, Lots, VINs)  │
│    - Multi-hop BFS blast radius graph traversals       │
└────────────────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 4. Deterministic Policy Solver (`policy_engine.py`)    │
│    - Slot capacity invariants (<= slots_per_day)       │
│    - Priority loaner sorting (Platinum before Gold)    │
│    - Dealer notification batching & quarantine containment
└────────────────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 5. Multi-Agent Dispatch (`agents/`)                    │
│    ├── MES Planner Specialist (Reschedules & Transfers)│
│    ├── Dealer Network Specialist (Alerts & Stop-Sales) │
│    └── Customer Care Specialist (VIP Loaners & Recalls)│
└────────────────────────────────────────────────────────┘
                 │
                 ▼
[ Enterprise Simulator / Live Server (`POST /act`) ] ─── 0 Errors (100% Policy Pass)
```

---

## 📋 The 8 Core Operations Policies Enforced

Every action adheres strictly to the [Wacky Wheels Operations Policy Handbook](data/policy_handbook.md):

1. **Earliest Feasible Rescheduling:** Disrupted production orders move to the earliest available weekday slot $\ge$ `min_reschedule_date` at the same plant.
2. **Plant Capacity Invariant:** Daily plant assembly slot limits (`slots_per_day`) are strictly maintained.
3. **Emergency Plant Transfer:** If the home plant is at 100% capacity, orders transfer to an alternate plant that builds that vehicle model.
4. **Dealer Notification Consolidation:** Every dealer with affected customer orders receives exactly **one** consolidated `dealer.notify` action with deduplicated order IDs.
5. **VIP Loaner Prioritization & Pool Caps:** Affected Platinum and Gold customers receive loaners from their dealership's limited pool:
   $$\text{Platinum} \to \text{Gold} \to \text{Earlier Promised Date} \to \text{Lower Order ID}$$
   Standard tier customers receive zero loaners. Dealer pool caps are strictly enforced.
6. **Defective Lot Containment:** Quarantines the part lot (`quality.hold_lot`), stops sale of unsold vehicles by dealer (`dealer.stop_sale`), and notifies buyers of sold vehicles (`crm.notify_customer`).
7. **Noise Suppression (Rule 7):** Positively identified non-manufacturing inquiries trigger strictly **zero** write actions.
8. **Human-in-the-Loop Governance (Rule 8):** Ambiguous floor rumors trigger **zero** write actions and route directly to human supervisor review (`escalate`).

---

## 📊 Audited Benchmark Performance & Telemetry

All metrics trace directly to disk artifacts in [`runs/`](runs/) and audited reports in [`docs/`](docs/):

| Metric | Deterministic Baseline (`runs/cached_run/`) | Live LLM Run (`runs/live_run/` & `e09_fix/`) |
|---|:---:|:---:|
| **Model** | `deterministic_rule_engine` | `gemini-3-flash-preview` |
| **Total Tool Calls Executed** | **783 calls** | **783 calls** (42 in live e09 rerun) |
| **Simulator Errors** | **0 errors (100% policy pass)** | **0 errors** |
| **End-to-End Latency** | **0.0351 seconds** (in-memory) | **3.5s - 4.7s** (live cloud API) |
| **Automated Tests Passing** | **19 / 19 passed (100%)** | **19 / 19 passed** |
| **Billed Tokens (15 Events)** | 0 tokens | **22,911 total billed tokens** |
| **Commercial Inference Cost** | $0.000000 | **$0.033** ($0.50/1M in, $3.00/1M out) |

---

## 🛠️ Quickstart & Reproduction

### Prerequisites
- Python 3.9+ (Standard library only; zero external pip dependencies required to run the engine, dashboard, or tests).

### 1. Run the Automated Test Suite (19 Unit & Stress Tests)
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
*Executes all 19 tests in < 1.7 seconds, validating rule compliance, extreme plant saturation, loaner pool floods, 100 fuzzed synthetic events, and live HTTP socket communication.*

### 2. Run the Deterministic Control Tower
```bash
python3 runner.py --mode cached --out runs/my_run
```
*Replays all 15 benchmark events, producing `action_log.jsonl`, `event_traces.json`, and `timing_summary.json`.*

### 3. Run Live Multi-Agent Perception (with Gemini API)
```bash
# Requires GEMINI_API_KEY exported or in ~/.config/hitachi/.env
python3 runner.py --mode live --events E-05,E-09 --out runs/my_live_run
```

### 4. Launch the Local Enterprise Server
```bash
python3 enterprise_server.py --port 8000
```
*Serves `GET /events`, `GET /tools`, and `POST /act` over local HTTP.*

### 5. View the Industrial Dashboard
Open `dashboard/index.html` in your web browser.

---

## 📁 Repository Structure

```
├── README.md                      # Official project documentation
├── DEVPOST_SUBMISSION.md          # Complete Devpost narrative and demo video script
├── design_card.md                 # One-page architectural breakdown
├── ontology_diagram.md            # Formal domain ontology schema & Mermaid diagrams
├── runner.py                      # Multi-agent execution runner & CLI
├── knowledge_graph.py             # Enterprise knowledge graph engine (16,955 nodes)
├── policy_engine.py               # Deterministic policy & constraint solver
├── enterprise.py                  # Company simulator & ground-truth validation engine
├── enterprise_server.py           # Local HTTP enterprise simulation server
├── config.py                      # Model configuration & secure credential loader
│
├── agents/                        # Multi-Agent Coordination System
│   ├── coordinator.py             # Master Control Tower Coordinating Agent
│   ├── event_parser.py            # NLU parser & entity grounding layer
│   ├── llm_client.py              # Gemini structured JSON client
│   ├── mes_specialist.py          # Production rescheduling & plant transfers
│   ├── dealer_specialist.py       # Dealer network alerts & stop-sale orders
│   └── crm_quality_specialist.py  # VIP loaner allocation & recall notifications
│
├── dashboard/                     # Executive Industrial UI
│   ├── index.html                 # Compiled standalone industrial dark-mode UI
│   └── build_dashboard.py         # Dashboard HTML/CSS/JS generator
│
├── tests/                         # Automated Verification Suite (19 tests)
│   ├── test_policy_rules.py       # 9 tests enforcing the 8 operations rules
│   ├── test_stress_and_invariants.py # 9 stress tests (fuzzing, saturation, HTTP)
│   └── test_unrecognized_fallback.py # Ambiguous rumor escalation test
│
├── docs/                          # Audited Reports & Evidence
│   ├── timing_audit.md            # Timing breakdown & token accounting
│   ├── parser_agreement.md        # LLM vs deterministic category agreement
│   ├── pricing_source.md          # Pricing citations ($0.50/1M in, $3.00/1M out)
│   └── reconciliation_report.md   # Exact token & action log reconciliation
│
└── runs/                          # Audited Execution Runs & Raw Traces
    ├── cached_run/                # 783 deterministic actions (0.0351s wall-clock)
    ├── live_run/                  # 15-event live run with raw model responses
    └── live_run_e09_fix/          # Targeted live run with verified E-05 & E-09
```

---

## 👥 Authors
Built for the **TAMU Datathon 2026 Hitachi Challenge**.
