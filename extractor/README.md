# Panel Extractor — AQUILLA (Electron Processing System)

Extracts 21 numeric values from screenshots of the VIVIRAD AQUILLA control panel
and maintains a cumulative Excel history of every extraction.

**Tested accuracy**: 100% on 6 images (software screenshots at multiple resolutions + phone photos at varying angles).
**Typical runtime**: 20–40 seconds per image.

---

## Usage

### Web interface

```bash
python -m streamlit run extractor/app.py
```

Opens at `http://localhost:8501`. Upload one image → data is extracted, appended
to the history, and the master Excel is regenerated. Download the cumulative
Excel file from the same page.

### Command line

```bash
python -m extractor images/screenshot.jfif
```

Same flow as the web UI. Use `--single` to also produce an individual Excel
for the current image:

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

Every extraction is appended to a single master Excel. This is the default and
only mode — individual per-image Excels require the `--single` flag.

### Storage

```
output/
    historique.json    Source of truth (append-only JSON log)
    historique.xlsx    Regenerated from JSON after every run
```

The JSON holds all extractions ever performed, each with its own timestamp. The
Excel is always rebuilt from the JSON at the end of each run, so it reflects
the complete history at that moment. Deleting the Excel is safe — it will be
regenerated from the JSON on the next run.

### Excel structure (4 sheets)

Every data row includes `Source` (filename) and `Date analyse` (timestamp)
columns for full traceability.

| Sheet | Rows per extraction | Purpose |
|---|---|---|
| `Puissance ICT` | 3 | All power-side values stacked chronologically |
| `Accelerateurs` | 2 | All accelerator-side values stacked chronologically |
| `Valeurs Globales` | 1 | Tension / Charge / Faisceau A / Faisceau B per analysis |
| `Resume Complet` | 1 (23 columns) | **All 21 values on one row**, one row per extraction — designed for pivoting, filtering, trend analysis |

The `Resume Complet` sheet has freeze panes on `Source` + `Date`, so they stay
visible when scrolling right through the 21 value columns.

---

## Extraction pipeline

```
Screenshot (jfif / jpg / png)
    │
    ├─ Image enhancement       Pillow: contrast + sharpness
    │
    ├─ Pass 1: full image      Gemini Vision reads the whole panel
    │                          returns structured JSON
    │
    ├─ Pass 2: 3 crops         Puissance ICT, Accelerateurs, Global values
    │  (parallel)              each analyzed independently; runs concurrently
    │                          using ThreadPoolExecutor (uses 3 keys at once)
    │
    ├─ Merge                   For each field: if both passes agree, use the value;
    │                          if they differ, prefer the cropped-region value
    │
    ├─ Pydantic validation     Every field checked:
    │                          - Exactly 3 rows for Puissance (B-C, C-A, A-B)
    │                          - Exactly 2 zones for Accelerateurs (A, B)
    │                          - Tension 0–1000 V, Courant 0–500 A, etc.
    │                          - Vide must parse as float (scientific notation)
    │                          Invalid data raises an exception — never silently
    │                          written to Excel.
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
- **On 503 (server busy)**: immediate model switch (no wasted wait on a busy model)
- **On 429 (rate limit)**: immediate model switch + key rotation
- **Final fallback**: if all models fail in round 1, wait 15s and try the full
  chain once more before giving up

With 6 keys and 5 models, each extraction has effectively 30 fallback paths.

---

## Configuration

Place API keys in a `.env` file at the project root:

```env
GEMINI_API_KEYS=key1,key2,key3,key4,key5,key6
```

Optional overrides:

```env
GEMINI_MODEL=gemini-2.5-flash
```

Free Gemini API keys can be created at https://aistudio.google.com/apikey.
Each key provides ~500 requests/day on `gemini-2.5-flash` plus additional
budgets on the other models in the fallback chain.

---

## Project structure

```
electrique/
    .env                              GEMINI_API_KEYS (loaded automatically)
    README.md
    images/                           Panel screenshots (input)
    output/
        historique.json               Source of truth — all extractions ever
        historique.xlsx               Regenerated each run, 4 sheets
    extractor/
        __init__.py                   Public API exports
        __main__.py                   CLI entry point
        app.py                        Streamlit web UI
        requirements.txt
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
    archive/                          Earlier experiments (can be deleted)
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

Install:

```bash
pip install -r extractor/requirements.txt
```

Python 3.11+ required.

---

## Behaviour notes

- **Hardcoded for the AQUILLA panel.** Zone labels (B-C, C-A, A-B), table
  names, column headers, and value ranges are calibrated for this specific
  panel. Adapting to a different panel type means editing `core/prompts.py`
  and `models/panel.py`.
- **Crop percentages** in `io/image.py` are calibrated for the AQUILLA layout.
  They are used only for Pass 2 verification. If the crops miss the tables
  on a non-standard screenshot, Pass 1 (full image) still produces correct
  values — Pass 2 just stops adding verification.
- **History timestamps** are captured at the start of extraction
  (`datetime.now()` when the user clicks Extract), not at file save time.
- **Atomic writes** for the JSON log: writes to `historique.json.tmp` then
  renames — no corruption even if the process is killed mid-write.
- **Accuracy does not degrade with history size.** The JSON is read/written
  in full each run. With 10,000 extractions the file is still <2 MB.
