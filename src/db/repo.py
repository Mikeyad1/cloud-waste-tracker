from datetime import datetime
from sqlalchemy import select
from .db import get_session
from .models import Base, User, Scan, Finding

def ensure_user(email: str) -> int:
    with get_session() as s:
        u = s.scalar(select(User).where(User.email == email))
        if not u:
            u = User(email=email, password_hash="!")
            s.add(u)
            s.flush()
        return u.id

def start_scan(user_id: int) -> int:
    with get_session() as s:
        scan = Scan(user_id=user_id, started_at=datetime.utcnow(), status="pending")
        s.add(scan); s.flush()
        return scan.id

def add_finding(scan_id: int, resource_id: str, resource_type: str,
                issue_type: str, estimated_saving_usd: float) -> int:
    with get_session() as s:
        f = Finding(scan_id=scan_id, resource_id=resource_id,
                    resource_type=resource_type, issue_type=issue_type,
                    estimated_saving_usd=estimated_saving_usd)
        s.add(f); s.flush()
        return f.id

def finish_scan(scan_id: int, status: str = "success") -> None:
    with get_session() as s:
        scan = s.get(Scan, scan_id)
        scan.status = status
        scan.finished_at = datetime.utcnow()

