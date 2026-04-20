"""Persistent history of extractions — JSON source + Excel regeneration.

Every run appends to `historique.json` and regenerates `historique.xlsx`.
The JSON is the source of truth — the Excel is always rebuilt from it.

This way:
- Excel file can be deleted and rebuilt at any time
- Excel can never be corrupted (always regenerated)
- History survives forever (JSON is append-only)
- Each extraction preserves its own timestamp
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from .excel import Extraction, generate_consolidated_excel
from ..models.panel import (
    AccelerateurGlobal,
    AccelerateurZone,
    PanelData,
    PuissanceICTRow,
)

logger = logging.getLogger(__name__)

HISTORY_VERSION = "1.0"


def _extraction_to_dict(ext: Extraction) -> dict:
    """Serialize one Extraction to a JSON-safe dict."""
    return {
        "timestamp": ext.analysis_datetime.isoformat(),
        "source_filename": ext.source_filename,
        "puissance_ict": [r.model_dump() for r in ext.data.puissance_ict],
        "accelerateurs_zones": [r.model_dump() for r in ext.data.accelerateurs_zones],
        "accelerateurs_global": ext.data.accelerateurs_global.model_dump(),
    }


def _dict_to_extraction(entry: dict) -> Extraction:
    """Deserialize one Extraction from a JSON dict (with Pydantic validation)."""
    data = PanelData(
        puissance_ict=[PuissanceICTRow(**r) for r in entry["puissance_ict"]],
        accelerateurs_zones=[AccelerateurZone(**r) for r in entry["accelerateurs_zones"]],
        accelerateurs_global=AccelerateurGlobal(**entry["accelerateurs_global"]),
    )
    return Extraction(
        data=data,
        analysis_datetime=datetime.fromisoformat(entry["timestamp"]),
        source_filename=entry["source_filename"],
    )


def load_history(json_path: str | Path) -> list[Extraction]:
    """Load all past extractions from the JSON log. Returns [] if file doesn't exist."""
    p = Path(json_path)
    if not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Cannot read history ({exc}) — starting fresh")
        return []
    return [_dict_to_extraction(e) for e in raw.get("extractions", [])]


def save_history(json_path: str | Path, extractions: list[Extraction]) -> None:
    """Atomically save all extractions to JSON log."""
    p = Path(json_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": HISTORY_VERSION,
        "last_updated": datetime.now().isoformat(),
        "count": len(extractions),
        "extractions": [_extraction_to_dict(e) for e in extractions],
    }
    # Write to temp file + rename for atomicity
    tmp_path = p.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    tmp_path.replace(p)


def append_and_regenerate(
    new_extraction: Extraction,
    history_json: str | Path,
    history_xlsx: str | Path,
) -> list[Extraction]:
    """Add *new_extraction* to the history log and regenerate the Excel.

    Returns the full history list (chronologically sorted).
    """
    history = load_history(history_json)
    history.append(new_extraction)
    # Keep chronological order (oldest first)
    history.sort(key=lambda e: e.analysis_datetime)

    save_history(history_json, history)
    generate_consolidated_excel(history, history_xlsx)

    logger.info(f"History updated: {len(history)} extractions total")
    return history
