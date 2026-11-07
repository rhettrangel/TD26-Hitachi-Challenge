# CHANGELOG: Timing, Attribution & Verification Fixes

**Date:** 2026-11-07  
**Objective:** Audit timing, correct model attribution, enforce verifiable telemetry, and remove unverified or promotional claims.

---

### Files Touched & Summary of Changes

1. **`docs/timing_audit.md` (Created)**
   * **Why:** Fulfills Step 1 by investigating and reporting what the "0.04s" figure actually measured.
   * **Details:** Disclosed that the 0.04s figure measured only in-memory deterministic processing (regex string matching, graph traversals, policy constraint solving, in-memory simulator mutations, and file I/O). Documented that zero live LLM API calls and zero network requests occurred during that run.

2. **`agents/llm_client.py` (Created)**
   * **Why:** Implements live Gemini API connectivity (`gemini-1.5-flash`) with structured JSON schema enforcement, error handling, token accounting, and per-event latency measurement.
   * **Details:** Formats prompts with company entity aliases and calendar context, requests `response_mime_type: "application/json"`, extracts `usageMetadata` (prompt & candidate tokens), and catches API/parse errors to fall back gracefully to the deterministic engine.

3. **`agents/event_parser.py` (Modified)**
   * **Why:** Connects `GeminiPerceptionClient` to the parser workflow while preserving deterministic fallback capabilities.
   * **Details:** Added `use_live_llm` toggle. When enabled, attempts structured LLM perception first; if an error or malformed JSON occurs, logs the event and triggers the deterministic rule-based parser. Returns `(incidents, telemetry_metrics)`.

4. **`agents/coordinator.py` (Modified)**
   * **Why:** Instrument per-event execution telemetry and pass configuration flags.
   * **Details:** Decouples `llm_perception_time_ms` from `deterministic_time_ms`. Adds token counts and model attribution to `EventProcessingResult.to_dict()`.

5. **`runner.py` (Modified)**
   * **Why:** Fulfills Step 2 by adding call-by-call timing instrumentation, token reporting, and cost calculation.
   * **Details:** Implemented `InstrumentedHttpClient` and `InstrumentedDirectClient`. Decoupled and reported:
     * LLM perception time per event
     * Deterministic pipeline time per event
     * Tool call execution time (in-memory simulator or HTTP server)
     * Total wall-clock time
     Outputs audited breakdown to `<out>/timing_summary.json`.

6. **`design_card.md` (Modified)**
   * **Why:** Fulfills Steps 3, 4, and 5 by correcting model attribution, updating timing/cost metrics, and adding limitations.
   * **Details:**
     * Model cited: Exclusively `gemini-1.5-flash` for perception, alongside the deterministic policy solver.
     * Removed all self-promotional text, "1st place" framing, and unverified latency claims.
     * Replaced "fractions of a cent" with computed cost of **\$0.001215** per 15-event run at published Google AI Studio rates (\$0.075/1M in, \$0.30/1M out), citing source and date.
     * Included real structured JSON schema and sample parsed response (E-12).
     * Scoped accuracy claim to the 15 benchmark events (783 / 783 tool calls executed with 0 errors).
     * Added explicit **Limitations** section.

7. **`DEVPOST_SUBMISSION.md` (Modified)**
   * **Why:** Fulfills Steps 3, 4, and 5 for DevPost documentation.
   * **Details:** Removed all hyperbole and self-promotional framing. Updated latency, model attribution (`gemini-1.5-flash`), cost computation, and scoped benchmark accuracy. Added explicit **Limitations** section.

8. **`dashboard/build_dashboard.py` & `dashboard/index.html` (Modified)**
   * **Why:** Synchronized dashboard KPI telemetry and judging rubric modal with audited metrics.
   * **Details:** Updated KPI headers to show "0.04s (In-Memory)", "0 Errors (783/783 OK)", and labeled the modal as "System Overview & Audited Metrics", removing unverified marketing claims.

9. **`runs/cached_run/` & `runs/run1/` (Generated)**
   * **Why:** Provides transparent, verifiable run artifacts.
   * **Details:** Stores `action_log.jsonl`, `event_traces.json`, and `timing_summary.json` containing exact microsecond-level timing and token counts.
