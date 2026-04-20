"""Two-pass extraction orchestrator — parallelized for speed.

Pass 1: full image (sequential — needs to finish first)
Pass 2: three cropped regions IN PARALLEL (uses different API keys simultaneously)
Merge: prefer cropped (higher zoom)
Validate: Pydantic strict checks
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .client import GeminiClient
from .prompts import ACCELERATEURS, FULL_EXTRACTION, GLOBAL_VALUES, PUISSANCE_ICT
from ..io.image import (
    CROP_ACCELERATEURS, CROP_GLOBAL, CROP_PUISSANCE,
    crop_percent, load_and_enhance, to_png_bytes,
)
from ..models import (
    AccelerateurGlobal, AccelerateurZone,
    ExtractionError, PanelData, PuissanceICTRow,
)

logger = logging.getLogger(__name__)


def _prefer_pass2(val1: Any, val2: Any, field: str) -> Any:
    """Prefer Pass 2 (cropped) unless identical."""
    if val1 == val2:
        return val2
    if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
        if abs(val1 - val2) < 0.01:
            return val2
    logger.warning(f"  MISMATCH {field}: pass1={val1} vs pass2={val2} -> using pass2")
    return val2


def _merge_rows(p1: list[dict], p2: list[dict], key: str, fields: list[str]) -> list[dict]:
    d1 = {r[key]: r for r in p1}
    d2 = {r[key]: r for r in p2}
    return [
        {key: k, **{f: _prefer_pass2(d1.get(k, {}).get(f), d2.get(k, d1.get(k, {})).get(f), f"{k}.{f}") for f in fields}}
        for k in d1
    ]


def extract(
    image_path: str | Path,
    client: GeminiClient,
    model: str = "gemini-2.5-flash",
    contrast: float = 1.4,
    sharpness: float = 1.8,
) -> PanelData:
    """Run parallelized two-pass extraction.

    Pass 1 runs first (~5-10s), Pass 2 runs its 3 crops concurrently (~5-10s).
    Total: ~15-25s on healthy API, ~30-40s with some retries.
    """
    img = load_and_enhance(image_path, contrast, sharpness)
    logger.info(f"Image: {img.size[0]}x{img.size[1]}")

    # Pre-compute all crops (CPU, fast)
    full_bytes = to_png_bytes(img)
    puiss_bytes = to_png_bytes(crop_percent(img, CROP_PUISSANCE))
    accel_bytes = to_png_bytes(crop_percent(img, CROP_ACCELERATEURS))
    glob_bytes = to_png_bytes(crop_percent(img, CROP_GLOBAL))

    # Pass 1
    logger.info("[Pass 1] Full image extraction...")
    data_full = client.call(full_bytes, FULL_EXTRACTION, model)
    logger.info("[Pass 1] OK")

    # Pass 2 — 3 CROPS IN PARALLEL (different keys used simultaneously)
    logger.info("[Pass 2] Cropped verification (parallel)...")
    with ThreadPoolExecutor(max_workers=3) as ex:
        fut_puiss = ex.submit(client.call, puiss_bytes, PUISSANCE_ICT, model)
        fut_accel = ex.submit(client.call, accel_bytes, ACCELERATEURS, model)
        fut_glob = ex.submit(client.call, glob_bytes, GLOBAL_VALUES, model)
        data_puiss = fut_puiss.result()
        data_accel = fut_accel.result()
        data_glob = fut_glob.result()
    logger.info("[Pass 2] All crops OK")

    # Merge
    puiss_fields = ["tension_primaire_v", "zone_courant_primaire", "courant_primaire_a",
                    "zone_courant_secondaire", "courant_secondaire_a"]
    merged_puiss = _merge_rows(data_full.get("puissance_ict", []),
                               data_puiss.get("puissance_ict", []),
                               "zone_tension", puiss_fields)

    accel_fields = ["r_icol_kv", "courant_colonne_ua", "vide_torr", "courant_aperture_ua"]
    merged_accel = _merge_rows(data_full.get("accelerateurs_zones", []),
                               data_accel.get("accelerateurs_zones", []),
                               "zone", accel_fields)

    g1 = data_full.get("accelerateurs_global", {})
    g2 = data_glob.get("accelerateurs_global", g1)
    merged_global = {f: _prefer_pass2(g1.get(f), g2.get(f), f"global.{f}")
                     for f in ["tension_kv", "charge_ma", "faisceau_ma_a", "faisceau_ma_b"]}

    # Validate
    logger.info("[Validate] Pydantic checks...")
    try:
        panel = PanelData(
            puissance_ict=[PuissanceICTRow(**r) for r in merged_puiss],
            accelerateurs_zones=[AccelerateurZone(**r) for r in merged_accel],
            accelerateurs_global=AccelerateurGlobal(**merged_global),
        )
    except Exception as exc:
        raise ExtractionError(f"Validation failed: {exc}") from exc

    for r in panel.puissance_ict:
        logger.info(f"  {r.zone_tension}: T={r.tension_primaire_v}V  Cp({r.zone_courant_primaire})={r.courant_primaire_a}A  Cs({r.zone_courant_secondaire})={r.courant_secondaire_a}A")
    for r in panel.accelerateurs_zones:
        logger.info(f"  Zone {r.zone}: R={r.r_icol_kv}KV  C={r.courant_colonne_ua}uA  V={r.vide_torr}  A={r.courant_aperture_ua}uA")
    g = panel.accelerateurs_global
    logger.info(f"  Global: T={g.tension_kv}KV  Ch={g.charge_ma}mA  FA={g.faisceau_ma_a}mA  FB={g.faisceau_ma_b}mA")

    return panel
