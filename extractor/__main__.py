"""CLI — extract one image and append to the history Excel.

Usage:
    python -m extractor images/screenshot.jfif

By default appends to output/historique.xlsx (the master history file).
Use --single to also generate an individual Excel for this image.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="extractor",
        description="Extract panel data and append to the master history Excel.",
    )
    parser.add_argument("image", help="Panel screenshot (JFIF/JPG/PNG)")
    parser.add_argument("--api-key", default=None, help="API key(s), comma-separated")
    parser.add_argument("--model", default=None, help="Model override")
    parser.add_argument("--single", action="store_true",
                        help="Also generate an individual .xlsx for this image")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for name in ("httpcore", "httpx", "urllib3", "PIL", "google", "google_genai"):
        logging.getLogger(name).setLevel(logging.WARNING)
    log = logging.getLogger("extractor")

    from .core.client import GeminiClient
    from .core.extractor import extract
    from .io.config import load_settings
    from .io.excel import Extraction, generate_excel
    from .io.history import append_and_regenerate, load_history

    settings = load_settings(cli_api_key=args.api_key, cli_model=args.model)
    if not settings.api_keys:
        log.error("No API key. Use --api-key, GEMINI_API_KEYS env var, or .env file")
        return 1

    image_path = Path(args.image)
    if not image_path.exists():
        log.error(f"File not found: {image_path}")
        return 1

    project_root = Path(__file__).parent.parent
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True)

    history_json = output_dir / "historique.json"
    history_xlsx = output_dir / "historique.xlsx"
    existing_count = len(load_history(history_json))

    log.info("=" * 60)
    log.info("PANEL EXTRACTOR — Electron Processing System")
    log.info("=" * 60)
    log.info(f"Image:      {image_path}")
    log.info(f"Historique: {history_xlsx}")
    log.info(f"Model:      {settings.primary_model}")
    log.info(f"Keys:       {len(settings.api_keys)} loaded")
    log.info(f"History:    {existing_count} extraction(s) on record")
    log.info("")

    t0 = time.time()
    analysis_dt = datetime.now()

    try:
        client = GeminiClient(settings.api_keys)
        data = extract(image_path, client, settings.primary_model,
                       settings.contrast, settings.sharpness)

        # Append to history and regenerate the master Excel
        new_ext = Extraction(
            data=data,
            analysis_datetime=analysis_dt,
            source_filename=image_path.name,
        )
        full_history = append_and_regenerate(new_ext, history_json, history_xlsx)

        # Optionally write individual Excel too
        if args.single:
            single_path = output_dir / f"{image_path.stem}.xlsx"
            generate_excel(
                data, single_path,
                analysis_datetime=analysis_dt,
                source_filename=image_path.name,
            )
            log.info(f"Individual Excel: {single_path}")

    except Exception as exc:
        log.error(f"Failed: {exc}", exc_info=args.verbose)
        return 1

    elapsed = time.time() - t0
    log.info(f"\nDONE in {elapsed:.1f}s")
    log.info(f"  Extraction #{len(full_history)} added to history")
    log.info(f"  Total extractions: {len(full_history)}")
    log.info(f"  Output: {history_xlsx}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
