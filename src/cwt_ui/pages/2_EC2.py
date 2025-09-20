# src/cwt_ui/pages/2_EC2.py
from __future__ import annotations
import io
import pandas as pd
import streamlit as st

# Expected columns (best-effort; the page will adapt if some are missing):
# ["instance_id","name","instance_type","region","avg_cpu_7d","monthly_cost_usd","recommendation","status"]

def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _normalize_reco(v: object) -> str:
    s = str(v).strip().upper()
    return s if s else "UNKNOWN"

def _compute_kpis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total": 0, "idle": 0, "waste": 0.0, "avg_cpu": 0.0}
    total = len(df)
    reco_col = "recommendation" if "recommendation" in df.columns else None
    cost_col = "monthly_cost_usd" if "monthly_cost_usd" in df.columns else None
    cpu_col  = "avg_cpu_7d" if "avg_cpu_7d" in df.columns else None

    if reco_col:
        idle_mask = ~df[reco_col].astype(str).str.upper().eq("OK")
        idle = int(idle_mask.sum())
    else:
        idle = 0

    if cost_col and reco_col:
        waste = float(df.loc[~df[reco_col].astype(str).str.upper().eq("OK"), cost_col].fillna(0).map(_safe_float).sum())
    else:
        waste = 0.0

    if cpu_col and cpu_col in df.columns:
        avg_cpu = float(pd.to_numeric(df[cpu_col], errors="coerce").fillna(0).mean())
    else:
        avg_cpu = 0.0

    return {"total": total, "idle": idle, "waste": waste, "avg_cpu": avg_cpu}

def _filtered(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    # Sidebar filters
    with st.sidebar:
        st.subheader("EC2 Filters")

        # Region filter
        regions = sorted([r for r in df["region"].dropna().unique().tolist()]) if "region" in df.columns else []
        selected_regions = st.multiselect("Region", regions, default=regions)

        # Recommendation filter
        if "recommendation" in df.columns:
            recos = sorted(df["recommendation"].fillna("UNKNOWN").astype(str).unique().tolist())
        else:
            recos = []
        selected_recos = st.multiselect("Recommendation", recos, default=recos)

        # Search by id/name
        query = st.text_input("Search (instance_id / name)", value="").strip().lower()

        # Min monthly cost
        if "monthly_cost_usd" in df.columns:
            min_cost = float(pd.to_numeric(df["monthly_cost_usd"], errors="coerce").fillna(0).min())
            max_cost = float(pd.to_numeric(df["monthly_cost_usd"], errors="coerce").fillna(0).max())
        else:
            min_cost, max_cost = 0.0, 0.0
        selected_min_cost = st.slider("Min monthly cost (USD)", min_value=float(0.0), max_value=float(max_cost if max_cost>0 else 100.0), value=float(min_cost if min_cost>=0 else 0.0))

        # Sort
        sort_options = []
        for col in ["monthly_cost_usd","avg_cpu_7d","region","instance_type","name","instance_id"]:
            if col in df.columns:
                sort_options.append(col)
        sort_by = st.selectbox("Sort by", options=sort_options or ["instance_id"])
        ascending = st.checkbox("Ascending", value=False)

    # Apply filters
    out = df.copy()

    # Region
    if "region" in out.columns and selected_regions:
        out = out[out["region"].isin(selected_regions)]

    # Recommendation
    if "recommendation" in out.columns and selected_recos:
        out = out[out["recommendation"].astype(str).isin(selected_recos)]

    # Cost
    if "monthly_cost_usd" in out.columns:
        out = out[pd.to_numeric(out["monthly_cost_usd"], errors="coerce").fillna(0) >= selected_min_cost]

    # Search
    if query:
        id_ok = out["instance_id"].astype(str).str.lower().str.contains(query) if "instance_id" in out.columns else False
        name_ok = out["name"].astype(str).str.lower().str.contains(query) if "name" in out.columns else False
        if isinstance(id_ok, pd.Series) and isinstance(name_ok, pd.Series):
            out = out[id_ok | name_ok]
        elif isinstance(id_ok, pd.Series):
            out = out[id_ok]
        elif isinstance(name_ok, pd.Series):
            out = out[name_ok]

    # Sort
    if sort_by in out.columns:
        out = out.sort_values(sort_by, ascending=ascending, na_position="last")

    return out

def _download_csv_button(df: pd.DataFrame, label="Download CSV", fname="ec2_filtered.csv"):
    if df.empty:
        return
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(label=label, data=csv, file_name=fname, mime="text/csv")

def render(ec2_df: pd.DataFrame, tables, formatters) -> None:
    st.header("EC2 Instances")

    if ec2_df is None or ec2_df.empty:
        st.info("No EC2 data available.")
        return

    # Ensure a status column (🔴/🟢) exists for visual scanning
    df = ec2_df.copy()
    if "status" not in df.columns and "recommendation" in df.columns:
        df["status"] = df["recommendation"].astype(str).str.upper().map(lambda x: "🟢 OK" if x == "OK" else "🔴 Action")

    # KPIs (before filters, using full dataset)
    kpi = _compute_kpis(df)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total instances", kpi["total"])
    with c2: st.metric("Idle (est.)", kpi["idle"])
    with c3: st.metric("Est. monthly waste", formatters.currency(kpi["waste"]))
    with c4: st.metric("Avg CPU (7d)", f"{kpi['avg_cpu']:.2f}%")

    st.divider()

    # Apply filters
    filtered = _filtered(df)

    # Columns to display (keep order if exists)
    display_cols = [c for c in [
        "status",
        "instance_id",
        "name",
        "instance_type",
        "region",
        "avg_cpu_7d",
        "monthly_cost_usd",
        "recommendation"
    ] if c in filtered.columns]

    # Render table with basic formatting and highlight flags
    tables.render(
        filtered[display_cols] if display_cols else filtered,
        column_order=display_cols or None,
        numeric_formatters={
            "monthly_cost_usd": formatters.currency
        },
        highlight_rules={
            "recommendation": (lambda v: "🟢" if str(v).strip().upper() == "OK" else "🔴")
        }
    )

    # Download
    st.caption("Export the filtered view:")
    _download_csv_button(filtered[display_cols] if display_cols else filtered)

