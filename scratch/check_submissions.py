import os
import sys

# Add backend root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.models.onboarding import FormSubmission

db = SessionLocal()
try:
    form_ids = [1, 11, 12, 13]
    print("--- Submissions for Forms 1, 11, 12, 13 ---")
    subs = db.query(FormSubmission).filter(FormSubmission.form_id.in_(form_ids)).all()
    for s in subs:
        print(f"Submission ID: {s.id}, Form ID: {s.form_id}, Name: {s.first_name} {s.last_name}")
        print(f"Uploaded Documents JSON: {s.uploaded_documents}")
        print(f"Personal Email: {s.personal_email}")
        print("-" * 50)
finally:
    db.close()
