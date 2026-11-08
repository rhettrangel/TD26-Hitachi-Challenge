# E-05 and E-09 Targeted Live Run Summary

**Execution Date:** 2026-11-08  
**Model:** `gemini-3-flash-preview`  
**API Endpoint:** `https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent`  
**Command Executed:**
```bash
python3 runner.py --mode live --events E-05,E-09 --out runs/live_run_e09_fix
```

---

## 1. Executive Summary

This targeted live run was conducted to test the updated perception prompt and JSON schema introduced in commit `66005e1` to address the E-09 sub-field omission (`supplier_id` and `part_id` extraction).

- **E-05 (Noise):** Succeeded live with **HTTP 200**. The response parsed cleanly under the strict JSON schema with `"required": ["category", "supplier_id", "part_id"]`. The model adhered to prompt instructions by providing empty strings `""` for non-operational noise, proving that requiring supplier and part IDs does not break Noise classification.
- **E-09 (Supplier Delay):** Returned **HTTP 429 (RESOURCE_EXHAUSTED)**. The Google AI Studio account reached its daily Free Tier limit of 20 requests per day for `gemini-3-flash`. In accordance with control tower design, the runner seamlessly engaged deterministic fallback and executed all 42 operational actions with 0 errors.

---

## 2. Event E-05 Live Result

- **HTTP Status:** 200 OK
- **Wall-Clock Latency:** 3,449.13 ms
- **Service Tier:** `standard`
- **Tokens:**
  - Prompt: 1,090 tokens
  - Candidate (Output): 62 tokens
  - Thought: 570 tokens
  - Total Reported: 1,722 tokens
- **Raw Parsed JSON:**
```json
{
  "incidents": [
    {
      "category": "Noise",
      "supplier_id": "",
      "part_id": "",
      "reason": "Dealer Amarillo, TX asks where to find the new brochure PDF."
    }
  ]
}
```
- **Validation Outcome:** **PASS**. The output satisfies the strict schema `required: ["category", "supplier_id", "part_id"]` while correctly identifying the event as Noise with 0 downstream write actions.

---

## 3. Event E-09 Live Result

- **HTTP Status:** 429 Too Many Requests (`RESOURCE_EXHAUSTED`)
- **Latency before Rejection:** 290.69 ms
- **Error Response Body:**
```json
{
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://aistudio.google.com/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3-flash, description: Generate content requests per day limit exceeded on Free Tier. See https://aistudio.google.com/docs/rate-limits.\nPlease retry in 1h22m7.110705392s.",
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.Help",
        "links": [
          {"description": "Learn more about Gemini API quotas", "url": "https://aistudio.google.com/docs/rate-limits"}
        ]
      },
      {
        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
        "violations": [
          {
            "description": "Generate content requests per day limit exceeded on Free Tier. See https://aistudio.google.com/docs/rate-limits.",
            "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
            "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
            "quotaDimensions": {"location": "global", "model": "gemini-3-flash"},
            "quotaValue": "20"
          }
        ]
      },
      {
        "@type": "type.googleapis.com/google.rpc.RetryInfo",
        "retryDelay": "4927s"
      }
    ]
  }
}
```
- **Fallback Execution:** The Coordinating Agent automatically detected the perception failure, invoked the deterministic rule-based baseline, and executed 42 tool actions (reschedules, transfers, dealer notifications, loaner allocations) with 0 simulator errors.
- **Verification Status:** **UNVERIFIED LIVE**. Because of API quota exhaustion, live extraction of `supplier_id` (SUP-09) and `part_id` (CAM-360) could not be verified in this live run session.

---

## 4. Run Telemetry & Timing

| Metric | E-05 (Live) | E-09 (Fallback) | Total |
|---|---|---|---|
| HTTP Status | 200 OK | 429 Quota Exhausted | - |
| LLM Perception Time | 3,449.1 ms | 290.7 ms | 3,739.8 ms |
| Deterministic Pipeline Time | 0.2 ms | 2.5 ms | 2.7 ms |
| Tool Actions Executed | 0 | 42 | 42 |
| Failed Tool Calls | 0 | 0 | 0 |
| Prompt Tokens | 1,090 | 0 | 1,090 |
| Candidate Output Tokens | 62 | 0 | 62 |
| Thought Tokens | 570 | 0 | 570 |
| Total Tokens (Billed Basis) | 1,722 | 0 | 1,722 |
| Incurred Cost (Standard Rates) | $0.002441 | $0.000000 | $0.002441 |
