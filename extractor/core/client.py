"""API client with key rotation, fast retry, and model fallback.

Speed-optimized:
- Immediate model switch on 503 (don't wait on same model)
- Short waits (3s for 503, parsed delay for 429)
- Thread-safe round-robin for parallel calls
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Any

from google import genai
from google.genai import types

from ..models.exceptions import AllModelsExhaustedError, ExtractionError

logger = logging.getLogger(__name__)

# Model fallback chain — each has its own quota, so switching gives instant recovery.
FALLBACK_MODELS: list[str] = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.5-pro",
]


class GeminiClient:
    """Thread-safe client with key rotation, 503 fast-fail, and model fallback.

    Args:
        api_keys: API keys for round-robin rotation.
        max_503_retries_per_model: How many 503s to tolerate on a model before switching.
        max_429_retries_per_model: How many 429s to tolerate on a model before switching.
    """

    def __init__(
        self,
        api_keys: list[str],
        max_503_retries_per_model: int = 0,  # 503: switch model immediately
        max_429_retries_per_model: int = 0,  # 429: switch model immediately (don't wait)
    ) -> None:
        if not api_keys:
            raise ValueError("At least one API key is required")
        self._clients = [genai.Client(api_key=k) for k in api_keys]
        self._num_keys = len(self._clients)
        self._index = 0
        self._lock = threading.Lock()  # thread-safe for parallel calls
        self._max_503 = max_503_retries_per_model
        self._max_429 = max_429_retries_per_model

    def _next_client(self) -> tuple[genai.Client, int]:
        """Thread-safe round-robin."""
        with self._lock:
            idx = self._index % self._num_keys
            self._index += 1
        return self._clients[idx], idx

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise ExtractionError(f"No JSON in response: {text[:300]}")

    @staticmethod
    def _parse_retry_delay(error_msg: str) -> float:
        m = re.search(r"retry in (\d+)", error_msg)
        return float(m.group(1)) + 2 if m else 20.0

    def call(self, image_bytes: bytes, prompt: str,
             model: str = "gemini-2.5-flash") -> dict[str, Any]:
        """Send image + prompt to Gemini. Aggressive model fallback.

        Strategy:
        - Try each model in the fallback chain once
        - On 503/429, immediately switch model (no wait)
        - If ALL models fail in round 1, wait 15s and try chain once more
        - Only then raise AllModelsExhaustedError
        """
        models_to_try = [model] + [m for m in FALLBACK_MODELS if m != model]

        for round_num in range(2):  # 2 full passes through model chain
            for try_model in models_to_try:
                err_503 = 0
                err_429 = 0

                while True:
                    client, key_id = self._next_client()
                    try:
                        response = client.models.generate_content(
                            model=try_model,
                            contents=[
                                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                                prompt,
                            ],
                        )
                        return self._extract_json(response.text.strip())

                    except Exception as exc:
                        err = str(exc)

                        if "503" in err or "UNAVAILABLE" in err:
                            err_503 += 1
                            if err_503 > self._max_503:
                                break  # next model
                            time.sleep(2)
                            continue

                        if "429" in err or "RESOURCE_EXHAUSTED" in err:
                            err_429 += 1
                            if err_429 > self._max_429:
                                break  # next model
                            time.sleep(3)
                            continue

                        raise  # Unknown — propagate

            # End of round: all models failed. Wait once before final retry.
            if round_num == 0:
                logger.warning("All models busy — waiting 15s for rate limits to reset...")
                time.sleep(15)

        raise AllModelsExhaustedError(
            "All models exhausted after 2 rounds. Gemini API is under heavy load."
        )
