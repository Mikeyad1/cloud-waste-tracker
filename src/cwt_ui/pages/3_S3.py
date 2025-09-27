# src/cwt_ui/pages/3_S3.py
from __future__ import annotations
import pandas as pd
import streamlit as st
import os

# === Environment detection and debug mode ===
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()

# Auto-configure debug mode based on environment
if APP_ENV == "production":
    DEBUG_MODE = False
else:
    DEBUG_MODE = True


# Apply layout fixes inline
st.markdown("""
<style>
    .main .block-container {
        padding-left: 1rem;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Debug utilities inline
def debug_write(message: str):
    """Write debug message only if DEBUG_MODE is enabled"""
    if DEBUG_MODE:
        st.write(message)

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
    
    # DEBUG: Page load indicator
    debug_write("🔍 **DEBUG:** S3 page loaded")
    debug_write(f"   - S3 data shape: {s3_df.shape if not s3_df.empty else 'EMPTY'}")
    if not s3_df.empty:
        debug_write(f"   - S3 columns: {list(s3_df.columns)}")

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
        "Status","Bucket","Region","Total Size (GB)","Objects",
        "Cold STANDARD (GB)","Cold STANDARD (Objects)","cold_ratio",
        "Lifecycle Config","Recommendation","Why","Scanned At",
    ]

    numeric_formatters = {
        "Total Size (GB)":      lambda x: formatters.human_gb(x, 2),
        "Cold STANDARD (GB)":   lambda x: formatters.human_gb(x, 2),
        "cold_ratio":         (lambda x: formatters.percent(float(x) * 100, 2)),  # 0..1 -> %
        "Objects":      (lambda x: f"{int(float(x)):,}" if str(x).strip() != "" else x),
        "Cold STANDARD (Objects)": (lambda x: f"{int(float(x)):,}" if str(x).strip() != "" else x),
    }

    highlight_rules = {
        "Recommendation": _cold_flag
    }

    # Rename for clarity
    rename_map = {
        "status": "Status",
        "bucket": "Bucket",
        "region": "Region",
        "size_total_gb": "Total Size (GB)",
        "objects_total": "Objects",
        "standard_cold_gb": "Cold STANDARD (GB)",
        "standard_cold_objects": "Cold STANDARD (Objects)",
        "lifecycle_defined": "Lifecycle Config",
        "recommendation": "Recommendation",
        "notes": "Why",
        "scanned_at": "Scanned At",
    }
    display_df = filtered.rename(columns={k: v for k, v in rename_map.items() if k in filtered.columns})
    sort_by = "Cold STANDARD (GB)" if "Cold STANDARD (GB)" in display_df.columns else ("standard_cold_gb" if "standard_cold_gb" in display_df.columns else None)
    if sort_by:
        display_df = display_df.sort_values(sort_by, ascending=False)

    tables.render(
        display_df,
        column_order=column_order,
        numeric_formatters=numeric_formatters,
        highlight_rules=highlight_rules,
    )

    st.caption("Tip: buckets with high Cold size and no lifecycle are prime candidates for lifecycle policies.")


# Allow running as a Streamlit multipage without main app router
def _maybe_render_self():
    if st.runtime.exists():  # type: ignore[attr-defined]
        debug_write("🔍 **DEBUG:** S3 self-render called")
        df = st.session_state.get("s3_df")
        if df is None:
            df = pd.DataFrame()
        debug_write(f"   - Retrieved S3 data: {df.shape if not df.empty else 'EMPTY'}")
        try:
            from cwt_ui.components import tables as _tables
        except Exception:
            class _Tables:
                @staticmethod
                def render(df: pd.DataFrame, **_):
                    st.dataframe(df, use_container_width=True)
            _tables = _Tables()
        try:
            from cwt_ui.services import formatters as _formatters
        except Exception:
            class _Fmt:
                @staticmethod
                def percent(x, d: int = 2):
                    try: return f"{float(x):.{d}f}%"
                    except Exception: return str(x)
                @staticmethod
                def human_gb(x, d: int = 2):
                    try: return f"{float(x):.{d}f} GB"
                    except Exception: return str(x)
            _formatters = _Fmt()
        render(df, _tables, _formatters)


_maybe_render_self()