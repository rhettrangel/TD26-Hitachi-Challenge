#!/usr/bin/env python3
"""Hack the Highway: Control Tower Multi-Agent Execution Runner.

Executes all operational events through the Coordinating Agent and Specialist Agents,
logging all actions to <out>/action_log.jsonl, saving complete audit traces
to <out>/event_traces.json, and generating an honest timing & token breakdown in
<out>/timing_summary.json.

Supports:
- Live Gemini API perception mode (--live-llm)
- Deterministic/cached perception baseline
- In-memory simulator or live HTTP server (--server http://...)
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

from agents.coordinator import CoordinatingAgent
from enterprise import Enterprise


class InstrumentedHttpClient:
    """HTTP Client connecting to enterprise_server.py with call-by-call timing."""
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.total_http_time_ms = 0.0
        self.total_calls = 0

    def call(self, event_id: str, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/act"
        payload = json.dumps({"event_id": event_id, "tool": tool, "args": args}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            elapsed = (time.time() - t0) * 1000.0
            self.total_http_time_ms += elapsed
            self.total_calls += 1
            return data
        except urllib.error.HTTPError as e:
            elapsed = (time.time() - t0) * 1000.0
            self.total_http_time_ms += elapsed
            self.total_calls += 1
            err_body = e.read().decode("utf-8")
            raise RuntimeError(f"HTTP {e.code}: {err_body}") from None


class InstrumentedDirectClient:
    """In-memory direct client calling Enterprise directly and writing action_log.jsonl."""
    def __init__(self, ent: Enterprise, log_path: str):
        self.ent = ent
        self.log_path = log_path
        self.total_action_time_ms = 0.0
        self.total_calls = 0
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        open(self.log_path, "w", encoding="utf-8").close()

    def call(self, event_id: str, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.time()
        try:
            res = self.ent.call(event_id, tool, args)
            err = None
        except Exception as e:
            res = {"error": str(e)}
            err = str(e)
            raise e
        finally:
            elapsed = (time.time() - t0) * 1000.0
            self.total_action_time_ms += elapsed
            self.total_calls += 1
            with open(self.log_path, "a", encoding="utf-8") as f:
                entry = {"event_id": event_id, "tool": tool, "args": args, "ok": err is None}
                f.write(json.dumps(entry) + "\n")
        return res


def run_control_tower(
    data_dir: str,
    events_path: str,
    out_dir: str,
    server_url: str = None,
    mode: str = "cached",
    api_key: str = None
):
    os.makedirs(out_dir, exist_ok=True)
    action_log_path = os.path.join(out_dir, "action_log.jsonl")
    traces_path = os.path.join(out_dir, "event_traces.json")
    timing_path = os.path.join(out_dir, "timing_summary.json")

    with open(events_path, encoding="utf-8") as f:
        events = json.load(f)

    use_live_llm = (mode == "live")
    raw_out = os.path.join(out_dir, "raw") if use_live_llm else None
    prompts_out = os.path.join(out_dir, "prompts") if use_live_llm else None

    mode_label = "LIVE GEMINI FLASH" if use_live_llm else "DETERMINISTIC / CACHED BASELINE"
    print(f"Loaded {len(events)} events from {events_path}")
    print(f"Output directory: {out_dir}")
    print(f"Perception Mode: {mode_label} (mode={mode})")

    if server_url:
        print(f"Connecting to live enterprise server at {server_url}...")
        client = InstrumentedHttpClient(server_url)
    else:
        print("Using direct in-memory Enterprise engine...")
        ent = Enterprise(data_dir)
        client = InstrumentedDirectClient(ent, action_log_path)

    coordinator = CoordinatingAgent(
        data_dir,
        use_live_llm=use_live_llm,
        api_key=api_key,
        raw_output_dir=raw_out,
        prompt_output_dir=prompts_out
    )
    traces = []
    per_event_telemetry = []

    print("\n" + "=" * 80)
    print(f"STARTING CONTROL TOWER EXECUTION [{mode_label}]")
    print("=" * 80 + "\n")

    t_wall_start = time.time()
    total_actions_all = 0
    failed_actions_all = 0

    for i, event in enumerate(events, start=1):
        eid = event["event_id"]
        t_evt_start = time.time()
        res = coordinator.process_event(event, client)
        evt_wall_time_ms = (time.time() - t_evt_start) * 1000.0

        traces.append(res.to_dict())

        acts = res.actions_taken
        failed = [a for a in acts if not a.get("ok", True)]
        total_actions_all += len(acts)
        failed_actions_all += len(failed)

        event_timing = {
            "event_id": eid,
            "category": res.category,
            "llm_perception_time_ms": res.llm_perception_time_ms,
            "deterministic_pipeline_time_ms": res.deterministic_time_ms,
            "event_wall_time_ms": round(evt_wall_time_ms, 2),
            "actions_executed": len(acts),
            "prompt_tokens": res.prompt_tokens,
            "output_tokens": res.output_tokens,
            "model_used": res.model_name
        }
        per_event_telemetry.append(event_timing)

        print(f"[{i}/{len(events)}] {eid} ({res.category}): {len(acts)} actions | "
              f"LLM: {res.llm_perception_time_ms:.1f}ms | Det: {res.deterministic_time_ms:.1f}ms")

    total_wall_clock_s = time.time() - t_wall_start

    # Aggregate timing and token metrics
    total_llm_time_ms = sum(t["llm_perception_time_ms"] for t in per_event_telemetry)
    total_det_time_ms = sum(t["deterministic_pipeline_time_ms"] for t in per_event_telemetry)
    total_prompt_tokens = sum(t["prompt_tokens"] for t in per_event_telemetry)
    total_output_tokens = sum(t["output_tokens"] for t in per_event_telemetry)
    http_time_ms = getattr(client, "total_http_time_ms", getattr(client, "total_action_time_ms", 0.0))

    # Pricing calculation (gemini-1.5-flash: $0.075/1M in, $0.30/1M out)
    cost_usd = (total_prompt_tokens * 0.075 / 1_000_000) + (total_output_tokens * 0.30 / 1_000_000)

    timing_summary = {
        "run_mode": "live_gemini" if use_live_llm else "cached_or_deterministic",
        "model_name_string": config.MODEL_NAME if use_live_llm else "deterministic_rule_engine",
        "pricing_source": "Google AI Studio Pricing (https://ai.google.dev/pricing), verified Nov 2024 / current",
        "total_wall_clock_seconds": round(total_wall_clock_s, 4),
        "total_llm_perception_seconds": round(total_llm_time_ms / 1000.0, 4),
        "total_deterministic_pipeline_seconds": round(total_det_time_ms / 1000.0, 4),
        "total_action_execution_seconds": round(http_time_ms / 1000.0, 4),
        "total_events_processed": len(events),
        "total_tool_calls_executed": total_actions_all,
        "failed_tool_calls": failed_actions_all,
        "total_prompt_tokens": total_prompt_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_prompt_tokens + total_output_tokens,
        "computed_cost_usd": round(cost_usd, 6),
        "per_event_breakdown": per_event_telemetry
    }

    # Save traces
    with open(traces_path, "w", encoding="utf-8") as f:
        json.dump(traces, f, indent=2)

    # Save timing summary
    with open(timing_path, "w", encoding="utf-8") as f:
        json.dump(timing_summary, f, indent=2)

    print("\n" + "=" * 80)
    print("EXECUTION COMPLETED")
    print(f"Run Mode: {timing_summary['run_mode']}")
    print(f"Model: {timing_summary['model_name_string']}")
    print(f"Total Wall-Clock Time: {total_wall_clock_s:.4f}s")
    print(f"  - LLM Perception Time: {total_llm_time_ms / 1000.0:.4f}s ({total_prompt_tokens} in / {total_output_tokens} out tokens)")
    print(f"  - Deterministic Pipeline Time: {total_det_time_ms / 1000.0:.4f}s")
    print(f"  - Tool Execution Time: {http_time_ms / 1000.0:.4f}s")
    print(f"Estimated Cost: ${cost_usd:.6f}")
    print(f"Action Log: {action_log_path}")
    print(f"Timing Breakdown: {timing_path}")
    print("=" * 80 + "\n")

    return timing_summary


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Control Tower Runner")
    parser.add_argument("--data", default="data", help="Data directory containing CSVs")
    parser.add_argument("--events", default="data/events.json", help="Path to events JSON")
    parser.add_argument("--out", default="runs/submission", help="Output directory for action_log.jsonl")
    parser.add_argument("--server", default=None, help="HTTP URL of enterprise_server (optional)")
    parser.add_argument("--mode", choices=["live", "cached"], default="cached", help="Perception mode: 'live' (live Gemini API calls) or 'cached' (deterministic baseline)")
    parser.add_argument("--live-llm", action="store_true", help="Deprecated alias for --mode live")
    parser.add_argument("--api-key", default=None, help="Gemini API Key (optional, defaults to GEMINI_API_KEY env)")
    args = parser.parse_args()

    mode = "live" if args.live_llm else args.mode
    run_control_tower(args.data, args.events, args.out, args.server, mode, args.api_key)


if __name__ == "__main__":
    main()
