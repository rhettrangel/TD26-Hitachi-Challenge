"""Central configuration for Wacky Wheels Control Tower.

Manages model configuration and secure API key loading.
Never prints, logs, or writes API keys to disk or output.
"""

import os
from typing import Optional


# Single config constant for the current Flash model (Step 1)
# 'gemini-3-flash-preview' is the active Flash model supporting structured JSON schema,
# robust temporal reasoning across event boundaries, and verified operational quota.
MODEL_NAME = "gemini-3-flash-preview"


def get_gemini_api_key() -> str:
    """Reads GEMINI_API_KEY from environment or ~/.config/hitachi/.env.

    Never logs or writes the key to disk.
    Raises RuntimeError with a clear message if missing or invalid.
    """
    key = os.environ.get("GEMINI_API_KEY")
    if key and key.strip() and key.strip() != "keyhere":
        return key.strip()

    env_path = os.path.expanduser("~/.config/hitachi/.env")
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#"):
                    continue
                if line.startswith("GEMINI_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip("\"'")
                    if val and val != "keyhere":
                        return val
                    elif val == "keyhere":
                        raise RuntimeError(
                            "GEMINI_API_KEY in ~/.config/hitachi/.env is set to placeholder 'keyhere'. "
                            "Please update ~/.config/hitachi/.env with your valid Google Gemini API key."
                        )

    raise RuntimeError(
        "GEMINI_API_KEY is missing! Please configure a valid API key in ~/.config/hitachi/.env "
        "(e.g. GEMINI_API_KEY=AIzaSy...) or export the GEMINI_API_KEY environment variable."
    )
