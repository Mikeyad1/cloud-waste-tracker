from datetime import datetime
from sqlalchemy import select
from .db import get_db
from .models import User, Scan, Finding

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
