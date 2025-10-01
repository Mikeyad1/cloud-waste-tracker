is#!/usr/bin/env python3
"""
Worker application for running cloud waste scans and persisting results to database.
Usage: python apps/worker/main.py --region us-east-1
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import our modules
from db.repo import save_scan_results
from cwt_ui.services.scans import run_all_scans


def main():
    parser = argparse.ArgumentParser(description="Cloud Waste Tracker - Worker")
    parser.add_argument("--region", default="us-east-1", help="AWS region to scan")
    args = parser.parse_args()
    
    print(f"🔍 Starting scan for region: {args.region}")
    
    try:
        # Prepare AWS credentials from environment variables
        aws_credentials = None
        aws_auth_method = "user"
        
        # Check if we have role-based credentials in environment
        if os.getenv("AWS_ROLE_ARN"):
            aws_credentials = {
                "AWS_ROLE_ARN": os.getenv("AWS_ROLE_ARN"),
                "AWS_EXTERNAL_ID": os.getenv("AWS_EXTERNAL_ID", ""),
                "AWS_ROLE_SESSION_NAME": os.getenv("AWS_ROLE_SESSION_NAME", "CloudWasteTracker"),
                "AWS_DEFAULT_REGION": args.region,
            }
            # Add base credentials if available
            if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
                aws_credentials.update({
                    "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
                    "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
                })
            aws_auth_method = "role"
            print("🔐 Using IAM Role authentication")
        elif os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            aws_credentials = {
                "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
                "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
                "AWS_DEFAULT_REGION": args.region,
            }
            if os.getenv("AWS_SESSION_TOKEN"):
                aws_credentials["AWS_SESSION_TOKEN"] = os.getenv("AWS_SESSION_TOKEN")
            aws_auth_method = "user"
            print("🔐 Using IAM User authentication")
        else:
            # No credentials found in environment - this should not happen in production
            print("❌ No AWS credentials found in environment variables")
            print("   Required: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
            print("   Optional: AWS_ROLE_ARN, AWS_EXTERNAL_ID")
            sys.exit(1)
        
        # Run the scans
        print("📊 Running EC2 and S3 scans...")
        ec2_df, s3_df = run_all_scans(
            region=args.region, 
            aws_credentials=aws_credentials, 
            aws_auth_method=aws_auth_method
        )
        
        # Get current timestamp
        scanned_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        
        # Persist results to database
        print("💾 Saving results to database...")
        save_scan_results(ec2_df, s3_df, scanned_at)
        
        print(f"✅ Scan completed successfully at {scanned_at}")
        print(f"   - EC2 findings: {len(ec2_df)}")
        print(f"   - S3 findings: {len(s3_df)}")
        
    except Exception as e:
        print(f"❌ Scan failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
