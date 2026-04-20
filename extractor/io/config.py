from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration."""

    api_keys: list[str] = field(default_factory=list)
    primary_model: str = "gemini-2.5-flash"
    inter_call_delay: float = 3.0
    contrast: float = 1.4
    sharpness: float = 1.8


def _load_dotenv() -> None:
    """Parse .env files into os.environ."""
    for env_path in [Path(".env"), Path(__file__).parent.parent.parent / ".env"]:
        if env_path.exists():
            with open(env_path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip().strip("\"'")
                    if key and value:
                        os.environ.setdefault(key, value)


def load_settings(cli_api_key: str | None = None, cli_model: str | None = None) -> Settings:
    """Build Settings from all sources (CLI > env > .env)."""
    _load_dotenv()

    keys: list[str] = []
    if cli_api_key:
        keys.extend(k.strip() for k in cli_api_key.split(",") if k.strip())
    if not keys:
        keys.extend(k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip())
    if not keys:
        single = os.environ.get("GEMINI_API_KEY", "").strip()
        if single:
            keys.append(single)

    return Settings(
        api_keys=keys,
        primary_model=cli_model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    )
