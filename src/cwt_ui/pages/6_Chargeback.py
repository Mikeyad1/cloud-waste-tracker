# pages/6_Chargeback.py — Chargeback
from __future__ import annotations

import sys
from pathlib import Path

for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parent.parents]:
    if (p / "src").exists() and str(p / "src") not in sys.path:
        sys.path.insert(0, str(p / "src"))
        break

import streamlit as st
from cwt_ui.components.ui.header import render_page_header

st.set_page_config(page_title="Chargeback", page_icon="📋", layout="wide")

render_page_header(
    title="Chargeback",
    subtitle="Showback / chargeback by team or product.",
    icon="📋",
)

st.info("**Coming soon.** Allocation model (by tag or account), summary by team/product, detail table, and export will appear here after Spend and allocation rules are set.")
