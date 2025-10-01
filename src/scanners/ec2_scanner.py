# src/scanners/ec2_scanner.py
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple

import boto3
from botocore.exceptions import ClientError

# ----------------------
# Settings / constants
# ----------------------
DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Below this average CPU (over lookback window) an instance is considered "idle"
IDLE_CPU_THRESHOLD = 5.0
# Lookback window for CPU metric
IDLE_LOOKBACK_DAYS = 7

# Simple on-demand hourly prices (Linux, us-east-1) – demo only
INSTANCE_PRICES = {
    "t3.micro": 0.0104, "t3.small": 0.0208, "t3.medium": 0.0416, "t3.large": 0.0832,
    "t2.micro": 0.0116, "t2.small": 0.023, "t2.medium": 0.0464,
}


# ----------------------
# Helpers
# ----------------------
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _daterange(days: int) -> Tuple[datetime, datetime]:
    end = _utc_now()
    start = end - timedelta(days=days)
    return start, end


def _estimate_monthly_cost(instance_type: str):
    hourly = INSTANCE_PRICES.get(instance_type)
    return "unknown" if hourly is None else round(hourly * 24 * 30, 2)  # ~720h


def _aws_client(service: str, region: str):
    # Use environment variables only, no local credentials file
    return boto3.client(
        service, 
        region_name=region,
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        aws_session_token=os.getenv('AWS_SESSION_TOKEN')
    )


# ----------------------
# Scanners (EC2 / EBS / EIP)
# ----------------------
def scan_ec2_idle(region: str) -> List[Dict]:
    """
    Return idle EC2 instance findings in the shape expected by the UI:
      type, region, instance_id, name, instance_type, avg_cpu_7d, recommendation, monthly_cost_usd
    """
    ec2 = _aws_client("ec2", region)
    cw = _aws_client("cloudwatch", region)

    reservations = ec2.describe_instances().get("Reservations", [])
    instances = [
        i
        for r in reservations
        for i in r.get("Instances", [])
        if i.get("State", {}).get("Name") == "running"
    ]

    start, end = _daterange(IDLE_LOOKBACK_DAYS)
    out: List[Dict] = []

    for inst in instances:
        instance_id = inst.get("InstanceId")
        itype = inst.get("InstanceType", "?")
        name_tag = next((t["Value"] for t in inst.get("Tags", []) if t.get("Key") == "Name"), "")

        # Average CPU over lookback window
        try:
            resp = cw.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start,
                EndTime=end,
                Period=3600 * 6,
                Statistics=["Average"],
            )
            dps = resp.get("Datapoints", [])
            avg_cpu = 0.0 if not dps else sum(dp["Average"] for dp in dps) / len(dps)
        except ClientError:
            avg_cpu = -1.0  # couldn't read metrics

        if avg_cpu >= 0 and avg_cpu < IDLE_CPU_THRESHOLD:
            out.append(
                {
                    "type": "idle_instance",
                    "region": region,
                    "instance_id": instance_id,
                    "name": name_tag,
                    "instance_type": itype,
                    "avg_cpu_7d": round(avg_cpu, 2),
                    "recommendation": "Stop or downsize",
                    "monthly_cost_usd": _estimate_monthly_cost(itype),
                }
            )

    return out


def scan_ebs_available(region: str) -> List[Dict]:
    """
    Return findings for available (detached) EBS volumes.
    """
    ec2 = _aws_client("ec2", region)
    vols = ec2.describe_volumes(Filters=[{"Name": "status", "Values": ["available"]}]).get("Volumes", [])
    out: List[Dict] = []
    for v in vols:
        vid = v.get("VolumeId")
        size = v.get("Size", 0)
        out.append(
            {
                "type": "unused_ebs",
                "region": region,
                "volume_id": vid,
                "size_gb": size,
                "recommendation": "Delete or snapshot then delete",
                "notes": f"Detached EBS ~{size}GB (consider snapshot+delete)",
            }
        )
    return out


def scan_eips_unassociated(region: str) -> List[Dict]:
    """
    Return findings for unassociated Elastic IPs.
    """
    ec2 = _aws_client("ec2", region)
    addrs = ec2.describe_addresses().get("Addresses", [])
    out: List[Dict] = []
    for a in addrs:
        if not a.get("AssociationId"):
            out.append(
                {
                    "type": "unused_eip",
                    "region": region,
                    "allocation_id": a.get("AllocationId"),
                    "public_ip": a.get("PublicIp"),
                    "recommendation": "Release Elastic IP",
                    "notes": "EIP charges when not associated",
                }
            )
    return out


# ----------------------
# Public entry points
# ----------------------
def scan_ec2(region: str | None = None):
    """
    Primary entry point used by the UI adapter (scans.py).
    Returns a list[dict] for EC2 idle instances only (the EC2 page focuses on instances).
    Other findings (EBS/EIP) are still available via helper functions above if you want to surface them later.
    """
    region = region or DEFAULT_REGION
    return scan_ec2_idle(region)


def run(region: str | None = None):
    """
    Backward-compatible CLI entry point.
    Aggregates all EC2/EBS/EIP findings and returns them (no CSV).
    """
    region = region or DEFAULT_REGION
    findings: List[Dict] = []
    findings += scan_ec2_idle(region)
    findings += scan_ebs_available(region)
    findings += scan_eips_unassociated(region)

    # brief console output
    for r in findings:
        t = r.get("type")
        if t == "idle_instance":
            print(
                f"[EC2 idle] {r.get('instance_id')} "
                f"avg_cpu_7d={r.get('avg_cpu_7d')}% cost={r.get('monthly_cost_usd')} -> {r.get('recommendation')}"
            )
        elif t == "unused_ebs":
            print(f"[EBS free] {r.get('volume_id')} size={r.get('size_gb')}GB -> {r.get('recommendation')}")
        elif t == "unused_eip":
            print(f"[EIP] {r.get('public_ip')} -> {r.get('recommendation')}")

    return findings


if __name__ == "__main__":
    # Allow standalone testing: python -m scanners.ec2_scanner --region us-east-1
    import argparse

    p = argparse.ArgumentParser(description="Cloud Waste Tracker – EC2/EBS/EIP (live, no CSV)")
    p.add_argument("--region", default=DEFAULT_REGION)
    args = p.parse_args()

    run(region=args.region)
