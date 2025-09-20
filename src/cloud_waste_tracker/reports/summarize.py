# cloud_waste_tracker/reports/summarize.py
from __future__ import annotations
import csv
from pathlib import Path
from datetime import date

from cloud_waste_tracker.utils.utils import (
    path_waste_csv,
    path_s3_csv,
    path_summary_txt,
    path_actions_txt,
    DEFAULT_REGION,
)

def _read_csv_rows(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def run() -> tuple[Path, Path]:
    """Build summary.txt and action_list.txt from current CSVs.
    Returns (summary_path, action_list_path)."""
    today = date.today().isoformat()

    ec2_rows = _read_csv_rows(path_waste_csv())
    s3_rows  = _read_csv_rows(path_s3_csv())

    # ---- summary.txt ----
    potential_savings = 0.0
    for r in ec2_rows:
        try:
            potential_savings += float((r.get("monthly_cost_usd") or "0").strip())
        except Exception:
            pass

    s3_missing_lc = [
        r for r in s3_rows
        if str(r.get("lifecycle_defined", "")).lower() not in ("true", "1", "yes")
    ]

    summary_lines = [
        f"Cloud Waste Report — {today}",
        "=" * 40,
        "",
        f"Default region: {DEFAULT_REGION}",
        f"EC2 idle instances detected: {len(ec2_rows)}",
        f"Potential monthly savings (EC2): ${potential_savings:,.2f}",
        f"S3 buckets scanned: {len(s3_rows)}",
        f"S3 buckets missing lifecycle: {len(s3_missing_lc)}",
        "",
        "Top recommendations:",
        "• Stop/Downsize EC2 instances with avg CPU < 5% (7d).",
        "• Add S3 lifecycle rules to transition old logs to Glacier.",
        "• (Next) Clean up unattached EBS volumes / unused Elastic IPs.",
        "",
    ]

    path_summary_txt().write_text("\n".join(summary_lines), encoding="utf-8")

    # ---- action_list.txt ----
    actions: list[str] = []

    # EC2 actions (stop candidates)
    for r in ec2_rows:
        if (r.get("type") == "idle_instance") or str(r.get("recommendation", "")).lower().startswith("stop"):
            iid = r.get("instance_id")
            region = r.get("region") or DEFAULT_REGION
            name = r.get("name") or ""
            itype = r.get("instance_type") or ""
            cost  = r.get("monthly_cost_usd") or "0"
            if iid:
                actions.append(f"# EC2 {iid} — {name} ({itype}) ~ ${cost}/mo")
                actions.append(f"aws ec2 stop-instances --instance-ids {iid} --region {region}")
                actions.append("")

    # S3 lifecycle actions (apply simple logs -> Glacier after 30 days)
    for r in s3_missing_lc:
        b = r.get("bucket")
        region = r.get("region") or DEFAULT_REGION
        if b:
            actions.append(f"# S3 lifecycle for bucket: {b}")
            actions.append(
                "aws s3api put-bucket-lifecycle-configuration "
                f"--bucket {b} --region {region} "
                "--lifecycle-configuration "
                "'{\"Rules\":[{\"ID\":\"logs-to-glacier-30d\",\"Status\":\"Enabled\",\"Filter\":{\"Prefix\":\"logs/\"},"
                "\"Transitions\":[{\"Days\":30,\"StorageClass\":\"GLACIER\"}]}]}'"
            )
            actions.append("")

    if not actions:
        actions.append("# No actions generated from current scan.")

    path_actions_txt().write_text("\n".join(actions), encoding="utf-8")

    return (path_summary_txt(), path_actions_txt())

if __name__ == "__main__":
    summary_p, actions_p = run()
    print(f"[✓] Wrote {summary_p.name} and {actions_p.name}")
