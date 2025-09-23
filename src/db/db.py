import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

# שליפת DATABASE_URL מהסביבה (Render מגדיר אותו)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in environment variables.")

# יצירת engine ל-Postgres
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# factory לסשנים
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# context manager לשימוש נוח
@contextmanager
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
