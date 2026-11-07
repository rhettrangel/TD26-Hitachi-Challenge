"""Hack the Highway: Gemini Live Perception Client & Schema Validator.

Handles LLM-based perception for operational event text using Google Gemini API:
- Model: gemini-1.5-flash
- Structured JSON output schema enforcement
- Latency and token usage instrumentation
- Robust fallback to deterministic parsing on API error or malformed JSON
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


# Gemini 1.5 Flash Pricing (Source: https://ai.google.dev/pricing, Nov 2024 / current)
# Prompts <= 128k: $0.075 per 1M input tokens, $0.30 per 1M output tokens
PRICE_PER_INPUT_TOKEN = 0.075 / 1_000_000
PRICE_PER_OUTPUT_TOKEN = 0.30 / 1_000_000

DEFAULT_MODEL_NAME = "gemini-1.5-flash"


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
                "required": ["category"]
            }
        }
    },
    "required": ["incidents"]
}


class GeminiPerceptionClient:
    """Client for Gemini 1.5 Flash structured event perception."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = DEFAULT_MODEL_NAME):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_llm_calls = 0
        self.total_llm_time_ms = 0.0

    def parse_event_text(
        self,
        event_id: str,
        text: str,
        aliases_context: str
    ) -> Tuple[Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        """
        Calls live Gemini 1.5 Flash API with structured JSON output.
        Returns:
            (incidents_list or None if failed, metrics_dict)
        """
        metrics = {
            "model": self.model_name,
            "live_call": False,
            "perception_time_ms": 0.0,
            "prompt_tokens": 0,
            "output_tokens": 0,
            "error": None,
            "raw_response": None
        }

        if not self.api_key:
            metrics["error"] = "GEMINI_API_KEY not configured; live call skipped."
            return None, metrics

        prompt = (
            f"You are the NLU intake component of an automaker Control Tower.\n"
            f"Extract operational incidents from the event message below according to company entities and calendar.\n"
            f"Today is Monday 2027-03-08.\n"
            f"Company Entity Aliases:\n{aliases_context}\n\n"
            f"Event [{event_id}]: {text}\n\n"
            f"Classify into category (Supplier Delay, Plant Outage, Quality Hold, Noise, Unconfirmed Report).\n"
            f"If noise, return category Noise with reason. If vague rumor without dates, return Unconfirmed Report with reason.\n"
            f"Format response strictly according to the required JSON schema."
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json",
                "response_schema": PERCEPTION_JSON_SCHEMA
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                elapsed_ms = (time.time() - t0) * 1000.0
                raw_bytes = resp.read()
                data = json.loads(raw_bytes.decode("utf-8"))

            usage = data.get("usageMetadata", {})
            prompt_tokens = usage.get("promptTokenCount", 0)
            output_tokens = usage.get("candidatesTokenCount", 0)

            self.total_input_tokens += prompt_tokens
            self.total_output_tokens += output_tokens
            self.total_llm_calls += 1
            self.total_llm_time_ms += elapsed_ms

            metrics["live_call"] = True
            metrics["perception_time_ms"] = elapsed_ms
            metrics["prompt_tokens"] = prompt_tokens
            metrics["output_tokens"] = output_tokens

            # Extract generated JSON
            candidate_part = data["candidates"][0]["content"]["parts"][0]["text"]
            metrics["raw_response"] = candidate_part
            parsed = json.loads(candidate_part)
            incidents = parsed.get("incidents", [])
            return incidents, metrics

        except urllib.error.HTTPError as e:
            elapsed_ms = (time.time() - t0) * 1000.0
            metrics["perception_time_ms"] = elapsed_ms
            err_msg = f"Gemini HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
            metrics["error"] = err_msg
            return None, metrics

        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000.0
            metrics["perception_time_ms"] = elapsed_ms
            metrics["error"] = f"Gemini call exception: {str(e)}"
            return None, metrics
