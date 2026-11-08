# E-05 and E-09 Targeted Live Run Summary: 100% Verified Live Execution

**Execution Date:** 2026-11-08  
**Model:** `gemini-3-flash-preview`  
**API Endpoint:** `https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent`  
**Command Executed:**
```bash
python3 runner.py --mode live --events E-05,E-09 --out runs/live_run_e09_fix
```

---

## 1. Executive Summary

This targeted live run empirically validates the updated perception prompt, strict JSON schema, entity grounding layer, and coordinator incident deduplication using `gemini-3-flash-preview` on Google AI Studio.

Both events completed with **HTTP 200 OK** and **0 simulator errors**:
- **E-05 (Noise):** Succeeded live with **HTTP 200 OK**. Validated that strict schema `"required": ["category", "supplier_id", "part_id"]` produces valid empty strings `""` for non-operational noise as instructed, maintaining zero downstream write actions.
- **E-09 (Supplier Delay):** Succeeded live with **HTTP 200 OK**. `gemini-3-flash-preview` successfully extracted `supplier_id: "Orbit"`, `part_id: "surround-view cameras"`, `plant_id: "P_AL"`, and `start_date: "2027-03-29"`. Grounding via the Knowledge Graph alias catalog resolved `Orbit` $\to$ `SUP-11` and `surround-view cameras` $\to$ `CAM-360`, and recovered `end_date: "2027-04-01"`. The deterministic policy engine executed **all 42 operational actions (reschedules, transfers, dealer notifications, VIP loaners) with 0 simulator errors**.

---

## 2. Event E-05 Live Result

- **HTTP Status:** 200 OK
- **Wall-Clock Latency:** 3,508.07 ms
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
- **Validation Outcome:** **PASS**. Cleanly conforms to strict schema `required: ["category", "supplier_id", "part_id"]` with 0 operational writes.

---

## 3. Event E-09 Live Result

- **HTTP Status:** 200 OK
- **Wall-Clock Latency:** 4,707.47 ms
- **Service Tier:** `standard`
- **Tokens:**
  - Prompt: 1,114 tokens
  - Candidate (Output): 154 tokens
  - Thought: 1,026 tokens
  - Total Reported: 2,294 tokens
- **Raw Parsed JSON:**
```json
{
  "incidents": [
    {
      "category": "Supplier Delay",
      "supplier_id": "Orbit",
      "part_id": "surround-view cameras",
      "plant_id": "P_AL",
      "start_date": "2027-03-29"
    }
  ]
}
```
- **Entity Grounding & Resolution:**
  - `Orbit` $\to$ Canonical Supplier `SUP-11`
  - `surround-view cameras` $\to$ Canonical Part `CAM-360`
  - `Huntsville` / `P_AL` $\to$ Canonical Plant `P_AL`
  - Missing end date recovered from message text $\to$ `2027-04-01`
- **Action Execution:**
  - Total Tool Calls: **42**
  - Tool Types: `mes.reschedule` (2), `mes.transfer` (4), `dealer.notify` (26), `crm.assign_loaner` (10)
  - Simulator Errors: **0** (100% compliance)

---

## 4. Run Telemetry & Timing

| Metric | E-05 (Noise) | E-09 (Supplier Delay) | Total |
|---|---|---|---|
| HTTP Status | 200 OK | 200 OK | - |
| LLM Perception Time | 3,508.1 ms | 4,707.5 ms | 8,215.5 ms |
| Deterministic Pipeline Time | 0.2 ms | 2.0 ms | 2.2 ms |
| Tool Actions Executed | 0 | 42 | 42 |
| Failed Tool Calls | 0 | 0 | 0 |
| Prompt Tokens | 1,090 | 1,114 | 2,204 |
| Candidate Output Tokens | 62 | 154 | 216 |
| Thought Tokens | 570 | 1,026 | 1,596 |
| Total Tokens (Billed Basis) | 1,722 | 2,294 | 4,016 |
| Incurred Cost (Standard Rates) | $0.002441 | $0.004167 | $0.006608 |
