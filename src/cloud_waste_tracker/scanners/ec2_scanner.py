# cloud_waste_tracker/scanners/ec2_scanner.py
from __future__ import annotations
import csv, os
from datetime import datetime, timedelta, timezone
from typing import List, Dict

from botocore.exceptions import ClientError
from cloud_waste_tracker.utils.utils import aws_client, DEFAULT_REGION, path_waste_csv

# -------- Settings --------
IDLE_CPU_THRESHOLD = 5.0          # below this avg CPU considered "idle"
IDLE_LOOKBACK_DAYS = 7            # how many days to look back

# Basic on-demand hourly prices (Linux, us-east-1) – demo only
INSTANCE_PRICES = {
    "t3.micro": 0.0104, "t3.small": 0.0208, "t3.medium": 0.0416, "t3.large": 0.0832,
    "t2.micro": 0.0116, "t2.small": 0.023, "t2.medium": 0.0464,
}

def utc_now(): return datetime.now(timezone.utc)
def daterange(days):
    end = utc_now(); start = end - timedelta(days=days); return start, end

def estimate_monthly_cost(instance_type: str):
    hourly = INSTANCE_PRICES.get(instance_type)
    return "unknown" if hourly is None else round(hourly * 24 * 30, 2)  # ~720h

def scan_ec2_idle(region: str) -> List[Dict]:
    ec2 = aws_client("ec2", region); cw = aws_client("cloudwatch", region)
    reservations = ec2.describe_instances()["Reservations"]
    instances = [i for r in reservations for i in r.get("Instances", []) if i["State"]["Name"] == "running"]

    start, end = daterange(IDLE_LOOKBACK_DAYS)
    results: List[Dict] = []
    for inst in instances:
        instance_id = inst["InstanceId"]
        itype = inst.get("InstanceType", "?")
        name_tag = next((t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), "")
        try:
            resp = cw.get_metric_statistics(
                Namespace="AWS/EC2", MetricName="CPUUtilization",
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start, EndTime=end, Period=3600 * 6, Statistics=["Average"],
            )
            dps = resp.get("Datapoints", [])
            avg_cpu = 0.0 if not dps else sum(dp["Average"] for dp in dps) / len(dps)
        except ClientError:
            avg_cpu = -1.0

        if (avg_cpu >= 0) and (avg_cpu < IDLE_CPU_THRESHOLD):
            results.append({
                "type": "idle_instance", "region": region,
                "instance_id": instance_id, "name": name_tag, "instance_type": itype,
                "avg_cpu_7d": round(avg_cpu, 2), "recommendation": "Stop or downsize",
                "monthly_cost_usd": estimate_monthly_cost(itype),
            })
    return results

def scan_ebs_available(region: str) -> List[Dict]:
    ec2 = aws_client("ec2", region)
    vols = ec2.describe_volumes(Filters=[{"Name": "status", "Values": ["available"]}]).get("Volumes", [])
    out: List[Dict] = []
    for v in vols:
        vid = v["VolumeId"]; size = v.get("Size", 0)
        out.append({
            "type": "unused_ebs", "region": region, "volume_id": vid, "size_gb": size,
            "recommendation": "Delete or snapshot then delete",
            "notes": f"Detached EBS ~{size}GB (consider snapshot+delete)",
        })
    return out

def scan_eips_unassociated(region: str) -> List[Dict]:
    ec2 = aws_client("ec2", region)
    addrs = ec2.describe_addresses().get("Addresses", [])
    out: List[Dict] = []
    for a in addrs:
        if not a.get("AssociationId"):
            out.append({
                "type": "unused_eip", "region": region,
                "allocation_id": a.get("AllocationId"), "public_ip": a.get("PublicIp"),
                "recommendation": "Release Elastic IP", "notes": "EIP charges when not associated",
            })
    return out

def write_csv(rows, outfile):
    if not rows:
        print("No waste findings. ✅"); return
    all_keys = set(); [all_keys.update(r.keys()) for r in rows]
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=sorted(all_keys)); w.writeheader(); w.writerows(rows)
    print(f"Report written: {outfile}  ({len(rows)} findings)")

# ---------- Public API used by main ----------
def run(region: str | None = None) -> None:
    """Collect EC2/EBS/EIP findings and write CSV to project root."""
    region = region or os.getenv("AWS_DEFAULT_REGION", DEFAULT_REGION)
    findings = []
    findings += scan_ec2_idle(region)
    findings += scan_ebs_available(region)
    findings += scan_eips_unassociated(region)
    write_csv(findings, outfile=str(path_waste_csv()))
    # brief console output
    for r in findings:
        if r["type"] == "idle_instance":
            print(f"[EC2 idle] {r['instance_id']} avg_cpu_7d={r['avg_cpu_7d']}% cost={r['monthly_cost_usd']} -> {r['recommendation']}")
        elif r["type"] == "unused_ebs":
            print(f"[EBS free] {r['volume_id']} size={r['size_gb']}GB -> {r['recommendation']}")
        elif r["type"] == "unused_eip":
            print(f"[EIP] {r['public_ip']} -> {r['recommendation']}")

if __name__ == "__main__":
    # keep CLI behavior for standalone runs
    import argparse
    p = argparse.ArgumentParser(description="Cloud Waste Tracker – EC2/EBS/EIP")
    p.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", DEFAULT_REGION))
    args = p.parse_args()
    run(region=args.region)
