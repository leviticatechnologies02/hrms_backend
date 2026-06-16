import os
import sys

# Add backend root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.models.employee import Employee, EmployeeDocument
from app.models.onboarding import OnboardingForm, CandidateDocument, FormSubmission

db = SessionLocal()
try:
    employee_id = 1
    business_id = 1
    
    print("--- Checking Employee ---")
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if emp:
        print(f"Employee ID: {emp.id}")
        print(f"Name: {emp.first_name} {emp.last_name}")
        print(f"Email: {emp.email}")
        print(f"Business ID: {emp.business_id}")
    else:
        print(f"No employee found with ID {employee_id}")

    print("\n--- Checking Onboarding Forms for Employee ID 1 ---")
    forms = db.query(OnboardingForm).filter(OnboardingForm.employee_id == employee_id).all()
    print(f"Found {len(forms)} forms linked to employee_id {employee_id}")
    for form in forms:
        print(f"Form ID: {form.id}, Candidate Name: {form.candidate_name}, Token: {form.form_token}, Status: {form.status}, Business ID: {form.business_id}")

    print("\n--- Checking Onboarding Forms by Email match ---")
    if emp:
        email_forms = db.query(OnboardingForm).filter(OnboardingForm.candidate_email == emp.email).all()
        print(f"Found {len(email_forms)} forms linked to email {emp.email}")
        for form in email_forms:
            print(f"Form ID: {form.id}, Candidate Name: {form.candidate_name}, Token: {form.form_token}, Status: {form.status}, Employee ID: {form.employee_id}, Business ID: {form.business_id}")

    print("\n--- Checking Form Submissions ---")
    submissions = db.query(FormSubmission).all()
    print(f"Total form submissions in DB: {len(submissions)}")
    for sub in submissions[:5]:
        print(f"Submission ID: {sub.id}, Form ID: {sub.form_id}, First Name: {sub.first_name}, Personal Email: {sub.personal_email}")

    print("\n--- Checking Candidate Documents ---")
    cand_docs = db.query(CandidateDocument).all()
    print(f"Total candidate documents in DB: {len(cand_docs)}")
    for doc in cand_docs[:5]:
        print(f"Doc ID: {doc.id}, Business ID: {doc.business_id}, Token: {doc.form_token}, Name: {doc.document_name}, Type: {doc.document_type}, Path: {doc.file_path}")

    print("\n--- Checking Employee Documents ---")
    emp_docs = db.query(EmployeeDocument).filter(EmployeeDocument.employee_id == employee_id).all()
    print(f"Found {len(emp_docs)} employee documents for employee {employee_id}")
    for doc in emp_docs:
        print(f"Doc ID: {doc.id}, Name: {doc.document_name}, Type: {doc.document_type}, Path: {doc.file_path}")

finally:
    db.close()
