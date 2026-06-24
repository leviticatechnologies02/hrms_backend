import sys
from sqlalchemy import create_engine

# Use the production database URL directly without importing app modules
db_url = "postgresql://levitica_hr_38nm_user:yUu6E00p44mOikLwZrt3k4uUoZ58Lq6U@dpg-cpi5u4aj1k6c738tldp0-a.singapore-postgres.render.com/levitica_hr_38nm?sslmode=require"

engine = create_engine(db_url)
with engine.connect() as conn:
    # Get the latest form submission for form_id 24
    result = conn.execute("SELECT first_name, last_name, date_of_birth, gender, marital_status, mobile, aadhaar_number, pan_number FROM form_submissions WHERE form_id = 24 ORDER BY id DESC LIMIT 1").fetchone()
    
    if result:
        print(f"Found submission: {result}")
        first_name = result[0]
        last_name = result[1]
        dob = result[2]
        gender = result[3]
        marital = result[4]
        mobile = result[5]
        aadhaar = result[6]
        pan = result[7]
        
        if dob:
            conn.execute(f"UPDATE employees SET date_of_birth = '{dob}' WHERE id = 53")
        if gender:
            conn.execute(f"UPDATE employees SET gender = '{gender}' WHERE id = 53")
        if marital:
            conn.execute(f"UPDATE employees SET marital_status = '{marital}' WHERE id = 53")
            
        if aadhaar or pan:
            # check if employee_profiles exists
            prof = conn.execute("SELECT id FROM employee_profiles WHERE employee_id = 53").fetchone()
            if prof:
                updates = []
                if aadhaar:
                    updates.append(f"aadhaar_number = '{aadhaar}'")
                if pan:
                    updates.append(f"pan_number = '{pan}'")
                conn.execute(f"UPDATE employee_profiles SET {', '.join(updates)} WHERE employee_id = 53")
            else:
                conn.execute(f"INSERT INTO employee_profiles (employee_id, aadhaar_number, pan_number) VALUES (53, '{aadhaar or ''}', '{pan or ''}')")
                
        print("Employee 53 backfilled successfully!")
    else:
        print("Could not find submission")
