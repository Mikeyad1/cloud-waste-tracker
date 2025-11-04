"""
AWS Region Discovery Service
Handles discovering enabled regions for multi-region scanning.
"""

from __future__ import annotations
from typing import List, Optional
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


def discover_enabled_regions(
    aws_credentials: Optional[dict] = None,
    aws_auth_method: str = "user"
) -> List[str]:
    """
    Discover all enabled AWS regions for the current account.
    
    Args:
        aws_credentials: Optional credential overrides
        aws_auth_method: "user" or "role"
    
    Returns:
        List of region names (e.g., ["us-east-1", "us-west-2", ...])
    """
    try:
        # Use a default region to query for all regions
        default_region = aws_credentials.get("AWS_DEFAULT_REGION", "us-east-1") if aws_credentials else os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        # Create EC2 client with credentials
        # Note: For role auth, the credentials should already contain temporary role credentials
        if aws_credentials:
            ec2_client = _create_ec2_client(default_region, aws_credentials)
        else:
            # Use environment variables
            ec2_client = boto3.client("ec2", region_name=default_region)
        
        # Describe regions - this works from any region
        response = ec2_client.describe_regions()
        regions = [r["RegionName"] for r in response.get("Regions", [])]
        
        # For global scanning, return ALL regions from describe_regions
        # The accessibility check was too restrictive and could skip regions with resources
        # If a region truly isn't accessible, the scan will fail gracefully for that region
        print(f"DEBUG: Found {len(regions)} total AWS regions")
        print(f"DEBUG: Regions list (first 10): {regions[:10]}")
        return regions
        
    except (NoCredentialsError, ClientError) as e:
        print(f"⚠️  Region discovery failed: {e}")
        # Fallback to common regions
        return _common_regions()


def _create_ec2_client(region: str, credentials: Optional[dict] = None) -> boto3.client:
    """Create an EC2 client with optional credential overrides."""
    if credentials:
        return boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=credentials.get("AWS_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=credentials.get("AWS_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=credentials.get("AWS_SESSION_TOKEN") or os.getenv("AWS_SESSION_TOKEN")
        )
    return boto3.client("ec2", region_name=region)


def _region_accessible(region: str, credentials: Optional[dict], auth_method: str) -> bool:
    """Quick check if a region is accessible (doesn't require listing resources)."""
    try:
        client = _create_ec2_client(region, credentials)
        # Simple API call to test access
        client.describe_availability_zones(MaxResults=1)
        return True
    except ClientError:
        return False


def _common_regions() -> List[str]:
    """Fallback list of common AWS regions."""
    return [
        "us-east-1",      # N. Virginia
        "us-east-2",      # Ohio
        "us-west-1",      # N. California
        "us-west-2",      # Oregon
        "eu-west-1",      # Ireland
        "eu-west-2",      # London
        "eu-central-1",   # Frankfurt
        "ap-southeast-1", # Singapore
        "ap-southeast-2", # Sydney
        "ap-northeast-1", # Tokyo
    ]


def get_region_display_name(region: str) -> str:
    """Get human-readable name for a region."""
    region_names = {
        "us-east-1": "US East (N. Virginia)",
        "us-east-2": "US East (Ohio)",
        "us-west-1": "US West (N. California)",
        "us-west-2": "US West (Oregon)",
        "eu-west-1": "EU (Ireland)",
        "eu-west-2": "EU (London)",
        "eu-central-1": "EU (Frankfurt)",
        "ap-southeast-1": "Asia Pacific (Singapore)",
        "ap-southeast-2": "Asia Pacific (Sydney)",
        "ap-northeast-1": "Asia Pacific (Tokyo)",
    }
    return region_names.get(region, region)

