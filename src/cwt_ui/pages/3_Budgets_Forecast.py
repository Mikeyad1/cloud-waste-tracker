# pages/3_Budgets_Forecast.py — Budgets & Forecast
from __future__ import annotations

import sys
from pathlib import Path

for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parent.parents]:
    if (p / "src").exists() and str(p / "src") not in sys.path:
        sys.path.insert(0, str(p / "src"))
        break

import streamlit as st
from cwt_ui.components.ui.header import render_page_header

st.set_page_config(page_title="Budgets & Forecast", page_icon="📈", layout="wide")

render_page_header(
    title="Budgets & Forecast",
    subtitle="Budgets, forecasts, and variance.",
    icon="📈",
)

st.info("**Coming soon.** Budget list (name, scope, amount, period, consumed %, status), per-budget detail, forecast, and alerts will appear here after Spend is connected.")
