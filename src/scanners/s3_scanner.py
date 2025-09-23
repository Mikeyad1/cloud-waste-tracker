# src/scanners/s3_scanner.py
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
    return boto3.client("s3", region_name=region or DEFAULT_REGION)


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
    token: Optional[str] = None
    while True:
        kwargs = {"Bucket": bucket, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3_client.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []) or []:
            yield obj
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")


# ----------------------
# Scanner
# ----------------------
def scan_s3_waste(region: str | None = None, days_cold: int = 60) -> List[Dict]:
    """
    Returns a list of S3 findings:
      - s3_bucket_summary   (always)
      - s3_no_lifecycle     (if lifecycle missing)
      - s3_cold_standard    (if STANDARD objects are older than `days_cold`)
    """
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

        # Always emit a per-bucket summary
        findings.append(
            {
                "type": "s3_bucket_summary",
                "bucket": name,
                "region": b_region,
                "objects_total": total_objs,
                "size_total_gb": _gb(total_bytes),
                "standard_cold_objects": standard_cold_objs,
                "standard_cold_gb": _gb(standard_cold_bytes),
                "lifecycle_defined": lifecycle_exists,
                "recommendation": (
                    "Add lifecycle + transition STANDARD cold -> IA/Glacier"
                    if (standard_cold_objs > 0 or not lifecycle_exists)
                    else "OK"
                ),
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
                    "recommendation": "Create lifecycle: transition after 30–60d, expire old versions",
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
                    "standard_cold_gb": _gb(standard_cold_bytes),
                    "recommendation": "Transition to S3 IA / Glacier (per access pattern)",
                    "notes": f"Objects not modified > {days_cold}d in STANDARD",
                }
            )

    return findings


# ----------------------
# Public entry points
# ----------------------
def scan_s3(region: str | None = None, days_cold: int = 60):
    """
    Primary entry point used by the UI adapter (scans.py).
    Returns list[dict] with bucket-level summaries and related findings.
    """
    return scan_s3_waste(region=region, days_cold=days_cold)


def run(region: str | None = None, days_cold: int = 60):
    """
    Backward-compatible CLI entry point.
    Returns all findings (no CSV).
    """
    results = scan_s3_waste(region=region, days_cold=days_cold)

    # brief console output
    for r in results:
        t = r.get("type")
        if t == "s3_bucket_summary":
            print(
                f"[S3] {r.get('bucket')} total={r.get('size_total_gb')}GB "
                f"cold_STANDARD={r.get('standard_cold_gb')}GB "
                f"lifecycle={r.get('lifecycle_defined')} -> {r.get('recommendation')}"
            )
        elif t == "s3_no_lifecycle":
            print(f"[S3] {r.get('bucket')} -> Missing lifecycle (add transitions/expirations)")
        elif t == "s3_cold_standard":
            print(
                f"[S3] {r.get('bucket')} cold STANDARD ~{r.get('standard_cold_gb')}GB "
                f"-> transition to IA/Glacier"
            )
        elif t == "s3_error":
            print(f"[S3] {r.get('bucket')} -> ERROR: {r.get('notes')}")
    return results


if __name__ == "__main__":
    # Allow: python -m scanners.s3_scanner --region us-east-1 --days 60
    import argparse

    p = argparse.ArgumentParser(description="Cloud Waste Tracker – S3 Scanner (live, no CSV)")
    p.add_argument("--region", default=DEFAULT_REGION)
    p.add_argument("--days", type=int, default=60, help="Days threshold for cold STANDARD objects")
    args = p.parse_args()

    run(region=args.region, days_cold=args.days)
