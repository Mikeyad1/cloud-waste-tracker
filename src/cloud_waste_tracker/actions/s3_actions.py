# cloud_waste_tracker/actions/s3_actions.py
"""
S3 actions:
- plan_lifecycle(): read s3_waste_report.csv and find buckets missing lifecycle
- apply_lifecycle(): apply a simple lifecycle rule (prefix -> transition after N days)

SAFE BY DEFAULT:
- CLI runs in dry-run unless you pass --yes
"""

from __future__ import annotations
import argparse
import csv
import json
from typing import List, Dict

from botocore.exceptions import ClientError

from cloud_waste_tracker.utils.utils import (
    path_s3_csv,
    aws_client,
)

def build_lifecycle_config(prefix: str, days: int, storage_class: str) -> Dict:
    return {
        "Rules": [
            {
                "ID": f"{(prefix or 'root')}-to-{storage_class}-{days}d",
                "Status": "Enabled",
                "Filter": {"Prefix": prefix} if prefix else {"Prefix": ""},
                "Transitions": [{"Days": days, "StorageClass": storage_class}],
            }
        ]
    }

def _s3_client():
    # Region resolution is handled by S3/boto; no explicit region required here.
    return aws_client("s3")

def _read_csv_rows() -> List[Dict]:
    rows: List[Dict] = []
    s3_csv = path_s3_csv()
    if not s3_csv.exists():
        print(f"[!] CSV not found: {s3_csv}")
        return rows
    with s3_csv.open(newline="", encoding="utf-8") as f:
        rows.extend(csv.DictReader(f))
    return rows

def plan_lifecycle() -> List[str]:
    """
    Return list of bucket names missing lifecycle from s3_waste_report.csv.
    Expects columns: bucket, lifecycle_defined
    """
    rows = _read_csv_rows()
    if not rows:
        return []
    missing: List[str] = []
    for r in rows:
        has_lc = str(r.get("lifecycle_defined", "")).strip().lower() in ("true", "1", "yes")
        bkt = (r.get("bucket") or "").strip()
        if bkt and not has_lc:
            missing.append(bkt)
    return sorted(set(missing))

def check_current_lifecycle(bucket: str) -> bool:
    """Return True if lifecycle exists, else False."""
    s3 = _s3_client()
    try:
        s3.get_bucket_lifecycle_configuration(Bucket=bucket)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchLifecycleConfiguration", "NoSuchLifecycle"):
            return False
        print(f"[!] check lifecycle error for {bucket}: {code}")
        return False

def apply_lifecycle(
    buckets: List[str],
    prefix: str = "logs/",
    days: int = 30,
    storage_class: str = "GLACIER",
    dry_run: bool = True,
):
    """
    Apply lifecycle to given buckets.
    - dry_run=True prints the plan only
    """
    if not buckets:
        print("[i] No buckets to apply lifecycle.")
        return

    cfg = build_lifecycle_config(prefix=prefix, days=days, storage_class=storage_class)
    s3 = _s3_client()

    print("=== S3 Lifecycle Apply ===")
    print(f"Prefix: '{prefix}'  Days: {days}  StorageClass: {storage_class}")
    print(f"Dry-run: {dry_run}")
    print("--------------------------")

    for b in buckets:
        b = b.strip()
        if not b:
            continue

        has_now = check_current_lifecycle(b)
        if has_now:
            print(f"[skip] {b} already has lifecycle.")
            continue

        if dry_run:
            print(f"[plan] Would apply lifecycle to bucket: {b}")
            print(f"       Config: {json.dumps(cfg)}")
            continue

        try:
            s3.put_bucket_lifecycle_configuration(
                Bucket=b,
                LifecycleConfiguration=cfg,
            )
            print(f"[✓] Applied lifecycle to {b}")
        except ClientError as e:
            print(f"[!] Failed to apply lifecycle to {b}: {e.response.get('Error', {}).get('Message')}")

# --- Optional CLI for direct use ---
def main():
    parser = argparse.ArgumentParser(description="S3 actions (lifecycle).")
    parser.add_argument("--plan", action="store_true", help="Show buckets missing lifecycle (from CSV).")
    parser.add_argument("--apply", action="store_true", help="Apply lifecycle to planned buckets.")
    parser.add_argument("--buckets", default="", help="Comma-separated bucket list (override CSV plan).")
    parser.add_argument("--prefix", default="logs/", help="Lifecycle prefix (default: logs/). Empty string = all objects.")
    parser.add_argument("--days", type=int, default=30, help="Transition after N days (default: 30).")
    parser.add_argument("--storage-class", default="GLACIER", help="Target storage class (default: GLACIER).")
    parser.add_argument("--yes", action="store_true", help="Confirm real apply (otherwise dry-run).")
    args = parser.parse_args()

    buckets = [b.strip() for b in args.buckets.split(",") if b.strip()] or plan_lifecycle()

    if args.plan and not args.apply:
        if buckets:
            print("Buckets missing lifecycle:")
            for b in buckets:
                print(f" - {b}")
        else:
            print("[i] No buckets missing lifecycle according to CSV.")
        return

    if args.apply:
        if not buckets:
            print("[i] Nothing to apply.")
            return
        apply_lifecycle(
            buckets=buckets,
            prefix=args.prefix,
            days=args.days,
            storage_class=args.storage_class,
            dry_run=not args.yes,
        )
        return

    parser.print_help()

if __name__ == "__main__":
    main()
