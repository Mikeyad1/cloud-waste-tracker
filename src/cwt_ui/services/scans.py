# src/cwt_ui/services/scans.py
from __future__ import annotations
from typing import Tuple, Optional, Any, Iterable, Mapping, List
import os
from contextlib import contextmanager
import pandas as pd
import boto3

# Import scanners from the new location: src/scanners
try:
    from scanners import ec2_scanner as _ec2_scanner  # type: ignore
except Exception:
    _ec2_scanner = None  # type: ignore

try:
    from scanners import s3_scanner as _s3_scanner  # type: ignore
except Exception:
    _s3_scanner = None  # type: ignore

try:
    from scanners.savings_plans_scanner import scan_savings_plans  # type: ignore
except Exception:
    scan_savings_plans = None  # type: ignore


_LAST_SAVINGS_PLAN_RESULTS: tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame] = (
    pd.DataFrame(),
    {},
    pd.DataFrame(),
    pd.DataFrame(),
)

# ------------------------------
# Public API (used by app.py)
# ------------------------------

def run_all_scans(
    region: str | List[str] | None = None, 
    aws_credentials: Optional[Mapping[str, str]] = None, 
    aws_auth_method: str = "user"
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run both EC2 and S3 scans, returning normalized DataFrames for the UI.
    
    If aws_credentials is provided, temporarily override environment variables for the
    duration of this call via process environment variables only (in-memory).
    
    Args:
        region: AWS region(s) to scan. Can be:
            - Single region string (e.g., "us-east-1")
            - List of regions (e.g., ["us-east-1", "us-west-2"])
            - None: auto-discover and scan all enabled regions
        aws_credentials: Credential mapping for IAM User auth
        aws_auth_method: "user" or "role" - determines how credentials are used
    
    For IAM User auth, keys supported: "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    "AWS_DEFAULT_REGION", "AWS_SESSION_TOKEN" (optional).
    
    For IAM Role auth, keys supported: "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    "AWS_DEFAULT_REGION", "AWS_ROLE_ARN", "AWS_EXTERNAL_ID", "AWS_ROLE_SESSION_NAME".
    """
    # Check if we should use role authentication from session state
    if aws_auth_method == "role":
        # Build credentials from session state if not provided
        if not aws_credentials:
            import streamlit as st
            creds = {}
            if st.session_state.get("aws_role_arn"):
                creds["AWS_ROLE_ARN"] = st.session_state.get("aws_role_arn", "")
                creds["AWS_EXTERNAL_ID"] = st.session_state.get("aws_external_id", "")
                creds["AWS_ROLE_SESSION_NAME"] = st.session_state.get("aws_role_session_name", "CloudWasteTracker")
                creds["AWS_DEFAULT_REGION"] = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
                aws_credentials = creds
        
        if aws_credentials and "AWS_ROLE_ARN" in aws_credentials:
            # Handle role-based authentication - ASSUME ROLE FIRST
            role_credentials = _assume_role(aws_credentials)
            if role_credentials:
                # Use temporary role credentials for everything
                with _temporary_env(role_credentials):
                    # NOW discover regions with the role credentials
                    if region is None:
                        try:
                            from core.services.region_service import discover_enabled_regions
                            # Discover regions using temporary role credentials (in env now)
                            regions = discover_enabled_regions(None, "user")  # Credentials are now in env
                            if os.getenv("APP_ENV", "development").strip().lower() != "production":
                                print(f"DEBUG: Discovered {len(regions)} regions: {regions}")
                            if not regions:
                                print("WARNING: No regions discovered, falling back to common regions")
                                from core.services.region_service import _common_regions
                                regions = _common_regions()
                        except Exception as e:
                            print(f"ERROR: Region discovery failed: {e}")
                            from core.services.region_service import _common_regions
                            regions = _common_regions()
                    elif isinstance(region, str):
                        regions = [region]
                    else:
                        regions = region
                    
                    return _scan_multiple_regions(regions, None, "user")  # Credentials are in env
            else:
                # Role assumption failed - raise an error with details
                role_arn = aws_credentials.get("AWS_ROLE_ARN", "Unknown")
                raise Exception(f"Failed to assume IAM role: {role_arn}. Please check:\n"
                              f"1. Role ARN is correct\n"
                              f"2. Base credentials have permission to assume the role\n"
                              f"3. External ID matches the role's trust policy (if required)\n"
                              f"4. Role trust policy allows the base user/account")
    
    # Normalize region input for non-role auth
    if region is None:
        # Auto-discover all enabled regions
        try:
            from core.services.region_service import discover_enabled_regions
            regions = discover_enabled_regions(aws_credentials, aws_auth_method)
            if os.getenv("APP_ENV", "development").strip().lower() != "production":
                print(f"DEBUG: Discovered {len(regions)} regions: {regions}")
            if not regions:
                from core.services.region_service import _common_regions
                regions = _common_regions()
        except Exception as e:
            print(f"ERROR: Region discovery failed: {e}")
            from core.services.region_service import _common_regions
            regions = _common_regions()
    elif isinstance(region, str):
        regions = [region]
    else:
        regions = region
    
    if aws_credentials:
        # Handle user-based authentication
        with _temporary_env(aws_credentials):
            return _scan_multiple_regions(regions, aws_credentials, aws_auth_method)
    
    return _scan_multiple_regions(regions, None, aws_auth_method)


def _scan_multiple_regions(
    regions: List[str],
    aws_credentials: Optional[Mapping[str, str]],
    aws_auth_method: str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Scan multiple regions and aggregate results."""
    all_ec2_results = []
    all_s3_results = []
    
    if os.getenv("APP_ENV", "development").strip().lower() != "production":
        print(f"DEBUG: Starting scan of {len(regions)} regions: {regions}")
    
    for region in regions:
        try:
            if os.getenv("APP_ENV", "development").strip().lower() != "production":
                print(f"DEBUG: Scanning region {region}...")
            ec2_df = scan_ec2(region=region)
            s3_df = scan_s3(region=region)
            
            ec2_count = len(ec2_df) if not ec2_df.empty else 0
            s3_count = len(s3_df) if not s3_df.empty else 0
            if os.getenv("APP_ENV", "development").strip().lower() != "production":
                print(f"DEBUG: Region {region}: Found {ec2_count} EC2 instances, {s3_count} S3 buckets")
            
            if not ec2_df.empty:
                all_ec2_results.append(ec2_df)
            if not s3_df.empty:
                all_s3_results.append(s3_df)
        except Exception as e:
            # Log error but continue with other regions
            print(f"⚠️  Error scanning {region}: {e}")
            import traceback
            print(traceback.format_exc())
            continue
    
    # Combine results
    final_ec2 = pd.concat(all_ec2_results, ignore_index=True) if all_ec2_results else pd.DataFrame()
    final_s3 = pd.concat(all_s3_results, ignore_index=True) if all_s3_results else pd.DataFrame()
    
    if os.getenv("APP_ENV", "development").strip().lower() != "production":
        print(f"DEBUG: Total results: {len(final_ec2)} EC2 instances, {len(final_s3)} S3 buckets")
    
    _update_savings_plans_cache()
    
    return final_ec2, final_s3
def _update_savings_plans_cache() -> None:
    """Refresh cached Savings Plans utilization results."""
    global _LAST_SAVINGS_PLAN_RESULTS
    if scan_savings_plans is None:
        _LAST_SAVINGS_PLAN_RESULTS = (pd.DataFrame(), {}, pd.DataFrame(), pd.DataFrame())
        return
    
    try:
        _LAST_SAVINGS_PLAN_RESULTS = scan_savings_plans()
    except Exception as exc:
        print(f"⚠️  Savings Plans scan failed: {exc}")
        _LAST_SAVINGS_PLAN_RESULTS = (
            pd.DataFrame(),
            {"error": str(exc)},
            pd.DataFrame(),
            pd.DataFrame(),
        )



def scan_ec2(region: Optional[str] = None) -> pd.DataFrame:
    """
    Run the EC2 scan and return a normalized DataFrame for the UI.
    Recommended columns: instance_id, name, instance_type, region,
    avg_cpu_7d, monthly_cost_usd, recommendation, type
    """
    if _ec2_scanner is None:
        return _empty_ec2_frame()

    # Try several common entry points for backward compatibility
    data = _call_scanner(
        _ec2_scanner,
        preferred=["scan_ec2", "run", "run_ec2", "main"],
        kwargs={"region": region} if region else {},
    )
    df = _to_dataframe(data)
    return _normalize_ec2(df)


def scan_s3(region: Optional[str] = None) -> pd.DataFrame:
    """
    Run the S3 scan and return a normalized DataFrame for the UI.
    Recommended columns: bucket, region, size_total_gb, objects_total,
    standard_cold_gb, standard_cold_objects, lifecycle_defined,
    recommendation, notes, type
    """
    if _s3_scanner is None:
        return _empty_s3_frame()

    data = _call_scanner(
        _s3_scanner,
        preferred=["scan_s3", "run", "run_s3", "main"],
        kwargs={"region": region} if region else {},
    )
    df = _to_dataframe(data)
    return _normalize_s3(df)


# ------------------------------
# Internal utilities
# ------------------------------

def _call_scanner(mod: Any, preferred: list[str], kwargs: dict) -> Any:
    """Call the first available function from `preferred` with kwargs."""
    for name in preferred:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn(**kwargs)
    raise RuntimeError(
        f"No callable scan entry point found. Tried: {', '.join(preferred)}"
    )


def _to_dataframe(data: Any) -> pd.DataFrame:
    """Convert list[dict] / DataFrame / None into a DataFrame."""
    if data is None:
        return pd.DataFrame()
    if isinstance(data, pd.DataFrame):
        return data
    if isinstance(data, Iterable):
        try:
            return pd.DataFrame(list(data))
        except Exception:
            pass
    return pd.DataFrame()


def _normalize_ec2(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure expected EC2 columns and types for the UI."""
    if df is None or df.empty:
        return _empty_ec2_frame()

    df = df.copy()

    # Aliases to harmonize different scanner field names
    alias_map = {
        "avg_cpu": "avg_cpu_7d",
        "cpu_avg_7d": "avg_cpu_7d",
        "monthly_usd": "monthly_cost_usd",
        "cost_monthly_usd": "monthly_cost_usd",
        "potential_savings": "potential_savings_usd",
        "savings": "potential_savings_usd",
        "type_": "type",
    }
    for old, new in alias_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    # Ensure required columns (including state for EC2 page)
    required_defaults = {
        "instance_id": "",
        "name": "",
        "instance_type": "",
        "region": "",
        "state": "unknown",  # Include state: running, stopped, terminated, etc.
        "avg_cpu_7d": 0.0,
        "monthly_cost_usd": 0.0,
        "potential_savings_usd": 0.0,
        "recommendation": "",
        "type": "ec2_instance",
    }
    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    # Coerce numeric
    df["avg_cpu_7d"] = _coerce_float(df["avg_cpu_7d"])
    df["monthly_cost_usd"] = _coerce_float(df["monthly_cost_usd"])
    df["potential_savings_usd"] = _coerce_float(df["potential_savings_usd"])

    # Stable column order (include state)
    cols = [
        "instance_id",
        "name",
        "instance_type",
        "region",
        "state",  # Include state for EC2 page
        "avg_cpu_7d",
        "monthly_cost_usd",
        "potential_savings_usd",
        "recommendation",
        "type",
    ]
    cols = [c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols]
    return df[cols]


def _normalize_s3(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure expected S3 columns and types for the UI."""
    if df is None or df.empty:
        return _empty_s3_frame()

    df = df.copy()

    # Aliases
    alias_map = {
        "cold_gb": "standard_cold_gb",
        "cold_objects": "standard_cold_objects",
        "size_gb": "size_total_gb",
        "objects": "objects_total",
        "monthly_usd": "monthly_cost_usd",
        "cost_monthly_usd": "monthly_cost_usd",
        "potential_savings": "potential_savings_usd",
        "savings": "potential_savings_usd",
        "type_": "type",
    }
    for old, new in alias_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    # Ensure required columns
    required_defaults = {
        "bucket": "",
        "region": "",
        "size_total_gb": 0.0,
        "objects_total": 0,
        "standard_cold_gb": 0.0,
        "standard_cold_objects": 0,
        "lifecycle_defined": False,
        "monthly_cost_usd": 0.0,
        "potential_savings_usd": 0.0,
        "recommendation": "",
        "notes": "",
        "type": "s3_bucket_summary",
    }
    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    # Coerce numeric
    df["size_total_gb"] = _coerce_float(df["size_total_gb"])
    df["standard_cold_gb"] = _coerce_float(df["standard_cold_gb"])
    df["monthly_cost_usd"] = _coerce_float(df["monthly_cost_usd"])
    df["potential_savings_usd"] = _coerce_float(df["potential_savings_usd"])

    # Stable column order
    cols = [
        "bucket",
        "region",
        "size_total_gb",
        "objects_total",
        "standard_cold_gb",
        "standard_cold_objects",
        "lifecycle_defined",
        "monthly_cost_usd",
        "potential_savings_usd",
        "recommendation",
        "notes",
        "type",
    ]
    cols = [c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols]
    return df[cols]


def _empty_ec2_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "instance_id",
            "name",
            "instance_type",
            "region",
            "avg_cpu_7d",
            "monthly_cost_usd",
            "potential_savings_usd",
            "recommendation",
            "type",
        ]
    )


