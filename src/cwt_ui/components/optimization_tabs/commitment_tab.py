# Optimization > Commitment (Savings Plans, EC2 vs SP) tab
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

# Ensure src on path for loading page modules (pages are under cwt_ui/pages)
_pages_dir = Path(__file__).resolve().parent.parent.parent / "pages"
for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parent.parents]:
    if (p / "src").exists() and str(p / "src") not in sys.path:
        sys.path.insert(0, str(p / "src"))
        break


def _run_page_as_tab(script_name: str) -> None:
    """Load and run a page script without its set_page_config/header (for embedding in tab)."""
    import importlib.util
    path = _pages_dir / script_name
    if not path.exists():
        st.info(f"Page module not found: {script_name}")
        return
    try:
        os.environ["CWT_AS_TAB"] = "1"
        spec = importlib.util.spec_from_file_location("_tab_page", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        os.environ.pop("CWT_AS_TAB", None)


def render_commitment_tab() -> None:
    sub_tab1, sub_tab2 = st.tabs(["Savings Plans", "EC2 vs SP Alignment"])
    with sub_tab1:
        st.markdown("##### Savings Plans — coverage and utilization")
        _run_page_as_tab("archive/1_Savings_Plans.py")
    with sub_tab2:
        st.markdown("##### EC2 vs Savings Plans alignment")
        _run_page_as_tab("archive/2_EC2_vs_SP_Alignment.py")
