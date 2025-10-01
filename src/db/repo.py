from datetime import datetime
from sqlalchemy import select, desc
from .db import get_db
from .models import User, Scan, Finding
import pandas as pd
import json

def ensure_user(email: str) -> User:
    """יוצר משתמש אם לא קיים ומחזיר אותו"""
    with get_db() as s:
        u = s.scalar(select(User).where(User.email == email))
        if not u:
            u = User(email=email, password_hash="!")
            s.add(u)
            s.flush()
        return u

def start_scan(user_id: int | None = None) -> Scan:
    """פותח סריקה חדשה"""
    with get_db() as s:
        scan = Scan(user_id=user_id, started_at=datetime.utcnow(), status="pending")
        s.add(scan)
        s.flush()
        return scan

def add_finding(scan_id: int, resource_id: str, resource_type: str,
                issue_type: str, estimated_saving_usd: float,
                region: str | None = None, attributes: dict | None = None) -> Finding:
    """מוסיף Finding חדש לסריקה"""
    with get_db() as s:
        f = Finding(
            scan_id=scan_id,
            resource_id=resource_id,
            resource_type=resource_type,
            issue_type=issue_type,
            estimated_saving_usd=estimated_saving_usd,
            region=region,
            attributes=attributes or {},
        )
        s.add(f)
        s.flush()
        return f

def finish_scan(scan_id: int, status: str = "success") -> None:
    """מסיים סריקה ומעדכן סטטוס"""
    with get_db() as s:
        scan = s.get(Scan, scan_id)
        if scan:
            scan.status = status
            scan.finished_at = datetime.utcnow()


def save_scan_results(ec2_df: pd.DataFrame, s3_df: pd.DataFrame, scanned_at: str) -> None:
    """שמירת תוצאות סריקה למסד הנתונים"""
    with get_db() as s:
        # Create a new scan record
        scan = Scan(
            user_id=None,  # No user for automated scans
            started_at=datetime.fromisoformat(scanned_at.replace('Z', '+00:00')),
            finished_at=datetime.utcnow(),
            status="success"
        )
        s.add(scan)
        s.flush()
        
        # Save EC2 findings
        if not ec2_df.empty:
            for _, row in ec2_df.iterrows():
                finding = Finding(
                    scan_id=scan.id,
                    resource_id=row.get('instance_id', ''),
                    resource_type='EC2',
                    issue_type=row.get('type', 'idle_instance'),
                    estimated_saving_usd=float(row.get('monthly_cost_usd', 0)),
                    region=row.get('region', ''),
                    attributes=row.to_dict()
                )
                s.add(finding)
        
        # Save S3 findings
        if not s3_df.empty:
            for _, row in s3_df.iterrows():
                finding = Finding(
                    scan_id=scan.id,
                    resource_id=row.get('bucket', ''),
                    resource_type='S3',
                    issue_type=row.get('type', 's3_bucket_summary'),
                    estimated_saving_usd=0.0,  # S3 savings are harder to quantify
                    region=row.get('region', ''),
                    attributes=row.to_dict()
                )
                s.add(finding)


def get_last_scan() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """קבלת הסריקה האחרונה ממסד הנתונים"""
    with get_db() as s:
        # Get the most recent scan
        scan = s.scalar(
            select(Scan)
            .where(Scan.status == "success")
            .order_by(desc(Scan.finished_at))
            .limit(1)
        )
        
        if not scan:
            return pd.DataFrame(), pd.DataFrame(), ""
        
        # Get findings for this scan
        findings = s.scalars(
            select(Finding)
            .where(Finding.scan_id == scan.id)
        ).all()
        
        # Separate EC2 and S3 findings
        ec2_data = []
        s3_data = []
        
        for finding in findings:
            if finding.resource_type == 'EC2':
                ec2_data.append(finding.attributes)
            elif finding.resource_type == 'S3':
                s3_data.append(finding.attributes)
        
        # Convert to DataFrames
        ec2_df = pd.DataFrame(ec2_data) if ec2_data else pd.DataFrame()
        s3_df = pd.DataFrame(s3_data) if s3_data else pd.DataFrame()
        
        # Format timestamp
        scanned_at = scan.finished_at.isoformat() + "Z" if scan.finished_at else ""
        
        return ec2_df, s3_df, scanned_at
