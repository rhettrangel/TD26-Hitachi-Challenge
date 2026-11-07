# Timing & Telemetry Audit Report: Wacky Wheels Control Tower

**Date:** 2026-11-07  
**Auditor:** Verification & Compliance Pipeline  
**Target:** `runner.py`, `agents/coordinator.py`, `agents/event_parser.py`, `agents/llm_client.py`, `enterprise.py`  
**Referenced Artifacts:** `runs/run1/timing_summary.json`, `runs/cached_run/timing_summary.json`

---

## 1. What the "0.04 Seconds" Figure Actually Measured

In `runner.py` (lines 92–117), a wall-clock timer wrapped the execution loop across all 15 events:

```python
t_start = time.time()
for i, event in enumerate(events, start=1):
    res = coordinator.process_event(event, client)
elapsed = time.time() - t_start
```

### Scope of the Timer
* **Included in 0.04s:**
  1. Regex/rule-based string pattern matching in `event_parser.py` across 15 event text payloads.
  2. In-memory Knowledge Graph traversals (BFS/dictionary lookups) across 16,955 nodes in `knowledge_graph.py`.
  3. In-memory deterministic policy constraint solving (slot assignment, loaner prioritization) in `policy_engine.py`.
  4. In-memory state mutations in `Enterprise` across 783 tool calls using `DirectSimulatorClient`.
  5. File I/O: 783 JSON lines written to `runs/run1/action_log.jsonl` and saving `runs/run1/event_traces.json`.
* **NOT Included in 0.04s:**
  1. **Zero LLM API calls:** No external or local LLM inference was executed within the timer.
  2. **Zero network calls:** `DirectSimulatorClient` executed in-process; no HTTP sockets to `enterprise_server.py` were opened.

---

## 2. LLM Perception Analysis: Live vs Cached vs Rule-Based

* **Were live LLM calls made during the 0.04s run?** **No.**
* **Did the parser read from a precomputed cache or fixture file?** **No.**
* **What generated the perceptions?** `agents/event_parser.py` executed Python regular expressions (`re.search`) and dictionary lookups against `data/aliases.csv` directly in memory.
* **Finding:** Prior marketing claims attributing the 0.04s execution speed to "Gemini 1.5 Flash inference" were inaccurate. The 0.04s measured only the local, deterministic Python pipeline.

---

## 3. Audited Timing Breakdown (From `runs/run1/timing_summary.json`)

Instrumentation was added to `runner.py` to decouple each phase per event:

| Metric | Measured Value | Description |
| :--- | :--- | :--- |
| **Total Wall-Clock Time** | **0.0405 s** | Full end-to-end replay for all 15 events. |
| **LLM Perception Time** | **0.0000 s** | Baseline cached/deterministic mode (0 live API calls). |
| **Deterministic Pipeline Time** | **0.0361 s** | Graph traversal (0.015s) + Policy constraint solving (0.021s). |
| **Tool Execution Time** | **0.0041 s** | In-memory simulator mutations across 783 tool calls. |
| **Tool Calls Executed** | **783 calls** | 0 failed calls (100% Policy Adherence on benchmark). |

### Per-Event Breakdown (Sample Events)
* **E-01 (Compound: Outage + Delay):** 96 actions | Det: 4.3ms | Total Event Wall: 6.7ms
* **E-02 (Unconfirmed Rumor):** 1 action (`escalate`) | Det: 0.4ms | Total Event Wall: 0.4ms
* **E-03 (Quality Hold):** 188 actions | Det: 8.4ms | Total Event Wall: 8.7ms
* **E-05 (Noise):** 0 actions | Det: 0.2ms | Total Event Wall: 0.2ms
* **E-08 (Plant Outage):** 46 actions | Det: 2.2ms | Total Event Wall: 2.4ms
* **E-12 (Supplier Delay):** 27 actions | Det: 1.3ms | Total Event Wall: 1.5ms

---

## 4. Structured Output Schema & Malformed Response Handling

Perception requests enforce structured JSON using the schema in `agents/llm_client.py`:

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

### Real Parsed Sample Output (Event E-12)
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

### Malformed Output & Failure Code Path
1. `agents/llm_client.py` wraps `urllib.request` in `try...except (urllib.error.HTTPError, json.JSONDecodeError, Exception)`.
2. If an API call fails or JSON is malformed, it records `metrics["error"]` and returns `None`.
3. `agents/event_parser.py` detects `incidents_raw is None`, flags `metrics["fallback_used"] = True`, and seamlessly triggers the deterministic rule-based parser.
4. If the fallback parser encounters an unrecognized text pattern, it defaults to:
   `category: "Noise", reason: "Unrecognized event pattern"`, ensuring zero unauthorized write actions on the manufacturing schedule.

---

## 5. Token & Cost Accounting

* **Model String:** `gemini-1.5-flash`
* **Pricing Reference:** Google AI Studio Published Pricing (`https://ai.google.dev/pricing`), verified Nov 2024 / current:
  * Input tokens ($\le 128k$): **\$0.075 / 1,000,000 tokens** (\$0.000000075 / token)
  * Output tokens ($\le 128k$): **\$0.30 / 1,000,000 tokens** (\$0.00000030 / token)
* **Estimated Usage across 15 Benchmark Events:**
  * Prompt Tokens: ~10,200 tokens (15 requests $\times$ ~680 tokens including system prompt & entity catalog).
  * Output Tokens: ~1,500 tokens (15 responses $\times$ ~100 tokens structured JSON).
  * Total Tokens: ~11,700 tokens.
* **Computed Cost:**
  $$\text{Cost} = (10,200 \times \$0.000000075) + (1,500 \times \$0.00000030) = \$0.000765 + \$0.000450 = \$0.001215$$
* **Result:** \$0.001215 per full 15-event benchmark run (approx. 0.12 cents).
