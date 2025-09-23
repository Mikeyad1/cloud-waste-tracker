# src/cwt_ui/pages/2_EC2.py
from __future__ import annotations
import pandas as pd
import streamlit as st

# Expected columns (best-effort; the page adapts if some are missing):
# ["instance_id","name","instance_type","region","avg_cpu_7d","monthly_cost_usd","recommendation","status"]

def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _compute_kpis(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"total": 0, "idle": 0, "waste": 0.0, "avg_cpu": 0.0}

    total = len(df)

    if "recommendation" in df.columns:
        idle_mask = ~df["recommendation"].astype(str).str.upper().eq("OK")
    else:
        idle_mask = pd.Series(False, index=df.index)
    idle = int(idle_mask.sum())

    if "monthly_cost_usd" in df.columns:
        waste = pd.to_numeric(df.loc[idle_mask, "monthly_cost_usd"], errors="coerce").fillna(0.0).sum()
    else:
        waste = 0.0

    if "avg_cpu_7d" in df.columns:
        avg_cpu = pd.to_numeric(df["avg_cpu_7d"], errors="coerce").fillna(0.0).mean()
    else:
        avg_cpu = 0.0

    return {"total": int(total), "idle": int(idle), "waste": float(waste), "avg_cpu": float(avg_cpu)}

def _filtered(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    with st.sidebar:
        st.subheader("EC2 Filters")

        # Regions
        if "region" in df.columns:
            regions = sorted(df["region"].dropna().astype(str).unique().tolist())
        else:
            regions = []
        selected_regions = st.multiselect("Region", regions, default=regions)

        # Recommendations
        if "recommendation" in df.columns:
            recos = sorted(df["recommendation"].fillna("UNKNOWN").astype(str).unique().tolist())
        else:
            recos = []
        selected_recos = st.multiselect("Recommendation", recos, default=recos)

        # Search
        query = st.text_input("Search (instance_id / name)", value="").strip().lower()

        # Min cost slider
        if "monthly_cost_usd" in df.columns:
            costs = pd.to_numeric(df["monthly_cost_usd"], errors="coerce").fillna(0.0)
            min_cost, max_cost = float(costs.min()), float(costs.max())
        else:
            min_cost, max_cost = 0.0, 0.0
        selected_min_cost = st.slider(
            "Min monthly cost (USD)",
            min_value=0.0,
            max_value=max(100.0, max_cost),
            value=min_cost if min_cost >= 0 else 0.0,
        )

        # Sort options
        sort_candidates = ["monthly_cost_usd","avg_cpu_7d","region","instance_type","name","instance_id"]
        sort_by = st.selectbox("Sort by", options=[c for c in sort_candidates if c in df.columns] or ["instance_id"])
        ascending = st.checkbox("Ascending", value=False)

    out = df.copy()

    if "region" in out.columns and selected_regions:
        out = out[out["region"].isin(selected_regions)]

    if "recommendation" in out.columns and selected_recos:
        out = out[out["recommendation"].astype(str).isin(selected_recos)]

    if "monthly_cost_usd" in out.columns:
        out = out[pd.to_numeric(out["monthly_cost_usd"], errors="coerce").fillna(0.0) >= selected_min_cost]

    if query:
        id_ok = out["instance_id"].astype(str).str.lower().str.contains(query) if "instance_id" in out.columns else None
        name_ok = out["name"].astype(str).str.lower().str.contains(query) if "name" in out.columns else None
        if isinstance(id_ok, pd.Series) and isinstance(name_ok, pd.Series):
            out = out[id_ok | name_ok]
        elif isinstance(id_ok, pd.Series):
            out = out[id_ok]
        elif isinstance(name_ok, pd.Series):
            out = out[name_ok]

    if sort_by in out.columns:
        out = out.sort_values(sort_by, ascending=ascending, na_position="last")

    return out

def _download_csv_button(df: pd.DataFrame, label="Download CSV", fname="ec2_filtered.csv"):
    if df is None or df.empty:
        return
    st.download_button(label=label, data=df.to_csv(index=False).encode("utf-8"), file_name=fname, mime="text/csv")

def render(ec2_df: pd.DataFrame, tables, formatters) -> None:
    st.header("EC2 Instances")

    if ec2_df is None or ec2_df.empty:
        st.info("No EC2 data available.")
        return

    df = ec2_df.copy()
    if "status" not in df.columns and "recommendation" in df.columns:
        df["status"] = df["recommendation"].astype(str).str.upper().map(lambda x: "🟢 OK" if x == "OK" else "🔴 Action")

    # KPIs
    kpi = _compute_kpis(df)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total instances", kpi["total"])
    with c2: st.metric("Idle (est.)", kpi["idle"])
    with c3: st.metric("Est. monthly waste", formatters.currency(kpi["waste"]))
    with c4: st.metric("Avg CPU (7d)", f"{kpi['avg_cpu']:.2f}%")

    st.divider()

    filtered = _filtered(df)

    display_cols = [c for c in [
        "status","instance_id","name","instance_type","region","avg_cpu_7d","monthly_cost_usd","recommendation"
    ] if c in filtered.columns]

    tables.render(
        filtered[display_cols] if display_cols else filtered,
        column_order=display_cols or None,
        numeric_formatters={
            "monthly_cost_usd": formatters.currency,
            "avg_cpu_7d":      (lambda x: f"{_safe_float(x):.2f}"),
        },
        highlight_rules={
            "recommendation": (lambda v: "🟢" if str(v).strip().upper() == "OK" else "🔴"),
            "status":         (lambda v: "🟢 OK" if "🟢" in str(v) or str(v).strip().upper() == "OK" else "🔴 Action"),
        }
    )

    st.caption("Export the filtered view:")
    _download_csv_button(filtered[display_cols] if display_cols else filtered)
