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
- **Live Call Success**: 14 of 15 live calls succeeded (HTTP 200). E-15 returned HTTP 429 (free-tier daily quota) and fell back to deterministic parsing.
- **Category Agreement on Successful Calls**: 14 of 14 successful calls (100%) exactly agreed with the deterministic baseline parser on incident category classification (Plant Outage, Supplier Delay, Quality Hold, Noise, Unconfirmed Report).
- **Sub-field Resolution Caveat (E-09)**: While category agreement was 100%, extraction was not complete across all entity fields. On event E-09, the LLM extracted plant `P_AL` and the delay dates (`2027-03-29` to `2027-04-01`), but missed extracting the supplier alias string (`Orbit` / SUP-09) and part number (`CAM-360`). Consequently, the live execution pipeline triggered 0 downstream rebalancing actions for E-09 (compared to 42 actions in deterministic mode). The ground truth confirms both the supplier ID and part number are required for full schedule rebalancing.
