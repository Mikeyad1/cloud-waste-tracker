# src/cloud_waste_tracker/config/secrets.py
import os
try:
    # Locally: load values from .env file if it exists (optional)
    from dotenv import load_dotenv  # requires: python-dotenv
    load_dotenv()
except Exception:
    pass

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

if not EMAIL_USER or not EMAIL_PASS:
    raise RuntimeError("Missing EMAIL_USER/EMAIL_PASS environment variables")
