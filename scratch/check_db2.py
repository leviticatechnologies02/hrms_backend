import os
import sys

# Add backend root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.models.employee import Employee
from app.models.onboarding import OnboardingForm, CandidateDocument

db = SessionLocal()
try:
    print("--- All Onboarding Forms in DB ---")
    forms = db.query(OnboardingForm).all()
    for f in forms:
        print(f"Form ID: {f.id}, Name: {f.candidate_name}, Token: {f.form_token}, Status: {f.status}, Employee ID: {f.employee_id}, Email: {f.candidate_email}")
        
    print("\n--- All Candidate Documents in DB ---")
    docs = db.query(CandidateDocument).all()
    for d in docs:
        print(f"Doc ID: {d.id}, Token: {d.form_token}, Name: {d.document_name}, Type: {d.document_type}, Path: {d.file_path}")

finally:
    db.close()
