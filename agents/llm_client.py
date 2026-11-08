"""Hack the Highway: Gemini Live Perception Client & Schema Validator.

Handles LLM-based perception for operational event text using Google Gemini API:
- Model: config.MODEL_NAME (single config constant)
- Structured JSON output schema enforcement
- Latency and token usage instrumentation
- Retry logic (max 2 retries on transient errors)
- Saves raw responses and prompt texts for auditing
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import config


PERCEPTION_JSON_SCHEMA = {
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
                # Note: "required" applies to all incident categories. For Noise and Unconfirmed Report events,
                # set supplier_id and part_id to empty strings ("").
                "required": ["category", "supplier_id", "part_id"]
            }
        }
    },
    "required": ["incidents"]
}


class GeminiPerceptionClient:
    """Client for Gemini Flash structured event perception."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = config.MODEL_NAME,
        raw_output_dir: Optional[str] = None,
        prompt_output_dir: Optional[str] = None
    ):
        self.api_key = api_key
        if not self.api_key:
            try:
                self.api_key = config.get_gemini_api_key()
            except RuntimeError:
                self.api_key = None

        self.model_name = model_name
        self.raw_output_dir = raw_output_dir
        self.prompt_output_dir = prompt_output_dir
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_llm_calls = 0
        self.total_llm_time_ms = 0.0

        if self.raw_output_dir:
            os.makedirs(self.raw_output_dir, exist_ok=True)
        if self.prompt_output_dir:
            os.makedirs(self.prompt_output_dir, exist_ok=True)

    def parse_event_text(
        self,
        event_id: str,
        text: str,
        aliases_context: str
    ) -> Tuple[Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        """
        Calls live Gemini API with structured JSON output.
        Retries up to 2 times on transient failures.
        Saves prompt to prompts/<event_id>.txt and raw response to raw/<event_id>.json.
        """
        metrics = {
            "model": self.model_name,
            "live_call": False,
            "perception_time_ms": 0.0,
            "prompt_tokens": 0,
            "output_tokens": 0,
            "error": None,
            "raw_response": None,
            "http_status": None,
            "retries": 0
        }

        if not self.api_key:
            metrics["error"] = "GEMINI_API_KEY not configured; live call skipped."
            return None, metrics

        prompt = (
            f"You are the NLU intake component of an automaker Control Tower.\n"
            f"Extract operational incidents from the event message below according to company entities and calendar.\n"
            f"Today is Monday 2027-03-08.\n"
            f"Calendar reference: 'next Friday' is 2027-03-19, 'next Monday' is 2027-03-15, 'next Tuesday' is 2027-03-16, 'next Thursday' is 2027-03-18.\n"
            f"Past dates: 'Thursday Feb 25' is 2027-02-25, 'last Monday' is 2027-03-01. 'Monday Feb 22' is 2027-02-22, 'Wednesday Feb 24' is 2027-02-24.\n"
            f"Important date rules for schema fields:\n"
            f"- For Plant Outage: provide start_date and end_date (e.g. 'next Friday through Monday Mar 22' -> start_date '2027-03-19', end_date '2027-03-22').\n"
            f"- For Supplier Delay: start_date is original ETA, end_date is new ETA (e.g. 'next Monday' to 'next Friday' -> start_date '2027-03-15', end_date '2027-03-19').\n"
            f"- For Supplier Delay incidents, you must extract supplier_id (for example SUP-09 or the supplier's name) and part_id (for example CAM-360) from the message. Copy identifiers exactly as they appear in the message. Do not omit them.\n"
            f"- For Quality Hold: start_date is build range start, end_date is build range end (e.g. 'Thursday Feb 25 through last Monday' -> start_date '2027-02-25', end_date '2027-03-01').\n"
            f"- For Noise and Unconfirmed Report events, set supplier_id and part_id to empty strings.\n"
            f"Company Entity Aliases:\n{aliases_context}\n\n"
            f"Event [{event_id}]: {text}\n\n"
            f"Classify into category (Supplier Delay, Plant Outage, Quality Hold, Noise, Unconfirmed Report).\n"
            f"If positively identified as a brochure/non-manufacturing inquiry, return category Noise with reason.\n"
            f"If unconfirmed rumor or ambiguous/unrecognized text, return category Unconfirmed Report with reason.\n"
            f"Format response strictly according to the required JSON schema."
        )

        # Save prompt text if output dir configured
        if self.prompt_output_dir:
            prompt_file = os.path.join(self.prompt_output_dir, f"{event_id}.txt")
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(prompt)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json",
                "response_schema": PERCEPTION_JSON_SCHEMA
            }
        }
        encoded_payload = json.dumps(payload).encode("utf-8")

        max_retries = 2
        for attempt in range(max_retries + 1):
            t0 = time.time()
            req = urllib.request.Request(
                url,
                data=encoded_payload,
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    elapsed_ms = (time.time() - t0) * 1000.0
                    raw_bytes = resp.read()
                    data = json.loads(raw_bytes.decode("utf-8"))

                metrics["http_status"] = 200
                metrics["retries"] = attempt
                metrics["live_call"] = True
                metrics["perception_time_ms"] = elapsed_ms

                usage = data.get("usageMetadata", {})
                prompt_tokens = usage.get("promptTokenCount", 0)
                output_tokens = usage.get("candidatesTokenCount", 0)
                total_tokens = usage.get("totalTokenCount", prompt_tokens + output_tokens)

                metrics["prompt_tokens"] = prompt_tokens
                metrics["output_tokens"] = output_tokens

                self.total_input_tokens += prompt_tokens
                self.total_output_tokens += output_tokens
                self.total_llm_calls += 1
                self.total_llm_time_ms += elapsed_ms

                candidate_part = data["candidates"][0]["content"]["parts"][0]["text"]
                metrics["raw_response"] = candidate_part
                parsed = json.loads(candidate_part)
                incidents = parsed.get("incidents", [])

                # Save raw response with timing and usage metadata
                if self.raw_output_dir:
                    raw_record = {
                        "event_id": event_id,
                        "model": self.model_name,
                        "wall_clock_latency_ms": round(elapsed_ms, 2),
                        "http_status": 200,
                        "usageMetadata": {
                            "promptTokenCount": prompt_tokens,
                            "candidatesTokenCount": output_tokens,
                            "totalTokenCount": total_tokens
                        },
                        "response": data,
                        "parsed_incidents": incidents
                    }
                    raw_file = os.path.join(self.raw_output_dir, f"{event_id}.json")
                    with open(raw_file, "w", encoding="utf-8") as f:
                        json.dump(raw_record, f, indent=2)

                return incidents, metrics

            except urllib.error.HTTPError as e:
                elapsed_ms = (time.time() - t0) * 1000.0
                metrics["http_status"] = e.code
                err_body = e.read().decode("utf-8", errors="replace")
                metrics["error"] = f"HTTP {e.code}: {err_body[:300]}"
                metrics["perception_time_ms"] = elapsed_ms

                # Save raw error response
                if self.raw_output_dir:
                    raw_record = {
                        "event_id": event_id,
                        "model": self.model_name,
                        "wall_clock_latency_ms": round(elapsed_ms, 2),
                        "http_status": e.code,
                        "error_body": err_body,
                        "attempt": attempt + 1
                    }
                    raw_file = os.path.join(self.raw_output_dir, f"{event_id}.json")
                    with open(raw_file, "w", encoding="utf-8") as f:
                        json.dump(raw_record, f, indent=2)

                if attempt < max_retries and e.code in (429, 500, 503):
                    time.sleep(1.0 * (attempt + 1))
                    continue
                return None, metrics

            except Exception as e:
                elapsed_ms = (time.time() - t0) * 1000.0
                metrics["error"] = f"Exception: {str(e)}"
                metrics["perception_time_ms"] = elapsed_ms

                if self.raw_output_dir:
                    raw_record = {
                        "event_id": event_id,
                        "model": self.model_name,
                        "wall_clock_latency_ms": round(elapsed_ms, 2),
                        "error": str(e),
                        "attempt": attempt + 1
                    }
                    raw_file = os.path.join(self.raw_output_dir, f"{event_id}.json")
                    with open(raw_file, "w", encoding="utf-8") as f:
                        json.dump(raw_record, f, indent=2)

                if attempt < max_retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                return None, metrics

        return None, metrics
