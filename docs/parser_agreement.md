# Parser Agreement Analysis: Live LLM vs. Deterministic Baseline

Analysis of classification agreement across all 15 benchmark events between live perception (`gemini-3-flash-preview`) and the deterministic rule engine.

| Event ID | LLM Category | Deterministic Category | Match | Notes & Ground-Truth Resolution |
| :--- | :--- | :--- | :---: | :--- |
| **E-01** | Plant Outage & Supplier Delay | Plant Outage & Supplier Delay | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 4169ms) |
| **E-02** | Unconfirmed Report | Unconfirmed Report | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 2519ms) |
| **E-03** | Quality Hold | Quality Hold | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 2367ms) |
| **E-04** | Plant Outage | Plant Outage | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 3098ms) |
| **E-05** | Noise | Noise | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 2164ms) |
| **E-06** | Noise | Noise | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 2000ms) |
| **E-07** | Noise | Noise | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 2657ms) |
| **E-08** | Plant Outage | Plant Outage | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 3120ms) |
| **E-09** | Supplier Delay | Supplier Delay | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 6536ms) |
| **E-10** | Supplier Delay | Supplier Delay | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 3345ms) |
| **E-11** | Plant Outage | Plant Outage | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 2477ms) |
| **E-12** | Supplier Delay | Supplier Delay | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 3791ms) |
| **E-13** | Unconfirmed Report | Unconfirmed Report | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 3012ms) |
| **E-14** | Quality Hold | Quality Hold | Yes | HTTP 200 OK. Ground-truth match: 100%. (Latency: 3385ms) |
| **E-15** | Quota Exceeded (HTTP 429) | Quality Hold | Fallback | Daily free tier request cap reached on 15th live call; deterministic fallback applied. Answer key matches deterministic path. |

## Summary of Findings
- **Direct Agreement on Live Calls**: 14 of 14 completed live Gemini calls (100%) exactly agreed with the deterministic baseline parser on incident category classification.
- **Rate Limit Resilience**: 1 call (E-15) hit Google AI Studio's Free Tier daily quota limit (`RESOURCE_EXHAUSTED` 429) and correctly engaged the deterministic fallback path without crashing the system.
- **Sub-field Resolution**: On E-09, the LLM extracted `P_AL` plant and delay dates, but omitted the supplier ID and part number strings from text, resulting in 0 actions taken in the live pipeline vs 42 actions in deterministic mode. The ground-truth answer key confirms `Orbit` (SUP-09) and `CAM-360` are required for full schedule rebalancing.
