# src/cwt_ui/pages/3_S3.py
from __future__ import annotations
import pandas as pd
import streamlit as st
from typing import Optional

def _to_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _cold_flag(v) -> str:
    """Emoji/marker for recommendation column."""
    txt = str(v).strip().upper()
    return "🟢" if txt == "OK" else "🔴"

def _prep(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()

    # Ensure expected columns exist (avoid key errors)
    for col in [
        "bucket","region","size_total_gb","objects_total",
        "standard_cold_gb","standard_cold_objects",
        "lifecycle_defined","recommendation","notes","status"
    ]:
        if col not in out.columns:
            out[col] = None

    # Normalize numeric columns
    for col in ["size_total_gb","standard_cold_gb"]:
        out[col] = out[col].apply(_to_float)

    for col in ["objects_total","standard_cold_objects"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)

    # Derive % cold of total (GB)
    with pd.option_context("mode.use_inf_as_na", True):
        out["cold_ratio"] = (
            (out["standard_cold_gb"] / out["size_total_gb"])
            .replace([pd.NA, pd.NaT], 0)
            .fillna(0)
        )
        out.loc[out["size_total_gb"] <= 0, "cold_ratio"] = 0.0

    # Status fallback if missing
    if "status" not in out or out["status"].isna().all():
        out["status"] = out["recommendation"].astype(str).str.upper().map(
            lambda x: "🟢 OK" if x == "OK" else "🔴 Action"
        )

    return out

def _summary(df: pd.DataFrame) -> tuple[float, int, float, int]:
    """Return (total_gb, total_objects, total_cold_gb, total_cold_objects)."""
    if df is None or df.empty:
        return 0.0, 0, 0.0, 0
    total_gb = float(df["size_total_gb"].sum())
    total_objs = int(df["objects_total"].sum())
    cold_gb = float(df["standard_cold_gb"].sum())
    cold_objs = int(df["standard_cold_objects"].sum())
    return total_gb, total_objs, cold_gb, cold_objs

def render(s3_df: pd.DataFrame, tables, formatters) -> None:
    """
    Render S3 details page:
      - Filters (region, lifecycle flag, recommendation)
      - KPI bar (totals)
      - Buckets table with formatting and flags
    """
    st.header("S3")

    df = _prep(s3_df)
    if df.empty:
        st.info("No S3 data available.")
        return

    # --- Filters ---
    with st.expander("Filters", expanded=False):
        regions = sorted([r for r in df["region"].dropna().unique().tolist() if r])
        region_sel = st.multiselect("Region", regions, default=regions)

        lifecycle_options = ["Any", "True", "False"]
        lifecycle_sel = st.selectbox("Lifecycle defined", lifecycle_options, index=0)

        reco_options = ["Any", "OK", "Action"]
        reco_sel = st.selectbox("Recommendation", reco_options, index=0)

        name_query = st.text_input("Bucket contains (substring)", "")

    filtered = df.copy()

    if region_sel:
        filtered = filtered[filtered["region"].isin(region_sel)]

    if lifecycle_sel != "Any":
        want = (lifecycle_sel == "True")
        filtered = filtered[filtered["lifecycle_defined"].astype(str).str.lower().isin(["true" if want else "false"])]

    if reco_sel != "Any":
        if reco_sel == "OK":
            mask = filtered["recommendation"].astype(str).str.upper().eq("OK")
        else:
            mask = ~filtered["recommendation"].astype(str).str.upper().eq("OK")
        filtered = filtered[mask]

    if name_query:
        q = name_query.strip().lower()
        filtered = filtered[filtered["bucket"].astype(str).str.lower().str.contains(q)]

    # --- KPIs ---
    total_gb, total_objs, cold_gb, cold_objs = _summary(filtered)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total size (GB)", formatters.human_gb(total_gb))
    c2.metric("Total objects", f"{total_objs:,}")
    c3.metric("Cold size (GB)", formatters.human_gb(cold_gb))
    c4.metric("Cold objects", f"{cold_objs:,}")

    # --- Table ---
    # Column order for a clean view
    column_order = [
        "status",
        "bucket",
        "region",
        "size_total_gb",
        "objects_total",
        "standard_cold_gb",
        "standard_cold_objects",
        "cold_ratio",
        "lifecycle_defined",
        "recommendation",
        "notes",
    ]

    # Numeric formatters
    numeric_formatters = {
        "size_total_gb": formatters.human_gb,
        "standard_cold_gb": formatters.human_gb,
        "cold_ratio": (lambda x: formatters.percent(float(x) * 100, 2)),  # expects 0..1 -> show as %
    }

    # Highlight flags (will render *_flag columns via tables.render)
    highlight_rules = {
        "recommendation": _cold_flag
    }

    # Sort by cold GB desc to surface biggest wins
    display_df = filtered.sort_values("standard_cold_gb", ascending=False)

    tables.render(
        display_df,
        column_order=column_order,
        numeric_formatters=numeric_formatters,
        highlight_rules=highlight_rules,
    )

    # --- Notes ---
    st.caption(
        "Tip: Buckets with high 'Cold size (GB)' and lifecycle_defined=False are prime candidates for lifecycle policies."
    )

