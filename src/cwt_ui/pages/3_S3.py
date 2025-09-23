# src/cwt_ui/pages/3_S3.py
from __future__ import annotations
import pandas as pd
import streamlit as st

def _to_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _to_bool(x) -> bool | None:
    s = str(x).strip().lower()
    if s in {"true", "1", "yes"}:  return True
    if s in {"false", "0", "no"}:  return False
    return None

def _cold_flag(v) -> str:
    txt = str(v).strip().upper()
    return "🟢" if txt == "OK" else "🔴"

def _prep(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()

    # ensure expected columns exist
    for col in [
        "bucket","region","size_total_gb","objects_total",
        "standard_cold_gb","standard_cold_objects",
        "lifecycle_defined","recommendation","notes","status"
    ]:
        if col not in out.columns:
            out[col] = None

    # numeric normalization
    for col in ["size_total_gb","standard_cold_gb"]:
        out[col] = out[col].apply(_to_float).fillna(0.0)

    for col in ["objects_total","standard_cold_objects"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)

    # lifecycle -> bool where possible
    out["lifecycle_defined_bool"] = out["lifecycle_defined"].map(_to_bool)

    # cold ratio (0..1)
    denom = out["size_total_gb"].replace(0, pd.NA)
    ratio = out["standard_cold_gb"] / denom
    out["cold_ratio"] = ratio.clip(lower=0, upper=1).fillna(0.0)

    # status fallback
    if "status" not in out or out["status"].isna().all():
        out["status"] = out["recommendation"].astype(str).str.upper().map(
            lambda x: "🟢 OK" if x == "OK" else "🔴 Action"
        )
    return out

def _summary(df: pd.DataFrame) -> tuple[float, int, float, int]:
    if df is None or df.empty:
        return 0.0, 0, 0.0, 0
    return (
        float(df["size_total_gb"].sum()),
        int(df["objects_total"].sum()),
        float(df["standard_cold_gb"].sum()),
        int(df["standard_cold_objects"].sum()),
    )

def render(s3_df: pd.DataFrame, tables, formatters) -> None:
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
        # prefer the coerced bool column; fall back to string matching if needed
        has_bool = filtered["lifecycle_defined_bool"].notna()
        filtered = filtered[
            (has_bool & (filtered["lifecycle_defined_bool"] == want)) |
            (~has_bool & (filtered["lifecycle_defined"].astype(str).str.lower() == ("true" if want else "false")))
        ]

    if reco_sel != "Any":
        is_ok = filtered["recommendation"].astype(str).str.upper().eq("OK")
        filtered = filtered[is_ok] if reco_sel == "OK" else filtered[~is_ok]

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
    column_order = [
        "status","bucket","region","size_total_gb","objects_total",
        "standard_cold_gb","standard_cold_objects","cold_ratio",
        "lifecycle_defined","recommendation","notes",
    ]

    numeric_formatters = {
        "size_total_gb":      lambda x: formatters.human_gb(x, 2),
        "standard_cold_gb":   lambda x: formatters.human_gb(x, 2),
        "cold_ratio":         (lambda x: formatters.percent(float(x) * 100, 2)),  # 0..1 -> %
        "objects_total":      (lambda x: f"{int(float(x)):,}" if str(x).strip() != "" else x),
        "standard_cold_objects": (lambda x: f"{int(float(x)):,}" if str(x).strip() != "" else x),
    }

    highlight_rules = {
        "recommendation": _cold_flag
    }

    display_df = filtered.sort_values("standard_cold_gb", ascending=False)

    tables.render(
        display_df,
        column_order=column_order,
        numeric_formatters=numeric_formatters,
        highlight_rules=highlight_rules,
    )

    st.caption("Tip: buckets with high Cold size and no lifecycle are prime candidates for lifecycle policies.")
