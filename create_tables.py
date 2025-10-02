#!/usr/bin/env python3
"""
Simple database table creation script for Render deployment
Usage: python create_tables.py
"""

import sys
import os
from pathlib import Path

# Load .env file first
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add src to path
REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from db.db import engine
    from db.models import Base
    
    def create_tables():
        """Create all database tables"""
        print("Creating database tables...")
        Base.metadata.create_all(engine)
        print("✅ Database tables created successfully")
        
        # List created tables
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"Created tables: {tables}")
    
    if __name__ == "__main__":
        create_tables()
        
except Exception as e:
    print(f"❌ Failed to create tables: {e}")
    sys.exit(1)
