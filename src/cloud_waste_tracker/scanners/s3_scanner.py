# cloud_waste_tracker/scanners/s3_scanner.py
from __future__ import annotations
import csv
from datetime import datetime, timedelta, timezone
from typing import List, Dict

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from cloud_waste_tracker.utils.utils import path_s3_csv

CSV_OUT = path_s3_csv()

def utc_now(): return datetime.now(timezone.utc)
def gb(bytes_val: int) -> float: return round(bytes_val / (1024**3), 3)

def bucket_region(s3_client, bucket):
    try:
        loc = s3_client.get_bucket_location(Bucket=bucket).get("LocationConstraint")
        return loc or "us-east-1"
    except ClientError:
        return "unknown"

def has_lifecycle(s3_client, bucket) -> bool:
    try:
        s3_client.get_bucket_lifecycle_configuration(Bucket=bucket); return True
    except ClientError:
        return False

def iter_objects(s3_client, bucket):
    token = None
    while True:
        kwargs = {"Bucket": bucket, "MaxKeys": 1000}
        if token: kwargs["ContinuationToken"] = token
        resp = s3_client.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []): yield obj
        if not resp.get("IsTruncated"): break
        token = resp.get("NextContinuationToken")

def scan_s3_waste(days_cold: int = 60) -> List[Dict]:
    findings: List[Dict] = []
    s3 = boto3.client("s3")
    try:
        buckets = s3.list_buckets().get("Buckets", [])
    except (NoCredentialsError, ClientError):
        print("AWS credentials error. Did you run `aws configure`?")
        return findings

    cold_before = utc_now() - timedelta(days=days_cold)
    for b in buckets:
        name = b["Name"]; region = bucket_region(s3, name); lifecycle_exists = has_lifecycle(s3, name)
        total_bytes = total_objs = standard_cold_bytes = standard_cold_objs = 0

        try:
            for obj in iter_objects(s3, name):
                total_objs += 1
                size = obj.get("Size", 0); total_bytes += size
                storage_class = obj.get("StorageClass", "STANDARD") or "STANDARD"
                last_modified = obj.get("LastModified")
                if storage_class == "STANDARD" and last_modified and last_modified < cold_before:
                    standard_cold_bytes += size; standard_cold_objs += 1
        except ClientError as e:
            findings.append({
                "type": "s3_error", "bucket": name, "region": region,
                "recommendation": "Verify permissions to list objects",
                "notes": f"Error: {e.response['Error'].get('Code','?')}",
            })
            continue

        findings.append({
            "type": "s3_bucket_summary", "bucket": name, "region": region,
            "objects_total": total_objs, "size_total_gb": gb(total_bytes),
            "standard_cold_objects": standard_cold_objs, "standard_cold_gb": gb(standard_cold_bytes),
            "lifecycle_defined": lifecycle_exists,
            "recommendation": (
                "Add lifecycle + transition STANDARD cold -> IA/Glacier"
                if (standard_cold_objs > 0 or not lifecycle_exists) else "OK"
            ),
            "notes": ("No lifecycle configuration" if not lifecycle_exists else
                      ("Move cold STANDARD to IA/Glacier" if standard_cold_objs > 0 else "")),
        })

        if not lifecycle_exists:
            findings.append({
                "type": "s3_no_lifecycle", "bucket": name, "region": region,
                "recommendation": "Create lifecycle: transition after 30-60d, expire old versions",
                "notes": "Missing lifecycle rules increases storage cost over time",
            })

        if standard_cold_objs > 0:
            findings.append({
                "type": "s3_cold_standard", "bucket": name, "region": region,
                "standard_cold_objects": standard_cold_objs, "standard_cold_gb": gb(standard_cold_bytes),
                "recommendation": "Transition to S3 IA / Glacier (per access pattern)",
                "notes": f"Objects not modified > {days_cold}d in STANDARD",
            })
    return findings

def write_csv(rows, outfile=CSV_OUT):
    if not rows:
        print("No S3 findings. ✅"); return
    all_keys = set(); [all_keys.update(r.keys()) for r in rows]
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=sorted(all_keys)); w.writeheader(); w.writerows(rows)
    print(f"Report written: {outfile}  ({len(rows)} findings)")

# ---------- Public API used by main ----------
def run(days_cold: int = 60) -> None:
    """Scan S3 and write CSV to project root."""
    findings = scan_s3_waste(days_cold=days_cold)
    write_csv(findings, outfile=str(CSV_OUT))
    # brief console output
    for r in findings:
        if r["type"] == "s3_bucket_summary":
            print(f"[S3] {r['bucket']} total={r['size_total_gb']}GB cold_STANDARD={r['standard_cold_gb']}GB lifecycle={r['lifecycle_defined']} -> {r['recommendation']}")
        elif r["type"] == "s3_no_lifecycle":
            print(f"[S3] {r['bucket']} -> Missing lifecycle (add transitions/expirations)")
        elif r["type"] == "s3_cold_standard":
            print(f"[S3] {r['bucket']} cold STANDARD ~{r['standard_cold_gb']}GB -> transition to IA/Glacier")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Cloud Waste Tracker – S3 Scanner")
    p.add_argument("--days", type=int, default=60, help="Days threshold for cold STANDARD objects")
    args = p.parse_args()
    run(days_cold=args.days)
