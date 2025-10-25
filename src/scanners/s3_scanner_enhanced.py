# src/scanners/s3_scanner_enhanced.py
"""
Enhanced S3 scanner with improved cost calculations and recommendations.
This is a temporary file - we'll replace the original once testing is complete.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Iterable, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")


# ----------------------
# Helpers
# ----------------------
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _gb(bytes_val: int | float) -> float:
    try:
        return round(float(bytes_val) / (1024 ** 3), 3)
    except Exception:
        return 0.0


def _s3_client(region: str | None = None):
    # Use environment variables only, no local credentials file
    return boto3.client(
        "s3", 
        region_name=region or DEFAULT_REGION,
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        aws_session_token=os.getenv('AWS_SESSION_TOKEN')
    )


def _bucket_region(s3_client, bucket: str) -> str:
    try:
        loc = s3_client.get_bucket_location(Bucket=bucket).get("LocationConstraint")
        # us-east-1 is represented as None
        return loc or "us-east-1"
    except ClientError:
        return "unknown"


def _has_lifecycle(s3_client, bucket: str) -> bool:
    try:
        s3_client.get_bucket_lifecycle_configuration(Bucket=bucket)
        return True
    except ClientError:
        return False


def _iter_objects(s3_client, bucket: str) -> Iterable[dict]:
    """Iterate over all objects in a bucket."""
    kwargs = {"Bucket": bucket, "MaxKeys": 1000}

    while True:
        if "ContinuationToken" in kwargs:
            del kwargs["ContinuationToken"]
        token = kwargs.get("ContinuationToken")

        if token:
            kwargs["ContinuationToken"] = token
        resp = s3_client.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []) or []:
            yield obj
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")


# ----------------------
# Enhanced Scanner
# ----------------------
def scan_s3_waste(region: str | None = None, days_cold: int = 60) -> List[Dict]:
    """
    Returns a list of S3 findings with enhanced cost analysis:
      - s3_bucket_summary   (always)
      - s3_no_lifecycle     (if lifecycle missing)
      - s3_cold_standard    (if STANDARD objects are older than `days_cold`)
    """
    # Import pricing service for accurate calculations
    try:
        from core.services.pricing_service import pricing_service
    except ImportError:
        pricing_service = None
    
    findings: List[Dict] = []
    s3_global = _s3_client(region)

    try:
        buckets = s3_global.list_buckets().get("Buckets", [])
    except (NoCredentialsError, ClientError) as e:
        print(f"AWS credentials error: {e}")
        return findings

    cold_before = _utc_now() - timedelta(days=days_cold)

    for b in buckets:
        name: str = b.get("Name", "")
        # Determine bucket region and use a regional client for per-bucket ops
        b_region = _bucket_region(s3_global, name)
        s3 = _s3_client(b_region if b_region != "unknown" else region)

        lifecycle_exists = _has_lifecycle(s3, name)
        total_bytes = 0
        total_objs = 0
        standard_cold_bytes = 0
        standard_cold_objs = 0

        try:
            for obj in _iter_objects(s3, name):
                total_objs += 1
                size = int(obj.get("Size", 0) or 0)
                total_bytes += size

                storage_class = (obj.get("StorageClass") or "STANDARD").upper()
                last_modified = obj.get("LastModified")
                if storage_class == "STANDARD" and last_modified and last_modified < cold_before:
                    standard_cold_bytes += size
                    standard_cold_objs += 1

        except ClientError as e:
            findings.append(
                {
                    "type": "s3_error",
                    "bucket": name,
                    "region": b_region,
                    "recommendation": "Verify permissions to list objects",
                    "notes": f"Error: {e.response.get('Error', {}).get('Code', '?')}",
                }
            )
            continue

        # Calculate costs and savings
        total_gb = _gb(total_bytes)
        cold_gb = _gb(standard_cold_bytes)
        
        if pricing_service:
            current_cost = pricing_service.get_s3_monthly_cost(total_gb, "STANDARD")
            cold_cost = pricing_service.get_s3_monthly_cost(cold_gb, "STANDARD")
            savings_analysis = pricing_service.calculate_s3_savings(cold_gb, name)
        else:
            # Fallback calculations
            current_cost = total_gb * 0.023  # Standard pricing
            cold_cost = cold_gb * 0.023
            savings_analysis = {
                "potential_savings": cold_cost * 0.5,  # Approximate savings
                "action": f"Move {cold_gb:.1f}GB cold data to S3 IA",
                "implementation_steps": ["Create lifecycle rule to transition to IA after 30 days"]
            }

        # Always emit a per-bucket summary
        findings.append(
            {
                "type": "s3_bucket_summary",
                "bucket": name,
                "region": b_region,
                "objects_total": total_objs,
                "size_total_gb": total_gb,
                "standard_cold_objects": standard_cold_objs,
                "standard_cold_gb": cold_gb,
                "lifecycle_defined": lifecycle_exists,
                "monthly_cost_usd": current_cost,
                "cold_storage_cost_usd": cold_cost,
                "potential_savings_usd": savings_analysis.get("potential_savings", 0),
                "recommendation": (
                    "Add lifecycle + transition STANDARD cold -> IA/Glacier"
                    if (standard_cold_objs > 0 or not lifecycle_exists)
                    else "OK"
                ),
                "priority": "HIGH" if (standard_cold_objs > 0 or not lifecycle_exists) else "LOW",
                "action": savings_analysis.get("action", "Optimize S3 storage"),
                "implementation_steps": savings_analysis.get("implementation_steps", []),
                "notes": (
                    "No lifecycle configuration"
                    if not lifecycle_exists
                    else ("Move cold STANDARD to IA/Glacier" if standard_cold_objs > 0 else "")
                ),
            }
        )

        if not lifecycle_exists:
            findings.append(
                {
                    "type": "s3_no_lifecycle",
                    "bucket": name,
                    "region": b_region,
                    "monthly_cost_usd": current_cost,
                    "potential_savings_usd": current_cost * 0.3,  # Approximate savings
                    "recommendation": "Create lifecycle: transition after 30–60d, expire old versions",
                    "priority": "MEDIUM",
                    "action": f"Add lifecycle rules to {name}",
                    "implementation_steps": [
                        f"1. Go to S3 Console → {name} → Management → Lifecycle",
                        "2. Create rule: Transition to IA after 30 days",
                        "3. Add expiration rule for old versions",
                        f"4. Potential savings: ${current_cost * 0.3:.2f}/month"
                    ],
                    "notes": "Missing lifecycle rules increases storage cost over time",
                }
            )

        if standard_cold_objs > 0:
            findings.append(
                {
                    "type": "s3_cold_standard",
                    "bucket": name,
                    "region": b_region,
                    "standard_cold_objects": standard_cold_objs,
                    "standard_cold_gb": cold_gb,
                    "monthly_cost_usd": cold_cost,
                    "potential_savings_usd": savings_analysis.get("potential_savings", cold_cost * 0.5),
                    "recommendation": "Transition to S3 IA / Glacier (per access pattern)",
                    "priority": "HIGH",
                    "action": savings_analysis.get("action", f"Move {cold_gb:.1f}GB cold data to IA"),
                    "implementation_steps": savings_analysis.get("implementation_steps", []),
                    "notes": f"Objects not modified > {days_cold}d in STANDARD",
                }
            )

    return findings


# ----------------------
# Public entry points
# ----------------------
def scan_s3(region: str | None = None):
    """
    Primary entry point used by the UI adapter (scans.py).
    Returns a list[dict] for S3 findings.
    """
    region = region or DEFAULT_REGION
    return scan_s3_waste(region)


def run(region: str | None = None):
    """
    Backward-compatible CLI entry point.
    """
    region = region or DEFAULT_REGION
    return scan_s3_waste(region)


if __name__ == "__main__":
    import json
    findings = run()
    print(json.dumps(findings, indent=2, default=str))


