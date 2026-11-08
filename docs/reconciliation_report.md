# Live Run & Token Reconciliation Report

**Date:** 2026-11-07  
**Status:** Audit & Reconciliation (No changes to claims or control code)  
**Target Files Inspected:**  
- `runs/cached_run/action_log.jsonl`
- `runs/live_run/action_log.jsonl`
- `runs/live_run/timing_summary.json`
- `runs/live_run/raw/*.json` (15 files)
- `agents/llm_client.py`
- `docs/pricing_source.md`
- `docs/timing_audit.md`
- `design_card.md`
- `DEVPOST_SUBMISSION.md`
- `dashboard/build_dashboard.py`

---

## 1. Source Values vs. Documentation Comparison

| Item | Value in Source File | Value in Docs | Match? | Source Citation & Notes |
| :--- | :--- | :--- | :---: | :--- |
| **Deterministic Tool Calls** | 783 | 783 | **Yes** | `wc -l runs/cached_run/action_log.jsonl` = 783. Docs (`DEVPOST_SUBMISSION.md`, `design_card.md`, `dashboard/`) cite 783. |
| **Live Run Tool Calls (Disk)** | 741 | 741 / 783 | **Partial** | `wc -l runs/live_run/action_log.jsonl` = 741. `docs/timing_audit.md` table correctly lists 741 for live run; text summaries in other docs highlight 783 for deterministic baseline. |
| **Live Run Tool Calls (JSON)** | 741 | 741 | **Yes** | `runs/live_run/timing_summary.json` (`total_tool_calls_executed`) = 741. |
| **Raw Live Response Files** | 15 files | 15 files | **Yes** | `ls runs/live_run/raw/` has 15 files (`E-01.json` through `E-15.json`). |
| **Successful Live Calls (HTTP 200)** | 14 calls | 14 calls | **Yes** | 14 files returned HTTP 200; `E-15.json` returned HTTP 429 (`RESOURCE_EXHAUSTED`). |
| **Prompt Tokens (HTTP 200 Sum)** | 14,445 | 14,445 | **Yes** | Sum of `usageMetadata.promptTokenCount` across 14 HTTP 200 raw files. Matches `runs/live_run/timing_summary.json` and docs. |
| **Candidate Output Tokens (HTTP 200 Sum)** | 751 | 751 | **Yes** | Sum of `usageMetadata.candidatesTokenCount` across 14 HTTP 200 raw files. Matches `runs/live_run/timing_summary.json` and docs. |
| **Thinking Tokens (HTTP 200 Sum)** | 7,715 | Not listed | **No** | Present in raw `response.usageMetadata.thoughtsTokenCount` across the 14 calls; omitted in root `timing_summary.json` output token count. |
| **Total Tokens (usageMetadata sum)** | 22,911 | 15,196 | **No** | API `totalTokenCount` sums prompt (14,445) + candidates (751) + thoughts (7,715) = 22,911. Docs cite prompt + candidates = 15,196. |
| **Commercial Cost (Billed, incl. Thinking)** | $0.0326205 | $0.033 | **Yes** | $(14{,}445 \times \$0.50/1\text{M}) + (8{,}466 \times \$3.00/1\text{M}) = \$0.0326205$. Thinking tokens (7,715) derived as total − prompt − candidates. Paid Standard rates; free tier charge is $0. |
| **Commercial Cost (Incl. Thoughts)** | $0.0326205 | Not cited | **No** | Calculated as $(14{,}445 \times \$0.50/1\text{M}) + ((751 + 7{,}715) \times \$3.00/1\text{M}) = \$0.0326205$ (~3.26 cents). |
| **Live Total Wall-Clock Time** | 53.3218 s | 53.3218 s | **Yes** | `runs/live_run/timing_summary.json` line 5. Cited identically in `docs/timing_audit.md` and `DEVPOST_SUBMISSION.md`. |
| **Live LLM Perception Time** | 37.3256 s (runner batch) / 45.20 s (backoff raw sum) | 45.20 s | **Mismatch** | `runs/live_run/timing_summary.json` records 37.3256 s from the initial batch run. Docs cite 45.20 s (sum of latencies from subsequent backoff calls for E-11, E-13, E-14). |
| **Live Deterministic Pipeline Time** | 0.0523 s | 0.0523 s | **Yes** | Matches across `timing_summary.json`, `docs/timing_audit.md`, and `DEVPOST_SUBMISSION.md`. |

