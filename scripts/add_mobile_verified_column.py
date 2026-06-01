"""Add candidate_mobile_verified column to onboarding_forms table."""
import sys
sys.path.insert(0, '.')

from app.core.database import engine
from sqlalchemy import text

conn = engine.connect()
try:
    conn.execute(text('ALTER TABLE onboarding_forms ADD COLUMN candidate_mobile_verified BOOLEAN DEFAULT FALSE'))
    conn.commit()
    print("Column 'candidate_mobile_verified' added successfully!")
except Exception as e:
    if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
        print("Column already exists, skipping.")
    else:
        print(f"Note: {e}")
finally:
    conn.close()
