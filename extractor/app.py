"""
Streamlit Web UI — Panel Data Extractor.

Single-image upload per run. Each extraction is appended to a persistent
history (historique.json) and the Excel file (historique.xlsx) is
regenerated with the full history after every run.

Run:
    streamlit run extractor/app.py
"""

from __future__ import annotations

import logging
import tempfile
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

logging.basicConfig(level=logging.INFO)

# ── Paths ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
HISTORY_JSON = OUTPUT_DIR / "historique.json"
HISTORY_XLSX = OUTPUT_DIR / "historique.xlsx"

# ── Page ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Panel Extractor — AQUILLA",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; max-width: 1100px; }
    header[data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"],
    button[data-testid="stSidebarCollapsedControl"] { display: none; }

    .hero {
        background: linear-gradient(135deg, #1a237e 0%, #283593 45%, #2e7d32 100%);
        padding: 1.4rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.8rem;
    }
    .hero h1 { color:#fff; margin:0; font-size:1.55rem; font-weight:700; }
    .hero p  { color:rgba(255,255,255,.75); margin:.3rem 0 0; font-size:.88rem; }

    .stFileUploader > div { border: 2px dashed #c5cae9 !important; border-radius: 10px !important; }

    .sec { font-size:.95rem; font-weight:600; margin:1rem 0 .4rem; padding-bottom:.3rem; }
    .sec-blue  { color:#1a237e; border-bottom:2px solid #c5cae9; }
    .sec-green { color:#2e7d32; border-bottom:2px solid #a5d6a7; }

    [data-testid="stMetric"] {
        background:#e8f5e9; border:1px solid #c8e6c9;
        border-radius:8px; padding:.6rem .8rem; text-align:center;
    }
    [data-testid="stMetricValue"] { font-size:1.25rem !important; color:#1b5e20 !important; }
    [data-testid="stMetricLabel"] { font-size:.75rem !important; color:#555 !important; }

    .ok-badge {
        display:inline-block; background:#c8e6c9; color:#1b5e20;
        padding:.2rem .7rem; border-radius:16px; font-size:.78rem; font-weight:600;
    }
    .history-badge {
        display:inline-block; background:#e3f2fd; color:#1565c0;
        padding:.2rem .7rem; border-radius:16px; font-size:.78rem; font-weight:600;
        margin-left:.5rem;
    }

    .empty-state { text-align:center; padding:5rem 2rem; color:#bbb; }
    .empty-state .icon { font-size:2.5rem; margin-bottom:.8rem; opacity:.4; }
    .empty-state p { margin:0; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero">
    <h1>⚡ Electron Processing System — Extracteur de Donnees</h1>
    <p>Chaque analyse est ajoutee a l'historique &rarr; un seul Excel evolutif</p>
</div>
""", unsafe_allow_html=True)

# ── Load settings + current history count ──────────────────────────────

from extractor.io.config import load_settings
from extractor.io.history import load_history

settings = load_settings()
if not settings.api_keys:
    st.error("Aucune cle API configuree. Ajoutez vos cles dans le fichier `.env`:\n\n"
             "`GEMINI_API_KEYS=key1,key2,key3`")
    st.stop()

existing_history = load_history(HISTORY_JSON)
history_count = len(existing_history)

# ── Session state ──────────────────────────────────────────────────────

if "analyzing" not in st.session_state:
    st.session_state.analyzing = False
if "last_result" not in st.session_state:
    st.session_state.last_result = None  # (data, analysis_dt, source, duration, total_count)

analyzing = st.session_state.analyzing

# ── Layout ─────────────────────────────────────────────────────────────

col_left, col_right = st.columns([4, 6], gap="large")

with col_left:
    uploaded = st.file_uploader(
        "Importer la capture du panneau",
        type=["jfif", "jpg", "jpeg", "png", "bmp", "webp"],
        accept_multiple_files=False,
        disabled=analyzing,
    )

    if uploaded:
        st.image(uploaded, width="stretch")
        st.caption(f"{uploaded.name} — {uploaded.size / 1024:.0f} KB")

    btn_label = "Analyse en cours..." if analyzing else "Extraire les valeurs"
    extract_btn = st.button(
        btn_label,
        type="primary",
        width="stretch",
        disabled=(not uploaded) or analyzing,
    )

    # History info is hidden during analysis to keep the UI focused
    if not analyzing:
        st.markdown("")
        st.markdown(
            f'<span class="history-badge">📚 {history_count} extraction(s) dans l\'historique</span>',
            unsafe_allow_html=True,
        )
        if history_count > 0:
            last_dt = max(e.analysis_datetime for e in existing_history)
            st.caption(f"Derniere analyse: {last_dt.strftime('%d/%m/%Y a %H:%M')}")


def render_data(data, analysis_dt, source_name):
    """Render extracted data preview."""
    st.markdown('<span class="ok-badge">21 valeurs extraites et validees</span>',
                unsafe_allow_html=True)
    st.caption(f"Analyse effectuee le {analysis_dt.strftime('%d/%m/%Y a %H:%M:%S')}  |  Source: {source_name}")

    st.markdown('<p class="sec sec-blue">Puissance ICT</p>', unsafe_allow_html=True)
    st.dataframe(
        [{
            "Zone": r.zone_tension,
            "Tension (V)": r.tension_primaire_v,
            "Zp": r.zone_courant_primaire,
            "Courant prim. (A)": r.courant_primaire_a,
            "Zs": r.zone_courant_secondaire,
            "Courant sec. (A)": r.courant_secondaire_a,
        } for r in data.puissance_ict],
        width="stretch", hide_index=True,
    )

    st.markdown('<p class="sec sec-green">Accelerateurs</p>', unsafe_allow_html=True)
    st.dataframe(
        [{
            "Zone": r.zone,
            "R Icol (KV)": r.r_icol_kv,
            "Courant col. (uA)": r.courant_colonne_ua,
            "Vide (Torr)": r.vide_torr,
            "Aperture (uA)": r.courant_aperture_ua,
        } for r in data.accelerateurs_zones],
        width="stretch", hide_index=True,
    )

    st.markdown('<p class="sec sec-green">Valeurs Globales</p>', unsafe_allow_html=True)
    g = data.accelerateurs_global
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tension", f"{g.tension_kv} KV")
    m2.metric("Charge", f"{g.charge_ma} mA")
    m3.metric("Faisceau A", f"{g.faisceau_ma_a} mA")
    m4.metric("Faisceau B", f"{g.faisceau_ma_b} mA")


with col_right:

    # ── User just clicked Extraire: enter analyzing state ──────────────
    if extract_btn and uploaded and not analyzing:
        st.session_state.analyzing = True
        st.session_state.last_result = None  # clear any previous result
        st.rerun()

    # ── Analyzing: show ONLY the progress bar (no old data visible) ────
    if st.session_state.analyzing and uploaded:
        from extractor.core.client import GeminiClient
        from extractor.core.extractor import extract
        from extractor.io.excel import Extraction
        from extractor.io.history import append_and_regenerate

        progress = st.progress(5, text="Preparation de l'image...")

        try:
            analysis_dt = datetime.now()
            t_start = time.time()

            with tempfile.NamedTemporaryFile(
                suffix=f".{uploaded.name.rsplit('.', 1)[-1]}", delete=False
            ) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name

            progress.progress(15, text="Analyse par vision IA (Pass 1)...")

            client = GeminiClient(settings.api_keys)
            data = extract(tmp_path, client, settings.primary_model)

            progress.progress(85, text="Mise a jour de l'historique...")

            new_ext = Extraction(
                data=data,
                analysis_datetime=analysis_dt,
                source_filename=uploaded.name,
            )
            full_history = append_and_regenerate(new_ext, HISTORY_JSON, HISTORY_XLSX)
            duration = time.time() - t_start

            # Save result in session and clear analyzing flag, then rerun
            st.session_state.last_result = {
                "data": data,
                "analysis_dt": analysis_dt,
                "source": uploaded.name,
                "duration": duration,
                "total_count": len(full_history),
                "first_dt": min(e.analysis_datetime for e in full_history),
            }
            st.session_state.analyzing = False
            progress.empty()
            st.rerun()

        except Exception as e:
            st.session_state.analyzing = False
            progress.empty()
            st.error(f"Echec de l'extraction: {e}")

    # ── Result available: show the new extraction ──────────────────────
    elif st.session_state.last_result is not None:
        r = st.session_state.last_result
        analysis_dt = r["analysis_dt"]
        first_dt = r["first_dt"]
        total = r["total_count"]
        delta = analysis_dt - first_dt
        span_days = delta.days
        if span_days >= 1:
            span_text = f"{span_days} jour(s)"
        elif delta.total_seconds() >= 3600:
            span_text = f"{delta.total_seconds() / 3600:.1f} h"
        else:
            span_text = "< 1 h"

        info_cols = st.columns([1, 1, 1, 1])
        info_cols[0].metric("Extraction #", total)
        info_cols[1].metric("Duree", f"{r['duration']:.1f} s")
        info_cols[2].metric("Historique", f"{total} total")
        info_cols[3].metric("Periode", span_text)

        if HISTORY_XLSX.exists():
            xlsx_bytes = HISTORY_XLSX.read_bytes()
            st.download_button(
                label=f"📥 Telecharger l'historique ({total} extractions)",
                data=xlsx_bytes,
                file_name="historique.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                width="stretch",
            )
            st.caption(f"Fichier sur disque: `{HISTORY_XLSX}`")

        st.markdown("")
        render_data(r["data"], r["analysis_dt"], r["source"])

    # ── No image uploaded + no current result: show last history ───────
    elif not uploaded:
        if existing_history:
            st.markdown("**Derniere extraction dans l'historique**")
            latest = max(existing_history, key=lambda e: e.analysis_datetime)
            render_data(latest.data, latest.analysis_datetime, latest.source_filename)

            if HISTORY_XLSX.exists():
                xlsx_bytes = HISTORY_XLSX.read_bytes()
                st.markdown("")
                st.download_button(
                    label=f"📥 Telecharger l'historique ({history_count} extractions)",
                    data=xlsx_bytes,
                    file_name="historique.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )
        else:
            st.markdown("""
            <div class="empty-state">
                <div class="icon">📊</div>
                <p style="font-size:1rem;">Les resultats apparaitront ici</p>
                <p style="font-size:.85rem; margin-top:.3rem;">Importez une capture et cliquez sur Extraire</p>
            </div>
            """, unsafe_allow_html=True)

    # ── Image uploaded, waiting for click ──────────────────────────────
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">⏵</div>
            <p style="font-size:1rem;">Image chargee</p>
            <p style="font-size:.85rem; margin-top:.3rem;">Cliquez sur "Extraire les valeurs" pour lancer l'analyse</p>
        </div>
        """, unsafe_allow_html=True)
