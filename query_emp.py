import sys
import os

from app.core.database import SessionLocal
from app.models.employee import Employee, EmployeeProfile
from app.models.onboarding import FormSubmission, OnboardingForm

db = SessionLocal()

emp = db.query(Employee).filter(Employee.id == 53).first()
if not emp:
    print("Employee 53 not found.")
    sys.exit(0)

print(f"Employee 53: {emp.first_name} {emp.last_name}")
print(f"Date of birth: {emp.date_of_birth}")
print(f"Gender: {emp.gender}")
print(f"Pan: {emp.profile.pan_number if emp.profile else None}")
print(f"Aadhar: {emp.profile.aadhaar_number if emp.profile else None}")

form = db.query(OnboardingForm).filter(OnboardingForm.employee_id == 53).first()
if form:
    print(f"Found form {form.id}")
    submission = db.query(FormSubmission).filter(FormSubmission.form_id == form.id).first()
    if submission:
        print(f"Submission DOB: {submission.date_of_birth}")
        print(f"Submission Gender: {submission.gender}")
        print(f"Submission Pan: {submission.pan_number}")
        print(f"Submission Aadhar: {submission.aadhaar_number}")
        print(f"Submission First Name: {submission.first_name}")
        print(f"Submission Image: {submission.profile_image}")
    else:
        print("No submission found.")
else:
    print("No onboarding form found for employee 53.")
