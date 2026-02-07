# Aggregate spend from scan-derived data (EC2, SP) for Spend page and Overview.
from __future__ import annotations

import pandas as pd
import streamlit as st


def get_spend_from_scan(period: str = "this_month") -> tuple[float, pd.DataFrame]:
    """
    Build spend total and by-service/region from session state.

    When data_source is "synthetic", returns full service list (EC2, S3, Data Transfer, etc.)
    from synthetic_data.get_synthetic_spend(). Otherwise uses ec2_df + SP data only.
    period: "this_month" | "last_month" (last_month only applies to synthetic).

    Returns:
        (total_usd, df) where df has columns: service, region, amount_usd[, category, environment, team, cost_center, linked_account_id, linked_account_name].
        total_usd is the sum of amount_usd. region may be "—" for service-level rows.
    """
    if st.session_state.get("data_source") == "synthetic":
        try:
            from cwt_ui.services.synthetic_data import get_synthetic_spend
            return get_synthetic_spend(period=period, include_tags=True)
        except Exception:
            pass  # fall through to scan-derived
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
                    rows.append({"service": "EC2", "region": str(row["region"]), "amount_usd": float(row["amount_usd"]), "category": "Compute"})
            else:
                rows.append({"service": "EC2", "region": "—", "amount_usd": float(total_ec2), "category": "Compute"})

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
            rows.append({"service": "Savings Plans (covered)", "region": "—", "amount_usd": float(covered), "category": "Commitment"})
            rows.append({"service": "Savings Plans (on-demand)", "region": "—", "amount_usd": float(ondemand), "category": "Commitment"})

    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["service", "region", "amount_usd", "category"])
    return total, df


def get_spend_mom_for_synthetic() -> tuple[float, float] | None:
    """
    For synthetic data only: returns (this_month_total, last_month_total) for MoM comparison.
    Returns None if not synthetic.
    """
    if st.session_state.get("data_source") != "synthetic":
        return None
    try:
        from cwt_ui.services.synthetic_data import get_synthetic_spend
        this_total, _ = get_synthetic_spend(period="this_month", include_tags=True)
        last_total, _ = get_synthetic_spend(period="last_month", include_tags=True)
        return (this_total, last_total)
    except Exception:
        return None


def get_optimization_metrics(ec2_df: pd.DataFrame) -> tuple[float, int]:
    """
    Compute optimization potential (sum of potential_savings_usd) and action count
    (recommendations that are not OK / No action) from EC2 dataframe.
    Used by Overview and by scan/synthetic load to store previous vs current.
    """
    if ec2_df is None or ec2_df.empty:
        return 0.0, 0
    potential = 0.0
    for col in ["potential_savings_usd", "Potential Savings ($)", "potential_savings"]:
        if col in ec2_df.columns:
            potential = float(pd.to_numeric(ec2_df[col], errors="coerce").fillna(0).sum())
            break
    rec_col = None
    for col in ["recommendation", "Recommendation"]:
        if col in ec2_df.columns:
            rec_col = col
            break
    action_count = 0
    if rec_col:
        rec_upper = ec2_df[rec_col].astype(str).str.upper()
        action_count = int((~rec_upper.str.contains("OK|NO ACTION", na=True)).sum())
    return potential, action_count
