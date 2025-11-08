from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import pandas as pd
from boto3.session import Session
from botocore.exceptions import ClientError

LOOKBACK_DAYS = 30


def _utc_today() -> datetime:
    return datetime.utcnow()


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _hours_between(start: datetime, end: datetime) -> float:
    delta = end - start
    return max(delta.total_seconds() / 3600.0, 1.0)


def scan_savings_plans() -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Fetch Savings Plans and utilization metrics for the past LOOKBACK_DAYS.

    Returns:
        tuple[pd.DataFrame, dict]: DataFrame of plan-level metrics and summary stats.
    """
    session = Session()

    try:
        savings_client = session.client("savingsplans")
        ce_client = session.client("ce", region_name="us-east-1")
    except Exception as exc:  # pragma: no cover - boto3 initialization errors
        raise RuntimeError(f"Failed to create AWS clients for Savings Plans: {exc}") from exc

    plans: List[Dict] = []
    next_token: str | None = None

    try:
        while True:
            kwargs: Dict[str, str] = {}
            if next_token:
                kwargs["nextToken"] = next_token
            response = savings_client.describe_savings_plans(**kwargs)  # type: ignore[arg-type]
            plans.extend(response.get("savingsPlans", []))
            next_token = response.get("nextToken")
            if not next_token:
                break
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"AccessDeniedException", "UnauthorizedOperation"}:
            summary = {
                "overall_utilization_pct": 0.0,
                "total_commitment_per_hour": 0.0,
                "total_used_per_hour": 0.0,
                "warning": (
                    "Savings Plans permissions are missing (savingsplans:DescribeSavingsPlans). "
                    "Skipping Savings Plan analysis."
                ),
            }
            return pd.DataFrame(
                columns=[
                    "Savings Plan",
                    "Plan Type",
                    "Term (months)",
                    "Commitment ($/hr)",
                    "Actual Usage ($/hr)",
                    "Utilization (%)",
                    "Forecast Utilization (%)",
                ]
            ), summary
        raise RuntimeError(f"Failed to list Savings Plans: {exc}") from exc

    if not plans:
        empty_df = pd.DataFrame(
            columns=[
                "Savings Plan",
                "Plan Type",
                "Term (months)",
                "Commitment ($/hr)",
                "Actual Usage ($/hr)",
                "Utilization (%)",
                "Forecast Utilization (%)",
            ]
        )
        summary = {
            "overall_utilization_pct": 0.0,
            "total_commitment_per_hour": 0.0,
            "total_used_per_hour": 0.0,
        }
        return empty_df, summary

    end_dt = _utc_today().replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
    hours_in_window = _hours_between(start_dt, end_dt)

    utilization_by_arn: Dict[str, Dict] = {}
    next_token = None

    try:
        while True:
            params: Dict = {
                "TimePeriod": {"Start": _date_str(start_dt), "End": _date_str(end_dt)},
                "Granularity": "DAILY",
            }
            if next_token:
                params["NextToken"] = next_token
            resp = ce_client.get_savings_plans_utilization_details(**params)
            for detail in resp.get("SavingsPlansUtilizationDetails", []):
                arn = detail.get("SavingsPlanArn")
                if arn:
                    utilization_by_arn[arn] = detail.get("Utilization", {})
            next_token = resp.get("NextToken")
            if not next_token:
                break
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"AccessDeniedException", "UnauthorizedOperation"}:
            summary = {
                "overall_utilization_pct": 0.0,
                "total_commitment_per_hour": 0.0,
                "total_used_per_hour": 0.0,
                "warning": (
                    "Savings Plans permissions are missing (ce:GetSavingsPlansUtilizationDetails). "
                    "Skipping Savings Plan analysis."
                ),
            }
            return pd.DataFrame(
                columns=[
                    "Savings Plan",
                    "Plan Type",
                    "Term (months)",
                    "Commitment ($/hr)",
                    "Actual Usage ($/hr)",
                    "Utilization (%)",
                    "Forecast Utilization (%)",
                ]
            ), summary
        raise RuntimeError(f"Failed to retrieve Savings Plans utilization: {exc}") from exc

    rows: List[Dict[str, float | str]] = []
    total_commitment_per_hour = 0.0
    total_used_per_hour = 0.0

    for plan in plans:
        arn = plan.get("savingsPlanArn", "")
        plan_id = plan.get("savingsPlanId", arn[-12:] if arn else "Unknown")
        plan_type = plan.get("savingsPlanType", "Unknown")
        term_seconds = float(plan.get("termDurationInSeconds") or 0)
        term_months = term_seconds / (3600 * 24 * 30) if term_seconds else 0.0
        commitment_per_hour = float(plan.get("commitment") or 0.0)

        utilization = utilization_by_arn.get(arn, {})
        total_commitment_amount = float(utilization.get("TotalCommitment", {}).get("Amount", 0.0))
        used_commitment_amount = float(utilization.get("UsedCommitment", {}).get("Amount", 0.0))
        utilization_pct = float(utilization.get("UtilizationPercentage") or 0.0)

        # Derive commitment/usage per hour from the utilization window when available
        if total_commitment_amount > 0:
            commitment_per_hour = total_commitment_amount / hours_in_window
        actual_usage_per_hour = (
            used_commitment_amount / hours_in_window if used_commitment_amount > 0 else 0.0
        )

        total_commitment_per_hour += commitment_per_hour
        total_used_per_hour += actual_usage_per_hour

        forecast_utilization_pct = utilization_pct  # Simple projection based on recent average

        rows.append(
            {
                "Savings Plan": plan_id,
                "Plan Type": plan_type,
                "Term (months)": round(term_months, 1),
                "Commitment ($/hr)": round(commitment_per_hour, 4),
                "Actual Usage ($/hr)": round(actual_usage_per_hour, 4),
                "Utilization (%)": round(utilization_pct, 2),
                "Forecast Utilization (%)": round(forecast_utilization_pct, 2),
            }
        )

    overall_utilization_pct = (
        (total_used_per_hour / total_commitment_per_hour) * 100.0
        if total_commitment_per_hour > 0
        else 0.0
    )

    summary = {
        "overall_utilization_pct": round(overall_utilization_pct, 2),
        "total_commitment_per_hour": round(total_commitment_per_hour, 4),
        "total_used_per_hour": round(total_used_per_hour, 4),
    }

    df = pd.DataFrame(rows)
    return df, summary

