# Summary of Audit, Verification & Code Remediation Fixes

This document records all modifications made to ensure that timing figures, model attribution, fallback behaviors, and performance metrics are verifiable against disk artifacts.

---

## Files Modified & Created

### 1. Configuration & Security
* **`config.py` (New):**
  * Created single source-of-truth configuration constant `MODEL_NAME = "gemini-3-flash-preview"` (the active, listed Flash model supporting structured JSON schema output with verified quota).
  * Implemented secure `get_gemini_api_key()` to read `GEMINI_API_KEY` from `~/.config/hitachi/.env` or process environment.
  * Ensures API keys are never printed, logged, or written to disk. Raises explicit `RuntimeError` if missing or placeholder `keyhere`.

### 2. Execution & Instrumentation
* **`runner.py` (Modified):**
  * Added `--mode live` and `--mode cached` execution flags.
  * Separated timing measurement into per-event:
    * `llm_perception_time_ms` (external API latency)
    * `deterministic_pipeline_time_ms` (graph traversal and policy solving)
    * `total_action_execution_seconds` (simulator mutations)
    * `total_wall_clock_seconds`
  * Added token accumulation and pricing formula computation based on retrieved Google AI Studio rates ($0.50/1M prompt, $3.00/1M output).
  * Directs live prompts to `runs/live_run/prompts/` and raw responses to `runs/live_run/raw/`.
* **`agents/llm_client.py` (New):**
  * Implemented `GeminiPerceptionClient` with structured JSON schema (`response_schema`), saving raw responses and exact prompt texts.
  * Enforces retry logic (max 2 retries) on transient errors.
* **`agents/coordinator.py` (Modified):**
  * Configured coordinator to pass prompt and raw output directories to parser and specialist agents.
* **`agents/event_parser.py` (Modified):**
  * Step 3 Unrecognized Event Default: Updated unclassified/ambiguous fallback to route to `category="Unconfirmed Report"` (TC6 escalation path, zero operational writes), eliminating default assignment to `Noise`.
  * Preserved positive identification of brochure requests (E-05, E-06, E-07) as `Noise`.

### 3. Verification Artifacts & Test Suites
* **`docs/model_availability.json` (New):**
  * Full JSON list response from `https://generativelanguage.googleapis.com/v1beta/models` (API key redacted), documenting retrieval date (2026-11-07), target model availability, and selection of `gemini-3-flash-preview`.
* **`docs/pricing_source.md` (New):**
  * Documents the source URL (`https://ai.google.dev/pricing`), retrieval date (2026-11-07), published rates for `gemini-3-flash-preview` ($0.50/1M input, $3.00/1M output), and the exact formula used.
* **`docs/policy_defaults.md` (New):**
  * Documents the policy default rule: ambiguous or unclassified messages route to escalation, while `Noise` is reserved exclusively for positively identified non-operational inquiries.
* **`docs/parser_agreement.md` (New):**
  * Table comparing LLM category vs. deterministic category across all 15 events. 14/14 completed live calls matched 100%. Documents E-15 hitting free tier rate limit with clean fallback.
* **`docs/timing_audit.md` (Updated):**
  * Detailed breakdown explaining that the 0.04s figure measured strictly local in-memory deterministic Python code (regex parsing, graph traversal, policy solving, simulator mutations), with 0 LLM calls and 0 network requests.
  * Displays the side-by-side comparison of the live run (53.32s wall-clock, 45.20s LLM time, 15,196 tokens, $0.009475 cost) vs. cached run (0.0351s).
  * Includes a real parsed sample from `runs/live_run/raw/E-12.json`.
* **`tests/test_unrecognized_fallback.py` (New):**
  * Test verifying that feeding an ambiguous, unclassifiable message results in 0 operational write actions and exactly 1 escalation.

### 4. Submission & Dashboard Documentation
* **`DEVPOST_SUBMISSION.md` & `design_card.md` (Updated):**
  * Removed all "1st place" framing and self-promotional text.
  * Replaced "fractions of a cent" with computed commercial inference cost ($0.009475 per 15-event run).
  * Replaced unverified "100% accuracy" claims with scoped statements: 783/783 deterministic actions against team-authored benchmark; 100% parser agreement on completed live LLM calls.
  * Added comprehensive **Limitations** section acknowledging benchmark origin, lack of external messy text testing, and pricing retrieval date.