---

## 2. Open Questions & Resolution Paths

### A. Thinking-Token Billing & Cost Sourcing
* **Finding:**
  The official pricing page at [https://ai.google.dev/pricing](https://ai.google.dev/pricing) explicitly states:
  > *"Output price (including thinking tokens) | Free Tier: Free of charge | Paid Tier: $3.00"*
* **Corrected Calculation:**
  Thinking tokens are billed at the output rate. Derived from usage metadata as total − prompt − candidates:
  $$\text{Cost}_{\text{billed}} = (14{,}445 \times \$0.0000005) + (8{,}466 \times \$0.000003) = \$0.0072225 + \$0.025398 = \$0.0326205\text{ (~3.3 cents)}$$
  The earlier figure of $0.0094755 excluded thinking tokens and is superseded.
* **Resolution:**
  Decide whether documentation should cite **Candidate Tokens Only** ($15{,}196$ tokens, $\$0.0095$) or **Total Billed Tokens** ($22{,}911$ tokens including thinking, $\$0.0326$), and explicitly footnote the breakdown.

---

### B. Schema Configuration for E-09 (Supplier & Part Fields)
* **Finding:**
  In `agents/llm_client.py`, the `PERCEPTION_JSON_SCHEMA` defines `supplier_id` and `part_id`:
  ```python
  "properties": {
      "category": {"type": "STRING", "enum": [...]},
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
  ```
  While `supplier_id` and `part_id` are declared in properties, they are **optional** (only `category` is in `"required"`).
* **Model Output on E-09:**
  In `runs/live_run/raw/E-09.json`, the model returned:
  ```json
  {"category": "Supplier Delay", "end_date": "2027-04-01", "plant_id": "P_AL", "reason": "customs inspection", "start_date": "2027-03-29"}
  ```
  The schema *requests* `supplier_id` and `part_id` as optional schema properties, but the model chose to omit them, causing the live pipeline to take 0 actions instead of 42.
* **Resolution:**
  Documentation accurately notes this caveat. If required for submission, the prompt/schema can be maintained with this behavior clearly documented in `docs/parser_agreement.md`.

---

### C. Live Run Tool Call Count vs. Deterministic Tool Call Count (741 vs 783)
* **Finding:**
  - `runs/cached_run/action_log.jsonl` contains **783 lines** (tool calls).
  - `runs/live_run/action_log.jsonl` contains **741 lines** (tool calls).
  - Difference: Exactly $783 - 741 = 42$ tool calls, corresponding to E-09 (42 rescheduled production orders in deterministic mode vs 0 in live mode due to omitted supplier/part fields).
* **Resolution:**
  Ensure all documents distinguish between:
  1. *Deterministic Replay Benchmark:* 783 tool calls executed with 0 simulator errors.
  2. *Live LLM Replay:* 741 tool calls executed with 0 simulator errors (42 fewer actions due to E-09 sub-field omission).

---

### D. Timing Summary Discrepancy (37.33 s vs 45.20 s)
* **Finding:**
  In `runs/live_run/timing_summary.json`, `total_llm_perception_seconds` is **37.3256 s**, which was captured during the single end-to-end batch execution before the manual paced backoff was executed for E-11, E-13, and E-14.
  The sum of the latest individual raw files in `runs/live_run/raw/` is **45.20 s**.
* **Resolution:**
  Clarify in `docs/timing_audit.md` whether the timing represents the single uninterrupted batch run (37.33 s) or the sum of the individually verified live responses (45.20 s).
