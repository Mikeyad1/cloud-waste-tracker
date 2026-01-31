# Aggregate spend from scan-derived data (EC2, SP) for Spend page and Overview.
from __future__ import annotations

import pandas as pd
import streamlit as st


def get_spend_from_scan() -> tuple[float, pd.DataFrame]:
    """
    Build spend total and by-service/region from session state (ec2_df, SP data).

    Returns:
        (total_usd, df) where df has columns: service, region, amount_usd.
        total_usd is the sum of amount_usd. region may be "—" for service-level rows.
    """
    rows: list[dict] = []
    total = 0.0

    # EC2: sum monthly_cost_usd by region
    ec2_df = st.session_state.get("ec2_df", pd.DataFrame())
    if ec2_df is not None and not ec2_df.empty:
        cost_col = None
        for c in ["monthly_cost_usd", "Monthly Cost (USD)", "monthly_cost"]:
            if c in ec2_df.columns:
                cost_col = c
                break
        region_col = None
        for c in ["region", "Region"]:
            if c in ec2_df.columns:
                region_col = c
                break
        if cost_col:
            amounts = pd.to_numeric(ec2_df[cost_col], errors="coerce").fillna(0)
            total_ec2 = amounts.sum()
            total += float(total_ec2)
            if region_col:
                by_region = ec2_df.groupby(region_col)[cost_col].apply(
                    lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum()
                ).reset_index()
                by_region.columns = ["region", "amount_usd"]
                for _, row in by_region.iterrows():
                    rows.append({"service": "EC2", "region": str(row["region"]), "amount_usd": float(row["amount_usd"])})
            else:
                rows.append({"service": "EC2", "region": "—", "amount_usd": float(total_ec2)})

    # Savings Plans: from coverage trend (covered + on-demand) or summary
    sp_coverage = st.session_state.get("SP_COVERAGE_TREND", pd.DataFrame())
    if sp_coverage is not None and not sp_coverage.empty:
        covered = 0.0
        ondemand = 0.0
        for c in ["covered_spend", "Covered Spend"]:
            if c in sp_coverage.columns:
                covered = pd.to_numeric(sp_coverage[c], errors="coerce").fillna(0).sum()
                break
        for c in ["ondemand_spend", "On-Demand Spend"]:
            if c in sp_coverage.columns:
                ondemand = pd.to_numeric(sp_coverage[c], errors="coerce").fillna(0).sum()
                break
        if covered > 0 or ondemand > 0:
            total_sp = covered + ondemand
            total += total_sp
            rows.append({"service": "Savings Plans (covered)", "region": "—", "amount_usd": float(covered)})
            rows.append({"service": "Savings Plans (on-demand)", "region": "—", "amount_usd": float(ondemand)})

    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["service", "region", "amount_usd"])
    return total, df
