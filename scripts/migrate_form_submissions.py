import sys
import os
import logging
from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal

logging.basicConfig(level=logging.INFO)

def main():
    db = SessionLocal()
    columns_to_add = {
        "mobile": "VARCHAR(20)",
        "home_phone": "VARCHAR(20)",
        "father_name": "VARCHAR(255)",
        "father_phone": "VARCHAR(20)",
        "father_dob": "DATE",
        "mother_name": "VARCHAR(255)",
        "mother_phone": "VARCHAR(20)",
        "mother_dob": "DATE",
        "passport_number": "VARCHAR(50)",
        "driving_license_number": "VARCHAR(50)",
        "uan_number": "VARCHAR(50)",
        "esi_number": "VARCHAR(50)",
        "present_address_line1": "VARCHAR(255)",
        "present_address_line2": "VARCHAR(255)",
        "present_city": "VARCHAR(100)",
        "present_pincode": "VARCHAR(20)",
        "present_state": "VARCHAR(100)",
        "present_country": "VARCHAR(100)",
        "permanent_address_line1": "VARCHAR(255)",
        "permanent_address_line2": "VARCHAR(255)",
        "permanent_city": "VARCHAR(100)",
        "permanent_pincode": "VARCHAR(20)",
        "permanent_state": "VARCHAR(100)",
        "permanent_country": "VARCHAR(100)",
        "account_holder_name": "VARCHAR(255)",
        "emergency_contact": "VARCHAR(20)",
        "mobile_verified": "BOOLEAN DEFAULT FALSE",
    }
    
    for col_name, col_type in columns_to_add.items():
        try:
            db.execute(text(f"ALTER TABLE form_submissions ADD COLUMN {col_name} {col_type};"))
            db.commit()
            logging.info(f"Added column {col_name}")
        except Exception as e:
            db.rollback()
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                logging.info(f"Column {col_name} already exists")
            else:
                logging.error(f"Error adding {col_name}: {e}")

    db.close()

if __name__ == "__main__":
    main()
