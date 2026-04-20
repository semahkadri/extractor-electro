# Extractor Electro — AQUILLA Panel Data Extraction

Extracts 21 numeric values from screenshots of the VIVIRAD AQUILLA
(Electron Processing System) control panel and maintains a cumulative
Excel history of every extraction.

**Tested accuracy**: 100% on 6 images (software screenshots + phone photos).
**Typical runtime**: 20–40 seconds per image.

---

## Installation

```bash
git clone https://github.com/<your-user>/extractor-electro.git
cd extractor-electro
pip install -r requirements.txt
```

Create a `.env` file at the repo root (copy from `.env.example`):

```env
GEMINI_API_KEYS=key1,key2,key3
```

Get free Gemini API keys at https://aistudio.google.com/apikey.
Multiple keys (comma-separated) enable round-robin rotation to avoid rate limits.

---

## Usage

### Web interface

```bash
python -m streamlit run extractor/app.py
```

Opens at `http://localhost:8501`. Upload one image → data is extracted,
appended to the history, master Excel is regenerated, downloadable from
the same page.

### Command line

```bash
python -m extractor images/screenshot.jfif
```

Same flow as the web UI. Add `--single` to also produce an individual
Excel for the current image:

```bash
python -m extractor images/screenshot.jfif --single
```

---

## What gets extracted

Each run produces 21 validated values grouped into three sections:

| Section | Fields |
|---|---|
| **Puissance ICT** (3 rows) | Tension primaire (V), Courant primaire (A) with zone, Courant secondaire (A) with zone — for zones B-C, C-A, A-B |
| **Accelerateurs** (2 rows) | R Icol (KV), Courant colonne (µA), Vide (Torr, scientific notation), Courant aperture (µA) — for zones A and B |
| **Global** (4 values) | Tension KV, Charge mA, Faisceau mA zone A, Faisceau mA zone B |

---

## History system

Every extraction is appended to a single master Excel. Individual per-image
Excels require the `--single` flag (CLI only).

### Storage

```
output/
    historique.json    Source of truth (append-only JSON log)
    historique.xlsx    Regenerated from JSON after every run
```

The JSON holds all extractions with their timestamps. The Excel is
rebuilt from the JSON at the end of each run. Deleting the Excel is safe —
it will be regenerated on the next extraction.

### Excel structure (4 sheets)

Every data row includes `Source` (filename) and `Date analyse` (timestamp)
columns for full traceability.

| Sheet | Rows per extraction | Purpose |
|---|---|---|
| `Puissance ICT` | 3 | All power-side values stacked chronologically |
| `Accelerateurs` | 2 | All accelerator-side values stacked chronologically |
| `Valeurs Globales` | 1 | Tension / Charge / Faisceau A / Faisceau B per analysis |
| `Resume Complet` | 1 (23 cols) | **All 21 values on one row**, one row per extraction — for pivoting, filtering, trend analysis. Freeze panes on Source + Date. |

---

## Extraction pipeline

```
Screenshot (jfif / jpg / png)
    │
    ├─ Image enhancement       Pillow: contrast + sharpness
    │
    ├─ Pass 1: full image      Gemini Vision reads the whole panel,
    │                          returns structured JSON
    │
    ├─ Pass 2: 3 crops         Puissance ICT, Accelerateurs, Global values
    │  (parallel)              each analyzed independently; runs concurrently
    │                          using ThreadPoolExecutor (3 keys at once)
    │
    ├─ Merge                   For each field: if both passes agree, use the value;
    │                          if they differ, prefer the cropped-region value
    │
    ├─ Pydantic validation     Every field checked:
    │                          - Exactly 3 rows for Puissance (B-C, C-A, A-B)
    │                          - Exactly 2 zones for Accelerateurs (A, B)
    │                          - Tension 0–1000 V, Courant 0–500 A, etc.
    │                          - Vide must parse as float (scientific notation)
    │                          Invalid data raises an exception — never
    │                          silently written to Excel.
    │
    ├─ History append          Load historique.json, append the new extraction,
    │                          sort chronologically, save atomically (temp file
    │                          + rename).
    │
    └─ Excel regeneration      Rebuild historique.xlsx from the full JSON list.
```

---

## API resilience

The Gemini client is designed to survive rate limits and server outages:

- **Multiple keys**: round-robin rotation across all keys in `GEMINI_API_KEYS`
  (thread-safe with a lock for parallel calls)
- **Model fallback chain**: `gemini-2.5-flash` → `gemini-2.0-flash` →
  `gemini-2.5-flash-lite` → `gemini-2.0-flash-lite` → `gemini-2.5-pro`
- **On 503 (server busy)**: immediate model switch (no wasted wait)
- **On 429 (rate limit)**: immediate model switch + key rotation
- **Final fallback**: if all models fail in round 1, wait 15s and try
  the full chain once more before giving up

With 6 keys and 5 models, each extraction has effectively 30 fallback paths.

---

## Project structure

```
extractor-electro/
    .env.example                      Template for API keys
    .gitignore
    README.md
    requirements.txt
    images/                           Panel screenshots (input)
    output/                           Generated outputs — in .gitignore
        historique.json               Source of truth — all extractions ever
        historique.xlsx               Regenerated each run, 4 sheets
    extractor/                        Python package
        __init__.py                   Public API exports
        __main__.py                   CLI entry point
        app.py                        Streamlit web UI
        core/
            client.py                 GeminiClient (keys + retry + fallback)
            extractor.py              Two-pass extraction orchestrator (parallel)
            prompts.py                Gemini prompt templates
        io/
            config.py                 Settings dataclass + .env loader
            image.py                  Load, enhance, crop, encode
            excel.py                  Single & consolidated Excel builders
            history.py                JSON log + atomic append + Excel rebuild
        models/
            panel.py                  Pydantic validation models
            exceptions.py             Custom exception hierarchy
```

---

## Dependencies

```
google-genai >= 1.0
pillow       >= 10.0
openpyxl     >= 3.1
pydantic     >= 2.0
streamlit    >= 1.30
```

Python 3.11+ required.

---

## Behaviour notes

- **Hardcoded for the AQUILLA panel.** Zone labels (B-C, C-A, A-B), table
  names, column headers, and value ranges are calibrated for this specific
  panel. Adapting to a different panel type means editing
  `extractor/core/prompts.py` and `extractor/models/panel.py`.
- **Crop percentages** in `extractor/io/image.py` are calibrated for the
  AQUILLA layout. They are used only for Pass 2 verification. If the crops
  miss the tables on a non-standard screenshot, Pass 1 (full image) still
  produces correct values.
- **History timestamps** are captured when the user clicks Extract, not at
  file save time.
- **Atomic writes** for the JSON log: writes to `historique.json.tmp` then
  renames — no corruption even if the process is killed mid-write.
- **Accuracy does not degrade with history size.** The JSON is read/written
  in full each run. With 10,000 extractions the file is still <2 MB.
