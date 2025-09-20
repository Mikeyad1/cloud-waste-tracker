# cloud_waste_tracker/utils/utils.py
from __future__ import annotations
from pathlib import Path
import os
import boto3

# --- Project root (folder that holds the CSV/TXT outputs) ---
FILE = Path(__file__).resolve()
ROOT: Path = FILE.parents[3]  # ...\cloud-waste-tracker

# --- Default config (can be overridden by environment variables) ---
DEFAULT_REGION = os.environ.get("CWT_REGION", "us-east-1")

# --- Paths helpers (single source of truth for file locations) ---
def path_waste_csv() -> Path:
    return ROOT / "waste_report.csv"

def path_s3_csv() -> Path:
    return ROOT / "s3_waste_report.csv"

def path_summary_txt() -> Path:
    return ROOT / "summary.txt"

def path_actions_txt() -> Path:
    return ROOT / "action_list.txt"

# --- AWS clients (use one place to create boto3 clients) ---
def aws_client(service: str, region: str | None = None):
    return boto3.client(service, region_name=region or DEFAULT_REGION)

def aws_resource(service: str, region: str | None = None):
    return boto3.resource(service, region_name=region or DEFAULT_REGION)
