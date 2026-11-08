# Timing & Telemetry Audit Report: Wacky Wheels Control Tower

**Date:** 2026-11-07  
**Auditor:** Verification & Compliance Pipeline  
**Target:** `runner.py`, `agents/coordinator.py`, `agents/event_parser.py`, `agents/llm_client.py`, `enterprise.py`  
**Referenced Artifacts:** `runs/cached_run/timing_summary.json`, `runs/live_run/timing_summary.json`

---

## 1. What the "0.04 Seconds" Figure Actually Measured

In `runner.py`, the initial figure of approximately 0.04 seconds (specifically 0.0357 seconds in `runs/cached_run/timing_summary.json`) produced by the execution timer wrapped only the local deterministic Python pipeline:

```python
t_start = time.time()
for i, event in enumerate(events, start=1):
    res = coordinator.process_event(event, client)
elapsed = time.time() - t_start
```

### Scope of the Timer
* **Included in 0.04s:**
  1. Regex and rule-based pattern matching in `event_parser.py` across 15 event text payloads.
  2. In-memory Knowledge Graph traversals (BFS and dictionary lookups) across 16,955 nodes in `knowledge_graph.py`.
  3. In-memory deterministic policy constraint solving (slot assignment, loaner prioritization) in `policy_engine.py`.
  4. In-memory state mutations in `Enterprise` across 783 tool calls in the deterministic baseline using `InstrumentedDirectClient`.
  5. File I/O: 783 JSON lines written to `action_log.jsonl` in the deterministic baseline and writing `event_traces.json`.
* **NOT Included in 0.04s:**
  1. **Zero LLM API calls:** No external or local LLM inference was executed within that timer.
  2. **Zero network calls:** `InstrumentedDirectClient` executed in-process; no HTTP sockets were opened.

---

## 2. LLM Perception Analysis: Live vs Deterministic Baseline

* **Were live LLM calls made during the 0.04s run?** **No.**
* **Did the parser read from a precomputed cache or fixture file?** **No.**
* **What generated the perceptions in that baseline run?** `agents/event_parser.py` executed Python regular expressions (`re.search`) and dictionary lookups directly against `data/aliases.csv` in memory.
* **Live Run Verification:** A full live run was captured in `runs/live_run/` using `gemini-3-flash-preview` on Google AI Studio's API endpoint, recording call-by-call prompts, raw responses, latencies, and token counts.

---

## 3. Honest Timing Breakdown: Live vs Deterministic

| Metric | Live Gemini Run (`runs/live_run/`) | Deterministic Baseline (`runs/cached_run/`) | Description |
| :--- | :--- | :--- | :--- |
| **Model Used** | `gemini-3-flash-preview` | `deterministic_rule_engine` | Model string called by coordinator. |
| **Total Wall-Clock Time** | **53.3218 s** | **0.0357 s** | Total time across all 15 events. |
| **LLM Perception Time** | **37.33 s** (Summed from `runs/live_run/timing_summary.json`) | **0.0000 s** | Real API round-trip latency. |
| **Deterministic Pipeline Time** | **0.0523 s** | **0.0314 s** | Graph traversal + policy solving. |
| **Action Execution Time** | **0.0087 s** | **0.0042 s** | In-memory simulator action dispatch. |
| **Tool Calls Executed** | **741 calls** (live run: E-15 failed with HTTP 429 and E-09 produced 0 live actions) | **783 calls** (deterministic baseline) | Executed write operations. |
| **Failed Tool Calls** | **0 calls** | **0 calls** | Zero policy violations. |
| **Total Tokens** | **14,445 prompt / 751 output** | **0 prompt / 0 output** | Measured from `usageMetadata`. |
| **Computed Cost** | **$0.033** | **$0.000000** | Standard published rates ($0.50/1M in, $3.00/1M out, including thinking tokens). |

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
          "category": {
            "type": "STRING",
            "enum": [
              "Supplier Delay",
              "Plant Outage",
              "Quality Hold",
              "Noise",
              "Unconfirmed Report"
            ]
          },
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
        "required": ["category", "supplier_id", "part_id"]
      }
    }
  },
  "required": ["incidents"]
}
```

### Real Parsed Sample Output (Event E-12)
*Source File: `runs/live_run/raw/E-12.json`*
```json
{
  "event_id": "E-12",
  "model": "gemini-3-flash-preview",
  "wall_clock_latency_ms": 3791.42,
  "http_status": 200,
  "usageMetadata": {
    "promptTokenCount": 1081,
    "candidatesTokenCount": 75,
    "totalTokenCount": 1844
  },
  "parsed_incidents": [
    {
      "category": "Supplier Delay",
      "end_date": "2027-03-18",
      "part_id": "CAM-360",
      "plant_id": "P_IN",
      "reason": "port congestion",
      "shipment_id": "SH-0182",
      "start_date": "2027-03-15"
    }
  ]
}
```

### Malformed Output & Failure Code Path
1. `agents/llm_client.py` wraps `urllib.request` in `try...except (urllib.error.HTTPError, json.JSONDecodeError, Exception)`.
2. If an API call fails or JSON is malformed, it records `metrics["error"]` and returns `None`.
3. `agents/event_parser.py` detects `incidents_raw is None`, flags `metrics["fallback_used"] = True`, and seamlessly triggers the deterministic rule-based parser.
4. If the fallback parser encounters an unrecognized text pattern, it defaults to:
   `category: "Unconfirmed Report", reason: "Unrecognized or ambiguous operational pattern; routed to supervisor review per Policy Rule 8"`, ensuring zero unauthorized operational writes and exactly one escalation.

---

## 5. Token & Cost Accounting

* **Model String:** `gemini-3-flash-preview`
* **Pricing Reference:** Google AI Studio Published Pricing (`https://ai.google.dev/pricing`), retrieved 2026-11-07 (documented in `docs/pricing_source.md`):
  * Input tokens: **$0.50 / 1,000,000 tokens** ($0.0000005 per token)
  * Output tokens (including thinking tokens): **$3.00 / 1,000,000 tokens** ($0.000003 per token)
* **Measured Token Counts Across Successful Live Calls:**
  * Input (Prompt) tokens: **14,445**
  * Candidate (Output) tokens: **751**
  * Thought tokens: **7,715**
  * Total billed tokens: **22,911**
* **Computed Commercial Cost per Full 15-Event Replay (Method B - Including Thinking Tokens):**
  $$\text{Cost} = (14{,}445 \times \$0.0000005) + ((751 + 7{,}715) \times \$0.000003) = \$0.0072225 + \$0.025398 = \mathbf{\$0.0326205}\text{ (approx. }\mathbf{\$0.033}\text{)}$$