def _empty_s3_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "bucket",
            "region",
            "size_total_gb",
            "objects_total",
            "standard_cold_gb",
            "standard_cold_objects",
            "lifecycle_defined",
            "monthly_cost_usd",
            "potential_savings_usd",
            "recommendation",
            "notes",
            "type",
        ]
    )


def _coerce_float(series: pd.Series) -> pd.Series:
    try:
        return pd.to_numeric(series, errors="coerce").fillna(0.0)
    except Exception:
        return series


@contextmanager
def _temporary_env(new_values: Mapping[str, str]):
    """Temporarily set environment variables, then restore originals.

    Only affects the current process memory; nothing is written to disk.
    """
    keys = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
        "AWS_SESSION_TOKEN",
    ]
    old: dict[str, Optional[str]] = {k: os.environ.get(k) for k in keys}
    try:
        for k in keys:
            if k in new_values and new_values[k]:
                os.environ[k] = new_values[k]  # type: ignore[index]
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _assume_role(credentials: Mapping[str, str]) -> Optional[dict[str, str]]:
    """Assume an IAM role and return temporary credentials.
    
    Args:
        credentials: Dictionary containing role assumption parameters
        
    Returns:
        Dictionary with temporary credentials or None if assumption fails
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Extract role parameters
        role_arn = credentials.get("AWS_ROLE_ARN", "").strip()
        external_id = credentials.get("AWS_EXTERNAL_ID", "").strip()
        session_name = credentials.get("AWS_ROLE_SESSION_NAME", "CloudWasteTracker").strip()
        region = credentials.get("AWS_DEFAULT_REGION", "us-east-1").strip()
        
        if not role_arn:
            print("ERROR: No role ARN provided")
            return None
            
        if os.getenv("APP_ENV", "development").strip().lower() != "production":
            print(f"DEBUG: Attempting to assume role {role_arn}")
            print(f"DEBUG: External ID: {'SET' if external_id else 'NOT SET'}")
            print(f"DEBUG: Session Name: {session_name}")
            print(f"DEBUG: Region: {region}")
            
        # Create STS client with base credentials
        # Use credentials from dict if provided, otherwise let boto3 use environment variables
        base_ak = credentials.get("AWS_ACCESS_KEY_ID", "")
        base_sk = credentials.get("AWS_SECRET_ACCESS_KEY", "")
        
        if base_ak and base_sk:
            # Use explicit credentials
            sts_client = boto3.client(
                'sts',
                aws_access_key_id=base_ak,
                aws_secret_access_key=base_sk,
                region_name=region
            )
        else:
            # Force boto3 to use only environment variables, not local files
            sts_client = boto3.client(
                'sts',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                aws_session_token=os.getenv('AWS_SESSION_TOKEN'),
                region_name=region
            )
        
        # Test base credentials first
        try:
            identity = sts_client.get_caller_identity()
            if os.getenv("APP_ENV", "development").strip().lower() != "production":
                print(f"DEBUG: Base credentials work. Caller: {identity.get('Arn', 'Unknown')}")
        except Exception as e:
            if os.getenv("APP_ENV", "development").strip().lower() != "production":
                print(f"DEBUG: Base credentials failed: {e}")
            return None
        
        # Prepare assume role parameters
        assume_role_kwargs = {
            'RoleArn': role_arn,
            'RoleSessionName': session_name,
            'DurationSeconds': 3600
        }
        
        if external_id:
            assume_role_kwargs['ExternalId'] = external_id
        
        response = sts_client.assume_role(**assume_role_kwargs)
        
        creds = response['Credentials']
        if os.getenv("APP_ENV", "development").strip().lower() != "production":
            print(f"DEBUG: Successfully assumed role {role_arn}")
            print(f"DEBUG: Temporary credentials expire at: {creds['Expiration']}")
        return {
            'AWS_ACCESS_KEY_ID': creds['AccessKeyId'],
            'AWS_SECRET_ACCESS_KEY': creds['SecretAccessKey'],
            'AWS_SESSION_TOKEN': creds['SessionToken'],
            'AWS_DEFAULT_REGION': region
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"Failed to assume role {role_arn}: {error_code} - {error_message}")
        
        if error_code == "AccessDenied":
            print("This usually means:")
            print("1. Base credentials don't have sts:AssumeRole permission")
            print("2. Role trust policy doesn't allow this user/account")
            print("3. External ID doesn't match (if required)")
        elif error_code == "InvalidUserID.NotFound":
            print("Base credentials are invalid or expired")
        elif error_code == "ValidationError":
            print("Role ARN format is incorrect")
        
        return None
    except Exception as e:
        print(f"Unexpected error during role assumption: {e}")
        return None


# ------------------------------
# Savings Plans helpers
# ------------------------------


def fetch_savings_plan_utilization(
    aws_credentials: Optional[Mapping[str, str]] = None,
) -> tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame]:
    """
    Retrieve Savings Plans utilization results.

    Returns cached results from the most recent scan when available. If cache is empty
    and credentials are provided, performs a fresh scan using those credentials.
    """
    cached_df, cached_summary, cached_util_trend, cached_coverage_trend = _LAST_SAVINGS_PLAN_RESULTS
    if not cached_df.empty or cached_summary:
        return cached_df, cached_summary, cached_util_trend, cached_coverage_trend

    if scan_savings_plans is None:
        return pd.DataFrame(), {}, pd.DataFrame(), pd.DataFrame()

    if aws_credentials:
        try:
            with _temporary_env(aws_credentials):
                return scan_savings_plans()
        except Exception as exc:
            print(f"⚠️  Savings Plans scan failed: {exc}")
            return (
                pd.DataFrame(),
                {"error": str(exc)},
                pd.DataFrame(),
                pd.DataFrame(),
            )

    try:
        return scan_savings_plans()
    except Exception as exc:
        print(f"⚠️  Savings Plans scan failed: {exc}")
        return pd.DataFrame(), {"error": str(exc)}, pd.DataFrame(), pd.DataFrame()


# ------------------------------
# Cost Explorer helpers
# ------------------------------

def get_cost_explorer_client(region: Optional[str] = None):
    # Cost Explorer is us-east-1 endpoint regardless of resources region
    return boto3.client("ce", region_name=region or "us-east-1")


def fetch_spend_summary(ce_client, *, days_7: bool = True, month_to_date: bool = True) -> dict:
    from datetime import datetime, timedelta, timezone

    out: dict[str, float | None] = {"last_7_days": None, "month_to_date": None}

    try:
        if days_7:
            end = datetime.now(timezone.utc).date()
            start = end - timedelta(days=7)
            resp = ce_client.get_cost_and_usage(
                TimePeriod={"Start": start.strftime("%Y-%m-%d"), "End": end.strftime("%Y-%m-%d")},
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
            )
            total = 0.0
            for p in resp.get("ResultsByTime", []) or []:
                try:
                    total += float(p["Total"]["UnblendedCost"]["Amount"])  # type: ignore[index]
                except Exception:
                    pass
            out["last_7_days"] = total

        if month_to_date:
            end = datetime.now(timezone.utc).date()
            start = end.replace(day=1)
            resp = ce_client.get_cost_and_usage(
                TimePeriod={"Start": start.strftime("%Y-%m-%d"), "End": end.strftime("%Y-%m-%d")},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
            )
            total = 0.0
            for p in resp.get("ResultsByTime", []) or []:
                try:
                    total += float(p["Total"]["UnblendedCost"]["Amount"])  # type: ignore[index]
                except Exception:
                    pass
            out["month_to_date"] = total
    except Exception:
        # Surface as None; UI can show N/A
        pass

    return out


def fetch_credit_balance(ce_client) -> float | None:
    # Credits are not exposed uniformly; attempt to extract via Dimension/Filter if available
    # Placeholder: return None so UI shows N/A; extend later when credit APIs are available to you
    try:
        return None
    except Exception:
        return None
