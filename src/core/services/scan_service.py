"""
Scan orchestration service - centralized business logic for running scans
"""

from typing import Tuple, Optional, Mapping
import pandas as pd
from datetime import datetime, timedelta

from scanners.ec2_scanner import scan_ec2
from scanners.s3_scanner import scan_s3
from db.repo import save_scan_results


class ScanService:
    """Central service for orchestrating cloud waste scans"""
    
    def __init__(self):
        pass
    
    def run_full_scan(
        self, 
        region: str = "us-east-1",
        aws_credentials: Optional[Mapping[str, str]] = None,
        aws_auth_method: str = "user",
        save_to_db: bool = True
    ) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
        """
        Run a complete scan (EC2 + S3) and optionally save to database.
        
        Args:
            region: AWS region to scan
            aws_credentials: Optional AWS credentials override
            aws_auth_method: "user" or "role" authentication method
            save_to_db: Whether to save results to database
            
        Returns:
            Tuple of (ec2_df, s3_df, timestamp)
        """
        # Import the existing scan orchestrator
        from cwt_ui.services.scans import run_all_scans
        
        # Run the scans using existing logic
        ec2_df, s3_df = run_all_scans(
            region=region,
            aws_credentials=aws_credentials,
            aws_auth_method=aws_auth_method
        )
        
        # Generate timestamp in Israel time
        israel_time = datetime.utcnow() + timedelta(hours=3)
        scanned_at = israel_time.replace(microsecond=0).isoformat() + " (Israel Time)"
        
        # Save to database if requested
        if save_to_db:
            try:
                save_scan_results(ec2_df, s3_df, scanned_at)
            except Exception as e:
                print(f"Warning: Failed to save scan to database: {e}")
        
        return ec2_df, s3_df, scanned_at
    
    def run_ec2_scan(self, region: str = "us-east-1") -> pd.DataFrame:
        """Run EC2-only scan"""
        from cwt_ui.services.scans import scan_ec2
        return scan_ec2(region)
    
    def run_s3_scan(self, region: str = "us-east-1") -> pd.DataFrame:
        """Run S3-only scan"""
        from cwt_ui.services.scans import scan_s3
        return scan_s3(region)
    
    def get_scan_summary(self, ec2_df: pd.DataFrame, s3_df: pd.DataFrame) -> dict:
        """Generate scan summary statistics"""
        summary = {
            "ec2_instances": len(ec2_df),
            "s3_buckets": len(s3_df),
            "total_findings": len(ec2_df) + len(s3_df),
            "estimated_monthly_waste": 0.0,
            "cold_storage_gb": 0.0
        }
        
        # Calculate EC2 waste
        if not ec2_df.empty and "monthly_cost_usd" in ec2_df.columns:
            if "recommendation" in ec2_df.columns:
                waste_mask = ~ec2_df["recommendation"].astype(str).str.upper().eq("OK")
                summary["estimated_monthly_waste"] = float(
                    pd.to_numeric(ec2_df.loc[waste_mask, "monthly_cost_usd"], errors="coerce")
                    .fillna(0.0).sum()
                )
        
        # Calculate S3 cold storage
        if not s3_df.empty and "standard_cold_gb" in s3_df.columns:
            summary["cold_storage_gb"] = float(
                pd.to_numeric(s3_df["standard_cold_gb"], errors="coerce")
                .fillna(0.0).sum()
            )
        
        return summary


# Global instance for easy access
scan_service = ScanService()
