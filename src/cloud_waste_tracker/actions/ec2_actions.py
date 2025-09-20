# cloud_waste_tracker/actions/ec2_actions.py
"""
EC2 Actions Module
- Reads waste_report.csv (from utils.path_waste_csv)
- Prepares plan of idle instances
- Can stop them if confirmed
"""

from __future__ import annotations
import csv
from collections import defaultdict
from typing import List, Tuple

from cloud_waste_tracker.utils.utils import (
    path_waste_csv,
    aws_client,
    DEFAULT_REGION,
)

# tuple: (instance_id, region)
PlanItem = Tuple[str, str]

def plan_stop_idle() -> List[PlanItem]:
    """
    Parse waste_report.csv and return list of idle instance IDs (with region).
    Idle if recommendation startswith('stop') or type == 'idle_instance'
    """
    ids: List[PlanItem] = []
    ec2_csv = path_waste_csv()
    if not ec2_csv.exists():
        print(f"[!] CSV not found: {ec2_csv}")
        return ids

    with ec2_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec = (row.get("recommendation") or "").lower()
            is_idle = rec.startswith("stop") or (row.get("type") == "idle_instance")
            if not is_idle:
                continue
            iid = (row.get("instance_id") or "").strip()
            region = (row.get("region") or DEFAULT_REGION).strip()
            if iid:
                ids.append((iid, region))
    return ids

def stop_instances(instance_ids: list[str], region: str | None = None) -> None:
    """
    Actually stop the given instance IDs (single region call).
    WARNING: This changes cloud state!
    """
    if not instance_ids:
        print("[i] No instances to stop.")
        return
    client = aws_client("ec2", region)
    print(f"[i] Stopping {len(instance_ids)} instance(s) in {region or DEFAULT_REGION}...")
    client.stop_instances(InstanceIds=instance_ids)
    print("[✓] Stop command sent.")

def stop_plan_grouped(plan: List[PlanItem]) -> None:
    """
    Convenience: group the (iid, region) plan and stop per-region.
    """
    if not plan:
        print("[i] Nothing to stop.")
        return
    by_region: dict[str, list[str]] = defaultdict(list)
    for iid, region in plan:
        by_region[region].append(iid)
    for region, ids in by_region.items():
        stop_instances(ids, region=region)

if __name__ == "__main__":
    plan = plan_stop_idle()
    if not plan:
        print("[i] No idle instances found.")
    else:
        print("[?] Found idle instances:", plan)
        confirm = input("Stop them now? (1=yes, 0=no): ").strip()
        if confirm == "1":
            stop_plan_grouped(plan)
