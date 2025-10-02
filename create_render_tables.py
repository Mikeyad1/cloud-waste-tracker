#!/usr/bin/env python3
"""
Create database tables directly on Render PostgreSQL
Usage: python create_render_tables.py
"""

import os
import sys
from pathlib import Path

# Add src to path
REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Use Render PostgreSQL URL directly
RENDER_DATABASE_URL = "postgresql://cwt_user:KAwdM9z1JNs9xF5D4lXJftOF8DE8F0u1@dpg-d38r9c8gjchc73d9k4qg-a.oregon-postgres.render.com/cwt_db_47u0"

try:
    from sqlalchemy import create_engine
    from db.models import Base
    
    print("🔗 Connecting to Render PostgreSQL...")
    engine = create_engine(RENDER_DATABASE_URL, pool_pre_ping=True)
    
    print("📋 Creating database tables...")
    Base.metadata.create_all(engine)
    
    print("✅ Database tables created successfully on Render!")
    
    # List created tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"📊 Created tables: {tables}")
    
except Exception as e:
    print(f"❌ Failed to create tables: {e}")
    sys.exit(1)
