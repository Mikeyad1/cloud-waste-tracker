"""
Pydantic models for API request/response validation
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class ScanSummary(BaseModel):
    """Summary statistics for a scan"""
    ec2_instances: int = Field(description="Number of EC2 instances found")
    s3_buckets: int = Field(description="Number of S3 buckets found")
    total_findings: int = Field(description="Total number of findings")
    estimated_monthly_waste: float = Field(description="Estimated monthly waste in USD")
    cold_storage_gb: float = Field(description="Cold storage in GB")


class EC2Finding(BaseModel):
    """EC2 finding model"""
    instance_id: str
    name: Optional[str] = None
    instance_type: str
    region: str
    avg_cpu_7d: Optional[float] = None
    monthly_cost_usd: Optional[float] = None
    recommendation: Optional[str] = None
    status: Optional[str] = None


class S3Finding(BaseModel):
    """S3 finding model"""
    bucket: str
    region: str
    size_total_gb: Optional[float] = None
    objects_total: Optional[int] = None
    standard_cold_gb: Optional[float] = None
    standard_cold_objects: Optional[int] = None
    lifecycle_defined: Optional[bool] = None
    recommendation: Optional[str] = None
    status: Optional[str] = None


class ScanResult(BaseModel):
    """Complete scan result"""
    scanned_at: str = Field(description="Timestamp when scan was completed")
    summary: ScanSummary
    ec2_findings: List[EC2Finding]
    s3_findings: List[S3Finding]


class ScanTriggerRequest(BaseModel):
    """Request to trigger a new scan"""
    region: str = Field(default="us-east-1", description="AWS region to scan")


class ScanTriggerResponse(BaseModel):
    """Response from triggering a scan"""
    message: str
    scanned_at: str
    summary: ScanSummary


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    environment: str
    features: Dict[str, bool]


class RecentScan(BaseModel):
    """Recent scan entry"""
    scan_time: str
    status: str


class ScanHistoryResponse(BaseModel):
    """Scan history response"""
    scans: List[RecentScan]
