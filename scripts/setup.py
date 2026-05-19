"""
Complete Database Setup Script
Creates database, tables, superadmin account, and sample onboarding data
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.models.base import Base
from app.models.user import User
from app.models.business import Business
from app.models.employee import Employee, EmployeeProfile, EmployeeDocument, EmployeeStatus, MaritalStatus, Gender
from app.models.employee_additional_info import EmployeeAdditionalInfo
from app.models.employee_permissions import EmployeePermissions
from app.models.employee_access import EmployeeAccess, EmployeeLoginSession
from app.models.onboarding import (
    OnboardingForm, OnboardingStatus, OfferLetterTemplate, OnboardingSettings,
    BulkOnboarding, FormSubmission
)
from app.models.credits import UserCredits, CreditTransaction, CreditPricing
from app.models.department import Department
from app.models.designations import Designation
from app.models.location import Location
from app.models.holiday import Holiday
from app.models.esi_settings import ESISettings, ESIComponentMapping, ESIRateChange
from app.models.cost_center import CostCenter
from app.models.business_unit import BusinessUnit
from app.models.work_shifts import WorkShift
from app.models.shift_policy import ShiftPolicy
from app.models.weekoff_policy import WeekOffPolicy
from app.models.grades import Grade
from app.models.leave_balance import LeaveBalance, LeaveCorrection
from app.models.leave_type import LeaveType
from app.models.setup.salary_and_deductions.overtime import OvertimePolicy
from app.models.employee_leave_policy import EmployeeLeavePolicy
from app.models.requests import (
    Request, ShiftRosterRequest, LeaveRequest, MissedPunchRequest,
    ClaimRequest, CompoffRequest, TimeRelaxationRequest, VisitPunchRequest,
    WorkflowRequest, HelpdeskRequest, StrikeExemptionRequest
)
from app.models.payroll import PayrollPeriod, PayrollPeriodStatus
from app.models.setup.Integrations.emailsettings import (
    EmailMailbox, EmailSmtpConfig, EmailOAuthConfig, EmailTestLog,
    EmailProvider, EmailOAuthProvider
)
from app.models.setup.Integrations.biometricsync import (
    BiometricDevice, BiometricSyncLog
)
from app.models.setup.Integrations.gatekeeper import (
    GatekeeperDevice
)
from app.models.setup.Integrations.sqlserver import (
    SqlServerSource, SqlServerSyncLog
)
from app.models.setup.Integrations.sap_mapping import (
    SAPMapping
)
from app.models.setup.Integrations.api_access import (
    APIAccess
)
from app.models.crm import (
    CRMCompany, CRMContact, CRMDeal, CRMActivity, CRMPipeline,
    ContactType, LeadStatus, DealStage, ActivityType, Priority
)
from app.models.contact_inquiry import (
    ContactInquiry, InquiryStatus, InquirySource
)
from app.schemas.enums import UserRole, UserStatus
from app.core.database import engine, get_db_context
from app.core.security import get_password_hash
from app.core.config import settings
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
import json
import uuid
import random
from datetime import datetime, timedelta, date
from decimal import Decimal

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def create_database_if_needed():
    """Create PostgreSQL database if it doesn't exist."""
    logger.info("Step 1: Checking database...")
    
    try:
        # Try connecting to target database
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME
        )
        conn.close()
        logger.info(f"Database '{settings.DB_NAME}' exists")
        return True
        
    except psycopg2.OperationalError:
        # Database doesn't exist, create it
        logger.info(f"Creating database '{settings.DB_NAME}'...")
        
        try:
            conn = psycopg2.connect(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            cursor.execute(f'CREATE DATABASE {settings.DB_NAME}')
            cursor.close()
            conn.close()
            logger.info(f"Database '{settings.DB_NAME}' created")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            return False


def clean_existing_objects():
    """Remove existing tables and constraints."""
    logger.info("\nStep 2: Cleaning existing objects...")
    
    try:
        with engine.connect() as conn:
            # Drop indexes
            indexes = ['ix_users_mobile', 'ix_users_email', 'ix_users_id',
                      'ix_users_email_status', 'ix_users_role_status']
            
            for index in indexes:
                try:
                    conn.execute(text(f"DROP INDEX IF EXISTS {index} CASCADE"))
                    conn.commit()
                except:
                    pass
            
            # Drop tables
            conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
            conn.commit()
            
            # Drop enum types
            conn.execute(text("DROP TYPE IF EXISTS user_role_enum CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS user_status_enum CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS userrole CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS userstatus CASCADE"))
            conn.commit()
            
        logger.info("Cleanup complete")
        return True
        
    except Exception as e:
        logger.warning(f"Cleanup warning: {e}")
        return True  # Continue anyway


def create_tables():
    """Create database tables from models."""
    logger.info("\nStep 3: Creating tables...")
    
    try:
        Base.metadata.create_all(bind=engine)
        
        # Verify creation
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
        
        if tables:
            logger.info(f"Created {len(tables)} table(s): {', '.join(tables)}")
            return True
        else:
            logger.error("No tables created")
            return False
            
    except Exception as e:
        logger.error(f"Table creation failed: {e}")
        return False


def add_ncp_columns_if_missing():
    """Add NCP days columns to salary_reports table if they don't exist."""
    logger.info("\nChecking for NCP columns in salary_reports table...")
    
    try:
        with get_db_context() as db:
            # Check if columns exist
            result = db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'salary_reports' 
                AND column_name IN ('ncp_days', 'working_days')
            """))
            existing_columns = [row[0] for row in result]
            
            columns_to_add = []
            if 'ncp_days' not in existing_columns:
                columns_to_add.append('ncp_days')
            if 'working_days' not in existing_columns:
                columns_to_add.append('working_days')
            
            if columns_to_add:
                logger.info(f"Adding missing columns: {', '.join(columns_to_add)}")
                
                if 'ncp_days' in columns_to_add:
                    db.execute(text("""
                        ALTER TABLE salary_reports 
                        ADD COLUMN IF NOT EXISTS ncp_days INTEGER NOT NULL DEFAULT 0
                    """))
                    logger.info("  ✓ Added ncp_days column")
                
                if 'working_days' in columns_to_add:
                    db.execute(text("""
                        ALTER TABLE salary_reports 
                        ADD COLUMN IF NOT EXISTS working_days INTEGER NOT NULL DEFAULT 30
                    """))
                    logger.info("  ✓ Added working_days column")
                
                db.commit()
                logger.info("NCP columns added successfully")
            else:
                logger.info("NCP columns already exist - skipping")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to add NCP columns: {e}")
        return False


def create_superadmin():
    """Create default superadmin account."""
    logger.info("\nStep 4: Creating superadmin...")
    
    try:
        with get_db_context() as db:
            # Check if superadmin exists
            existing = db.query(User).filter(
                User.email == settings.SUPERADMIN_EMAIL
            ).first()
            
            if existing:
                logger.info(f"Superadmin already exists: {settings.SUPERADMIN_EMAIL}")
                return True
            
            # Create superadmin
            superadmin = User(
                name=settings.SUPERADMIN_NAME,
                email=settings.SUPERADMIN_EMAIL,
                hashed_password=get_password_hash(settings.SUPERADMIN_PASSWORD),
                role=UserRole.SUPERADMIN,
                status=UserStatus.ACTIVE,
                is_email_verified=True,
                mobile="+91-9876543210",
                phone_number="+91-9876543210",
                address="123 Tech Park, Hyderabad, Telangana, India - 500081",
                website="https://levitica.com",
                account_url="levitica-hrms",
                plan_name="Enterprise",
                plan_type="Annual",
                currency="INR",
                language="English"
            )
            
            db.add(superadmin)
            db.commit()
            
            logger.info(f"Superadmin created: {settings.SUPERADMIN_EMAIL}")
            return True
            
    except Exception as e:
        logger.error(f"Superadmin creation failed: {e}")
        return False


def create_user_preferences():
    """Create default preferences for all users"""
    logger.info("\nCreating user preferences...")
    
    try:
        with get_db_context() as db:
            from app.models.user_preferences import UserPreferences
            
            # Get all users
            users = db.query(User).all()
            
            if not users:
                logger.warning("No users found to create preferences for")
                return True
            
            created_count = 0
            
            for user in users:
                # Check if preferences already exist
                existing = db.query(UserPreferences).filter(
                    UserPreferences.user_id == user.id
                ).first()
                
                if existing:
                    logger.info(f"Preferences already exist for user: {user.email}")
                    continue
                
                # Create default preferences
                preferences = UserPreferences(
                    user_id=user.id,
                    send_email_alerts=True,
                    send_sms_alerts=False,
                    send_browser_push_alerts=False,
                    daily_attendance_summary=True,
                    onboarding_form_updates=True,
                    employee_confirmation_reminders=True,
                    flight_risk_changes=False
                )
                
                db.add(preferences)
                created_count += 1
            
            db.commit()
            
            logger.info(f"[OK] Created preferences for {created_count} users")
            return True
            
    except Exception as e:
        logger.error(f"User preferences creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_sample_onboarding_data():
    """Create sample onboarding data for testing"""
    logger.info("\nStep 5: Creating sample onboarding data...")
    
    try:
        with get_db_context() as db:
            # Get or create default business
            business = db.query(Business).first()
            if not business:
                # Get superadmin user first
                superadmin = db.query(User).filter(User.email == settings.SUPERADMIN_EMAIL).first()
                if not superadmin:
                    logger.error("Superadmin not found")
                    return False
                
                business = Business(
                    owner_id=superadmin.id,
                    business_name="Levitica Technologies Private Limited",
                    gstin="22AAAAA0000A1Z5",
                    is_authorized=True,
                    pan="ABCDE1234F",
                    address="123 Business Street, Tech City, Karnataka",
                    city="Bangalore",
                    pincode="560001",
                    state="Karnataka",
                    constitution="Private Limited Company",
                    product="HRMS Suite",
                    plan="Professional",
                    employee_count=50,
                    billing_frequency="Monthly (1 month)",
                    business_url="levitica-tech",
                    biometric_license_count=3,
                    is_active=True
                )
                db.add(business)
                db.commit()
                db.refresh(business)
            
            # Get superadmin user
            superadmin = db.query(User).filter(User.email == settings.SUPERADMIN_EMAIL).first()
            if not superadmin:
                logger.error("Superadmin not found")
                return False
            
            # Create sample departments
            departments_data = [
                {"name": "OD Team", "head": "John Manager"},
                {"name": "Product Development Team", "head": "Jane Lead"},
                {"name": "Technical Support", "head": "Mike Support"},
                {"name": "Engineering", "head": "Sarah Engineer"},
                {"name": "Human Resources", "head": "David HR"}
            ]
            
            for dept_data in departments_data:
                existing_dept = db.query(Department).filter(Department.name == dept_data["name"]).first()
                if not existing_dept:
                    department = Department(
                        business_id=business.id,
                        name=dept_data["name"],
                        head=dept_data["head"],
                        is_active=True,
                        created_by=superadmin.id,
                        created_at=datetime.now()
                    )
                    db.add(department)
            
            # Create sample designations
            designations_data = [
                {"name": "Associate Software Engineer", "default": True},
                {"name": "HR Executive", "default": False},
                {"name": "Manager", "default": False},
                {"name": "Team Lead", "default": False}
            ]
            
            for desig_data in designations_data:
                # Check for existing designation globally (due to unique constraint on name)
                existing_desig = db.query(Designation).filter(
                    Designation.name == desig_data["name"]
                ).first()
                if not existing_desig:
                    designation = Designation(
                        business_id=business.id,
                        name=desig_data["name"],
                        default=desig_data["default"],
                        employees=0
                    )
                    db.add(designation)
            
            # Create sample locations
            locations_data = [
                {
                    "name": "Hyderabad", 
                    "state": "Telangana",
                    "location_head": "Rajesh Kumar",
                    "deputy_head": "Priya Sharma",
                    "is_default": True,
                    "map_url": "https://www.google.com/maps?q=17.446597,78.386319&z=15&output=embed"
                },
                {
                    "name": "Bangalore", 
                    "state": "Karnataka",
                    "location_head": "Amit Patel",
                    "deputy_head": "Sneha Reddy",
                    "is_default": False,
                    "map_url": "https://www.google.com/maps?q=12.9716,77.5946&z=15&output=embed"
                },
                {
                    "name": "Mumbai", 
                    "state": "Maharashtra",
                    "location_head": "Vikram Singh",
                    "deputy_head": "Anita Desai",
                    "is_default": False,
                    "map_url": "https://www.google.com/maps?q=19.0760,72.8777&z=15&output=embed"
                }
            ]
            
            for loc_data in locations_data:
                existing_loc = db.query(Location).filter(Location.name == loc_data["name"]).first()
                if not existing_loc:
                    location = Location(
                        business_id=business.id,
                        name=loc_data["name"],
                        state=loc_data["state"],
                        location_head=loc_data.get("location_head"),
                        deputy_head=loc_data.get("deputy_head"),
                        is_default=loc_data.get("is_default", False),
                        map_url=loc_data.get("map_url"),
                        employees=0,
                        is_active=True,
                        created_by=superadmin.id,
                        created_at=datetime.now()
                    )
                    db.add(location)
            
            # Create sample cost centers
            cost_centers_data = [
                {"name": "Engineering", "is_default": True},
                {"name": "Human Resources", "is_default": False},
                {"name": "Finance", "is_default": False},
                {"name": "Operations", "is_default": False},
                {"name": "Marketing", "is_default": False}
            ]
            
            for cc_data in cost_centers_data:
                existing_cc = db.query(CostCenter).filter(CostCenter.name == cc_data["name"]).first()
                if not existing_cc:
                    cost_center = CostCenter(
                        business_id=business.id,
                        name=cc_data["name"],
                        is_default=cc_data["is_default"],
                        employees=0,
                        is_active=True,
                        created_by=superadmin.id,
                        created_at=datetime.now()
                    )
                    db.add(cost_center)
            
            # Create sample grades
            grades_data = [
                {"name": "Associate"},
                {"name": "Engineer"},
                {"name": "Senior Engineer"},
                {"name": "Manager"},
                {"name": "Executive"},
                {"name": "Supervisor"},
                {"name": "Trainee"}
            ]
            
            for grade_data in grades_data:
                # Check for existing grade globally (due to unique constraint on name)
                existing_grade = db.query(Grade).filter(
                    Grade.name == grade_data["name"]
                ).first()
                if not existing_grade:
                    grade = Grade(
                        business_id=business.id,
                        name=grade_data["name"],
                        employees=0,
                        created_by=superadmin.id,
                        created_at=datetime.now()
                    )
                    db.add(grade)
            
            # Create sample business units
            business_units_data = [
                {
                    "name": "Levitica Technologies Software Division",
                    "report_title": "Software Division Annual Report",
                    "is_default": True,
                    "employees": 63
                },
                {
                    "name": "Levitica Technologies Hardware Division",
                    "report_title": "Hardware Division Annual Report", 
                    "is_default": False,
                    "employees": 25
                },
                {
                    "name": "Levitica Technologies Consulting Division",
                    "report_title": "Consulting Division Annual Report",
                    "is_default": False,
                    "employees": 18
                }
            ]
            
            for bu_data in business_units_data:
                existing_bu = db.query(BusinessUnit).filter(
                    BusinessUnit.business_id == business.id,
                    BusinessUnit.name == bu_data["name"]
                ).first()
                if not existing_bu:
                    business_unit = BusinessUnit(
                        business_id=business.id,
                        name=bu_data["name"],
                        report_title=bu_data["report_title"],
                        is_default=bu_data["is_default"],
                        employees=bu_data["employees"],
                        is_active=True,
                        created_at=datetime.now()
                    )
                    db.add(business_unit)
            
            # Create sample work shifts
            work_shifts_data = [
                {
                    "code": "DS",
                    "name": "Day Shift",
                    "payable_hrs": "8:00",
                    "rules": 1,
                    "default": True,
                    "timing": "09:00 AM - 06:00 PM",
                    "start_buffer_hours": 30,
                    "end_buffer_hours": 30
                },
                {
                    "code": "NS",
                    "name": "Night Shift",
                    "payable_hrs": "8:00",
                    "rules": 2,
                    "default": False,
                    "timing": "10:00 PM - 07:00 AM",
                    "start_buffer_hours": 15,
                    "end_buffer_hours": 15
                },
                {
                    "code": "FS",
                    "name": "Flexible Shift",
                    "payable_hrs": "8:00",
                    "rules": 0,
                    "default": False,
                    "timing": "Flexible Hours",
                    "start_buffer_hours": 60,
                    "end_buffer_hours": 60
                },
                {
                    "code": "MS",
                    "name": "Morning Shift",
                    "payable_hrs": "8:00",
                    "rules": 1,
                    "default": False,
                    "timing": "07:00 AM - 04:00 PM",
                    "start_buffer_hours": 15,
                    "end_buffer_hours": 15
                },
                {
                    "code": "ES",
                    "name": "Evening Shift",
                    "payable_hrs": "8:00",
                    "rules": 1,
                    "default": False,
                    "timing": "02:00 PM - 11:00 PM",
                    "start_buffer_hours": 15,
                    "end_buffer_hours": 15
                },
                {
                    "code": "WS",
                    "name": "Weekend Shift",
                    "payable_hrs": "6:00",
                    "rules": 3,
                    "default": False,
                    "timing": "10:00 AM - 05:00 PM",
                    "start_buffer_hours": 30,
                    "end_buffer_hours": 30
                }
            ]
            
            for ws_data in work_shifts_data:
                # Check for existing work shift globally (due to unique constraint on code)
                existing_ws = db.query(WorkShift).filter(
                    WorkShift.code == ws_data["code"]
                ).first()
                if not existing_ws:
                    work_shift = WorkShift(
                        business_id=business.id,
                        code=ws_data["code"],
                        name=ws_data["name"],
                        payable_hrs=ws_data["payable_hrs"],
                        rules=ws_data["rules"],
                        default=ws_data["default"],
                        timing=ws_data["timing"],
                        start_buffer_hours=ws_data["start_buffer_hours"],
                        end_buffer_hours=ws_data["end_buffer_hours"]
                    )
                    db.add(work_shift)
            
            # Create sample shift policies
            shift_policies_data = [
                {
                    "title": "Day Shift (9 AM - 6 PM)",
                    "description": "Standard day shift with 9 hours including 1 hour break",
                    "is_default": True,
                    "weekly_shifts": {}
                },
                {
                    "title": "Night Shift (10 PM - 7 AM)",
                    "description": "Night shift with 9 hours including 1 hour break",
                    "is_default": False,
                    "weekly_shifts": {}
                },
                {
                    "title": "Flexible Hours",
                    "description": "Flexible working hours policy",
                    "is_default": False,
                    "weekly_shifts": {}
                }
            ]
            
            for sp_data in shift_policies_data:
                existing_sp = db.query(ShiftPolicy).filter(ShiftPolicy.title == sp_data["title"]).first()
                if not existing_sp:
                    shift_policy = ShiftPolicy(
                        business_id=business.id,
                        title=sp_data["title"],
                        description=sp_data["description"],
                        is_default=sp_data["is_default"],
                        weekly_shifts=sp_data["weekly_shifts"],
                        created_at=datetime.now()
                    )
                    db.add(shift_policy)
            
            # Create sample week off policies
            weekoff_policies_data = [
                {
                    "title": "Saturday-Sunday Off",
                    "description": "Standard weekend off policy",
                    "is_default": True,
                    "general_week_offs": ["Saturday", "Sunday"],
                    "alternating_week_offs": [],
                    "weekoffs_payable": False
                },
                {
                    "title": "Sunday Only Off",
                    "description": "Only Sunday off policy",
                    "is_default": False,
                    "general_week_offs": ["Sunday"],
                    "alternating_week_offs": [],
                    "weekoffs_payable": False
                },
                {
                    "title": "Rotating Week Off",
                    "description": "Rotating week off policy - 1st and 3rd Sunday off",
                    "is_default": False,
                    "general_week_offs": [],
                    "alternating_week_offs": [
                        [],  # Monday
                        [],  # Tuesday
                        [],  # Wednesday
                        [],  # Thursday
                        [],  # Friday
                        [],  # Saturday
                        ["Week1", "Week3"]  # Sunday - 1st and 3rd week
                    ],
                    "weekoffs_payable": True
                }
            ]
            
            for wo_data in weekoff_policies_data:
                existing_wo = db.query(WeekOffPolicy).filter(WeekOffPolicy.title == wo_data["title"]).first()
                if not existing_wo:
                    weekoff_policy = WeekOffPolicy(
                        business_id=business.id,
                        title=wo_data["title"],
                        description=wo_data["description"],
                        is_default=wo_data["is_default"],
                        general_week_offs=wo_data["general_week_offs"],
                        alternating_week_offs=wo_data["alternating_week_offs"],
                        weekoffs_payable=wo_data["weekoffs_payable"],
                        created_at=datetime.now()
                    )
                    db.add(weekoff_policy)
            
            # Create sample overtime policies
            from app.models.setup.salary_and_deductions.overtime import OvertimePolicy
            
            overtime_policies_data = [
                {
                    "policy_name": "Not Applicable"
                },
                {
                    "policy_name": "Standard Overtime Policy"
                },
                {
                    "policy_name": "Premium Overtime Policy"
                }
            ]
            
            for ot_data in overtime_policies_data:
                existing_ot = db.query(OvertimePolicy).filter(OvertimePolicy.policy_name == ot_data["policy_name"]).first()
                if not existing_ot:
                    overtime_policy = OvertimePolicy(
                        business_id=business.id,
                        policy_name=ot_data["policy_name"]
                    )
                    db.add(overtime_policy)
            
            # Create offer letter templates
            templates_data = [
                {
                    "name": "Appointment Letter [Sample]",
                    "description": "Standard appointment letter template",
                    "template_content": "Dear {employee_name},\n\nWe are pleased to offer you the position of {designation} at {company_name}.\n\nYour joining date is {joining_date} and your CTC is {ctc}.\n\nWelcome to the team!\n\nBest regards,\nHR Team",
                    "available_variables": json.dumps(["employee_name", "designation", "company_name", "joining_date", "ctc"]),
                    "is_default": True
                },
                {
                    "name": "Sample-1",
                    "description": "Simple offer letter template",
                    "template_content": "Dear {employee_name},\n\nYour joining date is {joining_date} for the position of {designation}.\n\nRegards,\nHR Team",
                    "available_variables": json.dumps(["employee_name", "joining_date", "designation"])
                },
                {
                    "name": "Sample-2",
                    "description": "Detailed offer letter template",
                    "template_content": "Hello {employee_name},\n\nWe are pleased to offer you {designation} position at {company_name}.\n\nSalary Details:\n- Basic: {basic_salary}\n- Gross: {gross_salary}\n- CTC: {ctc}\n\nJoining Date: {joining_date}\nLocation: {location}\n\nWelcome aboard!",
                    "available_variables": json.dumps(["employee_name", "designation", "company_name", "basic_salary", "gross_salary", "ctc", "joining_date", "location"])
                }
            ]
            
            for template_data in templates_data:
                existing_template = db.query(OfferLetterTemplate).filter(
                    OfferLetterTemplate.name == template_data["name"]
                ).first()
                
                if not existing_template:
                    template = OfferLetterTemplate(
                        business_id=business.id,
                        created_by=superadmin.id,
                        created_at=datetime.now(),
                        is_active=True,
                        **template_data
                    )
                    db.add(template)
            
            # Create onboarding settings
            existing_settings = db.query(OnboardingSettings).filter(
                OnboardingSettings.business_id == business.id
            ).first()
            
            if not existing_settings:
                document_requirements = {
                    "PAN Card": True,
                    "Adhar Card": True,
                    "ESI Card": False,
                    "Driving License": False,
                    "Passport": False,
                    "Voter ID": False,
                    "Last Relieving Letter": False,
                    "Last Salary Slip": False,
                    "Latest Bank Statement": False,
                    "Highest Education Proof": True
                }
                
                field_requirements = {
                    "presentAddress": True,
                    "permanentAddress": True,
                    "bankDetails": True
                }
                
                settings_obj = OnboardingSettings(
                    business_id=business.id,
                    form_expiry_days=7,
                    allow_form_editing=True,
                    require_document_upload=True,
                    send_welcome_email=True,
                    send_reminder_emails=True,
                    reminder_frequency_days=2,
                    default_verify_mobile=True,
                    default_verify_pan=False,
                    default_verify_bank=False,
                    default_verify_aadhaar=False,
                    enable_auto_approval=False,
                    document_requirements=json.dumps(document_requirements),
                    field_requirements=json.dumps(field_requirements),
                    created_by=superadmin.id,
                    created_at=datetime.now()
                )
                db.add(settings_obj)
            
            # Create sample offer letter templates with professional content
            offer_letter_templates = [
                {
                    "name": "Standard Appointment Letter",
                    "description": "Standard appointment letter for regular positions",
                    "template_content": """{{company_name}}
{{company_address}}

Date: {{offer_date}}

{{candidate_name}}
{{candidate_address}}

Dear {{candidate_name}},

Subject: Appointment Letter - {{position_title}}

We are pleased to appoint you as {{position_title}} at {{company_name}}.

EMPLOYMENT DETAILS:
Position: {{position_title}}
Department: {{department}}
Joining Date: {{joining_date}}
Location: {{location}}
Reporting Manager: {{reporting_manager}}

COMPENSATION:
Monthly Gross Salary: ₹{{gross_salary}}
Annual CTC: ₹{{annual_ctc}}

WORKING HOURS:
{{shift_start_time}} to {{shift_end_time}}
Working Days: {{working_days}}

TERMS:
• Probation Period: {{probation_period}} months
• Notice Period: {{notice_period}} days
• Benefits: As per company policy

Please sign and return this letter as acceptance.

Regards,
{{hr_manager_name}}
{{hr_manager_designation}}

---
Employee Acceptance:
Name: {{candidate_name}}
Signature: _____________
Date: _____________""",
                    "available_variables": json.dumps([
                        "company_name", "company_address", "offer_date", "candidate_name", 
                        "candidate_address", "position_title", "department", "joining_date", 
                        "location", "reporting_manager", "gross_salary", "annual_ctc", 
                        "shift_start_time", "shift_end_time", "working_days", "probation_period", 
                        "notice_period", "hr_manager_name", "hr_manager_designation"
                    ]),
                    "is_active": True,
                    "is_default": True
                },
                {
                    "name": "Senior Position Appointment Letter",
                    "description": "Professional appointment letter for senior management positions",
                    "template_content": """{{company_name}}
{{company_address}}

Date: {{offer_date}}

{{candidate_name}}
{{candidate_address}}

Dear {{candidate_name}},

Subject: Appointment as {{position_title}}

We are delighted to offer you the position of {{position_title}} at {{company_name}}.

POSITION DETAILS:
Designation: {{position_title}}
Department: {{department}}
Location: {{location}}
Joining Date: {{joining_date}}
Reporting To: {{reporting_manager}}

COMPENSATION PACKAGE:
Basic Salary: ₹{{base_salary}} per month
House Rent Allowance: ₹{{hra}} per month
Special Allowance: ₹{{special_allowance}} per month
Gross Monthly Salary: ₹{{gross_salary}}
Annual CTC: ₹{{annual_ctc}}

BENEFITS:
• Health Insurance (Self + Family)
• Provident Fund (12% of Basic)
• Gratuity as per Payment of Gratuity Act
• Annual Performance Bonus
• {{annual_leave_days}} days paid leave per year
• Professional development opportunities

WORKING HOURS:
Standard: {{shift_start_time}} to {{shift_end_time}}
Flexible working arrangements available

TERMS & CONDITIONS:
• Probation Period: {{probation_period}} months
• Notice Period: {{notice_period}} days
• Confidentiality and non-compete clauses apply
• Subject to background verification

This offer is valid until {{offer_expiry_date}}.

We look forward to your valuable contribution.

Warm regards,
{{hr_manager_name}}
{{hr_manager_designation}}

---
Acceptance:
I accept the above terms and conditions.

{{candidate_name}}
Signature: _____________
Date: _____________""",
                    "available_variables": json.dumps([
                        "company_name", "company_address", "offer_date", "candidate_name", 
                        "candidate_address", "position_title", "department", "location", 
                        "joining_date", "reporting_manager", "base_salary", "hra", 
                        "special_allowance", "gross_salary", "annual_ctc", "annual_leave_days", 
                        "shift_start_time", "shift_end_time", "probation_period", "notice_period", 
                        "offer_expiry_date", "hr_manager_name", "hr_manager_designation"
                    ]),
                    "is_active": True,
                    "is_default": False
                },
                {
                    "name": "Internship Offer Letter",
                    "description": "Professional offer letter for internship positions",
                    "template_content": """{{company_name}}
{{company_address}}

Date: {{offer_date}}

{{candidate_name}}
{{candidate_address}}

Dear {{candidate_name}},

Subject: Internship Offer - {{position_title}}

We are pleased to offer you an internship at {{company_name}}.

INTERNSHIP DETAILS:
Position: {{position_title}}
Department: {{department}}
Duration: {{internship_duration}} months
Start Date: {{joining_date}}
End Date: {{internship_end_date}}
Location: {{location}}
Mentor: {{reporting_manager}}

STIPEND:
Monthly Stipend: ₹{{monthly_stipend}}

WORKING HOURS:
{{shift_start_time}} to {{shift_end_time}}
Working Days: {{working_days}}

LEARNING OPPORTUNITIES:
• Hands-on experience with real projects
• Mentorship from industry professionals
• Skill development workshops
• Networking opportunities
• Certificate upon successful completion
• Potential for full-time employment

TERMS:
• Performance evaluation every month
• Maintain confidentiality of company information
• Adhere to company policies and code of conduct
• Notice period: {{notice_period}} days

This offer is valid until {{offer_expiry_date}}.

We look forward to your learning journey with us.

Best regards,
{{hr_manager_name}}
{{hr_manager_designation}}

---
Acceptance:
{{candidate_name}}
Signature: _____________
Date: _____________""",
                    "available_variables": json.dumps([
                        "company_name", "company_address", "offer_date", "candidate_name", 
                        "candidate_address", "position_title", "department", "internship_duration", 
                        "joining_date", "internship_end_date", "location", "reporting_manager", 
                        "monthly_stipend", "shift_start_time", "shift_end_time", "working_days", 
                        "notice_period", "offer_expiry_date", "hr_manager_name", "hr_manager_designation"
                    ]),
                    "is_active": True,
                    "is_default": False
                },
                {
                    "name": "Appointment Letter [Sample]",
                    "description": "Simplified appointment letter template",
                    "template_content": """{{company_name}}
{{company_address}}

Date: {{offer_date}}

{{candidate_name}}
{{candidate_address}}

Dear {{candidate_name}},

Subject: Appointment as {{position_title}}

We are pleased to appoint you as {{position_title}} in our {{department}} department.

Position: {{position_title}}
Joining Date: {{joining_date}}
Location: {{location}}
CTC: ₹{{gross_salary}} per annum
Monthly Salary: ₹{{base_salary}}

Working Hours: {{shift_start_time}} to {{shift_end_time}}
Working Days: {{working_days}}
Probation: {{probation_period}} months

You will report to {{reporting_manager}}.

Please submit required documents on joining.

Welcome to {{company_name}}.

Regards,
{{hr_manager_name}}
{{hr_manager_designation}}

---
Accepted by:
{{candidate_name}}
Date: _______""",
                    "available_variables": json.dumps([
                        "company_name", "company_address", "offer_date", "candidate_name", 
                        "candidate_address", "position_title", "department", "joining_date", 
                        "location", "gross_salary", "base_salary", "shift_start_time", 
                        "shift_end_time", "working_days", "probation_period", "reporting_manager", 
                        "hr_manager_name", "hr_manager_designation"
                    ]),
                    "is_active": True,
                    "is_default": False
                },
                {
                    "name": "Sample-1",
                    "description": "Contract-based employment offer letter",
                    "template_content": """{{company_name}}
{{company_address}}

Date: {{offer_date}}

{{candidate_name}}
{{candidate_address}}

Subject: Contract Employment Offer - {{position_title}}

Dear {{candidate_name}},

We offer you a contract position as {{position_title}}.

Contract Period: {{contract_start_date}} to {{contract_end_date}}
Duration: {{contract_duration}} months
Monthly Compensation: ₹{{monthly_compensation}}
Location: {{location}}

Terms:
• Fixed-term contract
• Renewable based on performance
• {{contract_notice_period}} days notice period
• No benefits except statutory requirements

Please confirm by {{offer_expiry_date}}.

Regards,
{{hr_manager_name}}

---
Accepted:
{{candidate_name}}
Date: _______""",
                    "available_variables": json.dumps([
                        "company_name", "company_address", "offer_date", "candidate_name", 
                        "candidate_address", "position_title", "contract_start_date", 
                        "contract_end_date", "contract_duration", "monthly_compensation", 
                        "location", "contract_notice_period", "offer_expiry_date", "hr_manager_name"
                    ]),
                    "is_active": True,
                    "is_default": False
                },
                {
                    "name": "Sample-2",
                    "description": "Part-time employment offer letter",
                    "template_content": """{{company_name}}
{{company_address}}

Date: {{offer_date}}

{{candidate_name}}
{{candidate_address}}

Subject: Part-Time Employment Offer - {{position_title}}

Dear {{candidate_name}},

We are pleased to offer you a part-time position as {{position_title}}.

Position: {{position_title}}
Department: {{department}}
Start Date: {{joining_date}}
Working Hours: {{part_time_hours}} hours per week
Working Days: {{part_time_days}}
Hourly Rate: ₹{{hourly_rate}}
Monthly Compensation: ₹{{monthly_compensation}} (approx.)

This is a part-time position with flexible working arrangements.

Benefits:
• Flexible schedule
• Work-life balance
• Professional development opportunities

Terms:
• {{part_time_notice_period}} days notice period
• Performance review every {{review_period}} months
• Conversion to full-time: Subject to availability and performance

Please confirm acceptance by {{offer_expiry_date}}.

Welcome aboard!

{{hr_manager_name}}
{{hr_manager_designation}}

---
Accepted:
{{candidate_name}}
Date: _______""",
                    "available_variables": json.dumps([
                        "company_name", "company_address", "offer_date", "candidate_name", 
                        "candidate_address", "position_title", "department", "joining_date", 
                        "part_time_hours", "part_time_days", "hourly_rate", "monthly_compensation", 
                        "part_time_notice_period", "review_period", "offer_expiry_date", 
                        "hr_manager_name", "hr_manager_designation"
                    ]),
                    "is_active": True,
                    "is_default": False
                }
            ]
            
            for template_data in offer_letter_templates:
                existing_template = db.query(OfferLetterTemplate).filter(
                    OfferLetterTemplate.business_id == business.id,
                    OfferLetterTemplate.name == template_data["name"]
                ).first()
                
                if not existing_template:
                    template = OfferLetterTemplate(
                        business_id=business.id,
                        name=template_data["name"],
                        description=template_data["description"],
                        template_content=template_data["template_content"],
                        available_variables=template_data["available_variables"],
                        is_active=template_data["is_active"],
                        is_default=template_data["is_default"],
                        created_by=superadmin.id,
                        created_at=datetime.now()
                    )
                    db.add(template)
            
            # Create sample onboarding forms
            sample_forms = [
                {
                    "candidate_name": "John Doe",
                    "candidate_email": "john.doe@example.com",
                    "candidate_mobile": "+1234567890",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": False,
                    "verify_aadhaar": False
                },
                {
                    "candidate_name": "Jane Smith",
                    "candidate_email": "jane.smith@example.com",
                    "candidate_mobile": "+1234567891",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": True,
                    "verify_aadhaar": False
                },
                {
                    "candidate_name": "Mike Johnson",
                    "candidate_email": "mike.johnson@example.com",
                    "candidate_mobile": "+1234567892",
                    "status": OnboardingStatus.SENT,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": True,
                    "verify_aadhaar": True
                },
                {
                    "candidate_name": "Sarah Wilson",
                    "candidate_email": "sarah.wilson@example.com",
                    "candidate_mobile": "+1234567893",
                    "status": OnboardingStatus.DRAFT,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": False,
                    "verify_aadhaar": False
                },
                {
                    "candidate_name": "David Brown",
                    "candidate_email": "david.brown@example.com",
                    "candidate_mobile": "+1234567894",
                    "status": OnboardingStatus.REJECTED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "rejection_reason": "Incomplete documentation"
                },
                # Additional forms for approval workflow testing
                {
                    "candidate_name": "Bantapalli Pradeep",
                    "candidate_email": "pradeep.bantapalli@example.com",
                    "candidate_mobile": "+9876543210",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Joining date: 15-Oct-2025, Location: Hyderabad, Deputation: No"
                },
                {
                    "candidate_name": "Dasireddy Harsha Vardan Naidu",
                    "candidate_email": "harsha.dasireddy@example.com",
                    "candidate_mobile": "+9876543211",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": True,
                    "verify_aadhaar": True,
                    "notes": "Joining date: 10-Oct-2025, Location: Bangalore, Deputation: Yes"
                },
                {
                    "candidate_name": "Lokeshwar Reddy Kondappagari",
                    "candidate_email": "lokeshwar.kondappagari@example.com",
                    "candidate_mobile": "+9876543212",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": True,
                    "verify_aadhaar": False,
                    "notes": "Joining date: 20-Oct-2025, Location: Chennai, Deputation: No"
                },
                # Additional SUBMITTED forms for pagination testing
                {
                    "candidate_name": "Rajesh Kumar Sharma",
                    "candidate_email": "rajesh.sharma@example.com",
                    "candidate_mobile": "+9876543213",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Joining date: 25-Oct-2025, Location: Mumbai, Deputation: No"
                },
                {
                    "candidate_name": "Priya Patel",
                    "candidate_email": "priya.patel@example.com",
                    "candidate_mobile": "+9876543214",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": True,
                    "verify_aadhaar": True,
                    "notes": "Joining date: 30-Oct-2025, Location: Pune, Deputation: Yes"
                },
                {
                    "candidate_name": "Amit Singh Rathore",
                    "candidate_email": "amit.rathore@example.com",
                    "candidate_mobile": "+9876543215",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": True,
                    "verify_aadhaar": False,
                    "notes": "Joining date: 05-Nov-2025, Location: Delhi, Deputation: No"
                },
                {
                    "candidate_name": "Sneha Reddy Goud",
                    "candidate_email": "sneha.goud@example.com",
                    "candidate_mobile": "+9876543216",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": False,
                    "verify_aadhaar": True,
                    "notes": "Joining date: 10-Nov-2025, Location: Hyderabad, Deputation: Yes"
                },
                {
                    "candidate_name": "Vikram Singh Chauhan",
                    "candidate_email": "vikram.chauhan@example.com",
                    "candidate_mobile": "+9876543217",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": True,
                    "verify_aadhaar": True,
                    "notes": "Joining date: 15-Nov-2025, Location: Bangalore, Deputation: No"
                },
                {
                    "candidate_name": "Anita Desai Mehta",
                    "candidate_email": "anita.mehta@example.com",
                    "candidate_mobile": "+9876543218",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": True,
                    "verify_aadhaar": False,
                    "notes": "Joining date: 20-Nov-2025, Location: Chennai, Deputation: Yes"
                },
                {
                    "candidate_name": "Rohit Gupta Agarwal",
                    "candidate_email": "rohit.agarwal@example.com",
                    "candidate_mobile": "+9876543219",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": False,
                    "verify_aadhaar": True,
                    "notes": "Joining date: 25-Nov-2025, Location: Mumbai, Deputation: No"
                },
                {
                    "candidate_name": "Kavya Nair Pillai",
                    "candidate_email": "kavya.pillai@example.com",
                    "candidate_mobile": "+9876543220",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Joining date: 30-Nov-2025, Location: Kochi, Deputation: Yes"
                },
                {
                    "candidate_name": "Arjun Mehta Shah",
                    "candidate_email": "arjun.shah@example.com",
                    "candidate_mobile": "+9876543221",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": True,
                    "verify_aadhaar": False,
                    "notes": "Joining date: 05-Dec-2025, Location: Ahmedabad, Deputation: No"
                },
                {
                    "candidate_name": "Deepika Joshi Sharma",
                    "candidate_email": "deepika.sharma@example.com",
                    "candidate_mobile": "+9876543222",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": True,
                    "verify_aadhaar": True,
                    "notes": "Joining date: 10-Dec-2025, Location: Jaipur, Deputation: Yes"
                },
                {
                    "candidate_name": "Kiran Kumar Reddy",
                    "candidate_email": "kiran.reddy@example.com",
                    "candidate_mobile": "+9876543223",
                    "status": OnboardingStatus.SUBMITTED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Joining date: 15-Dec-2025, Location: Hyderabad, Deputation: No"
                },
                # Additional forms to match screenshot
                {
                    "candidate_name": "Chandragiri Durga Sai Vara Prasad",
                    "candidate_email": "durgasaivaraprasadchan@gmail.com",
                    "candidate_mobile": "9133934446",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Nagendra Uggirala",
                    "candidate_email": "nagendrauggirala@gmail.com",
                    "candidate_mobile": "7013125955",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Burri Gowtham",
                    "candidate_email": "burrigowtham079@gmail.com",
                    "candidate_mobile": "9347491079",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": True,
                    "verify_aadhaar": False,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Nollu Lalith Kumar",
                    "candidate_email": "lalithkumarnollu@gmail.com",
                    "candidate_mobile": "6303625199",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": True,
                    "verify_aadhaar": False,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Naveen Sai Koppereddy",
                    "candidate_email": "naveensaikoppereddy@gmail.com",
                    "candidate_mobile": "9491738151",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": False,
                    "verify_aadhaar": True,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Mani Bhargav",
                    "candidate_email": "mani@gmail.com",
                    "candidate_mobile": "9876543224",
                    "status": OnboardingStatus.SENT,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Form sent to candidate"
                },
                {
                    "candidate_name": "Internet Telecom Friends",
                    "candidate_email": "internet@telecom.com",
                    "candidate_mobile": "9876543225",
                    "status": OnboardingStatus.SENT,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Form sent to candidate"
                },
                {
                    "candidate_name": "John Doe",
                    "candidate_email": "john.doe@example.com",
                    "candidate_mobile": "9876543226",
                    "status": OnboardingStatus.REJECTED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "rejection_reason": "Incomplete documentation",
                    "notes": "Rejected due to missing documents"
                },
                {
                    "candidate_name": "Test Candidate Beta",
                    "candidate_email": "beta@test.example.com",
                    "candidate_mobile": "9876543227",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": True,
                    "verify_aadhaar": False,
                    "notes": "Test candidate - approved"
                },
                {
                    "candidate_name": "Test Candidate Alpha",
                    "candidate_email": "alpha@test.example.com",
                    "candidate_mobile": "9876543228",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": True,
                    "verify_aadhaar": True,
                    "notes": "Test candidate - approved"
                },
                {
                    "candidate_name": "Electricity Service Vendor/Walkin",
                    "candidate_email": "electricity@service.com",
                    "candidate_mobile": "9876543229",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Service vendor - approved"
                },
                {
                    "candidate_name": "Levitica Mobile Vendor/Walkin",
                    "candidate_email": "levitica@mobile.com",
                    "candidate_mobile": "9876543230",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Mobile vendor - approved"
                },
                {
                    "candidate_name": "Budugu Srinivas",
                    "candidate_email": "budugu.srinivas@example.com",
                    "candidate_mobile": "9876543231",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": True,
                    "verify_aadhaar": False,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Sagar Wilkson",
                    "candidate_email": "sagar.wilkson@example.com",
                    "candidate_mobile": "9876543232",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": True,
                    "verify_aadhaar": True,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "David Brown",
                    "candidate_email": "david.brown@example.com",
                    "candidate_mobile": "9876543233",
                    "status": OnboardingStatus.REJECTED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "rejection_reason": "Failed background check",
                    "notes": "Rejected after background verification"
                },
                {
                    "candidate_name": "Background Freelance",
                    "candidate_email": "background@freelance.com",
                    "candidate_mobile": "9876543234",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Freelance contractor - approved"
                },
                {
                    "candidate_name": "Pradeep Approval",
                    "candidate_email": "pradeep@approval.com",
                    "candidate_mobile": "9876543235",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": True,
                    "verify_aadhaar": False,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Rohit Gupta",
                    "candidate_email": "rohit@gupta.com",
                    "candidate_mobile": "9876543236",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": False,
                    "verify_aadhaar": True,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Suresh Gidde",
                    "candidate_email": "suresh@gidde.com",
                    "candidate_mobile": "9876543237",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Kanya Nair",
                    "candidate_email": "kanya@nair.com",
                    "candidate_mobile": "9876543238",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": True,
                    "verify_aadhaar": False,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Arjun Mohan",
                    "candidate_email": "arjun@mohan.com",
                    "candidate_mobile": "9876543239",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": True,
                    "verify_aadhaar": True,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Vikram Patel",
                    "candidate_email": "vikram@patel.com",
                    "candidate_mobile": "9876543240",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": False,
                    "verify_aadhaar": False,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Priya Sharma",
                    "candidate_email": "priya@sharma.com",
                    "candidate_mobile": "9876543241",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": False,
                    "verify_bank": False,
                    "verify_aadhaar": True,
                    "notes": "Approved candidate"
                },
                {
                    "candidate_name": "Kavita Reddy",
                    "candidate_email": "kavita@reddy.com",
                    "candidate_mobile": "9876543242",
                    "status": OnboardingStatus.APPROVED,
                    "verify_mobile": True,
                    "verify_pan": True,
                    "verify_bank": True,
                    "verify_aadhaar": False,
                    "notes": "Approved candidate"
                }
            ]
            
            for i, form_data in enumerate(sample_forms):
                existing_form = db.query(OnboardingForm).filter(
                    OnboardingForm.candidate_email == form_data["candidate_email"]
                ).first()
                
                if existing_form:
                    # Reset approval forms to submitted status for testing
                    submitted_candidates = [
                        "Bantapalli Pradeep", "Dasireddy Harsha Vardan Naidu", "Lokeshwar Reddy Kondappagari",
                        "Rajesh Kumar Sharma", "Priya Patel", "Amit Singh Rathore", "Sneha Reddy Goud",
                        "Vikram Singh Chauhan", "Anita Desai Mehta", "Rohit Gupta Agarwal", 
                        "Kavya Nair Pillai", "Arjun Mehta Shah", "Deepika Joshi Sharma", "Kiran Kumar Reddy"
                    ]
                    if form_data["candidate_name"] in submitted_candidates:
                        existing_form.status = OnboardingStatus.SUBMITTED
                        existing_form.submitted_at = datetime.now() - timedelta(days=i)
                        existing_form.approved_at = None
                        existing_form.rejected_at = None
                        existing_form.approved_by = None
                        existing_form.rejected_by = None
                        existing_form.rejection_reason = None
                        existing_form.notes = form_data.get("notes")
                        db.commit()
                elif not existing_form:
                    form_token = str(uuid.uuid4())
                    expires_at = datetime.now() + timedelta(days=7)
                    created_at = datetime.now() - timedelta(days=i)
                    
                    form = OnboardingForm(
                        business_id=business.id,
                        form_token=form_token,
                        expires_at=expires_at,
                        created_by=superadmin.id,
                        created_at=created_at,
                        **form_data
                    )
                    
                    # Set timestamps based on status
                    if form.status == OnboardingStatus.SENT:
                        form.sent_at = created_at + timedelta(hours=1)
                    elif form.status == OnboardingStatus.SUBMITTED:
                        form.sent_at = created_at + timedelta(hours=1)
                        form.submitted_at = created_at + timedelta(days=1)
                    elif form.status == OnboardingStatus.APPROVED:
                        form.sent_at = created_at + timedelta(hours=1)
                        form.submitted_at = created_at + timedelta(days=1)
                        form.approved_at = created_at + timedelta(days=2)
                        form.approved_by = superadmin.id
                    elif form.status == OnboardingStatus.REJECTED:
                        form.sent_at = created_at + timedelta(hours=1)
                        form.submitted_at = created_at + timedelta(days=1)
                        form.rejected_at = created_at + timedelta(days=2)
                        form.rejected_by = superadmin.id
                    
                    db.add(form)
            
            # Create candidate onboarding forms with tokens for workflow testing
            candidate_forms = [
                {
                    "candidate_name": "Chandu Thota",
                    "candidate_email": "chandu.thota@example.com",
                    "candidate_mobile": "9494231434",
                    "status": OnboardingStatus.SENT,
                    "form_token": "candidate-test-token-001",
                    "notes": "Test candidate for onboarding workflow"
                },
                {
                    "candidate_name": "Test Candidate Alpha",
                    "candidate_email": "alpha@test.com",
                    "candidate_mobile": "9876543210",
                    "status": OnboardingStatus.SENT,
                    "form_token": "candidate-test-token-002",
                    "notes": "Alpha test candidate for step-by-step workflow"
                },
                {
                    "candidate_name": "Test Candidate Beta",
                    "candidate_email": "beta@test.com",
                    "candidate_mobile": "9876543211",
                    "status": OnboardingStatus.SENT,
                    "form_token": "candidate-test-token-003",
                    "notes": "Beta test candidate for complete workflow testing"
                }
            ]
            
            for candidate_data in candidate_forms:
                existing_candidate = db.query(OnboardingForm).filter(
                    OnboardingForm.form_token == candidate_data["form_token"]
                ).first()
                
                if not existing_candidate:
                    expires_at = datetime.now() + timedelta(days=30)  # Extended expiry for testing
                    created_at = datetime.now() - timedelta(days=1)
                    
                    candidate_form = OnboardingForm(
                        business_id=business.id,
                        candidate_name=candidate_data["candidate_name"],
                        candidate_email=candidate_data["candidate_email"],
                        candidate_mobile=candidate_data["candidate_mobile"],
                        form_token=candidate_data["form_token"],
                        status=candidate_data["status"],
                        verify_mobile=True,
                        verify_pan=False,
                        verify_bank=False,
                        verify_aadhaar=False,
                        notes=candidate_data["notes"],
                        expires_at=expires_at,
                        created_by=superadmin.id,
                        created_at=created_at,
                        sent_at=created_at + timedelta(hours=1)
                    )
                    db.add(candidate_form)
                    db.flush()  # Flush to get the ID
                    
                    # Create partial form submission for testing
                    if candidate_data["form_token"] == "candidate-test-token-001":
                        submission = FormSubmission(
                            form_id=candidate_form.id,
                            first_name="Chandu",
                            last_name="Thota",
                            gender="Male",
                            date_of_birth=date(1995, 5, 15),
                            alternate_mobile="9494231434",
                            personal_email="chandu.thota@example.com",
                            submitted_at=created_at + timedelta(hours=2)
                        )
                        db.add(submission)
            
            # Create sample bulk onboarding operation
            existing_bulk = db.query(BulkOnboarding).first()
            if not existing_bulk:
                bulk_results = [
                    {"candidate_name": "Alice Cooper", "candidate_email": "alice@example.com", "status": "success", "form_id": 1},
                    {"candidate_name": "Bob Dylan", "candidate_email": "bob@example.com", "status": "success", "form_id": 2},
                    {"candidate_name": "Charlie Brown", "candidate_email": "charlie@example.com", "status": "failed", "error": "Invalid email"}
                ]
                
                bulk_operation = BulkOnboarding(
                    business_id=business.id,
                    operation_name="Q4 2024 Bulk Hiring",
                    total_candidates=3,
                    successful_sends=2,
                    failed_sends=1,
                    verify_mobile=True,
                    verify_pan=False,
                    verify_bank=True,
                    verify_aadhaar=False,
                    status="completed",
                    results_summary=json.dumps(bulk_results),
                    created_by=superadmin.id,
                    created_at=datetime.now() - timedelta(days=5),
                    completed_at=datetime.now() - timedelta(days=5, hours=2)
                )
                db.add(bulk_operation)
            
            # Create monthly approved forms for dashboard statistics
            monthly_approved_forms = [
                # November 2024
                {"name": "Rajesh Kumar", "email": "rajesh.nov@example.com", "mobile": "9876543201", "month_offset": 60, "day_offset": 5},
                {"name": "Priya Sharma", "email": "priya.nov@example.com", "mobile": "9876543202", "month_offset": 60, "day_offset": 10},
                {"name": "Amit Singh", "email": "amit.nov@example.com", "mobile": "9876543203", "month_offset": 60, "day_offset": 15},
                {"name": "Sneha Reddy", "email": "sneha.nov@example.com", "mobile": "9876543204", "month_offset": 60, "day_offset": 20},
                {"name": "Vikram Patel", "email": "vikram.nov@example.com", "mobile": "9876543205", "month_offset": 60, "day_offset": 25},
                
                # December 2024
                {"name": "Anita Desai", "email": "anita.dec@example.com", "mobile": "9876543206", "month_offset": 30, "day_offset": 3},
                {"name": "Rohit Gupta", "email": "rohit.dec@example.com", "mobile": "9876543207", "month_offset": 30, "day_offset": 8},
                {"name": "Kavya Nair", "email": "kavya.dec@example.com", "mobile": "9876543208", "month_offset": 30, "day_offset": 12},
                {"name": "Arjun Mehta", "email": "arjun.dec@example.com", "mobile": "9876543209", "month_offset": 30, "day_offset": 18},
                {"name": "Deepika Joshi", "email": "deepika.dec@example.com", "mobile": "9876543210", "month_offset": 30, "day_offset": 22},
                {"name": "Kiran Kumar", "email": "kiran.dec@example.com", "mobile": "9876543211", "month_offset": 30, "day_offset": 28},
                
                # January 2025
                {"name": "Sanjay Verma", "email": "sanjay.jan@example.com", "mobile": "9876543212", "month_offset": 15, "day_offset": 5},
                {"name": "Meera Iyer", "email": "meera.jan@example.com", "mobile": "9876543213", "month_offset": 15, "day_offset": 10},
                {"name": "Ravi Teja", "email": "ravi.jan@example.com", "mobile": "9876543214", "month_offset": 15, "day_offset": 15},
                {"name": "Pooja Agarwal", "email": "pooja.jan@example.com", "mobile": "9876543215", "month_offset": 15, "day_offset": 20},
                {"name": "Suresh Babu", "email": "suresh.jan@example.com", "mobile": "9876543216", "month_offset": 15, "day_offset": 25}
            ]
            
            for form_data in monthly_approved_forms:
                existing_form = db.query(OnboardingForm).filter(
                    OnboardingForm.candidate_email == form_data["email"]
                ).first()
                
                if not existing_form:
                    form_token = str(uuid.uuid4())
                    created_at = datetime.now() - timedelta(days=form_data["month_offset"] + form_data["day_offset"])
                    approved_at = created_at + timedelta(days=2)
                    
                    approved_form = OnboardingForm(
                        business_id=business.id,
                        candidate_name=form_data["name"],
                        candidate_email=form_data["email"],
                        candidate_mobile=form_data["mobile"],
                        form_token=form_token,
                        status=OnboardingStatus.APPROVED,
                        verify_mobile=True,
                        verify_pan=False,
                        verify_bank=False,
                        verify_aadhaar=False,
                        notes=f"Monthly hiring - approved on {approved_at.strftime('%Y-%m-%d')}",
                        expires_at=datetime.now() + timedelta(days=7),
                        created_by=superadmin.id,
                        created_at=created_at,
                        sent_at=created_at + timedelta(hours=1),
                        submitted_at=created_at + timedelta(days=1),
                        approved_at=approved_at,
                        approved_by=superadmin.id
                    )
                    db.add(approved_form)
            
            db.commit()
            logger.info("Sample onboarding data created successfully")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample onboarding data: {e}")
        return False


def create_credit_system_data():
    """Create credit system sample data"""
    logger.info("\nStep 6: Creating credit system data...")
    
    try:
        with get_db_context() as db:
            # Get or create default business
            business = db.query(Business).first()
            if not business:
                logger.error("Business not found")
                return False
            
            # Get superadmin user
            superadmin = db.query(User).filter(User.email == settings.SUPERADMIN_EMAIL).first()
            if not superadmin:
                logger.error("Superadmin not found")
                return False
            
            # Create credit pricing
            pricing_data = [
                {
                    "service_name": "mobile",
                    "service_display_name": "Mobile Verification",
                    "credits_required": 0,
                    "is_free": True
                },
                {
                    "service_name": "pan",
                    "service_display_name": "PAN Verification",
                    "credits_required": 5,
                    "is_free": False
                },
                {
                    "service_name": "bank",
                    "service_display_name": "Bank Verification",
                    "credits_required": 5,
                    "is_free": False
                },
                {
                    "service_name": "aadhaar",
                    "service_display_name": "Aadhaar Verification",
                    "credits_required": 10,
                    "is_free": False
                }
            ]
            
            for pricing in pricing_data:
                existing_pricing = db.query(CreditPricing).filter(
                    CreditPricing.business_id == business.id,
                    CreditPricing.service_name == pricing["service_name"]
                ).first()
                
                if not existing_pricing:
                    credit_pricing = CreditPricing(
                        business_id=business.id,
                        created_by=superadmin.id,
                        created_at=datetime.now(),
                        **pricing
                    )
                    db.add(credit_pricing)
            
            # Create user credits for superadmin (with some initial credits)
            existing_credits = db.query(UserCredits).filter(
                UserCredits.user_id == superadmin.id
            ).first()
            
            if not existing_credits:
                user_credits = UserCredits(
                    user_id=superadmin.id,
                    business_id=business.id,
                    credits=100,  # Give superadmin 100 initial credits
                    created_at=datetime.now()
                )
                db.add(user_credits)
                db.commit()
                db.refresh(user_credits)
                
                # Create initial credit transaction
                initial_transaction = CreditTransaction(
                    user_credits_id=user_credits.id,
                    transaction_type="purchase",
                    amount=100,
                    balance_before=0,
                    balance_after=100,
                    description="Initial credit allocation",
                    reference_id=f"INIT_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    reference_type="initial_allocation",
                    payment_method="system",
                    created_by=superadmin.id,
                    created_at=datetime.now()
                )
                db.add(initial_transaction)
            
            db.commit()
            logger.info("Credit system data created successfully")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create credit system data: {e}")
        return False


def create_attendance_sample_data():
    """Create sample attendance data for testing"""
    logger.info("\nStep 7: Creating sample attendance data...")
    
    try:
        from app.core.config import settings as app_settings
        
        with get_db_context() as db:
            # Get or create default business
            business = db.query(Business).first()
            if not business:
                logger.error("Business not found")
                return False
            
            # Get superadmin user
            superadmin = db.query(User).filter(User.email == app_settings.SUPERADMIN_EMAIL).first()
            if not superadmin:
                logger.error("Superadmin not found")
                return False
            
            # Import attendance models
            from app.models.attendance import AttendanceRecord, AttendancePunch, AttendanceStatus, PunchType
            from datetime import datetime, date, time, timedelta
            from decimal import Decimal
            import random
            
            # Get some employees for sample attendance
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(10).all()
            
            if not employees:
                logger.info("No employees found for attendance data")
                return True
            
            # Create comprehensive attendance data for current month and previous month
            today = date.today()
            current_month_start = date(today.year, today.month, 1)
            
            # Previous month
            if today.month == 1:
                prev_month_start = date(today.year - 1, 12, 1)
                prev_month_end = date(today.year, 1, 1) - timedelta(days=1)
            else:
                prev_month_start = date(today.year, today.month - 1, 1)
                prev_month_end = date(today.year, today.month, 1) - timedelta(days=1)
            
            # Current month (up to today)
            current_month_end = today
            
            # Generate attendance for both months
            date_ranges = [
                (prev_month_start, prev_month_end, "previous"),
                (current_month_start, current_month_end, "current")
            ]
            
            for start_date, end_date, period in date_ranges:
                current_date = start_date
                
                while current_date <= end_date:
                    # Skip future dates in current month
                    if period == "current" and current_date > today:
                        current_date += timedelta(days=1)
                        continue
                    
                    day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday
                    
                    for i, employee in enumerate(employees):
                        # Check if attendance record already exists
                        existing_record = db.query(AttendanceRecord).filter(
                            AttendanceRecord.employee_id == employee.id,
                            AttendanceRecord.attendance_date == current_date
                        ).first()
                        
                        if existing_record:
                            current_date += timedelta(days=1)
                            continue
                        
                        # Determine attendance status based on day and some randomness
                        attendance_status = AttendanceStatus.PRESENT
                        punch_in_time = None
                        punch_out_time = None
                        is_late = False
                        
                        # Weekend handling (Saturday=5, Sunday=6)
                        if day_of_week in [5, 6]:  # Weekend
                            # 90% chance of week off, 10% chance of working
                            if random.random() < 0.9:
                                # Skip creating record for week off (no record = week off)
                                continue
                            else:
                                # Working on weekend
                                attendance_status = AttendanceStatus.PRESENT
                        else:
                            # Weekday attendance patterns
                            rand = random.random()
                            if rand < 0.85:  # 85% present
                                attendance_status = AttendanceStatus.PRESENT
                            elif rand < 0.90:  # 5% absent
                                attendance_status = AttendanceStatus.ABSENT
                            elif rand < 0.95:  # 5% half day
                                attendance_status = AttendanceStatus.HALF_DAY
                            else:  # 5% on leave
                                attendance_status = AttendanceStatus.ON_LEAVE
                        
                        # Generate punch times for present/half day status
                        if attendance_status in [AttendanceStatus.PRESENT, AttendanceStatus.HALF_DAY]:
                            # Vary punch in times (8:30 AM to 10:30 AM)
                            base_hour = 8 + (i % 3)  # 8, 9, or 10 AM base
                            punch_in_minute = random.randint(0, 59)
                            
                            # Add some variation
                            if random.random() < 0.3:  # 30% chance of being late
                                base_hour += 1
                                is_late = True
                            
                            punch_in_time = datetime.combine(current_date, time(base_hour, punch_in_minute))
                            
                            # Punch out time (for completed days or half days)
                            if attendance_status == AttendanceStatus.HALF_DAY:
                                # Half day - punch out around 1-2 PM
                                punch_out_hour = 13 + random.randint(0, 1)
                                punch_out_minute = random.randint(0, 59)
                            else:
                                # Full day - punch out 5-7 PM
                                punch_out_hour = 17 + random.randint(0, 2)
                                punch_out_minute = random.randint(0, 59)
                            
                            # For current day, some employees might not have punched out yet
                            if current_date == today and random.random() < 0.3:
                                punch_out_time = None  # Still working
                            else:
                                punch_out_time = datetime.combine(current_date, time(punch_out_hour, punch_out_minute))
                        
                        # Calculate total hours
                        total_hours = None
                        if punch_in_time and punch_out_time:
                            total_hours = Decimal((punch_out_time - punch_in_time).total_seconds() / 3600)
                        
                        # Create attendance record
                        attendance_record = AttendanceRecord(
                            business_id=business.id,
                            employee_id=employee.id,
                            attendance_date=current_date,
                            punch_in_time=punch_in_time,
                            punch_out_time=punch_out_time,
                            total_hours=total_hours,
                            attendance_status=attendance_status,
                            is_late=is_late,
                            punch_in_location="Hyderabad Office" if punch_in_time else None,
                            punch_out_location="Hyderabad Office" if punch_out_time else None,
                            punch_in_ip="192.168.1.100" if punch_in_time else None,
                            punch_out_ip="192.168.1.100" if punch_out_time else None,
                            created_by=superadmin.id,
                            created_at=datetime.now()
                        )
                        db.add(attendance_record)
                        db.flush()  # Get the ID
                        
                        # Create punch records
                        if punch_in_time:
                            punch_in = AttendancePunch(
                                attendance_record_id=attendance_record.id,
                                employee_id=employee.id,
                                punch_time=punch_in_time,
                                punch_type=PunchType.IN,
                                location="Hyderabad Office",
                                ip_address="192.168.1.100",
                                device_info="Web Browser - Chrome",
                                is_biometric=False,
                                is_manual=False,
                                created_by=superadmin.id
                            )
                            db.add(punch_in)
                        
                        if punch_out_time:
                            punch_out = AttendancePunch(
                                attendance_record_id=attendance_record.id,
                                employee_id=employee.id,
                                punch_time=punch_out_time,
                                punch_type=PunchType.OUT,
                                location="Hyderabad Office",
                                ip_address="192.168.1.100",
                                device_info="Web Browser - Chrome",
                                is_biometric=False,
                                is_manual=False,
                                created_by=superadmin.id
                            )
                            db.add(punch_out)
                    
                    current_date += timedelta(days=1)
            
            # Add some holidays for the current month
            holidays = [
                (date(today.year, today.month, 15), "Independence Day"),
                (date(today.year, today.month, 26), "Republic Day")
            ]
            
            for holiday_date, holiday_name in holidays:
                if holiday_date.month == today.month and holiday_date <= today:
                    for employee in employees:
                        # Check if record exists
                        existing_record = db.query(AttendanceRecord).filter(
                            AttendanceRecord.employee_id == employee.id,
                            AttendanceRecord.attendance_date == holiday_date
                        ).first()
                        
                        if not existing_record:
                            # Create holiday record
                            holiday_record = AttendanceRecord(
                                business_id=business.id,
                                employee_id=employee.id,
                                attendance_date=holiday_date,
                                attendance_status=AttendanceStatus.PRESENT,  # Holiday is considered present
                                is_manual_entry=True,
                                manual_entry_reason=f"Holiday: {holiday_name}",
                                created_by=superadmin.id
                            )
                            db.add(holiday_record)
            
            db.commit()
            logger.info("Comprehensive sample attendance data created successfully")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample attendance data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_remote_punch_sample_data():
    """Create sample remote punch data for testing"""
    logger.info("\nStep 7.1: Creating sample remote punch data...")
    
    try:
        from app.core.config import settings as app_settings
        
        with get_db_context() as db:
            # Get or create default business
            business = db.query(Business).first()
            if not business:
                logger.error("Business not found")
                return False
            
            # Get superadmin user
            superadmin = db.query(User).filter(User.email == app_settings.SUPERADMIN_EMAIL).first()
            if not superadmin:
                logger.error("Superadmin not found")
                return False
            
            # Import attendance models
            from app.models.attendance import AttendancePunch, PunchType
            from datetime import datetime, date, time, timedelta
            import random
            
            # Get some employees for remote punch data
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(20).all()
            
            if not employees:
                logger.info("No employees found for remote punch data")
                return True
            
            # Create remote punch data for the last 7 days
            today = date.today()
            
            # Hyderabad office coordinates (base location)
            base_lat = 17.4469635
            base_lng = 78.3865801
            
            # Sample addresses for remote punches
            remote_addresses = [
                "Address Not Fetched",
                "Work from Home",
                "Client Location - Gachibowli",
                "Remote Location - Kondapur",
                "Field Work - Madhapur"
            ]
            
            for days_back in range(7):  # Last 7 days
                punch_date = today - timedelta(days=days_back)
                
                # Skip weekends for most employees
                if punch_date.weekday() in [5, 6]:  # Saturday, Sunday
                    continue
                
                # Select random employees for remote punches (30-50% of employees)
                num_remote_employees = random.randint(int(len(employees) * 0.3), int(len(employees) * 0.5))
                remote_employees = random.sample(employees, num_remote_employees)
                
                for employee in remote_employees:
                    # Create 1-2 remote punches per employee per day
                    num_punches = random.randint(1, 2)
                    
                    for punch_num in range(num_punches):
                        # Generate punch time
                        if punch_num == 0:  # First punch (IN)
                            punch_hour = random.randint(8, 10)  # 8-10 AM
                            punch_type = PunchType.IN
                        else:  # Second punch (OUT)
                            punch_hour = random.randint(17, 19)  # 5-7 PM
                            punch_type = PunchType.OUT
                        
                        punch_minute = random.randint(0, 59)
                        punch_time = datetime.combine(punch_date, time(punch_hour, punch_minute))
                        
                        # Generate GPS coordinates (slight variation from base location)
                        lat_variation = random.uniform(-0.001, 0.001)  # ~100m variation
                        lng_variation = random.uniform(-0.001, 0.001)
                        
                        latitude = base_lat + lat_variation
                        longitude = base_lng + lng_variation
                        
                        # Random location accuracy (GPS accuracy in meters)
                        location_accuracy = random.uniform(3.0, 15.0)
                        
                        # Random address
                        address = random.choice(remote_addresses)
                        
                        # Create remote punch record
                        remote_punch = AttendancePunch(
                            employee_id=employee.id,
                            punch_time=punch_time,
                            punch_type=punch_type,
                            location=address,
                            ip_address=f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
                            device_info=random.choice([
                                "Mobile App - Android",
                                "Mobile App - iOS", 
                                "Web Browser - Chrome Mobile",
                                "Web Browser - Safari Mobile"
                            ]),
                            is_remote=True,
                            latitude=latitude,
                            longitude=longitude,
                            location_accuracy=location_accuracy,
                            is_biometric=False,
                            is_manual=False,
                            created_by=superadmin.id
                        )
                        db.add(remote_punch)
            
            # Add some additional remote punches with specific patterns matching frontend mock data
            mock_employees = [
                ("LEV039", "Anusha Enigalla"),
                ("LEV122", "ARAVELLY THARUN"),
                ("LEV027", "Bogala Chandramouli"),
                ("LEV038", "Cheekati Abhinaya"),
                ("LEV123", "DHANIKELA BRAHMAM"),
                ("LEV127", "Gubba Vasini"),
                ("LEV118", "Hari Charan Teja Gudapati"),
                ("LEV050", "Harsha Vardhan Naidu Dasireddy"),
                ("LEV044", "Hemant Tukaram Pawade"),
                ("LEV008", "Hruthik Venkata Sai Ganesh Jamanu")
            ]
            
            # Create specific punches for today to match frontend expectations
            for emp_code, emp_name in mock_employees:
                # Find employee by code or create if needed
                employee = db.query(Employee).filter(Employee.employee_code == emp_code).first()
                if not employee:
                    continue
                
                # Create a remote punch for today
                punch_hour = random.randint(8, 10)
                punch_minute = random.randint(0, 59)
                punch_time = datetime.combine(today, time(punch_hour, punch_minute))
                
                # Specific coordinates close to base location
                latitude = base_lat + random.uniform(-0.0005, 0.0005)
                longitude = base_lng + random.uniform(-0.0005, 0.0005)
                
                remote_punch = AttendancePunch(
                    employee_id=employee.id,
                    punch_time=punch_time,
                    punch_type=PunchType.IN,
                    location="Address Not Fetched",
                    ip_address="192.168.1.100",
                    device_info="Mobile App - Android",
                    is_remote=True,
                    latitude=latitude,
                    longitude=longitude,
                    location_accuracy=random.uniform(5.0, 12.0),
                    is_biometric=False,
                    is_manual=False,
                    created_by=superadmin.id
                )
                db.add(remote_punch)
            
            db.commit()
            logger.info("Sample remote punch data created successfully")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample remote punch data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_manual_updates_sample_data():
    """Create sample manual updates data for testing"""
    logger.info("\nStep 7.2: Creating sample manual updates data...")
    
    try:
        from app.core.config import settings as app_settings
        
        with get_db_context() as db:
            # Get or create default business
            business = db.query(Business).first()
            if not business:
                logger.error("Business not found")
                return False
            
            # Get superadmin user
            superadmin = db.query(User).filter(User.email == app_settings.SUPERADMIN_EMAIL).first()
            if not superadmin:
                logger.error("Superadmin not found")
                return False
            
            # Import attendance models
            from app.models.attendance import AttendanceRecord, AttendanceCorrection, AttendanceStatus
            from datetime import datetime, date, timedelta
            import random
            
            # Get some employees for manual updates
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(10).all()
            
            if not employees:
                logger.info("No employees found for manual updates data")
                return True
            
            # Create manual attendance entries for the last 30 days
            today = date.today()
            
            # Sample reasons for manual updates
            manual_reasons = [
                "Manual correction",
                "Leave adjustment", 
                "Punch correction",
                "System error correction",
                "Late entry approval",
                "Holiday adjustment",
                "Attendance regularization",
                "Manager approval",
                "HR correction",
                "Biometric failure correction"
            ]
            
            # Sample original statuses
            original_statuses = ["Absent", "Half Day", "Late", "Early Exit", "Missing Punch"]
            
            # Create manual attendance records
            manual_updates_created = 0
            
            for days_back in range(30):  # Last 30 days
                update_date = today - timedelta(days=days_back)
                
                # Skip weekends for most updates
                if update_date.weekday() in [5, 6] and random.random() < 0.8:
                    continue
                
                # Create 1-3 manual updates per day
                num_updates = random.randint(1, 3)
                selected_employees = random.sample(employees, min(num_updates, len(employees)))
                
                for employee in selected_employees:
                    # Check if attendance record already exists
                    existing_record = db.query(AttendanceRecord).filter(
                        AttendanceRecord.employee_id == employee.id,
                        AttendanceRecord.attendance_date == update_date
                    ).first()
                    
                    if existing_record and existing_record.is_manual_entry:
                        continue  # Skip if already a manual entry
                    
                    # Create or update attendance record as manual entry
                    if existing_record:
                        # Update existing record to manual
                        existing_record.is_manual_entry = True
                        existing_record.manual_entry_reason = random.choice(manual_reasons)
                        existing_record.attendance_status = AttendanceStatus.PRESENT
                        existing_record.created_by = superadmin.id
                        existing_record.updated_at = datetime.now()
                    else:
                        # Create new manual attendance record
                        manual_record = AttendanceRecord(
                            business_id=business.id,
                            employee_id=employee.id,
                            attendance_date=update_date,
                            attendance_status=AttendanceStatus.PRESENT,
                            is_manual_entry=True,
                            manual_entry_reason=random.choice(manual_reasons),
                            created_by=superadmin.id,
                            created_at=datetime.now()
                        )
                        db.add(manual_record)
                    
                    manual_updates_created += 1
            
            # Create some attendance corrections
            corrections_created = 0
            
            for days_back in range(15):  # Last 15 days for corrections
                correction_date = today - timedelta(days=days_back)
                
                # Skip weekends
                if correction_date.weekday() in [5, 6]:
                    continue
                
                # Create 0-2 corrections per day
                if random.random() < 0.7:  # 70% chance of having corrections
                    num_corrections = random.randint(1, 2)
                    selected_employees = random.sample(employees, min(num_corrections, len(employees)))
                    
                    for employee in selected_employees:
                        # Get or create attendance record for correction
                        attendance_record = db.query(AttendanceRecord).filter(
                            AttendanceRecord.employee_id == employee.id,
                            AttendanceRecord.attendance_date == correction_date
                        ).first()
                        
                        if not attendance_record:
                            # Create attendance record first
                            attendance_record = AttendanceRecord(
                                business_id=business.id,
                                employee_id=employee.id,
                                attendance_date=correction_date,
                                attendance_status=AttendanceStatus.ABSENT,  # Original status
                                created_by=superadmin.id
                            )
                            db.add(attendance_record)
                            db.flush()  # Get the ID
                        
                        # Create attendance correction
                        correction_types = ['late_entry', 'early_exit', 'leave', 'absent', 'present']
                        correction = AttendanceCorrection(
                            attendance_record_id=attendance_record.id,
                            employee_id=employee.id,
                            correction_type=random.choice(correction_types),
                            reason=random.choice(manual_reasons),
                            status='approved',
                            requested_at=datetime.now() - timedelta(hours=random.randint(1, 24)),
                            approved_by=superadmin.id,
                            approved_at=datetime.now()
                        )
                        db.add(correction)
                        corrections_created += 1
            
            db.commit()
            logger.info(f"Sample manual updates data created successfully")
            logger.info(f"Manual attendance entries: {manual_updates_created}")
            logger.info(f"Attendance corrections: {corrections_created}")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample manual updates data: {e}")
        import traceback
        traceback.print_exc()
        return False


def fix_employee_statuses():
    """Fix employee statuses - convert TERMINATED to ACTIVE for sample data"""
    logger.info("\nStep 7.5: Fixing employee statuses...")
    
    try:
        with get_db_context() as db:
            # Get all employees with TERMINATED status
            terminated_employees = db.query(Employee).filter(
                Employee.employee_status == EmployeeStatus.TERMINATED
            ).all()
            
            if not terminated_employees:
                logger.info("No terminated employees found")
                return True
            
            logger.info(f"Found {len(terminated_employees)} terminated employees")
            
            # Convert first 10-15 terminated employees to active for sample data
            employees_to_activate = terminated_employees[:15]
            
            for employee in employees_to_activate:
                employee.employee_status = EmployeeStatus.ACTIVE
                employee.date_of_termination = None  # Clear termination date
                employee.is_active = True
                logger.info(f"Activated employee: {employee.full_name} ({employee.employee_code})")
            
            db.commit()
            
            logger.info(f"Successfully activated {len(employees_to_activate)} employees")
            return True
            
    except Exception as e:
        logger.error(f"Failed to fix employee statuses: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_sample_manager_relationships():
    """Create sample manager relationships for existing employees"""
    logger.info("\nStep 7.4: Creating sample manager relationships...")
    
    try:
        with get_db_context() as db:
            # Get all active employees
            employees = db.query(Employee).filter(
                Employee.employee_status == EmployeeStatus.ACTIVE
            ).all()
            
            if len(employees) < 5:
                logger.warning("Not enough active employees to create meaningful manager relationships")
                return True
            
            logger.info(f"Found {len(employees)} active employees")
            
            # Create a simple organizational hierarchy
            # CEO -> VPs -> Managers -> Associates
            
            # Designate first employee as CEO (no manager)
            ceo = employees[0]
            ceo.reporting_manager_id = None
            ceo.hr_manager_id = None
            ceo.indirect_manager_id = None
            logger.info(f"Set {ceo.full_name} as CEO (no managers)")
            
            # Designate next 2-3 employees as VPs reporting to CEO
            vp_count = min(3, len(employees) - 1)
            vps = employees[1:1+vp_count]
            
            for vp in vps:
                vp.reporting_manager_id = ceo.id
                vp.hr_manager_id = ceo.id  # CEO also acts as HR for VPs
                vp.indirect_manager_id = None
                logger.info(f"Set {vp.full_name} as VP reporting to CEO")
            
            # Designate next employees as Managers reporting to VPs
            remaining_employees = employees[1+vp_count:]
            if remaining_employees:
                manager_count = min(len(remaining_employees) // 2, len(vps) * 2)
                managers = remaining_employees[:manager_count]
                
                for i, manager in enumerate(managers):
                    # Assign to VPs in round-robin fashion
                    assigned_vp = vps[i % len(vps)]
                    manager.reporting_manager_id = assigned_vp.id
                    manager.hr_manager_id = ceo.id  # CEO acts as HR manager
                    manager.indirect_manager_id = ceo.id  # CEO is indirect manager
                    logger.info(f"Set {manager.full_name} as Manager reporting to {assigned_vp.full_name}")
                
                # Remaining employees report to managers
                associates = remaining_employees[manager_count:]
                for i, associate in enumerate(associates):
                    # Assign to managers in round-robin fashion
                    if managers:
                        assigned_manager = managers[i % len(managers)]
                        assigned_vp = vps[(i // len(managers)) % len(vps)]
                        
                        associate.reporting_manager_id = assigned_manager.id
                        associate.hr_manager_id = ceo.id  # CEO acts as HR manager
                        associate.indirect_manager_id = assigned_vp.id  # VP is indirect manager
                        logger.info(f"Set {associate.full_name} as Associate reporting to {assigned_manager.full_name}")
                    else:
                        # If no managers, report directly to VPs
                        assigned_vp = vps[i % len(vps)]
                        associate.reporting_manager_id = assigned_vp.id
                        associate.hr_manager_id = ceo.id
                        associate.indirect_manager_id = ceo.id
                        logger.info(f"Set {associate.full_name} as Associate reporting to {assigned_vp.full_name}")
            
            db.commit()
            
            # Log the final hierarchy
            logger.info("Manager hierarchy created:")
            logger.info(f"  - CEO: {ceo.full_name}")
            logger.info(f"  - VPs: {[vp.full_name for vp in vps]}")
            if 'managers' in locals():
                logger.info(f"  - Managers: {[m.full_name for m in managers]}")
            if 'associates' in locals():
                logger.info(f"  - Associates: {[a.full_name for a in associates]}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create sample manager relationships: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_employee_register_sample_data():
    """Create sample employee register data for testing"""
    logger.info("\nStep 7.3: Creating sample employee register data...")
    
    try:
        from app.core.config import settings as app_settings
        
        with get_db_context() as db:
            # Check if employee profiles already exist
            from app.models.employee import EmployeeProfile
            existing_profiles = db.query(EmployeeProfile).count()
            if existing_profiles > 0:
                logger.info("Employee register sample data already exists, skipping...")
                return True
            
            # Get or create default business
            business = db.query(Business).first()
            if not business:
                logger.error("Business not found")
                return False
            
            # Get superadmin user
            superadmin = db.query(User).filter(User.email == app_settings.SUPERADMIN_EMAIL).first()
            if not superadmin:
                logger.error("Superadmin not found")
                return False
            
            # Import models
            import random
            
            # Get employees that need additional profile data
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "ACTIVE"
            ).limit(10).all()
            
            if not employees:
                logger.info("No employees found for register data")
                return True
            
            # Sample data for profiles
            pan_prefixes = ["ABCDE", "FGHIJ", "KLMNO", "PQRST", "UVWXY"]
            esi_numbers = ["1234567890", "0987654321", "1122334455", "5566778899", "9988776655"]
            uan_numbers = ["123456789012", "987654321098", "112233445566", "556677889900", "998877665544"]
            aadhaar_numbers = ["123456789012", "987654321098", "112233445566", "556677889900", "998877665544"]
            
            # Sample bank data
            banks = [
                {"name": "HDFC Bank", "ifsc": "HDFC0001234", "branch": "HDFC Main Branch"},
                {"name": "ICICI Bank", "ifsc": "ICIC0001234", "branch": "ICICI Main Branch"},
                {"name": "SBI", "ifsc": "SBIN0001234", "branch": "SBI Main Branch"},
                {"name": "Axis Bank", "ifsc": "UTIB0001234", "branch": "Axis Main Branch"},
                {"name": "Kotak Bank", "ifsc": "KKBK0001234", "branch": "Kotak Main Branch"}
            ]
            
            # Sample cities and states
            cities = [
                {"city": "Hyderabad", "state": "Telangana", "country": "India", "pincode": "500001"},
                {"city": "Bangalore", "state": "Karnataka", "country": "India", "pincode": "560001"},
                {"city": "Mumbai", "state": "Maharashtra", "country": "India", "pincode": "400001"},
                {"city": "Chennai", "state": "Tamil Nadu", "country": "India", "pincode": "600001"},
                {"city": "Delhi", "state": "Delhi", "country": "India", "pincode": "110001"}
            ]
            
            # Sample other info
            blood_groups = ["A+", "B+", "AB+", "O+", "A-", "B-", "AB-", "O-"]
            marital_statuses = ["Single", "Married", "Divorced", "Widowed"]
            
            profiles_created = 0
            
            for i, employee in enumerate(employees):
                # Check if employee profile already exists
                existing_profile = db.query(EmployeeProfile).filter(
                    EmployeeProfile.employee_id == employee.id
                ).first()
                
                if not existing_profile:
                    # Create employee profile with all required data
                    bank = random.choice(banks)
                    city_data = random.choice(cities)
                    
                    employee_profile = EmployeeProfile(
                        employee_id=employee.id,
                        
                        # Present Address
                        present_address_line1=f"Flat {random.randint(101, 999)}, Building {random.randint(1, 50)}",
                        present_address_line2=f"Street {random.randint(1, 100)}, Area {random.randint(1, 20)}",
                        present_city=city_data["city"],
                        present_state=city_data["state"],
                        present_country=city_data["country"],
                        present_pincode=city_data["pincode"],
                        
                        # Permanent Address (same as present for simplicity)
                        permanent_address_line1=f"Flat {random.randint(101, 999)}, Building {random.randint(1, 50)}",
                        permanent_address_line2=f"Street {random.randint(1, 100)}, Area {random.randint(1, 20)}",
                        permanent_city=city_data["city"],
                        permanent_state=city_data["state"],
                        permanent_country=city_data["country"],
                        permanent_pincode=city_data["pincode"],
                        
                        # Statutory Information
                        pan_number=f"{random.choice(pan_prefixes)}{random.randint(1000, 9999)}F",
                        aadhaar_number=random.choice(aadhaar_numbers),
                        uan_number=random.choice(uan_numbers),
                        esi_number=random.choice(esi_numbers),
                        
                        # Bank Information
                        bank_name=bank["name"],
                        bank_account_number=f"{random.randint(100000000000, 999999999999)}",
                        bank_ifsc_code=bank["ifsc"],
                        bank_branch=bank["branch"],
                        
                        # Emergency Contact
                        emergency_contact_name=f"{employee.first_name} Family",
                        emergency_contact_relationship="Father",
                        emergency_contact_mobile=f"+91-{random.randint(7000000000, 9999999999)}",
                        emergency_contact_address=f"Emergency Address for {employee.first_name}",
                        
                        # Additional Information
                        bio=f"Experienced professional working at {business.business_name}",
                        skills=f"Technical Skills: Python, SQL, Data Analysis",
                        certifications=f"Certified in relevant technologies",
                        
                        # Wedding date for married employees (for employee events)
                        wedding_date=None,
                        
                        created_at=datetime.now()
                    )
                    
                    # Add wedding date for married employees
                    if employee.marital_status == "married":
                        # Generate a random wedding date between 1-10 years ago
                        years_ago = random.randint(1, 10)
                        wedding_year = datetime.now().year - years_ago
                        wedding_month = random.randint(1, 12)
                        wedding_day = random.randint(1, 28)  # Safe day range for all months
                        employee_profile.wedding_date = date(wedding_year, wedding_month, wedding_day)
                    
                    # Add vaccination status (70% vaccinated, 30% not vaccinated)
                    vaccination_statuses = ["Vaccinated", "Not Vaccinated"]
                    vaccination_weights = [0.7, 0.3]  # 70% vaccinated
                    employee_profile.vaccination_status = random.choices(vaccination_statuses, weights=vaccination_weights)[0]
                    
                    # Add workman status (60% installed, 40% not installed)
                    workman_installed = random.choices([True, False], weights=[0.6, 0.4])[0]
                    employee_profile.workman_installed = workman_installed
                    
                    if workman_installed:
                        # Random workman version for installed users
                        versions = ["7.5.33", "7.5.32", "7.5.31", "7.4.28", "7.4.27"]
                        employee_profile.workman_version = random.choice(versions)
                        
                        # Random last seen within last 30 days
                        days_ago = random.randint(0, 30)
                        hours_ago = random.randint(0, 23)
                        minutes_ago = random.randint(0, 59)
                        employee_profile.workman_last_seen = datetime.now() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
                    else:
                        employee_profile.workman_version = "Not Installed"
                        employee_profile.workman_last_seen = None
                    
                    db.add(employee_profile)
                    profiles_created += 1
            
            db.commit()
            logger.info(f"Sample employee register data created successfully")
            logger.info(f"Employee profiles created: {profiles_created}")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample employee register data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_separation_sample_data():
    """Create sample separation data for testing"""
    logger.info("\nStep 8: Creating sample separation data...")
    
    try:
        from app.core.config import settings as app_settings
        
        with get_db_context() as db:
            # Get or create default business
            business = db.query(Business).first()
            if not business:
                logger.error("Business not found")
                return False
            
            # Get superadmin user
            superadmin = db.query(User).filter(User.email == app_settings.SUPERADMIN_EMAIL).first()
            if not superadmin:
                logger.error("Superadmin not found")
                return False
            
            # Create exit reasons (including frontend-compatible options)
            exit_reasons_data = [
                {"name": "Better Opportunity", "esi_mapping": "Better Career Growth"},
                {"name": "Personal Reasons", "esi_mapping": "Personal Issues"},
                {"name": "Relocation", "esi_mapping": "Family Relocation"},
                {"name": "Higher Studies", "esi_mapping": "Education"},
                {"name": "Health Issues", "esi_mapping": "Medical Reasons"},
                {"name": "Termination", "esi_mapping": "Performance Issues"},
                {"name": "Retirement", "esi_mapping": "Age Retirement"},
                {"name": "End of Contract", "esi_mapping": "Contract Completion"},
                # Frontend-compatible options from Initiate.jsx dropdown
                {"name": "Resign", "esi_mapping": "Employee Resignation"},
                {"name": "Obscand", "esi_mapping": "Absconding"}
            ]
            
            from app.models.exit_reason import ExitReason
            
            for reason_data in exit_reasons_data:
                existing_reason = db.query(ExitReason).filter(
                    ExitReason.business_id == business.id,
                    ExitReason.name == reason_data["name"]
                ).first()
                
                if not existing_reason:
                    exit_reason = ExitReason(
                        business_id=business.id,
                        name=reason_data["name"],
                        esi_mapping=reason_data["esi_mapping"],
                        created_by=superadmin.id,
                        created_at=datetime.now()
                    )
                    db.add(exit_reason)
            
            # Create separation settings
            from app.models.separation import SeparationSettings
            
            existing_settings = db.query(SeparationSettings).filter(
                SeparationSettings.business_id == business.id
            ).first()
            
            if not existing_settings:
                default_clearance_items = [
                    {
                        "department": "IT",
                        "item_name": "Laptop Return",
                        "description": "Return company laptop and accessories",
                        "is_mandatory": True
                    },
                    {
                        "department": "IT",
                        "item_name": "Access Card Return",
                        "description": "Return office access card",
                        "is_mandatory": True
                    },
                    {
                        "department": "HR",
                        "item_name": "Exit Interview",
                        "description": "Complete exit interview process",
                        "is_mandatory": True
                    },
                    {
                        "department": "Finance",
                        "item_name": "Final Settlement",
                        "description": "Process final salary and dues settlement",
                        "is_mandatory": True
                    },
                    {
                        "department": "HR",
                        "item_name": "Document Handover",
                        "description": "Handover all project documents and files",
                        "is_mandatory": True
                    }
                ]
                
                settings = SeparationSettings(
                    business_id=business.id,
                    default_notice_period_days=30,
                    allow_notice_period_buyout=True,
                    require_manager_approval=True,
                    require_hr_approval=True,
                    require_admin_approval=False,
                    mandatory_exit_interview=True,
                    default_clearance_items=json.dumps(default_clearance_items),
                    auto_create_clearance=True,
                    notify_manager=True,
                    notify_hr=True,
                    notify_admin=False,
                    created_by=superadmin.id,
                    created_at=datetime.now()
                )
                db.add(settings)
            
            # Create sample separation requests
            from app.models.separation import SeparationRequest, SeparationType, SeparationStatus
            from app.models.employee import Employee
            
            # Get some employees for sample separations
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(3).all()
            
            if employees:
                sample_separations = [
                    {
                        "employee": employees[0],
                        "separation_type": SeparationType.RESIGNATION,
                        "status": SeparationStatus.PENDING_APPROVAL,
                        "request_date": date(2024, 12, 1),
                        "last_working_date": date(2024, 12, 31),
                        "reason": "Better career opportunity with higher compensation and growth prospects in a leading technology company.",
                        "initiated_by": "employee",
                        "notice_period_days": 30
                    },
                    {
                        "employee": employees[1] if len(employees) > 1 else employees[0],
                        "separation_type": SeparationType.RESIGNATION,
                        "status": SeparationStatus.IN_PROGRESS,
                        "request_date": date(2024, 11, 15),
                        "last_working_date": date(2024, 12, 15),
                        "reason": "Relocating to another city due to family commitments and personal reasons.",
                        "initiated_by": "employee",
                        "notice_period_days": 30
                    }
                ]
                
                for sep_data in sample_separations:
                    # Check if separation already exists for this employee
                    existing_sep = db.query(SeparationRequest).filter(
                        SeparationRequest.employee_id == sep_data["employee"].id
                    ).first()
                    
                    if not existing_sep:
                        separation = SeparationRequest(
                            business_id=business.id,
                            employee_id=sep_data["employee"].id,
                            separation_type=sep_data["separation_type"],
                            status=sep_data["status"],
                            request_date=sep_data["request_date"],
                            last_working_date=sep_data["last_working_date"],
                            reason=sep_data["reason"],
                            initiated_by=sep_data["initiated_by"],
                            notice_period_days=sep_data["notice_period_days"],
                            initiated_by_user=superadmin.id,
                            created_at=datetime.now()
                        )
                        db.add(separation)
                        db.commit()
                        db.refresh(separation)
                        
                        # Create sample clearance items for in-progress separation
                        if sep_data["status"] == SeparationStatus.IN_PROGRESS:
                            from app.models.separation import SeparationClearance, ClearanceStatus
                            
                            clearance_items = [
                                {
                                    "department": "IT",
                                    "item_name": "Laptop Return",
                                    "description": "Return company laptop and accessories",
                                    "status": ClearanceStatus.COMPLETED,
                                    "is_mandatory": True
                                },
                                {
                                    "department": "HR",
                                    "item_name": "Exit Interview",
                                    "description": "Complete exit interview process",
                                    "status": ClearanceStatus.PENDING,
                                    "is_mandatory": True
                                },
                                {
                                    "department": "Finance",
                                    "item_name": "Final Settlement",
                                    "description": "Process final salary and dues settlement",
                                    "status": ClearanceStatus.PENDING,
                                    "is_mandatory": True
                                }
                            ]
                            
                            for item_data in clearance_items:
                                clearance = SeparationClearance(
                                    separation_id=separation.id,
                                    department=item_data["department"],
                                    item_name=item_data["item_name"],
                                    description=item_data["description"],
                                    status=item_data["status"],
                                    is_mandatory=item_data["is_mandatory"],
                                    created_at=datetime.now()
                                )
                                
                                if item_data["status"] == ClearanceStatus.COMPLETED:
                                    clearance.cleared_by = superadmin.id
                                    clearance.cleared_at = datetime.now()
                                
                                db.add(clearance)
            
            # Create one ex-employee (terminated)
            if len(employees) > 2:
                ex_employee = employees[2]
                ex_employee.employee_status = "terminated"
                ex_employee.date_of_termination = date(2024, 10, 31)
                
                # Create completed separation for ex-employee
                completed_separation = SeparationRequest(
                    business_id=business.id,
                    employee_id=ex_employee.id,
                    separation_type=SeparationType.RESIGNATION,
                    status=SeparationStatus.COMPLETED,
                    request_date=date(2024, 10, 1),
                    last_working_date=date(2024, 10, 31),
                    actual_separation_date=date(2024, 10, 31),
                    reason="Personal reasons and family commitments requiring immediate attention.",
                    initiated_by="employee",
                    notice_period_days=30,
                    final_settlement_amount=45000.00,
                    initiated_by_user=superadmin.id,
                    approved_by=superadmin.id,
                    created_at=datetime.now() - timedelta(days=60),
                    approved_at=datetime.now() - timedelta(days=55),
                    completed_at=datetime.now() - timedelta(days=30)
                )
                db.add(completed_separation)
                db.commit()
                db.refresh(completed_separation)
                
                # Create sample separation documents for the completed separation
                from app.models.separation import SeparationDocument
                
                sample_documents = [
                    {
                        "document_type": "resignation_letter",
                        "document_name": "Resignation Letter",
                        "file_path": f"/documents/separation/{completed_separation.id}/resignation_letter.pdf",
                        "file_size": 251392,  # 245 KB
                        "mime_type": "application/pdf",
                        "description": "Employee resignation letter submitted on request date",
                        "is_mandatory": True,
                        "is_generated": False,
                        "uploaded_at": completed_separation.created_at,
                        "uploaded_by": completed_separation.initiated_by_user
                    },
                    {
                        "document_type": "clearance_certificate",
                        "document_name": "Clearance Certificate",
                        "file_path": f"/documents/separation/{completed_separation.id}/clearance_certificate.pdf",
                        "file_size": 184320,  # 180 KB
                        "mime_type": "application/pdf",
                        "description": "Department clearance certificate confirming all items returned",
                        "is_mandatory": True,
                        "is_generated": True,
                        "uploaded_at": completed_separation.approved_at,
                        "uploaded_by": completed_separation.approved_by
                    },
                    {
                        "document_type": "experience_letter",
                        "document_name": "Experience Letter",
                        "file_path": f"/documents/separation/{completed_separation.id}/experience_letter.pdf",
                        "file_size": 159744,  # 156 KB
                        "mime_type": "application/pdf",
                        "description": "Employment experience and service letter",
                        "is_mandatory": False,
                        "is_generated": True,
                        "uploaded_at": completed_separation.completed_at,
                        "uploaded_by": completed_separation.approved_by
                    },
                    {
                        "document_type": "settlement_statement",
                        "document_name": "Final Settlement Statement",
                        "file_path": f"/documents/separation/{completed_separation.id}/settlement_statement.pdf",
                        "file_size": 202752,  # 198 KB
                        "mime_type": "application/pdf",
                        "description": "Final salary and dues settlement statement",
                        "is_mandatory": True,
                        "is_generated": True,
                        "uploaded_at": completed_separation.completed_at,
                        "uploaded_by": completed_separation.approved_by
                    },
                    {
                        "document_type": "noc_letter",
                        "document_name": "No Objection Certificate",
                        "file_path": f"/documents/separation/{completed_separation.id}/noc_letter.pdf",
                        "file_size": 145408,  # 142 KB
                        "mime_type": "application/pdf",
                        "description": "No objection certificate for future employment",
                        "is_mandatory": False,
                        "is_generated": True,
                        "uploaded_at": completed_separation.completed_at,
                        "uploaded_by": completed_separation.approved_by
                    }
                ]
                
                for doc_data in sample_documents:
                    # Check if document already exists
                    existing_doc = db.query(SeparationDocument).filter(
                        SeparationDocument.separation_id == completed_separation.id,
                        SeparationDocument.document_type == doc_data["document_type"]
                    ).first()
                    
                    if not existing_doc:
                        document = SeparationDocument(
                            separation_id=completed_separation.id,
                            document_type=doc_data["document_type"],
                            document_name=doc_data["document_name"],
                            file_path=doc_data["file_path"],
                            file_size=doc_data["file_size"],
                            mime_type=doc_data["mime_type"],
                            description=doc_data["description"],
                            is_mandatory=doc_data["is_mandatory"],
                            is_generated=doc_data["is_generated"],
                            uploaded_at=doc_data["uploaded_at"],
                            uploaded_by=doc_data["uploaded_by"]
                        )
                        db.add(document)
            
            db.commit()
            logger.info("Sample separation data created successfully")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample separation data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_extra_days_sample_data():
    """Create sample extra days data for testing"""
    logger.info("\nStep 9: Creating sample extra days data...")
    
    try:
        with get_db_context() as db:
            from app.models.datacapture import ExtraDay
            from app.models.employee import Employee
            from decimal import Decimal
            
            # Check if extra days data already exists
            existing_extra_days = db.query(ExtraDay).first()
            if existing_extra_days:
                logger.info("Extra days sample data already exists, skipping...")
                return True
            
            # Get some employees to create extra days for
            employees = db.query(Employee).limit(5).all()
            if not employees:
                logger.warning("No employees found, skipping extra days sample data")
                return True
            
            # Create sample extra days records
            sample_extra_days = []
            
            for i, employee in enumerate(employees):
                # Create 2-3 extra days records per employee
                for j in range(2):
                    work_date = date.today() - timedelta(days=(i * 7 + j * 3))
                    hours_worked = Decimal(str(2.5 + (i * 0.5) + (j * 1.0)))  # 2.5 to 6.0 hours
                    hourly_rate = Decimal("500.00")
                    total_amount = hours_worked * hourly_rate
                    
                    extra_day = ExtraDay(
                        business_id=employee.business_id,
                        employee_id=employee.id,
                        work_date=work_date,
                        hours_worked=hours_worked,
                        hourly_rate=hourly_rate,
                        total_amount=total_amount,
                        work_description=f"Weekend project work - Task {j+1}",
                        location="Office",
                        is_approved=True if j == 0 else False,
                        is_paid=False,
                        created_by=1  # Superadmin
                    )
                    
                    if j == 0:  # First record is approved
                        extra_day.approved_by = 1
                        extra_day.approval_date = work_date + timedelta(days=1)
                    
                    sample_extra_days.append(extra_day)
            
            # Add all extra days records
            for extra_day in sample_extra_days:
                db.add(extra_day)
            
            db.commit()
            logger.info(f"Created {len(sample_extra_days)} sample extra days records")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample extra days data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_leave_balance_sample_data():
    """Create sample leave balance data for testing"""
    logger.info("\nStep 10: Creating sample leave balance data...")
    
    with get_db_context() as db:
        try:
            from app.models.leave_balance import LeaveBalance, LeaveCorrection
            from app.models.leave_type import LeaveType
            
            # Get business and employees
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            employees = db.query(Employee).filter(Employee.business_id == business.id).all()
            if not employees:
                logger.info("No employees found, skipping leave balance sample data")
                return True
            
            # Get or create default leave type
            leave_type = db.query(LeaveType).filter(LeaveType.business_id == business.id).first()
            if not leave_type:
                leave_type = LeaveType(
                    business_id=business.id,
                    name="Annual Leave",
                    alias="AL",
                    color="#e7f3ff",
                    paid=True,
                    track_balance=True,
                    probation="Allow",
                    allow_requests=True,
                    allow_future_requests=True,
                    advance_leaves=0,
                    past_days=30,
                    monthly_limit=0
                )
                db.add(leave_type)
                db.flush()
            
            # Create leave balances for current month and previous months
            current_date = datetime.now()
            
            for employee in employees:
                # Create balances for last 6 months including current month
                for month_offset in range(6):
                    target_date = current_date - timedelta(days=30 * month_offset)
                    target_year = target_date.year
                    target_month = target_date.month
                    
                    # Check if balance already exists
                    existing_balance = db.query(LeaveBalance).filter(
                        LeaveBalance.employee_id == employee.id,
                        LeaveBalance.leave_type_id == leave_type.id,
                        LeaveBalance.balance_year == target_year,
                        LeaveBalance.balance_month == target_month
                    ).first()
                    
                    if not existing_balance:
                        # Create realistic balance data matching frontend expectations
                        opening_balance = Decimal('24.0')  # Annual leave allocation
                        
                        # Vary activity based on month and employee
                        if month_offset == 0:  # Current month
                            activity_balance = Decimal(str(random.choice([-2.0, -1.5, -3.0, -0.5])))
                        elif month_offset < 3:  # Recent months
                            activity_balance = Decimal(str(random.choice([-1.0, -2.0, -1.5])))
                        else:  # Older months
                            activity_balance = Decimal('0.0')
                        
                        # Some employees have corrections
                        if employee.id % 3 == 0 and month_offset == 0:  # Every 3rd employee in current month
                            correction_balance = Decimal(str(random.choice([1.0, 0.5, 2.0])))
                        else:
                            correction_balance = Decimal('0.0')
                        
                        closing_balance = opening_balance + activity_balance + correction_balance
                        
                        leave_balance = LeaveBalance(
                            business_id=business.id,
                            employee_id=employee.id,
                            leave_type_id=leave_type.id,
                            opening_balance=opening_balance,
                            activity_balance=activity_balance,
                            correction_balance=correction_balance,
                            closing_balance=closing_balance,
                            balance_year=target_year,
                            balance_month=target_month,
                            balance_date=date(target_year, target_month, 1),
                            is_active=True
                        )
                        db.add(leave_balance)
            
            # Commit leave balances first
            db.commit()
            
            # Now create correction records with proper leave_balance_id
            for employee in employees:
                for month_offset in range(6):
                    target_date = current_date - timedelta(days=30 * month_offset)
                    target_year = target_date.year
                    target_month = target_date.month
                    
                    # Check if this employee should have corrections
                    if employee.id % 3 == 0 and month_offset == 0:  # Every 3rd employee in current month
                        correction_balance = Decimal(str(random.choice([1.0, 0.5, 2.0])))
                        
                        # Find the corresponding leave balance
                        leave_balance = db.query(LeaveBalance).filter(
                            LeaveBalance.employee_id == employee.id,
                            LeaveBalance.leave_type_id == leave_type.id,
                            LeaveBalance.balance_year == target_year,
                            LeaveBalance.balance_month == target_month
                        ).first()
                        
                        if leave_balance:
                            opening_balance = Decimal('24.0')
                            activity_balance = Decimal(str(random.choice([-2.0, -1.5, -3.0, -0.5])))
                            
                            correction_record = LeaveCorrection(
                                business_id=business.id,
                                employee_id=employee.id,
                                leave_balance_id=leave_balance.id,  # Now we have the proper ID
                                correction_amount=correction_balance,
                                previous_balance=opening_balance + activity_balance,
                                new_balance=opening_balance + activity_balance + correction_balance,
                                correction_reason=f"Manual leave balance adjustment for {employee.first_name}",
                                correction_year=target_year,
                                correction_month=target_month,
                                correction_date=date(target_year, target_month, 15),
                                created_by=1  # Superadmin
                            )
                            db.add(correction_record)
            
            # Commit correction records
            db.commit()
            logger.info(f"[OK] Created leave balance data for {len(employees)} employees with realistic balances")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create leave balance sample data: {e}")
            return False


def create_comprehensive_request_sample_data():
    """Create comprehensive sample data for all request types"""
    logger.info("\nStep 11: Creating comprehensive request sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.requests import (
                Request, RequestStatus, RequestType, LeaveRequest, MissedPunchRequest,
                ClaimRequest, CompoffRequest, TimeRelaxationRequest, VisitPunchRequest,
                WorkflowRequest, HelpdeskRequest, StrikeExemptionRequest, ShiftRosterRequest
            )
            from decimal import Decimal
            import random
            from datetime import datetime
            
            # Check if sample data already exists
            existing_requests = db.query(Request).count()
            
            if existing_requests > 0:
                logger.info("Request sample data already exists, skipping...")
                return True
            
            # Get businesses and employees
            businesses = db.query(Business).all()
            if not businesses:
                logger.warning("No businesses found, skipping request sample data")
                return True
            
            business = businesses[0]
            
            # Get active employees
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(10).all()
            
            if not employees:
                logger.warning("No active employees found, skipping request sample data")
                return True
            
            # Common data
            statuses = [RequestStatus.PENDING, RequestStatus.IN_REVIEW, RequestStatus.APPROVED, RequestStatus.REJECTED]
            priorities = ["low", "medium", "high", "urgent"]
            
            request_counter = 1
            
            # 1. LEAVE REQUESTS - Enhanced for Frontend Compatibility
            leave_types = ["Casual Leave", "Sick Leave", "Annual Leave", "Maternity Leave", "Paternity Leave", "Emergency Leave"]
            leave_reasons = [
                "I am in hometown for personal reason.",
                "I would like to request casual leave tomorrow.kindly approve my leave",
                "Paid Leave",
                "Family vacation and personal time",
                "Medical appointment and recovery",
                "Personal emergency situation"
            ]
            
            # Create more comprehensive leave requests to match frontend data
            leave_request_data = [
                {
                    "employee_idx": 0,
                    "leave_type": "Casual Leave",
                    "reason": "I am in hometown for personal reason.",
                    "from_date": date(2025, 10, 8),
                    "to_date": date(2025, 10, 8),
                    "total_days": 1,
                    "status": RequestStatus.PENDING,
                    "request_date": date(2025, 10, 7)
                },
                {
                    "employee_idx": 1,
                    "leave_type": "Casual Leave", 
                    "reason": "I would like to request casual leave tomorrow.kindly approve my leave",
                    "from_date": date(2025, 10, 7),
                    "to_date": date(2025, 10, 7),
                    "total_days": 1,
                    "status": RequestStatus.PENDING,
                    "request_date": date(2025, 10, 6)
                },
                {
                    "employee_idx": 2,
                    "leave_type": "Casual Leave",
                    "reason": "Paid Leave",
                    "from_date": date(2025, 10, 1),
                    "to_date": date(2025, 10, 1),
                    "total_days": 1,
                    "status": RequestStatus.PENDING,
                    "request_date": date(2025, 9, 30)
                },
                {
                    "employee_idx": 0,
                    "leave_type": "Annual Leave",
                    "reason": "Family vacation and personal time",
                    "from_date": date(2025, 11, 15),
                    "to_date": date(2025, 11, 17),
                    "total_days": 3,
                    "status": RequestStatus.APPROVED,
                    "request_date": date(2025, 10, 15)
                },
                {
                    "employee_idx": 1,
                    "leave_type": "Sick Leave",
                    "reason": "Medical appointment and recovery",
                    "from_date": date(2025, 10, 20),
                    "to_date": date(2025, 10, 21),
                    "total_days": 2,
                    "status": RequestStatus.IN_REVIEW,
                    "request_date": date(2025, 10, 18)
                },
                {
                    "employee_idx": 2,
                    "leave_type": "Emergency Leave",
                    "reason": "Personal emergency situation",
                    "from_date": date(2025, 10, 25),
                    "to_date": date(2025, 10, 25),
                    "total_days": 1,
                    "status": RequestStatus.REJECTED,
                    "request_date": date(2025, 10, 24)
                }
            ]
            
            for i, leave_data in enumerate(leave_request_data):
                employee = employees[leave_data["employee_idx"] % len(employees)]
                
                # Create base request
                base_request = Request(
                    business_id=business.id,
                    employee_id=employee.id,
                    request_type=RequestType.LEAVE,
                    title=f"{leave_data['leave_type']} Request",
                    description=leave_data["reason"],
                    status=leave_data["status"],
                    request_date=leave_data["request_date"],
                    from_date=leave_data["from_date"],
                    to_date=leave_data["to_date"],
                    priority=priorities[i % len(priorities)],
                    created_by=employee.id
                )
                
                # Set approval details for approved/rejected requests
                if base_request.status == RequestStatus.APPROVED:
                    base_request.approved_date = datetime.now() - timedelta(days=i)
                    base_request.approved_by = employees[0].id
                    base_request.approval_comments = "Leave approved by manager"
                elif base_request.status == RequestStatus.REJECTED:
                    base_request.approved_date = datetime.now() - timedelta(days=i)
                    base_request.approved_by = employees[0].id
                    base_request.approval_comments = "Leave rejected due to project deadlines"
                
                db.add(base_request)
                db.flush()
                
                # Create leave details
                leave_details = LeaveRequest(
                    request_id=base_request.id,
                    leave_type=leave_data["leave_type"],
                    total_days=leave_data["total_days"],
                    half_day=False,
                    reason=leave_data["reason"],
                    emergency_contact="Emergency Contact Person",
                    emergency_phone="+91-9876543210"
                )
                
                db.add(leave_details)
                request_counter += 1
            
            # 2. MISSED PUNCH REQUESTS
            punch_types = ["in", "out", "break_in", "break_out"]
            punch_reasons = [
                "Forgot to punch in due to urgent meeting",
                "System was down during punch out time",
                "Biometric device not working properly",
                "Emergency call during break time"
            ]
            
            for i in range(4):
                employee = employees[(i+1) % len(employees)]
                request_date = date.today() - timedelta(days=i+2)
                missed_date = request_date - timedelta(days=1)
                
                base_request = Request(
                    business_id=business.id,
                    employee_id=employee.id,
                    request_type=RequestType.MISSED_PUNCH,
                    title=f"Missed {punch_types[i].title()} Punch",
                    description=punch_reasons[i],
                    status=statuses[i % len(statuses)],
                    request_date=request_date,
                    from_date=missed_date,
                    priority="medium",
                    created_by=employee.id
                )
                
                db.add(base_request)
                db.flush()
                
                punch_details = MissedPunchRequest(
                    request_id=base_request.id,
                    missed_date=missed_date,
                    punch_type=punch_types[i],
                    expected_time="09:30" if punch_types[i] == "in" else "18:30",
                    reason=punch_reasons[i]
                )
                
                db.add(punch_details)
                request_counter += 1
            
            # 3. CLAIM REQUESTS
            claim_types = ["Travel", "Medical", "Food", "Accommodation", "Communication"]
            claim_amounts = [2500.00, 1200.00, 800.00, 3500.00, 450.00]
            vendors = ["Uber Technologies", "Apollo Hospital", "Hotel Taj", "Airtel", "Local Vendor"]
            
            for i in range(5):
                employee = employees[(i+2) % len(employees)]
                request_date = date.today() - timedelta(days=i+3)
                expense_date = request_date - timedelta(days=2)
                
                base_request = Request(
                    business_id=business.id,
                    employee_id=employee.id,
                    request_type=RequestType.CLAIM,
                    title=f"{claim_types[i]} Reimbursement",
                    description=f"Expense claim for {claim_types[i].lower()} - Amount: ₹{claim_amounts[i]}",
                    status=statuses[i % len(statuses)],
                    request_date=request_date,
                    from_date=expense_date,
                    amount=Decimal(str(claim_amounts[i])),
                    priority="medium",
                    created_by=employee.id
                )
                
                db.add(base_request)
                db.flush()
                
                claim_details = ClaimRequest(
                    request_id=base_request.id,
                    claim_type=claim_types[i],
                    claim_amount=Decimal(str(claim_amounts[i])),
                    expense_date=expense_date,
                    vendor_name=vendors[i],
                    bill_number=f"BILL{1000+i}",
                    project_code=f"PRJ{100+i}",
                    client_name=f"Client {i+1}"
                )
                
                db.add(claim_details)
                request_counter += 1
            
            # 4. COMP-OFF REQUESTS - Enhanced for Frontend Compatibility
            compoff_data = [
                {
                    "employee_idx": 0,
                    "request_date": date(2025, 10, 28),
                    "worked_date": date(2025, 10, 26),
                    "compoff_date": date(2025, 11, 5),
                    "worked_hours": Decimal("10.5"),
                    "reason_for_work": "Testing",
                    "status": RequestStatus.PENDING
                },
                {
                    "employee_idx": 1,
                    "request_date": date(2025, 10, 25),
                    "worked_date": date(2025, 10, 23),
                    "compoff_date": date(2025, 11, 2),
                    "worked_hours": Decimal("12.0"),
                    "reason_for_work": "Forgot to punch due to meeting",
                    "status": RequestStatus.IN_REVIEW
                },
                {
                    "employee_idx": 2,
                    "request_date": date(2025, 10, 22),
                    "worked_date": date(2025, 10, 20),
                    "compoff_date": date(2025, 10, 30),
                    "worked_hours": Decimal("9.5"),
                    "reason_for_work": "Critical project delivery deadline",
                    "status": RequestStatus.APPROVED
                },
                {
                    "employee_idx": 0,
                    "request_date": date(2025, 10, 20),
                    "worked_date": date(2025, 10, 18),
                    "compoff_date": date(2025, 10, 28),
                    "worked_hours": Decimal("11.0"),
                    "reason_for_work": "Weekend project work for client delivery",
                    "status": RequestStatus.REJECTED
                }
            ]
            
            for i, compoff_item in enumerate(compoff_data):
                employee = employees[compoff_item["employee_idx"] % len(employees)]
                
                base_request = Request(
                    business_id=business.id,
                    employee_id=employee.id,
                    request_type=RequestType.COMPOFF,
                    title=f"Comp-off for {compoff_item['worked_date'].strftime('%Y-%m-%d')}",
                    description=compoff_item["reason_for_work"],
                    status=compoff_item["status"],
                    request_date=compoff_item["request_date"],
                    from_date=compoff_item["compoff_date"],
                    priority="medium",
                    created_by=employee.id
                )
                
                # Set approval details for approved/rejected requests
                if base_request.status == RequestStatus.APPROVED:
                    base_request.approved_date = datetime.now() - timedelta(days=i)
                    base_request.approved_by = employees[0].id
                    base_request.approval_comments = "Comp-off approved by manager"
                elif base_request.status == RequestStatus.REJECTED:
                    base_request.approved_date = datetime.now() - timedelta(days=i)
                    base_request.approved_by = employees[0].id
                    base_request.approval_comments = "Comp-off rejected due to operational requirements"
                
                db.add(base_request)
                db.flush()
                
                compoff_details = CompoffRequest(
                    request_id=base_request.id,
                    worked_date=compoff_item["worked_date"],
                    worked_hours=compoff_item["worked_hours"],
                    compoff_date=compoff_item["compoff_date"],
                    reason_for_work=compoff_item["reason_for_work"]
                )
                
                db.add(compoff_details)
                request_counter += 1
            
            # 5. TIME RELAXATION REQUESTS - Enhanced for Frontend Compatibility
            time_relaxation_data = [
                {
                    "employee_idx": 0,
                    "request_date": date(2025, 10, 28),
                    "relaxation_date": date(2025, 10, 28),
                    "requested_in_time": "22:45",
                    "requested_out_time": "22:51",
                    "reason": "Testing",
                    "status": RequestStatus.PENDING
                },
                {
                    "employee_idx": 1,
                    "request_date": date(2025, 10, 25),
                    "relaxation_date": date(2025, 10, 25),
                    "requested_in_time": "18:20",
                    "requested_out_time": "18:35",
                    "reason": "Forgot to punch due to meeting",
                    "status": RequestStatus.IN_REVIEW
                },
                {
                    "employee_idx": 2,
                    "request_date": date(2025, 10, 22),
                    "relaxation_date": date(2025, 10, 22),
                    "requested_in_time": "09:15",
                    "requested_out_time": "18:45",
                    "reason": "Medical appointment in the morning",
                    "status": RequestStatus.APPROVED
                },
                {
                    "employee_idx": 0,
                    "request_date": date(2025, 10, 20),
                    "relaxation_date": date(2025, 10, 20),
                    "requested_in_time": "10:00",
                    "requested_out_time": "19:00",
                    "reason": "Personal emergency situation",
                    "status": RequestStatus.REJECTED
                }
            ]
            
            for i, time_data in enumerate(time_relaxation_data):
                employee = employees[time_data["employee_idx"] % len(employees)]
                
                base_request = Request(
                    business_id=business.id,
                    employee_id=employee.id,
                    request_type=RequestType.TIME_RELAXATION,
                    title=f"Time Relaxation for {time_data['relaxation_date'].strftime('%Y-%m-%d')}",
                    description=time_data["reason"],
                    status=time_data["status"],
                    request_date=time_data["request_date"],
                    from_date=time_data["relaxation_date"],
                    priority="medium",
                    created_by=employee.id
                )
                
                # Set approval details for approved/rejected requests
                if base_request.status == RequestStatus.APPROVED:
                    base_request.approved_date = datetime.now() - timedelta(days=i)
                    base_request.approved_by = employees[0].id
                    base_request.approval_comments = "Time relaxation approved by manager"
                elif base_request.status == RequestStatus.REJECTED:
                    base_request.approved_date = datetime.now() - timedelta(days=i)
                    base_request.approved_by = employees[0].id
                    base_request.approval_comments = "Time relaxation rejected due to operational requirements"
                
                db.add(base_request)
                db.flush()
                
                time_details = TimeRelaxationRequest(
                    request_id=base_request.id,
                    relaxation_date=time_data["relaxation_date"],
                    requested_in_time=time_data["requested_in_time"],
                    requested_out_time=time_data["requested_out_time"],
                    reason=time_data["reason"]
                )
                
                db.add(time_details)
                request_counter += 1
            
            # 6. VISIT PUNCH REQUESTS
            clients = ["TechCorp Solutions", "Global Industries", "Innovation Labs"]
            addresses = [
                "Tech Park, Hitech City, Hyderabad",
                "Business District, Bangalore",
                "IT Corridor, Chennai"
            ]
            
            for i in range(3):
                employee = employees[(i+5) % len(employees)]
                request_date = date.today() - timedelta(days=i+6)
                visit_date = request_date + timedelta(days=2)
                
                base_request = Request(
                    business_id=business.id,
                    employee_id=employee.id,
                    request_type=RequestType.VISIT_PUNCH,
                    title=f"Client Visit - {clients[i]}",
                    description=f"Business meeting and project discussion at {clients[i]}",
                    status=statuses[i % len(statuses)],
                    request_date=request_date,
                    from_date=visit_date,
                    priority="medium",
                    created_by=employee.id
                )
                
                db.add(base_request)
                db.flush()
                
                visit_details = VisitPunchRequest(
                    request_id=base_request.id,
                    visit_date=visit_date,
                    client_name=clients[i],
                    client_address=addresses[i],
                    purpose="Project requirement discussion and demo",
                    expected_duration="4 hours"
                )
                
                db.add(visit_details)
                request_counter += 1
            
            # 7. HELPDESK REQUESTS
            categories = ["IT Support", "HR Support", "Admin Support", "Facilities"]
            issue_types = ["Hardware Issue", "Software Problem", "Access Request", "Maintenance"]
            urgencies = ["low", "medium", "high", "critical"]
            
            for i in range(4):
                employee = employees[(i+6) % len(employees)]
                request_date = date.today() - timedelta(days=i+7)
                
                base_request = Request(
                    business_id=business.id,
                    employee_id=employee.id,
                    request_type=RequestType.HELPDESK,
                    title=f"{categories[i]} - {issue_types[i]}",
                    description=f"Need assistance with {issue_types[i].lower()} in {categories[i].lower()}",
                    status=statuses[i % len(statuses)],
                    request_date=request_date,
                    priority=urgencies[i],
                    created_by=employee.id
                )
                
                db.add(base_request)
                db.flush()
                
                helpdesk_details = HelpdeskRequest(
                    request_id=base_request.id,
                    category=categories[i],
                    subcategory=f"{categories[i]} - Level 1",
                    issue_type=issue_types[i],
                    urgency=urgencies[i],
                    asset_tag=f"AST{1000+i}" if i < 2 else None,
                    location="Office Floor 3"
                )
                
                db.add(helpdesk_details)
                request_counter += 1
            
            # 8. SHIFT ROSTER REQUESTS
            shift_types = ["General", "Regular", "Night", "Morning", "Evening"]
            locations = ["Hyderabad", "Bangalore", "Chennai", "Mumbai", "Delhi"]
            
            for i in range(5):
                employee = employees[(i+7) % len(employees)]
                request_date = date.today() - timedelta(days=i+8)
                
                base_request = Request(
                    business_id=business.id,
                    employee_id=employee.id,
                    request_type=RequestType.SHIFT_ROSTER,
                    title=f"Shift Change to {shift_types[i]}",
                    description=f"Requesting shift change to {shift_types[i]} due to personal reasons",
                    status=statuses[i % len(statuses)],
                    request_date=request_date,
                    priority="medium",
                    created_by=employee.id
                )
                
                db.add(base_request)
                db.flush()
                
                shift_request = ShiftRosterRequest(
                    request_id=base_request.id,
                    requested_date=request_date + timedelta(days=7),
                    current_shift_type="Regular",
                    requested_shift_type=shift_types[i],
                    shift_start_time="09:00",
                    shift_end_time="18:00",
                    reason=f"Need {shift_types[i].lower()} shift for personal commitments",
                    location=locations[i % len(locations)],
                    is_permanent=False,
                    effective_from=request_date + timedelta(days=7),
                    effective_to=request_date + timedelta(days=14),
                    manager_approval=False,
                    hr_approval=False
                )
                
                db.add(shift_request)
                request_counter += 1
            
            # 9. STRIKE EXEMPTION REQUESTS - Enhanced for Frontend Compatibility
            strike_types = ["Late Coming", "Early Going", "Late Going", "Absent", "Half Day"]
            strike_reasons = [
                "Traffic jam caused delay in arrival",
                "Personal emergency required early departure", 
                "Medical appointment caused late departure",
                "Family emergency - unable to attend",
                "Doctor appointment in morning"
            ]
            work_justifications = [
                "Completed all assigned tasks before leaving",
                "Worked extra hours previous day to compensate",
                "Coordinated with team to cover responsibilities",
                "Finished critical project deliverables",
                "Made up time by working through lunch break"
            ]
            
            # Define base date for strike exemption requests
            base_date = date.today()
            
            for i in range(5):
                employee = employees[i % len(employees)]
                request_date = base_date - timedelta(days=random.randint(1, 30))
                strike_date = request_date + timedelta(days=random.randint(0, 7))
                
                base_request = Request(
                    business_id=business.id,
                    employee_id=employee.id,
                    request_type=RequestType.STRIKE_EXEMPTION,
                    title=f"Strike Exemption Request - {strike_types[i]}",
                    description=f"Requesting exemption for {strike_types[i].lower()} due to {strike_reasons[i].lower()}",
                    request_date=request_date,
                    from_date=strike_date,
                    status=RequestStatus.PENDING,
                    priority=priorities[i % len(priorities)],
                    created_by=employee.id,
                    created_at=datetime.combine(request_date, datetime.min.time()),
                    updated_at=datetime.combine(request_date, datetime.min.time())
                )
                
                db.add(base_request)
                db.flush()
                
                strike_request = StrikeExemptionRequest(
                    request_id=base_request.id,
                    strike_date=strike_date,
                    exemption_reason=strike_types[i],
                    work_justification=work_justifications[i],
                    department_approval=False
                )
                
                db.add(strike_request)
                request_counter += 1
            
            # 10. WORKFLOW REQUESTS - Enhanced for Frontend Compatibility
            workflow_names = ["Leave Approval", "Expense Approval", "Document Review", "Project Approval", "Policy Review"]
            workflow_descriptions = [
                "Multi-step leave approval workflow",
                "Expense claim approval process",
                "Document review and approval",
                "Project proposal approval",
                "Policy document review"
            ]
            workflow_locations = ["Head Office", "Branch Office", "Regional Office", "Corporate Office", "Remote Office"]
            
            for i in range(5):
                employee = employees[i % len(employees)]
                request_date = date.today() - timedelta(days=i+12)
                
                base_request = Request(
                    business_id=business.id,
                    employee_id=employee.id,
                    request_type=RequestType.WORKFLOW,
                    title=f"Workflow Request - {workflow_names[i]}",
                    description=workflow_descriptions[i],
                    status=RequestStatus.PENDING if i < 3 else RequestStatus.APPROVED if i == 3 else RequestStatus.IN_REVIEW,
                    priority="medium",
                    request_date=request_date,
                    created_by=employee.id,
                    created_at=datetime.combine(request_date, datetime.min.time()),
                    updated_at=datetime.combine(request_date, datetime.min.time())
                )
                
                db.add(base_request)
                db.flush()
                
                workflow_details = WorkflowRequest(
                    request_id=base_request.id,
                    workflow_name=workflow_names[i],
                    current_step=1 if i < 3 else 3 if i == 3 else 2,
                    total_steps=3,
                    workflow_data=f'{{"location": "{workflow_locations[i]}", "department": "General", "priority": "medium"}}'
                )
                
                db.add(workflow_details)
                request_counter += 1
            
            db.commit()
            logger.info(f"[OK] Created comprehensive request sample data: {request_counter-1} requests across all types")
            return True
            
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create comprehensive request sample data: {e}")
        return False


def create_roster_sample_data():
    """Create sample roster request data (Week Roster and Shift Roster)"""
    logger.info("\nCreating roster sample data (Week Roster & Shift Roster)...")
    
    try:
        with get_db_context() as db:
            from app.models.requests import Request, RequestStatus, RequestType, ShiftRosterRequest
            from datetime import datetime, date, timedelta
            
            # Check if roster data already exists
            existing_rosters = db.query(Request).filter(
                Request.request_type == RequestType.SHIFT_ROSTER
            ).count()
            
            if existing_rosters > 0:
                logger.info(f"Roster sample data already exists ({existing_rosters} found), skipping...")
                return True
            
            # Get business and employees
            business = db.query(Business).first()
            if not business:
                logger.warning("No business found, skipping roster sample data")
                return True
            
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(10).all()
            
            if not employees:
                logger.warning("No active employees found, skipping roster sample data")
                return True
            
            # Get locations for roster requests
            locations = db.query(Location).filter(Location.business_id == business.id).all()
            if not locations:
                logger.warning("No locations found, skipping roster sample data")
                return True
            
            logger.info(f"Creating roster requests for {len(employees)} employees...")
            
            # WEEK ROSTER REQUESTS (4 total: 2 pending, 1 approved, 1 rejected)
            week_roster_data = [
                {
                    "employee_idx": 0,
                    "week_start": date.today() + timedelta(days=7),
                    "week_end": date.today() + timedelta(days=13),
                    "roster_type": "Regular Week",
                    "status": RequestStatus.PENDING,
                    "reason": "Requesting regular week roster for next week"
                },
                {
                    "employee_idx": 1,
                    "week_start": date.today() + timedelta(days=14),
                    "week_end": date.today() + timedelta(days=20),
                    "roster_type": "Flexible Week",
                    "status": RequestStatus.PENDING,
                    "reason": "Need flexible roster due to project requirements"
                },
                {
                    "employee_idx": 2,
                    "week_start": date.today() - timedelta(days=7),
                    "week_end": date.today() - timedelta(days=1),
                    "roster_type": "Regular Week",
                    "status": RequestStatus.APPROVED,
                    "reason": "Week roster for last week - approved"
                },
                {
                    "employee_idx": 3,
                    "week_start": date.today() + timedelta(days=21),
                    "week_end": date.today() + timedelta(days=27),
                    "roster_type": "Special Week",
                    "status": RequestStatus.REJECTED,
                    "reason": "Special roster request - rejected due to staffing"
                }
            ]
            
            for i, roster_data in enumerate(week_roster_data):
                employee = employees[roster_data["employee_idx"] % len(employees)]
                location = locations[i % len(locations)]
                
                # Create base request
                base_request = Request(
                    business_id=business.id,
                    employee_id=employee.id,
                    request_type=RequestType.SHIFT_ROSTER,  # Week roster uses SHIFT_ROSTER type
                    title=f"Week Roster Request - {roster_data['roster_type']}",
                    description=roster_data["reason"],
                    status=roster_data["status"],
                    request_date=date.today() - timedelta(days=i),
                    from_date=roster_data["week_start"],
                    to_date=roster_data["week_end"],
                    priority="medium",
                    created_by=employee.id,
                    location_id=location.id
                )
                
                # Set approval details for approved/rejected requests
                if base_request.status == RequestStatus.APPROVED:
                    base_request.approved_date = datetime.now() - timedelta(days=i)
                    base_request.approved_by = employees[0].id
                    base_request.approval_comments = "Week roster approved by manager"
                elif base_request.status == RequestStatus.REJECTED:
                    base_request.approved_date = datetime.now() - timedelta(days=i)
                    base_request.approved_by = employees[0].id
                    base_request.approval_comments = "Week roster rejected - insufficient staffing"
                
                db.add(base_request)
                db.flush()
                
                # Create week roster details
                roster_details = ShiftRosterRequest(
                    request_id=base_request.id,
                    week_start_date=roster_data["week_start"],
                    week_end_date=roster_data["week_end"],
                    roster_type=roster_data["roster_type"],
                    reason=roster_data["reason"]
                )
                
                db.add(roster_details)
            
            logger.info("[OK] Created 4 Week Roster requests (2 pending, 1 approved, 1 rejected)")
            
            # SHIFT ROSTER REQUESTS (5 total: 3 pending, 1 approved, 1 rejected)
            shift_roster_data = [
                {
                    "employee_idx": 4,
                    "week_start": date.today() + timedelta(days=7),
                    "week_end": date.today() + timedelta(days=13),
                    "roster_type": "Day Shift",
                    "status": RequestStatus.PENDING,
                    "reason": "Requesting day shift for next week"
                },
                {
                    "employee_idx": 5,
                    "week_start": date.today() + timedelta(days=14),
                    "week_end": date.today() + timedelta(days=20),
                    "roster_type": "Night Shift",
                    "status": RequestStatus.PENDING,
                    "reason": "Need night shift assignment for project work"
                },
                {
                    "employee_idx": 6,
                    "week_start": date.today() + timedelta(days=21),
                    "week_end": date.today() + timedelta(days=27),
                    "roster_type": "Flexible Shift",
                    "status": RequestStatus.PENDING,
                    "reason": "Flexible shift needed for client meetings"
                },
                {
                    "employee_idx": 7,
                    "week_start": date.today() - timedelta(days=7),
                    "week_end": date.today() - timedelta(days=1),
                    "roster_type": "Day Shift",
                    "status": RequestStatus.APPROVED,
                    "reason": "Day shift roster - approved"
                },
                {
                    "employee_idx": 8,
                    "week_start": date.today() + timedelta(days=28),
                    "week_end": date.today() + timedelta(days=34),
                    "roster_type": "Evening Shift",
                    "status": RequestStatus.REJECTED,
                    "reason": "Evening shift request - rejected due to coverage"
                }
            ]
            
            for i, roster_data in enumerate(shift_roster_data):
                employee = employees[roster_data["employee_idx"] % len(employees)]
                location = locations[i % len(locations)]
                
                # Create base request
                base_request = Request(
                    business_id=business.id,
                    employee_id=employee.id,
                    request_type=RequestType.SHIFT_ROSTER,
                    title=f"Shift Roster Request - {roster_data['roster_type']}",
                    description=roster_data["reason"],
                    status=roster_data["status"],
                    request_date=date.today() - timedelta(days=i),
                    from_date=roster_data["week_start"],
                    to_date=roster_data["week_end"],
                    priority="medium",
                    created_by=employee.id,
                    location_id=location.id
                )
                
                # Set approval details for approved/rejected requests
                if base_request.status == RequestStatus.APPROVED:
                    base_request.approved_date = datetime.now() - timedelta(days=i)
                    base_request.approved_by = employees[0].id
                    base_request.approval_comments = "Shift roster approved by manager"
                elif base_request.status == RequestStatus.REJECTED:
                    base_request.approved_date = datetime.now() - timedelta(days=i)
                    base_request.approved_by = employees[0].id
                    base_request.approval_comments = "Shift roster rejected - coverage issues"
                
                db.add(base_request)
                db.flush()
                
                # Create shift roster details
                roster_details = ShiftRosterRequest(
                    request_id=base_request.id,
                    week_start_date=roster_data["week_start"],
                    week_end_date=roster_data["week_end"],
                    roster_type=roster_data["roster_type"],
                    reason=roster_data["reason"]
                )
                
                db.add(roster_details)
            
            logger.info("[OK] Created 5 Shift Roster requests (3 pending, 1 approved, 1 rejected)")
            
            db.commit()
            logger.info("[OK] Roster sample data created successfully (9 total requests)")
            return True
            
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create roster sample data: {e}")
        return False


def create_salary_units_sample_data():
    """Create sample salary units data for testing"""
    logger.info("\nStep 11: Creating sample salary units data...")
    
    try:
        with get_db_context() as db:
            from app.models.datacapture import SalaryUnit, EmployeeSalaryUnit
            from app.models.employee import Employee
            from decimal import Decimal
            from datetime import date
            
            # Check if salary units data already exists
            existing_units = db.query(EmployeeSalaryUnit).first()
            if existing_units:
                logger.info("Employee salary units sample data already exists, skipping...")
                return True
            
            # Get business and employees
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(20).all()
            
            if not employees:
                logger.warning("No employees found, skipping salary units sample data")
                return True
            
            # Create sample salary unit configurations (master data)
            unit_configs = [
                {
                    "unit_name": "Travel Allowance",
                    "unit_code": "TRAVEL_ALLOW",
                    "unit_type": "monthly",
                    "base_rate": Decimal("2000.00"),
                    "description": "Monthly travel allowance for employees"
                },
                {
                    "unit_name": "Food Allowance",
                    "unit_code": "FOOD_ALLOW",
                    "unit_type": "monthly",
                    "base_rate": Decimal("1500.00"),
                    "description": "Monthly food allowance for employees"
                },
                {
                    "unit_name": "Mobile Allowance",
                    "unit_code": "MOBILE_ALLOW",
                    "unit_type": "monthly",
                    "base_rate": Decimal("800.00"),
                    "description": "Monthly mobile allowance for employees"
                },
                {
                    "unit_name": "Conveyance",
                    "unit_code": "CONVEYANCE",
                    "unit_type": "monthly",
                    "base_rate": Decimal("1200.00"),
                    "description": "Monthly conveyance allowance"
                },
                {
                    "unit_name": "Performance Bonus",
                    "unit_code": "PERF_BONUS",
                    "unit_type": "variable",
                    "base_rate": Decimal("5000.00"),
                    "description": "Performance-based bonus component"
                }
            ]
            
            # Create salary unit configurations (master data)
            created_units = []
            for config in unit_configs:
                # Check if unit already exists
                existing_unit = db.query(SalaryUnit).filter(
                    SalaryUnit.unit_code == config["unit_code"],
                    SalaryUnit.business_id == business.id
                ).first()
                
                if not existing_unit:
                    salary_unit = SalaryUnit(
                        business_id=business.id,
                        unit_name=config["unit_name"],
                        unit_code=config["unit_code"],
                        unit_type=config["unit_type"],
                        base_rate=config["base_rate"],
                        description=config["description"],
                        is_overtime_applicable=False,
                        overtime_multiplier=Decimal("1.5"),
                        is_active=True,
                        created_by=1  # Superadmin
                    )
                    db.add(salary_unit)
                    created_units.append(salary_unit)
                else:
                    created_units.append(existing_unit)
            
            # Commit to get IDs
            db.commit()
            
            # Create employee-specific salary units for current month (January 2026)
            import random
            current_date = date(2026, 1, 1)
            
            employee_units_created = 0
            
            for i, employee in enumerate(employees):
                # Assign 2-4 random salary units to each employee with varying amounts
                num_units = random.randint(2, 4)
                selected_units = random.sample(created_units, min(num_units, len(created_units)))
                
                for unit in selected_units:
                    # Create employee-specific unit with variation in amount
                    variation = random.uniform(0.8, 1.2)  # 80% to 120% of base rate
                    employee_amount = unit.base_rate * Decimal(str(variation))
                    
                    # Create EmployeeSalaryUnit record
                    employee_salary_unit = EmployeeSalaryUnit(
                        business_id=business.id,
                        employee_id=employee.id,
                        unit_name=unit.unit_name,
                        unit_type=unit.unit_type,
                        amount=employee_amount,
                        effective_date=current_date,
                        comments=f"Sample {unit.unit_name.lower()} for {employee.full_name}",
                        is_arrear=random.choice([True, False]) if i % 5 == 0 else False,  # 20% chance of arrear
                        is_active=True,
                        created_by=1  # Superadmin
                    )
                    db.add(employee_salary_unit)
                    employee_units_created += 1
            
            db.commit()
            
            logger.info(f"[OK] Created {len(created_units)} salary unit configurations")
            logger.info(f"[OK] Created {employee_units_created} employee salary unit records")
            logger.info(f"  - For {len(employees)} employees")
            logger.info(f"  - Effective date: {current_date}")
            
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample salary units data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_salary_details_sample_data():
    """Create sample salary details data for testing"""
    logger.info("\nStep 11.1: Creating sample salary details data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee, EmployeeSalary
            from app.models.datacapture import SalaryVariable, SalaryVariableType
            from decimal import Decimal
            import random
            
            # Check if salary details data already exists
            existing_salary = db.query(EmployeeSalary).first()
            if existing_salary:
                logger.info("Salary details sample data already exists, skipping...")
                return True
            
            # Get business and employees
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            employees = db.query(Employee).filter(
                Employee.business_id == business.id
            ).all()  # Get all employees regardless of status for salary data
            
            if not employees:
                logger.warning("No employees found, skipping salary details sample data")
                return True
            
            # Sample salary data matching frontend expectations
            salary_data = [
                {
                    "basic_salary": Decimal("8700.00"),
                    "hra": Decimal("2200.00"),
                    "special_allowance": Decimal("3500.00"),
                    "medical_allowance": Decimal("700.00"),
                    "conveyance_allowance": Decimal("700.00"),
                    "transport_allowance": Decimal("0.00")
                },
                {
                    "basic_salary": Decimal("12000.00"),
                    "hra": Decimal("3600.00"),
                    "special_allowance": Decimal("5060.00"),
                    "medical_allowance": Decimal("1000.00"),
                    "conveyance_allowance": Decimal("1000.00"),
                    "transport_allowance": Decimal("0.00")
                },
                {
                    "basic_salary": Decimal("15000.00"),
                    "hra": Decimal("4500.00"),
                    "special_allowance": Decimal("6000.00"),
                    "medical_allowance": Decimal("1200.00"),
                    "conveyance_allowance": Decimal("1200.00"),
                    "transport_allowance": Decimal("500.00")
                },
                {
                    "basic_salary": Decimal("10000.00"),
                    "hra": Decimal("3000.00"),
                    "special_allowance": Decimal("4000.00"),
                    "medical_allowance": Decimal("800.00"),
                    "conveyance_allowance": Decimal("800.00"),
                    "transport_allowance": Decimal("200.00")
                },
                {
                    "basic_salary": Decimal("18000.00"),
                    "hra": Decimal("5400.00"),
                    "special_allowance": Decimal("7200.00"),
                    "medical_allowance": Decimal("1500.00"),
                    "conveyance_allowance": Decimal("1500.00"),
                    "transport_allowance": Decimal("800.00")
                }
            ]
            
            # Create salary records for employees
            for i, employee in enumerate(employees):
                # Use sample data or generate random data
                if i < len(salary_data):
                    salary_info = salary_data[i]
                else:
                    # Generate random salary data for additional employees
                    base_basic = random.choice([8700, 10000, 12000, 15000, 18000])
                    salary_info = {
                        "basic_salary": Decimal(str(base_basic)),
                        "hra": Decimal(str(base_basic * 0.25)),  # 25% of basic
                        "special_allowance": Decimal(str(base_basic * 0.40)),  # 40% of basic
                        "medical_allowance": Decimal(str(random.choice([700, 800, 1000, 1200, 1500]))),
                        "conveyance_allowance": Decimal(str(random.choice([700, 800, 1000, 1200, 1500]))),
                        "transport_allowance": Decimal(str(random.choice([0, 200, 500, 800])))
                    }
                
                # Calculate gross salary
                gross_salary = (
                    salary_info["basic_salary"] +
                    salary_info["hra"] +
                    salary_info["special_allowance"] +
                    salary_info["medical_allowance"] +
                    salary_info["conveyance_allowance"] +
                    salary_info["transport_allowance"]
                )
                
                # Create EmployeeSalary record
                employee_salary = EmployeeSalary(
                    employee_id=employee.id,
                    basic_salary=salary_info["basic_salary"],
                    house_rent_allowance=salary_info["hra"],
                    special_allowance=salary_info["special_allowance"],
                    medical_allowance=salary_info["medical_allowance"],
                    conveyance_allowance=salary_info["conveyance_allowance"],
                    telephone_allowance=salary_info["transport_allowance"],  # Using transport as telephone
                    gross_salary=gross_salary,
                    ctc=gross_salary,  # Simplified CTC calculation
                    effective_from=date(2024, 7, 1),  # July 2024
                    is_active=True,
                    created_at=datetime.now()
                )
                db.add(employee_salary)
                
                # Create SalaryVariable records for allowances
                allowances = [
                    ("HRA", salary_info["hra"]),
                    ("Special Allowance", salary_info["special_allowance"]),
                    ("Medical Allowance", salary_info["medical_allowance"]),
                    ("Conveyance Allowance", salary_info["conveyance_allowance"]),
                    ("Transport Allowance", salary_info["transport_allowance"])
                ]
                
                for allowance_name, amount in allowances:
                    if amount > 0:  # Only create records for non-zero amounts
                        salary_variable = SalaryVariable(
                            business_id=business.id,
                            employee_id=employee.id,
                            variable_name=allowance_name,
                            variable_type=SalaryVariableType.ALLOWANCE,
                            amount=amount,
                            effective_date=date(2024, 7, 1),
                            is_recurring=True,
                            frequency="monthly",
                            is_taxable=True,
                            is_active=True,
                            created_at=datetime.now(),
                            created_by=1  # Superadmin
                        )
                        db.add(salary_variable)
                
                # Create additional variable salary components for June 2025 (frontend default)
                # Leave Encashment (for some employees)
                if i % 3 == 0:  # Every 3rd employee gets leave encashment
                    leave_encashment = SalaryVariable(
                        business_id=business.id,
                        employee_id=employee.id,
                        variable_name="Leave Encashment",
                        variable_type=SalaryVariableType.ALLOWANCE,
                        amount=Decimal(str(random.randint(2000, 5000))),
                        effective_date=date(2025, 6, 1),  # June 2025
                        is_recurring=False,
                        frequency="one_time",
                        description="Annual leave encashment",
                        is_taxable=True,
                        is_active=True,
                        created_at=datetime.now(),
                        created_by=1
                    )
                    db.add(leave_encashment)
                
                # Bonus (for some employees)
                if i % 2 == 0:  # Every 2nd employee gets bonus
                    bonus_amount = salary_info["basic_salary"] * Decimal('0.5')  # 50% of basic as bonus
                    bonus = SalaryVariable(
                        business_id=business.id,
                        employee_id=employee.id,
                        variable_name="Performance Bonus",
                        variable_type=SalaryVariableType.BONUS,
                        amount=bonus_amount,
                        effective_date=date(2025, 6, 1),  # June 2025
                        is_recurring=False,
                        frequency="quarterly",
                        description="Quarterly performance bonus",
                        is_taxable=True,
                        is_active=True,
                        created_at=datetime.now(),
                        created_by=1
                    )
                    db.add(bonus)
                
                # Gratuity (for senior employees - those with higher basic salary)
                if salary_info["basic_salary"] >= 15000:
                    gratuity_amount = salary_info["basic_salary"] * Decimal('0.25')  # 25% of basic
                    gratuity = SalaryVariable(
                        business_id=business.id,
                        employee_id=employee.id,
                        variable_name="Gratuity Payment",
                        variable_type=SalaryVariableType.ALLOWANCE,
                        amount=gratuity_amount,
                        effective_date=date(2025, 6, 1),  # June 2025
                        is_recurring=False,
                        frequency="yearly",
                        description="Annual gratuity payment",
                        is_taxable=True,
                        is_active=True,
                        created_at=datetime.now(),
                        created_by=1
                    )
                    db.add(gratuity)
            
            db.commit()
            logger.info(f"Sample salary details data created for {len(employees)} employees")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample salary details data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_salary_deductions_sample_data():
    """Create sample salary deductions data for testing"""
    logger.info("\nStep 11.2: Creating sample salary deductions data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee
            from app.models.datacapture import EmployeeDeduction, DeductionType
            from decimal import Decimal
            import random
            
            # Check if salary deductions data already exists
            existing_deduction = db.query(EmployeeDeduction).filter(
                EmployeeDeduction.deduction_name.in_(["GI", "Gratuity", "PF", "Professional Tax", "Income Tax"])
            ).first()
            if existing_deduction:
                logger.info("Salary deductions sample data already exists, skipping...")
                return True
            
            # Get business and employees
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).all()
            
            if not employees:
                logger.warning("No employees found, skipping salary deductions sample data")
                return True
            
            # Enhanced sample deductions data for comprehensive testing
            deductions_data = [
                {
                    "gi": Decimal("800.00"),
                    "gratuity": Decimal("577.00"),
                    "pf": Decimal("1800.00"),
                    "professional_tax": Decimal("200.00"),
                    "income_tax": Decimal("5000.00")
                },
                {
                    "gi": Decimal("1000.00"),
                    "gratuity": Decimal("650.00"),
                    "pf": Decimal("2100.00"),
                    "professional_tax": Decimal("200.00"),
                    "income_tax": Decimal("7500.00")
                },
                {
                    "gi": Decimal("800.00"),
                    "gratuity": Decimal("577.00"),
                    "pf": Decimal("1800.00"),
                    "professional_tax": Decimal("200.00"),
                    "income_tax": Decimal("4500.00")
                },
                {
                    "gi": Decimal("1200.00"),
                    "gratuity": Decimal("750.00"),
                    "pf": Decimal("2400.00"),
                    "professional_tax": Decimal("200.00"),
                    "income_tax": Decimal("8000.00")
                },
                {
                    "gi": Decimal("800.00"),
                    "gratuity": Decimal("577.00"),
                    "pf": Decimal("1800.00"),
                    "professional_tax": Decimal("200.00"),
                    "income_tax": Decimal("6000.00")
                }
            ]
            
            # Create deduction records for employees
            for i, employee in enumerate(employees):
                # Use sample data or generate random data
                if i < len(deductions_data):
                    deduction_info = deductions_data[i]
                else:
                    # Generate random deduction data for additional employees
                    deduction_info = {
                        "gi": Decimal(str(random.choice([0, 800, 1000, 1200]))),
                        "gratuity": Decimal(str(random.choice([0, 577, 650, 750]))),
                        "pf": Decimal(str(random.choice([1800, 2100, 2400]))),
                        "professional_tax": Decimal("200.00"),
                        "income_tax": Decimal(str(random.choice([4500, 5000, 6000, 7500, 8000])))
                    }
                
                # Create EmployeeDeduction records for all deduction types
                deductions = [
                    ("GI", deduction_info["gi"], DeductionType.INSURANCE),
                    ("Gratuity", deduction_info["gratuity"], DeductionType.OTHER),
                    ("PF", deduction_info["pf"], DeductionType.TAX),
                    ("Professional Tax", deduction_info["professional_tax"], DeductionType.TAX),
                    ("Income Tax", deduction_info["income_tax"], DeductionType.TAX)
                ]
                
                for deduction_name, amount, deduction_type in deductions:
                    if amount > 0:  # Only create records for non-zero amounts
                        # Create for current month (August 2025)
                        employee_deduction = EmployeeDeduction(
                            business_id=business.id,
                            employee_id=employee.id,
                            deduction_name=deduction_name,
                            deduction_type=deduction_type,
                            amount=amount,
                            effective_date=date(2025, 8, 1),
                            is_recurring=True,
                            frequency="monthly",
                            is_active=True,
                            created_at=datetime.now(),
                            created_by=1  # Superadmin
                        )
                        db.add(employee_deduction)
                        
                        # Also create for previous months for historical data
                        for month_offset in [1, 2, 3]:  # July, June, May 2025
                            historical_date = date(2025, 8 - month_offset, 1)
                            historical_amount = amount * Decimal(str(random.uniform(0.8, 1.2)))  # Slight variation
                            
                            historical_deduction = EmployeeDeduction(
                                business_id=business.id,
                                employee_id=employee.id,
                                deduction_name=deduction_name,
                                deduction_type=deduction_type,
                                amount=historical_amount,
                                effective_date=historical_date,
                                is_recurring=True,
                                frequency="monthly",
                                is_active=True,
                                created_at=datetime.now(),
                                created_by=1  # Superadmin
                            )
                            db.add(historical_deduction)
                
                # Add some additional deductions for variety
                if i % 5 == 0:  # Every 5th employee gets ESI deduction
                    esi_deduction = EmployeeDeduction(
                        business_id=business.id,
                        employee_id=employee.id,
                        deduction_name="ESI",
                        deduction_type=DeductionType.INSURANCE,
                        amount=Decimal("150.00"),
                        effective_date=date(2025, 8, 1),
                        is_recurring=True,
                        frequency="monthly",
                        is_active=True,
                        created_at=datetime.now(),
                        created_by=1  # Superadmin
                    )
                    db.add(esi_deduction)
                
                if i % 7 == 0:  # Every 7th employee gets Loan deduction
                    loan_deduction = EmployeeDeduction(
                        business_id=business.id,
                        employee_id=employee.id,
                        deduction_name="Loan Deduction",
                        deduction_type=DeductionType.LOAN,
                        amount=Decimal("3000.00"),
                        effective_date=date(2025, 8, 1),
                        is_recurring=True,
                        frequency="monthly",
                        is_active=True,
                        created_at=datetime.now(),
                        created_by=1  # Superadmin
                    )
                    db.add(loan_deduction)
            
            db.commit()
            logger.info(f"Enhanced salary deductions sample data created for {len(employees)} employees")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample salary deductions data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_work_profile_sample_data():
    """Create sample work profile data for testing"""
    logger.info("\nStep 11.3: Creating sample work profile data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee
            from app.models.location import Location
            from app.models.cost_center import CostCenter
            from app.models.department import Department
            from app.models.grades import Grade
            from app.models.designations import Designation
            from app.models.shift_policy import ShiftPolicy
            from app.models.weekoff_policy import WeekOffPolicy
            import random
            
            # Get business and employees
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).all()
            
            if not employees:
                logger.warning("No employees found, skipping work profile sample data")
                return True
            
            # Get or create sample locations
            locations = db.query(Location).filter(Location.business_id == business.id).all()
            if not locations:
                # Create sample locations
                sample_locations = [
                    {"name": "Hyderabad", "state": "Telangana"},
                    {"name": "Bangalore", "state": "Karnataka"},
                    {"name": "Chennai", "state": "Tamil Nadu"}
                ]
                for loc_data in sample_locations:
                    # Check if location already exists
                    existing_location = db.query(Location).filter(
                        Location.business_id == business.id,
                        Location.name == loc_data["name"]
                    ).first()
                    
                    if not existing_location:
                        location = Location(
                            business_id=business.id,
                            name=loc_data["name"],
                            state=loc_data["state"],
                            is_active=True,
                            created_by=1,
                            created_at=datetime.now()
                        )
                        db.add(location)
                
                try:
                    db.commit()
                except Exception as e:
                    logger.warning(f"Some locations may already exist: {e}")
                    db.rollback()
                
                locations = db.query(Location).filter(Location.business_id == business.id).all()
            
            # Create sample holidays for each location
            existing_holidays = db.query(Holiday).filter(Holiday.business_id == business.id).first()
            if not existing_holidays:
                logger.info("Creating sample holidays...")
                current_year = datetime.now().year
                
                # Sample holidays for the current year
                sample_holidays = [
                    {"date": date(current_year, 1, 26), "name": "Republic Day"},
                    {"date": date(current_year, 3, 8), "name": "Holi"},
                    {"date": date(current_year, 8, 15), "name": "Independence Day"},
                    {"date": date(current_year, 10, 2), "name": "Gandhi Jayanti"},
                    {"date": date(current_year, 10, 24), "name": "Dussehra"},
                    {"date": date(current_year, 11, 12), "name": "Diwali"},
                    {"date": date(current_year, 12, 25), "name": "Christmas Day"}
                ]
                
                # Add holidays for each location
                for location in locations:
                    for holiday_data in sample_holidays:
                        # Check if holiday already exists for this location and date
                        existing = db.query(Holiday).filter(
                            Holiday.business_id == business.id,
                            Holiday.location_id == location.id,
                            Holiday.date == holiday_data["date"]
                        ).first()
                        
                        if not existing:
                            holiday = Holiday(
                                business_id=business.id,
                                location_id=location.id,
                                date=holiday_data["date"],
                                name=holiday_data["name"]
                            )
                            db.add(holiday)
                
                db.commit()
                logger.info(f"Created sample holidays for {len(locations)} locations")
            
            # Get or create sample cost centers
            cost_centers = db.query(CostCenter).filter(CostCenter.business_id == business.id).all()
            if not cost_centers:
                # Create sample cost centers
                sample_cost_centers = [
                    {"name": "Associate Sof"},
                    {"name": "Tech Support"},
                    {"name": "Business Ops"},
                    {"name": "HR Services"}
                ]
                for cc_data in sample_cost_centers:
                    # Check if cost center already exists
                    existing_cc = db.query(CostCenter).filter(
                        CostCenter.business_id == business.id,
                        CostCenter.name == cc_data["name"]
                    ).first()
                    
                    if not existing_cc:
                        cost_center = CostCenter(
                            business_id=business.id,
                            name=cc_data["name"],
                            is_active=True,
                            created_by=1,
                            created_at=datetime.now()
                        )
                        db.add(cost_center)
                
                try:
                    db.commit()
                except Exception as e:
                    logger.warning(f"Some cost centers may already exist: {e}")
                    db.rollback()
                
                cost_centers = db.query(CostCenter).filter(CostCenter.business_id == business.id).all()
            
            # Get or create sample grades
            grades = db.query(Grade).filter(Grade.business_id == business.id).all()
            if not grades:
                # Create sample grades
                sample_grades = [
                    {"name": "Trainee"},
                    {"name": "Associate"},
                    {"name": "Senior Associate"},
                    {"name": "Lead"}
                ]
                for grade_data in sample_grades:
                    # Check for existing grade globally (due to unique constraint on name)
                    existing_grade = db.query(Grade).filter(
                        Grade.name == grade_data["name"]
                    ).first()
                    if not existing_grade:
                        grade = Grade(
                            business_id=business.id,
                            name=grade_data["name"],
                            created_by=1,
                            created_at=datetime.now()
                        )
                        db.add(grade)
                db.commit()
                grades = db.query(Grade).filter(Grade.business_id == business.id).all()
            
            # Get or create sample designations
            designations = db.query(Designation).filter(Designation.business_id == business.id).all()
            if not designations:
                # Create sample designations
                sample_designations = [
                    {"name": "Associate Sof"},
                    {"name": "Software Engineer"},
                    {"name": "Team Lead"},
                    {"name": "Manager"}
                ]
                for desig_data in sample_designations:
                    # Check if designation already exists globally (due to unique constraint on name)
                    existing_designation = db.query(Designation).filter(
                        Designation.name == desig_data["name"]
                    ).first()
                    
                    if not existing_designation:
                        designation = Designation(
                            business_id=business.id,
                            name=desig_data["name"],
                            created_by=1,
                            created_at=datetime.now()
                        )
                        db.add(designation)
                    else:
                        # If designation exists globally, check if we need to assign it to this business
                        if existing_designation.business_id != business.id:
                            logger.info(f"Designation '{desig_data['name']}' exists globally, skipping for business {business.id}")
                
                try:
                    db.commit()
                except Exception as e:
                    logger.warning(f"Some designations may already exist: {e}")
                    db.rollback()
                
                designations = db.query(Designation).filter(Designation.business_id == business.id).all()
            
            # Get or create sample shift policies
            shift_policies = db.query(ShiftPolicy).filter(ShiftPolicy.business_id == business.id).all()
            if not shift_policies:
                # Create sample shift policies
                sample_shift_policies = [
                    {"title": "General Policy", "description": "Standard working hours"},
                    {"title": "Night Shift", "description": "Night shift policy"},
                    {"title": "Rotational Shift", "description": "Rotating shift policy"}
                ]
                for sp_data in sample_shift_policies:
                    # Check if shift policy already exists
                    existing_policy = db.query(ShiftPolicy).filter(
                        ShiftPolicy.business_id == business.id,
                        ShiftPolicy.title == sp_data["title"]
                    ).first()
                    
                    if not existing_policy:
                        shift_policy = ShiftPolicy(
                            business_id=business.id,
                            title=sp_data["title"],
                            description=sp_data["description"],
                            is_default=sp_data["title"] == "General Policy",
                            weekly_shifts={},
                            created_at=datetime.now()
                        )
                        db.add(shift_policy)
                
                try:
                    db.commit()
                except Exception as e:
                    logger.warning(f"Some shift policies may already exist: {e}")
                    db.rollback()
                
                shift_policies = db.query(ShiftPolicy).filter(ShiftPolicy.business_id == business.id).all()
            
            # Get or create sample weekoff policies
            weekoff_policies = db.query(WeekOffPolicy).filter(WeekOffPolicy.business_id == business.id).all()
            if not weekoff_policies:
                # Create sample weekoff policies
                sample_weekoff_policies = [
                    {"title": "Hyderabad Week", "description": "Standard weekend off"},
                    {"title": "Alternate Weekoff", "description": "Alternate weekend off"},
                    {"title": "Fixed Sunday", "description": "Fixed Sunday off"}
                ]
                for wo_data in sample_weekoff_policies:
                    # Check if weekoff policy already exists
                    existing_policy = db.query(WeekOffPolicy).filter(
                        WeekOffPolicy.business_id == business.id,
                        WeekOffPolicy.title == wo_data["title"]
                    ).first()
                    
                    if not existing_policy:
                        weekoff_policy = WeekOffPolicy(
                            business_id=business.id,
                            title=wo_data["title"],
                            description=wo_data["description"],
                            is_default=wo_data["title"] == "Hyderabad Week",
                            general_week_offs=["Sunday"],
                            alternating_week_offs=[],
                            weekoffs_payable=False,
                            created_at=datetime.now()
                        )
                        db.add(weekoff_policy)
                
                try:
                    db.commit()
                except Exception as e:
                    logger.warning(f"Some weekoff policies may already exist: {e}")
                    db.rollback()
                
                weekoff_policies = db.query(WeekOffPolicy).filter(WeekOffPolicy.business_id == business.id).all()
            
            # Update employees with work profile data
            updated_count = 0
            for i, employee in enumerate(employees):
                # Assign work profile data to employees
                employee.location_id = locations[i % len(locations)].id if locations else None
                employee.cost_center_id = cost_centers[i % len(cost_centers)].id if cost_centers else None
                employee.grade_id = grades[i % len(grades)].id if grades else None
                employee.designation_id = designations[i % len(designations)].id if designations else None
                employee.shift_policy_id = shift_policies[i % len(shift_policies)].id if shift_policies else None
                employee.weekoff_policy_id = weekoff_policies[i % len(weekoff_policies)].id if weekoff_policies else None
                
                # Update audit fields
                employee.updated_by = 1  # Superadmin
                employee.updated_at = datetime.now()
                
                updated_count += 1
            
            db.commit()
            logger.info(f"Sample work profile data created for {updated_count} employees")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample work profile data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_deduction_sample_data():
    """Create sample deduction data for testing"""
    logger.info("\nStep 12: Creating sample deduction data...")
    
    try:
        with get_db_context() as db:
            from app.models.datacapture import EmployeeDeduction, DeductionType
            from app.models.employee import Employee
            from decimal import Decimal
            
            # Check if deduction data already exists
            existing_deductions = db.query(EmployeeDeduction).first()
            if existing_deductions:
                logger.info("Deduction sample data already exists, skipping...")
                return True
            
            # Get business and employees
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(10).all()
            
            if not employees:
                logger.warning("No employees found, skipping deduction sample data")
                return True
            
            # Create sample deduction configurations with complete data
            deduction_configs = [
                {
                    "deduction_name": "Voluntary PF",
                    "deduction_type": DeductionType.TAX,
                    "base_amount": Decimal("1800.00"),
                    "description": "Voluntary Provident Fund contribution",
                    "reference_prefix": "VPF"
                },
                {
                    "deduction_name": "Professional Tax",
                    "deduction_type": DeductionType.TAX,
                    "base_amount": Decimal("200.00"),
                    "description": "Monthly professional tax deduction",
                    "reference_prefix": "PT"
                },
                {
                    "deduction_name": "ESI",
                    "deduction_type": DeductionType.INSURANCE,
                    "base_amount": Decimal("150.00"),
                    "description": "Employee State Insurance contribution",
                    "reference_prefix": "ESI"
                },
                {
                    "deduction_name": "Income Tax",
                    "deduction_type": DeductionType.TAX,
                    "base_amount": Decimal("2500.00"),
                    "description": "Monthly income tax deduction",
                    "reference_prefix": "IT"
                },
                {
                    "deduction_name": "Loan Deduction",
                    "deduction_type": DeductionType.LOAN,
                    "base_amount": Decimal("5000.00"),
                    "description": "Employee loan repayment deduction",
                    "reference_prefix": "LOAN"
                }
            ]
            
            # Create employee-specific deductions (varying amounts)
            import random
            deduction_counter = 1
            
            for employee in employees:
                # Assign 2-3 random deductions to each employee with varying amounts
                selected_configs = random.sample(deduction_configs, random.randint(2, 4))
                
                for config in selected_configs:
                    # Create employee-specific deduction with variation in amount
                    variation = random.uniform(0.8, 1.2)  # 80% to 120% of base amount
                    employee_amount = config["base_amount"] * Decimal(str(variation))
                    
                    # Create deduction for current month (AUG-2025)
                    current_date = date(2025, 8, 1)  # August 2025
                    
                    employee_deduction = EmployeeDeduction(
                        business_id=business.id,
                        employee_id=employee.id,
                        deduction_name=config["deduction_name"],
                        deduction_type=config["deduction_type"],
                        amount=employee_amount,
                        effective_date=current_date,
                        end_date=None,  # Ongoing deduction
                        description=f"{config['description']} for {employee.full_name}",
                        reference_number=f"{config['reference_prefix']}{deduction_counter:04d}",
                        is_recurring=True,
                        frequency="monthly",
                        is_active=True,
                        created_by=1  # Superadmin
                    )
                    db.add(employee_deduction)
                    deduction_counter += 1
                    
                    # Also create deduction for previous month (JUL-2025)
                    prev_month_date = date(2025, 7, 1)  # July 2025
                    
                    prev_employee_deduction = EmployeeDeduction(
                        business_id=business.id,
                        employee_id=employee.id,
                        deduction_name=config["deduction_name"],
                        deduction_type=config["deduction_type"],
                        amount=employee_amount,
                        effective_date=prev_month_date,
                        end_date=None,  # Ongoing deduction
                        description=f"{config['description']} for {employee.full_name}",
                        reference_number=f"{config['reference_prefix']}{deduction_counter:04d}",
                        is_recurring=True,
                        frequency="monthly",
                        is_active=True,
                        created_by=1  # Superadmin
                    )
                    db.add(prev_employee_deduction)
                    deduction_counter += 1
                    
                    # Create deduction for DEC-2024 (for frontend computation date)
                    dec_date = date(2024, 12, 1)  # December 2024
                    
                    dec_employee_deduction = EmployeeDeduction(
                        business_id=business.id,
                        employee_id=employee.id,
                        deduction_name=config["deduction_name"],
                        deduction_type=config["deduction_type"],
                        amount=employee_amount * Decimal("0.95"),  # Slightly different amount
                        effective_date=dec_date,
                        end_date=None,
                        description=f"{config['description']} for {employee.full_name}",
                        reference_number=f"{config['reference_prefix']}{deduction_counter:04d}",
                        is_recurring=True,
                        frequency="monthly",
                        is_active=True,
                        created_by=1  # Superadmin
                    )
                    db.add(dec_employee_deduction)
                    deduction_counter += 1
            
            db.commit()
            
            # Count created records
            total_deductions = db.query(EmployeeDeduction).count()
            logger.info(f"[OK] Created {total_deductions} sample deduction records")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample deduction data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_tds_challan_sample_data():
    """Create sample TDS challan data for testing"""
    logger.info("\nStep 18: Creating sample TDS challan data...")
    
    try:
        with get_db_context() as db:
            from app.models.datacapture import TDSChallan
            from app.models.employee import Employee
            from decimal import Decimal
            
            # Check if TDS challan data already exists
            existing_challans = db.query(TDSChallan).first()
            if existing_challans:
                logger.info("TDS challan sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Create sample TDS challans for financial year 2024-25
            financial_year = "2024-25"
            
            # Sample challan data for different months
            challan_configs = [
                {
                    "month": "APR-2024",
                    "challan_number": "CHALLAN001APR24",
                    "deposit_date": date(2024, 4, 15),
                    "quarter": "Q1",
                    "branch_code": "12345678",
                    "tds_amount": Decimal("15000.00"),
                    "remarks": "TDS challan for April 2024"
                },
                {
                    "month": "MAY-2024", 
                    "challan_number": "CHALLAN002MAY24",
                    "deposit_date": date(2024, 5, 15),
                    "quarter": "Q1",
                    "branch_code": "12345679",
                    "tds_amount": Decimal("18000.00"),
                    "remarks": "TDS challan for May 2024"
                },
                {
                    "month": "JUN-2024",
                    "challan_number": "CHALLAN003JUN24", 
                    "deposit_date": date(2024, 6, 15),
                    "quarter": "Q1",
                    "branch_code": "12345680",
                    "tds_amount": Decimal("16500.00"),
                    "remarks": "TDS challan for June 2024"
                },
                {
                    "month": "JUL-2024",
                    "challan_number": "CHALLAN004JUL24",
                    "deposit_date": date(2024, 7, 15),
                    "quarter": "Q2", 
                    "branch_code": "12345681",
                    "tds_amount": Decimal("17200.00"),
                    "remarks": "TDS challan for July 2024"
                },
                {
                    "month": "AUG-2024",
                    "challan_number": "CHALLAN005AUG24",
                    "deposit_date": date(2024, 8, 15),
                    "quarter": "Q2",
                    "branch_code": "12345682", 
                    "tds_amount": Decimal("19800.00"),
                    "remarks": "TDS challan for August 2024"
                },
                {
                    "month": "SEP-2024",
                    "challan_number": "CHALLAN006SEP24",
                    "deposit_date": date(2024, 9, 15),
                    "quarter": "Q2",
                    "branch_code": "12345683",
                    "tds_amount": Decimal("18500.00"),
                    "remarks": "TDS challan for September 2024"
                }
            ]
            
            # Create TDS challan records
            for config in challan_configs:
                tds_challan = TDSChallan(
                    business_id=business.id,
                    challan_number=config["challan_number"],
                    financial_year=financial_year,
                    quarter=config["quarter"],
                    deposit_date=config["deposit_date"],
                    tds_amount=config["tds_amount"],
                    interest=Decimal("0.00"),
                    penalty=Decimal("0.00"),
                    total_amount=config["tds_amount"],  # Total = TDS amount + interest + penalty
                    bank_name="State Bank of India",
                    branch_code=config["branch_code"],
                    remarks=config["remarks"],
                    uploaded_file_path="",  # No file uploaded initially
                    created_by=1  # Superadmin
                )
                db.add(tds_challan)
            
            db.commit()
            
            # Count created records
            total_challans = db.query(TDSChallan).count()
            logger.info(f"[OK] Created {total_challans} sample TDS challan records")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample TDS challan data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_tds_return_sample_data():
    """Create sample TDS return data for testing"""
    logger.info("\nStep 19: Creating sample TDS return data...")
    
    try:
        with get_db_context() as db:
            from app.models.datacapture import TDSReturn
            from app.models.business import Business
            from decimal import Decimal
            
            # Check if TDS return data already exists
            existing_returns = db.query(TDSReturn).first()
            if existing_returns:
                logger.info("TDS return sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Create sample TDS returns for financial year 2024-25
            financial_year = "2024-25"
            
            # Sample return data for different quarters
            return_configs = [
                {
                    "quarter": "Q1",
                    "return_type": "24Q",
                    "filing_date": date(2024, 7, 31),  # Q1 filing deadline
                    "acknowledgment_number": "ACK240731001",
                    "total_deductees": 25,
                    "total_tds_amount": Decimal("49500.00"),
                    "total_deposited": Decimal("49500.00"),
                    "is_filed": True,
                    "remarks": "Q1 TDS return filed successfully"
                },
                {
                    "quarter": "Q2", 
                    "return_type": "24Q",
                    "filing_date": date(2024, 10, 31),  # Q2 filing deadline
                    "acknowledgment_number": "ACK241031002",
                    "total_deductees": 28,
                    "total_tds_amount": Decimal("55200.00"),
                    "total_deposited": Decimal("55200.00"),
                    "is_filed": True,
                    "remarks": "Q2 TDS return filed successfully"
                },
                {
                    "quarter": "Q3",
                    "return_type": "24Q",
                    "filing_date": date(2025, 1, 31),  # Q3 filing deadline
                    "acknowledgment_number": "ACK250131003",
                    "total_deductees": 30,
                    "total_tds_amount": Decimal("58800.00"),
                    "total_deposited": Decimal("58800.00"),
                    "is_filed": True,
                    "remarks": "Q3 TDS return filed successfully"
                }
                # Q4 not filed yet (pending)
            ]
            
            # Create TDS return records
            for config in return_configs:
                tds_return = TDSReturn(
                    business_id=business.id,
                    return_type=config["return_type"],
                    financial_year=financial_year,
                    quarter=config["quarter"],
                    filing_date=config["filing_date"],
                    acknowledgment_number=config["acknowledgment_number"],
                    total_deductees=config["total_deductees"],
                    total_tds_amount=config["total_tds_amount"],
                    total_deposited=config["total_deposited"],
                    is_filed=config["is_filed"],
                    is_revised=False,
                    revision_number=0,
                    return_file_path="",  # No file uploaded initially
                    acknowledgment_file_path="",  # No file uploaded initially
                    remarks=config["remarks"],
                    created_by=1  # Superadmin
                )
                db.add(tds_return)
            
            db.commit()
            
            # Count created records
            total_returns = db.query(TDSReturn).count()
            logger.info(f"[OK] Created {total_returns} sample TDS return records")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample TDS return data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_income_tax_tds_sample_data():
    """Create sample income tax TDS data"""
    logger.info("\nStep 14: Creating sample income tax TDS data...")
    
    try:
        with get_db_context() as db:
            from app.models.datacapture import IncomeTaxTDS
            from app.models.employee import Employee
            from decimal import Decimal
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get active employees
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(10).all()
            
            if not employees:
                logger.info("No employees found for TDS data creation")
                return True
            
            # TDS configurations for different employee levels
            tds_configs = [
                {
                    "financial_year": "2024-25",
                    "quarter": "Q3",
                    "gross_salary": Decimal("50000.00"),
                    "taxable_income": Decimal("45000.00"),
                    "tds_amount": Decimal("4500.00"),
                    "tax_slab_rate": Decimal("20.00"),
                    "exemptions": Decimal("2500.00"),
                    "deductions_80c": Decimal("15000.00"),
                    "other_deductions": Decimal("5000.00")
                },
                {
                    "financial_year": "2024-25",
                    "quarter": "Q3",
                    "gross_salary": Decimal("75000.00"),
                    "taxable_income": Decimal("70000.00"),
                    "tds_amount": Decimal("8500.00"),
                    "tax_slab_rate": Decimal("30.00"),
                    "exemptions": Decimal("3000.00"),
                    "deductions_80c": Decimal("20000.00"),
                    "other_deductions": Decimal("7500.00")
                },
                {
                    "financial_year": "2024-25",
                    "quarter": "Q3",
                    "gross_salary": Decimal("35000.00"),
                    "taxable_income": Decimal("32000.00"),
                    "tds_amount": Decimal("1600.00"),
                    "tax_slab_rate": Decimal("10.00"),
                    "exemptions": Decimal("1500.00"),
                    "deductions_80c": Decimal("10000.00"),
                    "other_deductions": Decimal("2500.00")
                }
            ]
            
            # Create TDS records for employees
            for i, employee in enumerate(employees):
                config = tds_configs[i % len(tds_configs)]
                
                # Check if TDS record already exists
                existing_tds = db.query(IncomeTaxTDS).filter(
                    IncomeTaxTDS.business_id == business.id,
                    IncomeTaxTDS.employee_id == employee.id,
                    IncomeTaxTDS.financial_year == config["financial_year"],
                    IncomeTaxTDS.quarter == config["quarter"]
                ).first()
                
                if existing_tds:
                    continue
                
                # Create TDS record
                tds_record = IncomeTaxTDS(
                    business_id=business.id,
                    employee_id=employee.id,
                    financial_year=config["financial_year"],
                    quarter=config["quarter"],
                    gross_salary=config["gross_salary"],
                    taxable_income=config["taxable_income"],
                    tds_amount=config["tds_amount"],
                    tax_slab_rate=config["tax_slab_rate"],
                    exemptions=config["exemptions"],
                    deductions_80c=config["deductions_80c"],
                    other_deductions=config["other_deductions"],
                    challan_number=f"CHAL{employee.id:04d}Q3",
                    deposit_date=date(2025, 1, 15),
                    remarks=f"Q3 TDS for {employee.full_name}",
                    created_by=1  # Superadmin
                )
                db.add(tds_record)
                
                # Also create previous quarter data for copy functionality testing
                prev_quarter_tds = IncomeTaxTDS(
                    business_id=business.id,
                    employee_id=employee.id,
                    financial_year=config["financial_year"],
                    quarter="Q2",
                    gross_salary=config["gross_salary"] * Decimal("0.95"),  # Slightly lower
                    taxable_income=config["taxable_income"] * Decimal("0.95"),
                    tds_amount=config["tds_amount"] * Decimal("0.95"),
                    tax_slab_rate=config["tax_slab_rate"],
                    exemptions=config["exemptions"],
                    deductions_80c=config["deductions_80c"],
                    other_deductions=config["other_deductions"],
                    challan_number=f"CHAL{employee.id:04d}Q2",
                    deposit_date=date(2024, 10, 15),
                    remarks=f"Q2 TDS for {employee.full_name}",
                    created_by=1  # Superadmin
                )
                db.add(prev_quarter_tds)
            
            db.commit()
            logger.info("Sample income tax TDS data created successfully")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample income tax TDS data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_extra_hours_sample_data():
    """Create sample extra hours data"""
    logger.info("\nStep 15: Creating sample extra hours data...")
    
    try:
        with get_db_context() as db:
            from app.models.datacapture import ExtraHour
            from app.models.employee import Employee
            from decimal import Decimal
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get active employees
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(10).all()
            
            if not employees:
                logger.info("No employees found for extra hours data creation")
                return True
            
            # Extra hours configurations for different scenarios
            extra_hours_configs = [
                {
                    "extra_hours": Decimal("4.0"),
                    "overtime_rate": Decimal("600.00"),
                    "work_description": "Weekend project work",
                    "start_time": "18:00",
                    "end_time": "22:00"
                },
                {
                    "extra_hours": Decimal("2.5"),
                    "overtime_rate": Decimal("550.00"),
                    "work_description": "Client meeting preparation",
                    "start_time": "19:00",
                    "end_time": "21:30"
                },
                {
                    "extra_hours": Decimal("6.0"),
                    "overtime_rate": Decimal("650.00"),
                    "work_description": "Production deployment",
                    "start_time": "20:00",
                    "end_time": "02:00"
                }
            ]
            
            # Create extra hours records for employees across multiple months
            for i, employee in enumerate(employees):
                config = extra_hours_configs[i % len(extra_hours_configs)]
                
                # Create overtime data for June 2025 (frontend default)
                june_dates = [date(2025, 6, 10), date(2025, 6, 15), date(2025, 6, 20)]
                for j, work_date in enumerate(june_dates):
                    # Check if extra hours record already exists
                    existing_extra_hours = db.query(ExtraHour).filter(
                        ExtraHour.business_id == business.id,
                        ExtraHour.employee_id == employee.id,
                        ExtraHour.work_date == work_date
                    ).first()
                    
                    if existing_extra_hours:
                        continue
                    
                    # Vary the overtime hours and rates for different dates
                    overtime_multiplier = Decimal("1.0") + (Decimal("0.2") * j)  # 1.0, 1.2, 1.4
                    adjusted_hours = config["extra_hours"] * overtime_multiplier
                    adjusted_rate = config["overtime_rate"] + (Decimal("50.00") * j)
                    total_amount = adjusted_hours * adjusted_rate
                    
                    extra_hours_record = ExtraHour(
                        business_id=business.id,
                        employee_id=employee.id,
                        work_date=work_date,
                        regular_hours=Decimal("8.0"),
                        extra_hours=adjusted_hours,
                        overtime_rate=adjusted_rate,
                        total_amount=total_amount,
                        start_time=config["start_time"],
                        end_time=config["end_time"],
                        work_description=f"{config['work_description']} - Week {j+1}",
                        is_approved=True,
                        is_paid=False,
                        created_by=1  # Superadmin
                    )
                    db.add(extra_hours_record)
                
                # Create extra hours record for August 2025 (existing data)
                existing_aug_extra_hours = db.query(ExtraHour).filter(
                    ExtraHour.business_id == business.id,
                    ExtraHour.employee_id == employee.id,
                    ExtraHour.work_date == date(2025, 8, 15)
                ).first()
                
                if not existing_aug_extra_hours:
                    total_amount = config["extra_hours"] * config["overtime_rate"]
                    
                    extra_hours_record = ExtraHour(
                        business_id=business.id,
                        employee_id=employee.id,
                        work_date=date(2025, 8, 15),  # Sample date
                        regular_hours=Decimal("8.0"),
                        extra_hours=config["extra_hours"],
                        overtime_rate=config["overtime_rate"],
                        total_amount=total_amount,
                        start_time=config["start_time"],
                        end_time=config["end_time"],
                        work_description=config["work_description"],
                        is_approved=True,
                        is_paid=False,
                        created_by=1  # Superadmin
                    )
                    db.add(extra_hours_record)
                
                # Also create previous month data for testing (July 2025)
                existing_july_extra_hours = db.query(ExtraHour).filter(
                    ExtraHour.business_id == business.id,
                    ExtraHour.employee_id == employee.id,
                    ExtraHour.work_date == date(2025, 7, 20)
                ).first()
                
                if not existing_july_extra_hours:
                    prev_month_extra_hours = ExtraHour(
                        business_id=business.id,
                        employee_id=employee.id,
                        work_date=date(2025, 7, 20),  # Previous month
                        regular_hours=Decimal("8.0"),
                        extra_hours=config["extra_hours"] * Decimal("0.8"),  # Slightly less
                        overtime_rate=config["overtime_rate"],
                        total_amount=(config["extra_hours"] * Decimal("0.8")) * config["overtime_rate"],
                        start_time=config["start_time"],
                        end_time=config["end_time"],
                        work_description=f"Previous month: {config['work_description']}",
                        is_approved=True,
                        is_paid=True,
                        created_by=1  # Superadmin
                    )
                    db.add(prev_month_extra_hours)
            
            db.commit()
            logger.info("Sample extra hours data created successfully")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample extra hours data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_loan_sample_data():
    """Create sample loan data"""
    logger.info("\nStep 16: Creating sample loan data...")
    
    try:
        with get_db_context() as db:
            from app.models.datacapture import EmployeeLoan, LoanStatus
            from app.models.employee import Employee
            from decimal import Decimal
            from datetime import date, timedelta
            import calendar
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get active employees
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(5).all()
            
            if not employees:
                logger.info("No employees found for loan data creation")
                return True
            
            # Loan configurations for different scenarios
            loan_configs = [
                {
                    "loan_type": "Personal Loan",
                    "loan_amount": Decimal("75000.00"),
                    "interest_rate": Decimal("12.0"),
                    "tenure_months": 24,
                    "purpose": "Medical emergency"
                },
                {
                    "loan_type": "Home Loan",
                    "loan_amount": Decimal("500000.00"),
                    "interest_rate": Decimal("8.5"),
                    "tenure_months": 60,
                    "purpose": "House purchase"
                },
                {
                    "loan_type": "Vehicle Loan",
                    "loan_amount": Decimal("200000.00"),
                    "interest_rate": Decimal("10.0"),
                    "tenure_months": 36,
                    "purpose": "Car purchase"
                },
                {
                    "loan_type": "Emergency Loan",
                    "loan_amount": Decimal("25000.00"),
                    "interest_rate": Decimal("0.0"),
                    "tenure_months": 12,
                    "purpose": "Family emergency"
                },
                {
                    "loan_type": "Education Loan",
                    "loan_amount": Decimal("150000.00"),
                    "interest_rate": Decimal("9.5"),
                    "tenure_months": 48,
                    "purpose": "Higher education"
                }
            ]
            
            # Create loan records
            created_count = 0
            
            for i, employee in enumerate(employees):
                config = loan_configs[i % len(loan_configs)]
                
                # Calculate EMI
                loan_amount = config["loan_amount"]
                interest_rate = config["interest_rate"]
                tenure_months = config["tenure_months"]
                
                if interest_rate > 0:
                    monthly_rate = interest_rate / (12 * 100)
                    emi_amount = (loan_amount * monthly_rate * (1 + monthly_rate) ** tenure_months) / ((1 + monthly_rate) ** tenure_months - 1)
                else:
                    emi_amount = loan_amount / tenure_months
                
                # Set loan dates
                loan_date = date.today() - timedelta(days=90 + (i * 30))
                first_emi_date = loan_date + timedelta(days=30)
                
                # Calculate last EMI date
                year = first_emi_date.year
                month = first_emi_date.month + tenure_months - 1
                
                while month > 12:
                    year += 1
                    month -= 12
                
                last_day = calendar.monthrange(year, month)[1]
                day = min(first_emi_date.day, last_day)
                last_emi_date = date(year, month, day)
                
                # Calculate paid EMIs (simulate some payments)
                paid_emis = min(3 + i, tenure_months // 4)
                paid_amount = emi_amount * paid_emis
                outstanding_amount = loan_amount - paid_amount
                
                loan_data = {
                    "business_id": business.id,
                    "employee_id": employee.id,
                    "loan_type": config["loan_type"],
                    "loan_amount": loan_amount,
                    "interest_rate": interest_rate,
                    "tenure_months": tenure_months,
                    "emi_amount": emi_amount,
                    "loan_date": loan_date,
                    "first_emi_date": first_emi_date,
                    "last_emi_date": last_emi_date,
                    "status": LoanStatus.ACTIVE,
                    "outstanding_amount": outstanding_amount,
                    "paid_amount": paid_amount,
                    "paid_emis": paid_emis,
                    "remaining_emis": tenure_months - paid_emis,
                    "purpose": config["purpose"],
                    "guarantor_name": f"Guarantor for {employee.full_name}",
                    "guarantor_relation": "Family Member"
                }
                
                # Check if loan already exists
                existing_loan = db.query(EmployeeLoan).filter(
                    EmployeeLoan.employee_id == employee.id,
                    EmployeeLoan.loan_type == config["loan_type"]
                ).first()
                
                if not existing_loan:
                    loan = EmployeeLoan(**loan_data)
                    db.add(loan)
                    created_count += 1
            
            db.commit()
            logger.info(f"[OK] Created {created_count} sample loan records")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample loan data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_it_declaration_sample_data():
    """Create sample IT declaration data"""
    logger.info("\nStep 17: Creating sample IT declaration data...")
    
    try:
        with get_db_context() as db:
            from app.models.datacapture import ITDeclaration, ITDeclarationStatus
            from app.models.employee import Employee
            from decimal import Decimal
            from datetime import date, datetime
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get active employees
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(5).all()
            
            if not employees:
                logger.info("No employees found for IT declaration data creation")
                return True
            
            # Financial years
            financial_years = ["2023-24", "2024-25", "2025-26"]
            
            # IT declaration configurations for different scenarios
            declaration_configs = [
                {
                    "pf_amount": Decimal("150000.00"),
                    "life_insurance": Decimal("25000.00"),
                    "elss_mutual_funds": Decimal("50000.00"),
                    "home_loan_principal": Decimal("100000.00"),
                    "section_80d_medical": Decimal("25000.00"),
                    "hra_exemption": Decimal("120000.00"),
                    "rent_paid": Decimal("180000.00"),
                    "landlord_name": "John Landlord",
                    "landlord_pan": "ABCDE1234F"
                },
                {
                    "pf_amount": Decimal("120000.00"),
                    "life_insurance": Decimal("30000.00"),
                    "elss_mutual_funds": Decimal("0.00"),
                    "home_loan_principal": Decimal("150000.00"),
                    "section_80d_medical": Decimal("15000.00"),
                    "section_24_home_loan_interest": Decimal("200000.00"),
                    "hra_exemption": Decimal("0.00"),
                    "rent_paid": Decimal("0.00")
                },
                {
                    "pf_amount": Decimal("100000.00"),
                    "life_insurance": Decimal("20000.00"),
                    "tuition_fees": Decimal("30000.00"),
                    "other_80c": Decimal("0.00"),
                    "section_80d_medical": Decimal("20000.00"),
                    "section_80g_donations": Decimal("10000.00"),
                    "hra_exemption": Decimal("96000.00"),
                    "rent_paid": Decimal("144000.00"),
                    "landlord_name": "Jane Property Owner",
                    "landlord_pan": "FGHIJ5678K"
                }
            ]
            
            # Create IT declaration records
            created_count = 0
            
            for i, employee in enumerate(employees):
                for j, financial_year in enumerate(financial_years):
                    config = declaration_configs[i % len(declaration_configs)]
                    
                    # Calculate total 80C
                    total_80c = (
                        config.get("pf_amount", Decimal("0")) +
                        config.get("life_insurance", Decimal("0")) +
                        config.get("elss_mutual_funds", Decimal("0")) +
                        config.get("home_loan_principal", Decimal("0")) +
                        config.get("tuition_fees", Decimal("0")) +
                        config.get("other_80c", Decimal("0"))
                    )
                    
                    # Determine status based on financial year
                    if financial_year == "2023-24":
                        status = ITDeclarationStatus.APPROVED
                        submitted_at = datetime.now() - timedelta(days=200 + (i * 10))
                    elif financial_year == "2024-25":
                        status = ITDeclarationStatus.SUBMITTED
                        submitted_at = datetime.now() - timedelta(days=30 + (i * 5))
                    else:
                        status = ITDeclarationStatus.DRAFT
                        submitted_at = None
                    
                    declaration_data = {
                        "business_id": business.id,
                        "employee_id": employee.id,
                        "financial_year": financial_year,
                        "status": status,
                        "pf_amount": config.get("pf_amount", Decimal("0")),
                        "life_insurance": config.get("life_insurance", Decimal("0")),
                        "elss_mutual_funds": config.get("elss_mutual_funds", Decimal("0")),
                        "home_loan_principal": config.get("home_loan_principal", Decimal("0")),
                        "tuition_fees": config.get("tuition_fees", Decimal("0")),
                        "other_80c": config.get("other_80c", Decimal("0")),
                        "total_80c": total_80c,
                        "section_80d_medical": config.get("section_80d_medical", Decimal("0")),
                        "section_24_home_loan_interest": config.get("section_24_home_loan_interest", Decimal("0")),
                        "section_80g_donations": config.get("section_80g_donations", Decimal("0")),
                        "hra_exemption": config.get("hra_exemption", Decimal("0")),
                        "rent_paid": config.get("rent_paid", Decimal("0")),
                        "landlord_name": config.get("landlord_name"),
                        "landlord_pan": config.get("landlord_pan"),
                        "submitted_at": submitted_at
                    }
                    
                    # Check if declaration already exists
                    existing_declaration = db.query(ITDeclaration).filter(
                        ITDeclaration.employee_id == employee.id,
                        ITDeclaration.financial_year == financial_year
                    ).first()
                    
                    if not existing_declaration:
                        declaration = ITDeclaration(**declaration_data)
                        db.add(declaration)
                        created_count += 1
            
            db.commit()
            logger.info(f"[OK] Created {created_count} sample IT declaration records")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample IT declaration data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_biometric_code_sample_data():
    """Create sample biometric code data"""
    logger.info("\nStep 20: Creating sample biometric code data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee
            from app.models.business import Business
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get active employees
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).all()
            
            if not employees:
                logger.info("No employees found for biometric code data creation")
                return True
            
            # Biometric code configurations
            biometric_codes = [
                "BIO001", "BIO002", "BIO003", "BIO004", "BIO005",
                "BIO006", "BIO007", "BIO008", "BIO009", "BIO010"
            ]
            
            # Update employees with biometric codes
            updated_count = 0
            
            for i, employee in enumerate(employees):
                # Only update if biometric code is not already set
                if not employee.biometric_code:
                    biometric_code = biometric_codes[i % len(biometric_codes)]
                    employee.biometric_code = f"{biometric_code}_{employee.employee_code}"
                    employee.updated_at = datetime.now()
                    updated_count += 1
            
            db.commit()
            logger.info(f"[OK] Updated {updated_count} employees with biometric codes")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample biometric code data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_bank_details_sample_data():
    """Create sample bank details data for employees"""
    logger.info("\nStep 21: Creating sample bank details data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee, EmployeeProfile
            from app.models.business import Business
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get active employees
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).all()
            
            if not employees:
                logger.info("No employees found for bank details data creation")
                return True
            
            # Sample bank details configurations
            bank_details_configs = [
                {
                    "bank_name": "State Bank of India",
                    "bank_ifsc_code": "SBIN0017895",
                    "bank_branch": "Hyderabad Main Branch"
                },
                {
                    "bank_name": "HDFC Bank",
                    "bank_ifsc_code": "HDFC0002348",
                    "bank_branch": "Banjara Hills Branch"
                },
                {
                    "bank_name": "ICICI Bank",
                    "bank_ifsc_code": "ICIC0001234",
                    "bank_branch": "Jubilee Hills Branch"
                },
                {
                    "bank_name": "Axis Bank",
                    "bank_ifsc_code": "AXIS0001567",
                    "bank_branch": "Gachibowli Branch"
                },
                {
                    "bank_name": "Canara Bank",
                    "bank_ifsc_code": "CNRB0013494",
                    "bank_branch": "Madhapur Branch"
                },
                {
                    "bank_name": "Punjab National Bank",
                    "bank_ifsc_code": "PUNB0123456",
                    "bank_branch": "Kondapur Branch"
                },
                {
                    "bank_name": "Union Bank of India",
                    "bank_ifsc_code": "UBIN0567890",
                    "bank_branch": "Hitech City Branch"
                },
                {
                    "bank_name": "Bank of Baroda",
                    "bank_ifsc_code": "BARB0987654",
                    "bank_branch": "Kukatpally Branch"
                }
            ]
            
            # Create or update employee profiles with bank details
            updated_count = 0
            created_count = 0
            
            for i, employee in enumerate(employees):
                # Get or create employee profile
                profile = db.query(EmployeeProfile).filter(
                    EmployeeProfile.employee_id == employee.id
                ).first()
                
                if not profile:
                    profile = EmployeeProfile(employee_id=employee.id)
                    db.add(profile)
                    created_count += 1
                
                # Only update if bank details are not already set
                if not profile.bank_account_number:
                    bank_config = bank_details_configs[i % len(bank_details_configs)]
                    
                    # Generate realistic account numbers
                    account_number = f"{40579942875 + i:011d}"
                    
                    profile.bank_name = bank_config["bank_name"]
                    profile.bank_ifsc_code = bank_config["bank_ifsc_code"]
                    profile.bank_account_number = account_number
                    profile.bank_branch = bank_config["bank_branch"]
                    
                    # Add vaccination status if not already set (70% vaccinated, 30% not vaccinated)
                    if not profile.vaccination_status:
                        vaccination_statuses = ["Vaccinated", "Not Vaccinated"]
                        vaccination_weights = [0.7, 0.3]  # 70% vaccinated
                        profile.vaccination_status = random.choices(vaccination_statuses, weights=vaccination_weights)[0]
                    
                    # Add workman status if not already set (60% installed, 40% not installed)
                    if profile.workman_installed is None:
                        workman_installed = random.choices([True, False], weights=[0.6, 0.4])[0]
                        profile.workman_installed = workman_installed
                        
                        if workman_installed:
                            # Random workman version for installed users
                            versions = ["7.5.33", "7.5.32", "7.5.31", "7.4.28", "7.4.27"]
                            profile.workman_version = random.choice(versions)
                            
                            # Random last seen within last 30 days
                            days_ago = random.randint(0, 30)
                            hours_ago = random.randint(0, 23)
                            minutes_ago = random.randint(0, 59)
                            profile.workman_last_seen = datetime.now() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
                        else:
                            profile.workman_version = "Not Installed"
                            profile.workman_last_seen = None
                    
                    profile.updated_at = datetime.now()
                    
                    # Update employee audit fields
                    employee.updated_at = datetime.now()
                    updated_count += 1
            
            db.commit()
            logger.info(f"[OK] Created {created_count} employee profiles")
            logger.info(f"[OK] Updated {updated_count} employees with bank details")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample bank details data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_hrmanagement_sample_data():
    """Create HR management sample data for notifications, letters, alerts, etc."""
    logger.info("\nStep 22: Creating HR management sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.hrmanagement import (
                Notification, Letter, Alert, Greeting, HRPolicy, GreetingConfiguration,
                NotificationStatus, NotificationPriority, LetterType,
                AlertType, GreetingType, PolicyStatus
            )
            
            # Check if sample data already exists
            existing_notifications = db.query(Notification).count()
            
            if existing_notifications > 0:
                logger.info("HR management sample data already exists, skipping...")
                return True
            
            # Get businesses and employees
            businesses = db.query(Business).all()
            if not businesses:
                logger.warning("No businesses found, skipping HR management sample data")
                return True
            
            business = businesses[0]
            
            # Get active employees
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == "active"
            ).limit(10).all()
            
            if not employees:
                logger.warning("No active employees found, skipping HR management sample data")
                return True
            
            # 1. CREATE NOTIFICATIONS
            notification_data = [
                {
                    "title": "New Company Policy Update",
                    "content": "We have updated our remote work policy to provide more flexibility for employees. Please review the new guidelines in the HR portal.",
                    "priority": NotificationPriority.HIGH,
                    "status": NotificationStatus.PUBLISHED,
                    "publish_date": datetime.now() - timedelta(days=2),
                    "expiry_date": datetime.now() + timedelta(days=30),
                    "is_pinned": True
                },
                {
                    "title": "System Maintenance Scheduled",
                    "content": "The HRMS system will undergo maintenance on Saturday from 2 AM to 6 AM. Please complete any pending tasks before this time.",
                    "priority": NotificationPriority.MEDIUM,
                    "status": NotificationStatus.PUBLISHED,
                    "publish_date": datetime.now() - timedelta(days=1),
                    "expiry_date": datetime.now() + timedelta(days=7)
                },
                {
                    "title": "Annual Performance Review Cycle",
                    "content": "The annual performance review cycle has begun. All employees are requested to complete their self-assessments by the end of this month.",
                    "priority": NotificationPriority.HIGH,
                    "status": NotificationStatus.PUBLISHED,
                    "publish_date": datetime.now() - timedelta(hours=6),
                    "expiry_date": datetime.now() + timedelta(days=45),
                    "is_pinned": True
                },
                {
                    "title": "Holiday Calendar Updated",
                    "content": "The holiday calendar for next year has been updated. Please check the new dates and plan your leaves accordingly.",
                    "priority": NotificationPriority.LOW,
                    "status": NotificationStatus.PUBLISHED,
                    "publish_date": datetime.now() - timedelta(hours=12),
                    "expiry_date": datetime.now() + timedelta(days=60)
                },
                {
                    "title": "New Employee Onboarding Session",
                    "content": "We will be conducting an onboarding session for new joiners next week. HR team will share the schedule soon.",
                    "priority": NotificationPriority.MEDIUM,
                    "status": NotificationStatus.PUBLISHED,
                    "publish_date": datetime.now() - timedelta(hours=18),
                    "expiry_date": datetime.now() + timedelta(days=14)
                },
                {
                    "title": "IT Security Training Mandatory",
                    "content": "All employees must complete the IT security training module by the end of this week. This is mandatory for compliance.",
                    "priority": NotificationPriority.URGENT,
                    "status": NotificationStatus.PUBLISHED,
                    "publish_date": datetime.now() - timedelta(days=3),
                    "expiry_date": datetime.now() + timedelta(days=5),
                    "is_pinned": True
                },
                {
                    "title": "Office Cafeteria Menu Update",
                    "content": "The cafeteria has introduced new healthy meal options. Check out the updated menu on the notice board.",
                    "priority": NotificationPriority.LOW,
                    "status": NotificationStatus.PUBLISHED,
                    "publish_date": datetime.now() - timedelta(days=1),
                    "expiry_date": datetime.now() + timedelta(days=30)
                },
                {
                    "title": "Quarterly Town Hall Meeting",
                    "content": "Join us for the quarterly town hall meeting this Friday at 3 PM in the main conference room. CEO will share company updates.",
                    "priority": NotificationPriority.HIGH,
                    "status": NotificationStatus.PUBLISHED,
                    "publish_date": datetime.now() - timedelta(hours=4),
                    "expiry_date": datetime.now() + timedelta(days=3),
                    "is_pinned": True
                }
            ]
            
            for i, notif_data in enumerate(notification_data):
                creator = employees[i % len(employees)]
                
                notification = Notification(
                    business_id=business.id,
                    created_by=creator.id,
                    title=notif_data["title"],
                    content=notif_data["content"],
                    priority=notif_data["priority"],
                    status=notif_data["status"],
                    publish_date=notif_data["publish_date"],
                    expiry_date=notif_data.get("expiry_date"),
                    target_all_employees=True,
                    is_pinned=notif_data.get("is_pinned", False),
                    view_count=random.randint(5, 50),
                    created_at=notif_data["publish_date"]
                )
                
                db.add(notification)
            
            # 2. CREATE LETTERS
            letter_data = [
                {
                    "letter_type": LetterType.APPOINTMENT,
                    "subject": "Appointment Letter - Software Developer",
                    "content": "We are pleased to offer you the position of Software Developer at our company.",
                    "employee_id": employees[0].id
                },
                {
                    "letter_type": LetterType.CONFIRMATION,
                    "subject": "Confirmation of Employment",
                    "content": "We are happy to confirm your employment after successful completion of probation period.",
                    "employee_id": employees[min(1, len(employees)-1)].id
                },
                {
                    "letter_type": LetterType.PROMOTION,
                    "subject": "Promotion to Senior Developer",
                    "content": "Congratulations! You have been promoted to Senior Developer effective immediately.",
                    "employee_id": employees[min(2, len(employees)-1)].id
                },
                {
                    "letter_type": LetterType.APPRECIATION,
                    "subject": "Letter of Appreciation",
                    "content": "We appreciate your outstanding contribution to the recent project success.",
                    "employee_id": employees[min(3, len(employees)-1)].id
                }
            ]
            
            for i, letter_data_item in enumerate(letter_data):
                creator = employees[0]  # HR creates letters
                letter_count = i + 1
                
                letter = Letter(
                    business_id=business.id,
                    employee_id=letter_data_item["employee_id"],
                    created_by=creator.id,
                    letter_type=letter_data_item["letter_type"],
                    letter_number=f"HR/{letter_data_item['letter_type'].value.upper()}/{datetime.now().year}/{letter_count:04d}",
                    subject=letter_data_item["subject"],
                    content=letter_data_item["content"],
                    letter_date=date.today() - timedelta(days=i+1),
                    is_generated=True,
                    is_sent=i < 2,  # First 2 letters are sent
                    sent_date=datetime.now() - timedelta(days=i) if i < 2 else None,
                    letterhead_used=True
                )
                
                db.add(letter)
            
            # 3. CREATE ALERTS
            alert_data = [
                {
                    "alert_type": AlertType.DEADLINE,
                    "title": "Timesheet Submission Deadline",
                    "message": "Please submit your timesheets by end of day today.",
                    "expiry_date": datetime.now() + timedelta(hours=8),
                    "is_popup": True,
                    "acknowledgment_required": True
                },
                {
                    "alert_type": AlertType.SYSTEM,
                    "title": "System Update Available",
                    "message": "A new system update is available. Please update your browser for better performance.",
                    "expiry_date": datetime.now() + timedelta(days=7),
                    "is_popup": False
                },
                {
                    "alert_type": AlertType.SECURITY,
                    "title": "Password Expiry Warning",
                    "message": "Your password will expire in 3 days. Please change it to avoid account lockout.",
                    "expiry_date": datetime.now() + timedelta(days=3),
                    "is_popup": True,
                    "acknowledgment_required": True
                },
                # Attendance-based alerts for frontend compatibility
                {
                    "alert_type": AlertType.GENERAL,
                    "title": "Excessive Absence Alert",
                    "message": "Alert for employees with excessive absences",
                    "alert_name": "Excessive Absence Alert",
                    "condition": "Absent",
                    "days": 3,
                    "send_letter": "Warning",
                    "check_every": "day",
                    "expiry_date": None,
                    "is_popup": False,
                    "acknowledgment_required": False
                },
                {
                    "alert_type": AlertType.GENERAL,
                    "title": "Late Coming Alert",
                    "message": "Alert for employees with frequent late arrivals",
                    "alert_name": "Late Coming Alert",
                    "condition": "Late",
                    "days": 5,
                    "send_letter": "Notice",
                    "check_every": "week",
                    "expiry_date": None,
                    "is_popup": False,
                    "acknowledgment_required": False
                }
            ]
            
            for alert_data_item in alert_data:
                creator = employees[0]  # HR creates alerts
                
                alert = Alert(
                    business_id=business.id,
                    created_by=creator.id,
                    alert_type=alert_data_item["alert_type"],
                    title=alert_data_item["title"],
                    message=alert_data_item["message"],
                    alert_date=datetime.now(),
                    expiry_date=alert_data_item["expiry_date"],
                    is_popup=alert_data_item.get("is_popup", False),
                    is_email=False,
                    is_sms=False,
                    target_all_employees=True,
                    acknowledgment_required=alert_data_item.get("acknowledgment_required", False),
                    is_active=True,
                    
                    # Attendance-specific fields
                    alert_name=alert_data_item.get("alert_name"),
                    condition=alert_data_item.get("condition"),
                    days=alert_data_item.get("days"),
                    send_letter=alert_data_item.get("send_letter"),
                    check_every=alert_data_item.get("check_every", "day")
                )
                
                db.add(alert)
            
            # 4. CREATE GREETINGS
            greeting_data = [
                {
                    "greeting_type": GreetingType.BIRTHDAY,
                    "title": "Happy Birthday!",
                    "message": "Wishing you a very happy birthday and a wonderful year ahead!",
                    "employee_id": employees[min(4, len(employees)-1)].id if len(employees) > 4 else employees[0].id,
                    "greeting_date": date.today()
                },
                {
                    "greeting_type": GreetingType.ANNIVERSARY,
                    "title": "Work Anniversary Celebration",
                    "message": "Congratulations on completing 2 years with us! Thank you for your dedication.",
                    "employee_id": employees[min(5, len(employees)-1)].id if len(employees) > 5 else employees[min(1, len(employees)-1)].id,
                    "greeting_date": date.today() - timedelta(days=1)
                },
                {
                    "greeting_type": GreetingType.ACHIEVEMENT,
                    "title": "Outstanding Performance Award",
                    "message": "Congratulations on winning the Employee of the Month award!",
                    "employee_id": employees[min(6, len(employees)-1)].id if len(employees) > 6 else employees[min(2, len(employees)-1)].id,
                    "greeting_date": date.today() - timedelta(days=2)
                }
            ]
            
            for greeting_data_item in greeting_data:
                creator = employees[0]  # HR creates greetings
                
                greeting = Greeting(
                    business_id=business.id,
                    employee_id=greeting_data_item["employee_id"],
                    created_by=creator.id,
                    greeting_type=greeting_data_item["greeting_type"],
                    title=greeting_data_item["title"],
                    message=greeting_data_item["message"],
                    greeting_date=greeting_data_item["greeting_date"],
                    display_from=datetime.combine(greeting_data_item["greeting_date"], datetime.min.time()),
                    display_until=datetime.combine(greeting_data_item["greeting_date"] + timedelta(days=7), datetime.max.time()),
                    is_public=True,
                    show_on_dashboard=True,
                    send_notification=True,
                    like_count=random.randint(5, 25),
                    comment_count=random.randint(1, 8)
                )
                
                db.add(greeting)
            
            # 4.1. CREATE GREETING CONFIGURATIONS
            greeting_config_data = [
                {
                    "greeting_type": GreetingType.BIRTHDAY,
                    "is_enabled": True,
                    "send_to_managers": True,
                    "post_on_org_feed": True,
                    "send_email": True,
                    "send_push_notification": True,
                    "email_subject": "Happy Birthday!",
                    "message_template": "Happy Birthday, {{first_name}} {{last_name}}! Wishing you a joyful year ahead filled with success and happiness. [SUCCESS]",
                    "process_time": "07:00"
                },
                {
                    "greeting_type": GreetingType.ANNIVERSARY,
                    "is_enabled": False,
                    "send_to_managers": True,
                    "post_on_org_feed": True,
                    "send_email": True,
                    "send_push_notification": True,
                    "email_subject": "Work Anniversary Congratulations",
                    "message_template": "Congratulations {{first_name}} {{last_name}} on your work anniversary! Thank you for your dedication and contribution to our team.",
                    "process_time": "07:00"
                }
            ]
            
            for config_data in greeting_config_data:
                creator = employees[0]  # HR creates configurations
                
                greeting_config = GreetingConfiguration(
                    business_id=business.id,
                    created_by=creator.id,
                    greeting_type=config_data["greeting_type"],
                    is_enabled=config_data["is_enabled"],
                    send_to_managers=config_data["send_to_managers"],
                    post_on_org_feed=config_data["post_on_org_feed"],
                    send_email=config_data["send_email"],
                    send_push_notification=config_data["send_push_notification"],
                    email_subject=config_data["email_subject"],
                    message_template=config_data["message_template"],
                    process_time=config_data["process_time"]
                )
                
                db.add(greeting_config)
            
            # 5. CREATE HR POLICIES
            policy_data = [
                {
                    "policy_name": "Leave Policy",
                    "policy_code": "POL-2024-001",
                    "category": "Leave Management",
                    "description": "Comprehensive leave policy covering all types of leaves",
                    "content": "This policy outlines the leave entitlements, application process, and approval workflow for all employees.",
                    "version": "2.0",
                    "effective_date": date.today() - timedelta(days=90),
                    "review_date": date.today() + timedelta(days=275),
                    "is_mandatory_reading": True,
                    "acknowledgment_required": True
                },
                {
                    "policy_name": "Code of Conduct",
                    "policy_code": "POL-2024-002",
                    "category": "Behavioral",
                    "description": "Employee code of conduct and ethics guidelines",
                    "content": "This policy defines the expected behavior and ethical standards for all employees.",
                    "version": "1.5",
                    "effective_date": date.today() - timedelta(days=180),
                    "review_date": date.today() + timedelta(days=185),
                    "is_mandatory_reading": True,
                    "acknowledgment_required": True
                },
                {
                    "policy_name": "Remote Work Policy",
                    "policy_code": "POL-2024-003",
                    "category": "Work Arrangement",
                    "description": "Guidelines for remote work arrangements and expectations",
                    "content": "This policy covers the eligibility, application process, and guidelines for remote work.",
                    "version": "1.0",
                    "effective_date": date.today() - timedelta(days=30),
                    "review_date": date.today() + timedelta(days=335),
                    "is_mandatory_reading": False,
                    "acknowledgment_required": False
                }
            ]
            
            for policy_data_item in policy_data:
                creator = employees[0]  # HR creates policies
                
                policy = HRPolicy(
                    business_id=business.id,
                    created_by=creator.id,
                    policy_name=policy_data_item["policy_name"],
                    policy_code=policy_data_item["policy_code"],
                    category=policy_data_item["category"],
                    description=policy_data_item["description"],
                    content=policy_data_item["content"],
                    version=policy_data_item["version"],
                    status=PolicyStatus.ACTIVE,
                    effective_date=policy_data_item["effective_date"],
                    review_date=policy_data_item["review_date"],
                    is_mandatory_reading=policy_data_item["is_mandatory_reading"],
                    acknowledgment_required=policy_data_item["acknowledgment_required"],
                    applies_to_all=True,
                    approval_date=datetime.now() - timedelta(days=5),
                    approved_by=creator.id
                )
                
                db.add(policy)
            
            db.commit()
            logger.info("[OK] Created HR management sample data: 8 notifications, 4 letters, 5 alerts, 3 greetings, 2 greeting configs, 3 policies")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create HR management sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_payroll_periods_sample_data():
    """Create sample payroll periods data"""
    logger.info("\nStep 23: Creating payroll periods sample data...")
    
    try:
        with get_db_context() as db:
            # Get the first business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found for payroll periods")
                return False
            
            # Check if sample data already exists for this business
            existing_periods = db.query(PayrollPeriod).filter(PayrollPeriod.business_id == business.id).first()
            if existing_periods:
                logger.info("Payroll periods sample data already exists, skipping...")
                return True
            
            # Create sample payroll periods
            periods_data = [
                {
                    "name": "DEC-2025",
                    "start_date": date(2025, 12, 1),
                    "end_date": date(2025, 12, 31),
                    "status": PayrollPeriodStatus.CLOSED.value,
                    "custom_days_enabled": False,
                    "custom_days": None,
                    "different_month": False,
                    "calendar_month": None,
                    "calendar_year": None,
                    "reporting_enabled": False
                },
                {
                    "name": "NOV-2025",
                    "start_date": date(2025, 11, 1),
                    "end_date": date(2025, 11, 30),
                    "status": PayrollPeriodStatus.CLOSED.value,
                    "custom_days_enabled": False,
                    "custom_days": None,
                    "different_month": False,
                    "calendar_month": None,
                    "calendar_year": None,
                    "reporting_enabled": False
                },
                {
                    "name": "OCT-2025",
                    "start_date": date(2025, 10, 1),
                    "end_date": date(2025, 10, 31),
                    "status": PayrollPeriodStatus.OPEN.value,
                    "custom_days_enabled": False,
                    "custom_days": None,
                    "different_month": False,
                    "calendar_month": None,
                    "calendar_year": None,
                    "reporting_enabled": False
                },
                {
                    "name": "SEP-2025",
                    "start_date": date(2025, 9, 1),
                    "end_date": date(2025, 9, 30),
                    "status": PayrollPeriodStatus.OPEN.value,
                    "custom_days_enabled": True,
                    "custom_days": 28,
                    "different_month": False,
                    "calendar_month": None,
                    "calendar_year": None,
                    "reporting_enabled": True
                },
                {
                    "name": "AUG-2025",
                    "start_date": date(2025, 8, 1),
                    "end_date": date(2025, 8, 31),
                    "status": PayrollPeriodStatus.PROCESSING.value,
                    "custom_days_enabled": False,
                    "custom_days": None,
                    "different_month": True,
                    "calendar_month": "Jul",
                    "calendar_year": 2025,
                    "reporting_enabled": True
                }
            ]
            
            created_periods = []
            for period_data in periods_data:
                period = PayrollPeriod(
                    business_id=business.id,
                    name=period_data["name"],
                    start_date=period_data["start_date"],
                    end_date=period_data["end_date"],
                    status=period_data["status"],
                    custom_days_enabled=period_data["custom_days_enabled"],
                    custom_days=period_data["custom_days"],
                    different_month=period_data["different_month"],
                    calendar_month=period_data["calendar_month"],
                    calendar_year=period_data["calendar_year"],
                    reporting_enabled=period_data["reporting_enabled"]
                )
                db.add(period)
                created_periods.append(period)
            
            db.commit()
            logger.info(f"[OK] Created {len(created_periods)} sample payroll periods")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create payroll periods sample data: {e}")
        return False


def create_leave_encashment_sample_data():
    """Create sample leave encashment data for testing"""
    logger.info("\nStep 24: Creating leave encashment sample data...")
    
    try:
        with get_db_context() as db:
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get superadmin user for created_by
            superadmin = db.query(User).filter(User.email == "superadmin@levitica.com").first()
            if not superadmin:
                logger.error("No superadmin user found")
                return False
            
            # Get employees
            employees = db.query(Employee).filter(Employee.business_id == business.id).limit(10).all()
            if not employees:
                logger.info("No employees found, skipping leave encashment sample data")
                return True
            
            # Get payroll periods
            periods = db.query(PayrollPeriod).filter(PayrollPeriod.business_id == business.id).all()
            if not periods:
                logger.error("No payroll periods found")
                return False
            
            # Get leave types
            leave_types = db.query(LeaveType).filter(LeaveType.business_id == business.id).all()
            if not leave_types:
                logger.error("No leave types found")
                return False
            
            from app.models.payroll import LeaveEncashment
            
            # Create sample leave encashments
            encashments_data = []
            
            for i, employee in enumerate(employees[:5]):  # Create for first 5 employees
                leave_type = random.choice(leave_types)
                period = random.choice(periods)
                
                # Generate realistic encashment data
                leave_balance = Decimal(str(random.uniform(20, 35)))  # 20-35 days balance
                balance_above = Decimal('5.0')  # Keep 5 days minimum
                encashment_days = max(Decimal('0'), leave_balance - balance_above)
                
                # Calculate daily salary - use a default value since salary structure varies
                daily_salary = Decimal(str(random.uniform(800, 1500)))  # Random daily salary
                encashment_amount = encashment_days * daily_salary
                
                encashment_data = {
                    "business_id": business.id,
                    "period_id": period.id,
                    "employee_id": employee.id,
                    "created_by": superadmin.id,  # Use superadmin user ID
                    "leave_type": leave_type.name,
                    "leave_balance": leave_balance,
                    "encashment_days": encashment_days,
                    "daily_salary": daily_salary,
                    "encashment_amount": encashment_amount,
                    "payment_period": period.start_date,
                    "balance_as_on": period.start_date,
                    "balance_above": balance_above,
                    "salary_components": ["basicSalary", "houseRentAllowance"],
                    "is_processed": i < 3,  # First 3 are processed
                    "processed_date": datetime.now() if i < 3 else None
                }
                encashments_data.append(encashment_data)
            
            # Create additional unprocessed encashments for testing
            for i, employee in enumerate(employees[5:8]):  # Next 3 employees
                leave_type = random.choice(leave_types)
                period = periods[0]  # Use first period
                
                leave_balance = Decimal(str(random.uniform(15, 30)))
                balance_above = Decimal('3.0')
                encashment_days = max(Decimal('0'), leave_balance - balance_above)
                
                daily_salary = Decimal(str(random.uniform(1000, 2000)))
                encashment_amount = encashment_days * daily_salary
                
                encashment_data = {
                    "business_id": business.id,
                    "period_id": period.id,
                    "employee_id": employee.id,
                    "created_by": superadmin.id,  # Use superadmin user ID
                    "leave_type": leave_type.name,
                    "leave_balance": leave_balance,
                    "encashment_days": encashment_days,
                    "daily_salary": daily_salary,
                    "encashment_amount": encashment_amount,
                    "payment_period": period.start_date,
                    "balance_as_on": period.start_date,
                    "balance_above": balance_above,
                    "salary_components": ["basicSalary", "specialAllowance", "medicalAllowance"],
                    "is_processed": False,
                    "processed_date": None
                }
                encashments_data.append(encashment_data)
            
            # Insert encashments
            created_encashments = []
            for encashment_data in encashments_data:
                encashment = LeaveEncashment(**encashment_data)
                db.add(encashment)
                created_encashments.append(encashment)
            
            db.commit()
            logger.info(f"[OK] Created {len(created_encashments)} sample leave encashments")
            
            # Log summary
            processed_count = sum(1 for e in created_encashments if e.is_processed)
            pending_count = len(created_encashments) - processed_count
            total_amount = sum(float(e.encashment_amount) for e in created_encashments)
            
            logger.info(f"  - Processed: {processed_count}")
            logger.info(f"  - Pending: {pending_count}")
            logger.info(f"  - Total Amount: ${total_amount:,.2f}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create leave encashment sample data: {e}")
        return False


def create_payroll_recalculation_sample_data():
    """Create sample payroll recalculation data for testing"""
    logger.info("\nStep 25: Creating payroll recalculation sample data...")
    
    try:
        with get_db_context() as db:
            # Import PayrollRecalculation model
            from app.models.payroll import PayrollRecalculation
            
            # Check if sample data already exists
            existing_recalc = db.query(PayrollRecalculation).first()
            if existing_recalc:
                logger.info("Payroll recalculation sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get employees
            employees = db.query(Employee).filter(Employee.business_id == business.id).all()
            if not employees:
                logger.info("No employees found, skipping payroll recalculation sample data")
                return True
            
            # Get payroll periods
            periods = db.query(PayrollPeriod).filter(PayrollPeriod.business_id == business.id).all()
            if not periods:
                logger.error("No payroll periods found")
                return False
            
            # Get superadmin user for created_by
            superadmin = db.query(User).filter(User.role == UserRole.SUPERADMIN).first()
            if not superadmin:
                logger.error("No superadmin found")
                return False
            
            # Get first employee for created_by
            first_employee = employees[0]
            
            # Create sample recalculation records
            recalculations_data = [
                {
                    "period_id": periods[0].id,
                    "date_from": periods[0].start_date,
                    "date_to": periods[0].end_date,
                    "all_employees": True,
                    "selected_employees": None,
                    "status": "completed",
                    "progress_percentage": 100,
                    "total_employees": len(employees),
                    "processed_employees": len(employees),
                    "failed_employees": 0,
                    "started_at": datetime.now() - timedelta(hours=2),
                    "completed_at": datetime.now() - timedelta(hours=1, minutes=30),
                    "success_message": "Attendance recalculation successfully finished",
                    "error_message": None
                },
                {
                    "period_id": periods[1].id if len(periods) > 1 else periods[0].id,
                    "date_from": date(2025, 11, 1),
                    "date_to": date(2025, 11, 15),
                    "all_employees": False,
                    "selected_employees": [employees[0].id, employees[1].id] if len(employees) > 1 else [employees[0].id],
                    "status": "completed",
                    "progress_percentage": 100,
                    "total_employees": 2 if len(employees) > 1 else 1,
                    "processed_employees": 2 if len(employees) > 1 else 1,
                    "failed_employees": 0,
                    "started_at": datetime.now() - timedelta(days=1, hours=3),
                    "completed_at": datetime.now() - timedelta(days=1, hours=2, minutes=45),
                    "success_message": "Recalculation completed successfully for 2 employees",
                    "error_message": None
                },
                {
                    "period_id": periods[2].id if len(periods) > 2 else periods[0].id,
                    "date_from": date(2025, 10, 1),
                    "date_to": date(2025, 10, 10),
                    "all_employees": True,
                    "selected_employees": None,
                    "status": "failed",
                    "progress_percentage": 45,
                    "total_employees": len(employees),
                    "processed_employees": int(len(employees) * 0.4),
                    "failed_employees": int(len(employees) * 0.6),
                    "started_at": datetime.now() - timedelta(days=2, hours=1),
                    "completed_at": datetime.now() - timedelta(days=2, hours=0, minutes=30),
                    "success_message": None,
                    "error_message": "Recalculation failed due to data validation errors"
                },
                {
                    "period_id": periods[0].id,
                    "date_from": date(2025, 12, 15),
                    "date_to": date(2025, 12, 25),
                    "all_employees": False,
                    "selected_employees": [employees[0].id],
                    "status": "running",
                    "progress_percentage": 67,
                    "total_employees": 1,
                    "processed_employees": 0,
                    "failed_employees": 0,
                    "started_at": datetime.now() - timedelta(minutes=10),
                    "completed_at": None,
                    "success_message": "Attendance recalculation successfully finished",
                    "error_message": None
                },
                {
                    "period_id": periods[1].id if len(periods) > 1 else periods[0].id,
                    "date_from": date(2025, 11, 20),
                    "date_to": date(2025, 11, 30),
                    "all_employees": True,
                    "selected_employees": None,
                    "status": "pending",
                    "progress_percentage": 0,
                    "total_employees": len(employees),
                    "processed_employees": 0,
                    "failed_employees": 0,
                    "started_at": None,
                    "completed_at": None,
                    "success_message": None,
                    "error_message": None
                }
            ]
            
            created_recalculations = []
            for recalc_data in recalculations_data:
                recalculation = PayrollRecalculation(
                    business_id=business.id,
                    period_id=recalc_data["period_id"],
                    created_by=first_employee.id,
                    date_from=recalc_data["date_from"],
                    date_to=recalc_data["date_to"],
                    all_employees=recalc_data["all_employees"],
                    selected_employees=recalc_data["selected_employees"],
                    status=recalc_data["status"],
                    progress_percentage=recalc_data["progress_percentage"],
                    total_employees=recalc_data["total_employees"],
                    processed_employees=recalc_data["processed_employees"],
                    failed_employees=recalc_data["failed_employees"],
                    started_at=recalc_data["started_at"],
                    completed_at=recalc_data["completed_at"],
                    success_message=recalc_data["success_message"],
                    error_message=recalc_data["error_message"]
                )
                db.add(recalculation)
                created_recalculations.append(recalculation)
            
            db.commit()
            logger.info(f"[OK] Created {len(created_recalculations)} sample payroll recalculation records")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create payroll recalculation sample data: {e}")
        return False


def create_statutory_bonus_sample_data():
    """Create sample statutory bonus data for testing"""
    logger.info("\nStep 26: Creating statutory bonus sample data...")
    
    try:
        with get_db_context() as db:
            # Import StatutoryBonus model
            from app.models.payroll import StatutoryBonus
            
            # Check if sample data already exists
            existing_bonus = db.query(StatutoryBonus).first()
            if existing_bonus:
                logger.info("Statutory bonus sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get employees
            employees = db.query(Employee).filter(Employee.business_id == business.id).all()
            if not employees:
                logger.info("No employees found, skipping statutory bonus sample data")
                return True
            
            # Get payroll periods
            periods = db.query(PayrollPeriod).filter(PayrollPeriod.business_id == business.id).all()
            if not periods:
                logger.error("No payroll periods found")
                return False
            
            # Get first employee for created_by
            first_employee = employees[0]
            
            # Create sample statutory bonus records
            bonuses_data = [
                {
                    "period_id": periods[0].id,
                    "employee_id": employees[0].id,
                    "bonus_rate": Decimal('8.33'),
                    "eligibility_cutoff": Decimal('21000'),
                    "min_wages": Decimal('7000'),
                    "min_bonus": Decimal('100'),
                    "max_bonus": Decimal('0'),
                    "base_salary": Decimal('8700'),
                    "bonus_amount": Decimal('724.11'),
                    "salary_components": ["basic", "hra"],
                    "is_processed": True,
                    "processed_date": datetime.now() - timedelta(days=5)
                },
                {
                    "period_id": periods[0].id,
                    "employee_id": employees[1].id if len(employees) > 1 else employees[0].id,
                    "bonus_rate": Decimal('8.33'),
                    "eligibility_cutoff": Decimal('21000'),
                    "min_wages": Decimal('7000'),
                    "min_bonus": Decimal('100'),
                    "max_bonus": Decimal('0'),
                    "base_salary": Decimal('12000'),
                    "bonus_amount": Decimal('999.60'),
                    "salary_components": ["basic", "hra", "sa"],
                    "is_processed": True,
                    "processed_date": datetime.now() - timedelta(days=5)
                },
                {
                    "period_id": periods[1].id if len(periods) > 1 else periods[0].id,
                    "employee_id": employees[2].id if len(employees) > 2 else employees[0].id,
                    "bonus_rate": Decimal('8.33'),
                    "eligibility_cutoff": Decimal('21000'),
                    "min_wages": Decimal('7000'),
                    "min_bonus": Decimal('100'),
                    "max_bonus": Decimal('0'),
                    "base_salary": Decimal('15000'),
                    "bonus_amount": Decimal('1249.50'),
                    "salary_components": ["basic", "hra", "sa", "mda"],
                    "is_processed": False,
                    "processed_date": None
                },
                {
                    "period_id": periods[1].id if len(periods) > 1 else periods[0].id,
                    "employee_id": employees[3].id if len(employees) > 3 else employees[0].id,
                    "bonus_rate": Decimal('8.33'),
                    "eligibility_cutoff": Decimal('21000'),
                    "min_wages": Decimal('7000'),
                    "min_bonus": Decimal('100'),
                    "max_bonus": Decimal('0'),
                    "base_salary": Decimal('9500'),
                    "bonus_amount": Decimal('791.35'),
                    "salary_components": ["basic", "hra"],
                    "is_processed": False,
                    "processed_date": None
                },
                {
                    "period_id": periods[2].id if len(periods) > 2 else periods[0].id,
                    "employee_id": employees[4].id if len(employees) > 4 else employees[0].id,
                    "bonus_rate": Decimal('8.33'),
                    "eligibility_cutoff": Decimal('21000'),
                    "min_wages": Decimal('7000'),
                    "min_bonus": Decimal('100'),
                    "max_bonus": Decimal('0'),
                    "base_salary": Decimal('18000'),
                    "bonus_amount": Decimal('1499.40'),
                    "salary_components": ["basic", "hra", "sa", "mda", "conveyance"],
                    "is_processed": False,
                    "processed_date": None
                },
                {
                    "period_id": periods[2].id if len(periods) > 2 else periods[0].id,
                    "employee_id": employees[5].id if len(employees) > 5 else employees[0].id,
                    "bonus_rate": Decimal('8.33'),
                    "eligibility_cutoff": Decimal('21000'),
                    "min_wages": Decimal('7000'),
                    "min_bonus": Decimal('100'),
                    "max_bonus": Decimal('0'),
                    "base_salary": Decimal('11000'),
                    "bonus_amount": Decimal('916.30'),
                    "salary_components": ["basic", "hra", "sa"],
                    "is_processed": False,
                    "processed_date": None
                }
            ]
            
            created_bonuses = []
            for bonus_data in bonuses_data:
                bonus = StatutoryBonus(
                    business_id=business.id,
                    period_id=bonus_data["period_id"],
                    employee_id=bonus_data["employee_id"],
                    created_by=first_employee.id,
                    bonus_rate=bonus_data["bonus_rate"],
                    eligibility_cutoff=bonus_data["eligibility_cutoff"],
                    min_wages=bonus_data["min_wages"],
                    min_bonus=bonus_data["min_bonus"],
                    max_bonus=bonus_data["max_bonus"],
                    base_salary=bonus_data["base_salary"],
                    bonus_amount=bonus_data["bonus_amount"],
                    salary_components=bonus_data["salary_components"],
                    is_processed=bonus_data["is_processed"],
                    processed_date=bonus_data["processed_date"]
                )
                db.add(bonus)
                created_bonuses.append(bonus)
            
            db.commit()
            
            # Calculate statistics
            processed_count = sum(1 for b in created_bonuses if b.is_processed)
            pending_count = len(created_bonuses) - processed_count
            total_amount = sum(float(b.bonus_amount) for b in created_bonuses)
            
            logger.info(f"[OK] Created {len(created_bonuses)} sample statutory bonus records")
            logger.info(f"  - Processed: {processed_count}")
            logger.info(f"  - Pending: {pending_count}")
            logger.info(f"  - Total Amount: ${total_amount:,.2f}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create statutory bonus sample data: {e}")
        return False


def create_esi_settings_sample_data():
    """Create sample ESI settings data for testing"""
    logger.info("\nStep 26.1: Creating ESI settings sample data...")
    
    try:
        with get_db_context() as db:
            # Check if sample data already exists
            existing_esi = db.query(ESISettings).first()
            if existing_esi:
                logger.info("ESI settings sample data already exists, skipping...")
                return True
            
            # Get the first business
            from app.models.business import Business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found for ESI settings")
                return False
            
            # Create ESI Settings with default components
            default_components = [
                {"component_name": "Basic Salary - Basic", "component_code": "BASIC", "component_type": "Paid Days", "is_selected": True},
                {"component_name": "House Rent Allowance - HRA", "component_code": "HRA", "component_type": "Paid Days", "is_selected": True},
                {"component_name": "Special Allowance - SA", "component_code": "SA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Medical Allowance - MDA", "component_code": "MDA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Leave Encashment - Leave", "component_code": "LEAVE", "component_type": "Variable", "is_selected": False},
                {"component_name": "Bonus - Bonus", "component_code": "BONUS", "component_type": "Variable", "is_selected": False},
                {"component_name": "Conveyance Allowance - CA", "component_code": "CA", "component_type": "Paid Days", "is_selected": True},
                {"component_name": "Telephone Allowance - TA", "component_code": "TA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Gratuity - Graty", "component_code": "GRATY", "component_type": "Variable", "is_selected": False},
                {"component_name": "Loan - Loan", "component_code": "LOAN", "component_type": "System", "is_selected": False},
                {"component_name": "Overtime (Hours) - OT", "component_code": "OT", "component_type": "System", "is_selected": False},
                {"component_name": "Overtime (Days) - OTD", "component_code": "OTD", "component_type": "System", "is_selected": False},
                {"component_name": "Retention Bonus - RTB", "component_code": "RTB", "component_type": "System", "is_selected": False},
            ]
            
            # Create ESI Settings
            esi_settings = ESISettings(
                business_id=business.id,
                is_enabled=True,
                calculation_base="Gross Salary"
            )
            db.add(esi_settings)
            db.flush()
            
            # Add component mappings
            for comp in default_components:
                mapping = ESIComponentMapping(
                    esi_settings_id=esi_settings.id,
                    **comp
                )
                db.add(mapping)
            
            # Add sample ESI rates
            esi_rates = [
                {
                    "status": "Enabled",
                    "effective_from": date(2019, 7, 1),
                    "employee_rate": 0.75,
                    "employer_rate": 3.25,
                    "wage_limit": 21000.0
                },
                {
                    "status": "Enabled", 
                    "effective_from": date(2023, 4, 1),
                    "employee_rate": 0.75,
                    "employer_rate": 3.25,
                    "wage_limit": 21000.0
                }
            ]
            
            for rate_data in esi_rates:
                rate = ESIRateChange(
                    esi_settings_id=esi_settings.id,
                    **rate_data
                )
                db.add(rate)
            
            db.commit()
            
            logger.info(f"[OK] Created ESI settings for business {business.id}")
            logger.info(f"  - Components: {len(default_components)}")
            logger.info(f"  - Rate changes: {len(esi_rates)}")
            logger.info(f"  - Enabled components: {sum(1 for c in default_components if c['is_selected'])}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create ESI settings sample data: {e}")
        return False


def create_epf_settings_sample_data():
    """Create sample EPF settings data for testing"""
    logger.info("\nStep 26.2: Creating EPF settings sample data...")
    
    try:
        with get_db_context() as db:
            # Check if sample data already exists
            from app.models.epf_settings import EPFSettings, EPFComponentMapping, EPFRateChange
            existing_epf = db.query(EPFSettings).first()
            if existing_epf:
                logger.info("EPF settings sample data already exists, skipping...")
                return True
            
            # Get the first business
            from app.models.business import Business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found for EPF settings")
                return False
            
            # Create EPF Settings with default components
            default_components = [
                {"component_name": "Basic Salary - Basic", "component_code": "BASIC", "component_type": "Paid Days", "is_selected": True},
                {"component_name": "House Rent Allowance - HRA", "component_code": "HRA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Special Allowance - SA", "component_code": "SA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Medical Allowance - MDA", "component_code": "MDA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Leave Encashment - Leave", "component_code": "LEAVE", "component_type": "Variable", "is_selected": False},
                {"component_name": "Bonus - Bonus", "component_code": "BONUS", "component_type": "Variable", "is_selected": False},
                {"component_name": "Conveyance Allowance - CA", "component_code": "CA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Telephone Allowance - TA", "component_code": "TA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Gratuity - Graty", "component_code": "GRATY", "component_type": "Variable", "is_selected": False},
                {"component_name": "Loan - Loan", "component_code": "LOAN", "component_type": "System", "is_selected": False},
                {"component_name": "Overtime (Hours) - OT", "component_code": "OT", "component_type": "System", "is_selected": False},
                {"component_name": "Overtime (Days) - OTD", "component_code": "OTD", "component_type": "System", "is_selected": False},
                {"component_name": "Retention Bonus - RTB", "component_code": "RTB", "component_type": "System", "is_selected": False},
            ]
            
            # Create EPF Settings
            epf_settings = EPFSettings(
                business_id=business.id,
                is_enabled=True,
                calculation_base="Gross Salary"
            )
            db.add(epf_settings)
            db.flush()
            
            # Add component mappings
            for comp in default_components:
                mapping = EPFComponentMapping(
                    epf_settings_id=epf_settings.id,
                    **comp
                )
                db.add(mapping)
            
            # Add sample EPF rates
            epf_rates = [
                {
                    "status": "Enabled",
                    "effective_from": date(2019, 9, 1),
                    "emp_pf_rate_non_senior": 12.0,
                    "employer_pf_rate_non_senior": 12.0,
                    "pension_rate_non_senior": 8.33,
                    "emp_pf_rate_senior": 12.0,
                    "employer_pf_rate_senior": 12.0,
                    "pension_rate_senior": 0.0,
                    "edli_rate": 0.5,
                    "wage_ceiling": 15000.0,
                    "senior_age": 58
                },
                {
                    "status": "Enabled", 
                    "effective_from": date(2025, 5, 12),
                    "emp_pf_rate_non_senior": 12.0,
                    "employer_pf_rate_non_senior": 12.0,
                    "pension_rate_non_senior": 0.0,
                    "emp_pf_rate_senior": 12.0,
                    "employer_pf_rate_senior": 12.0,
                    "pension_rate_senior": 0.0,
                    "edli_rate": 0.5,
                    "wage_ceiling": 15000.0,
                    "senior_age": 58
                }
            ]
            
            for rate_data in epf_rates:
                rate = EPFRateChange(
                    epf_settings_id=epf_settings.id,
                    **rate_data
                )
                db.add(rate)
            
            db.commit()
            
            logger.info(f"[OK] Created EPF settings for business {business.id}")
            logger.info(f"  - Components: {len(default_components)}")
            logger.info(f"  - Rate changes: {len(epf_rates)}")
            logger.info(f"  - Enabled components: {sum(1 for c in default_components if c['is_selected'])}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create EPF settings sample data: {e}")
        return False


def create_professional_tax_sample_data():
    """Create sample Professional Tax settings data for testing"""
    logger.info("\nStep 26.3: Creating Professional Tax settings sample data...")
    
    try:
        with get_db_context() as db:
            # Check if sample data already exists
            from app.models.professional_tax import ProfessionalTaxSettings, PTComponentMapping, ProfessionalTaxRate
            existing_pt = db.query(ProfessionalTaxSettings).first()
            if existing_pt:
                logger.info("Professional Tax settings sample data already exists, skipping...")
                return True
            
            # Get the first business
            from app.models.business import Business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found for Professional Tax settings")
                return False
            
            # Create Professional Tax Settings with default components (matching frontend)
            default_components = [
                {"component_name": "Basic Salary (Basic)", "component_code": "BASIC", "component_type": "Payable Days", "is_selected": True},
                {"component_name": "House Rent Allowance (HRA)", "component_code": "HRA", "component_type": "Payable Days", "is_selected": True},
                {"component_name": "Special Allowance (SA)", "component_code": "SA", "component_type": "Payable Days", "is_selected": True},
                {"component_name": "Medical Allowance (MDA)", "component_code": "MDA", "component_type": "Payable Days", "is_selected": True},
                {"component_name": "Leave Encashment (Leave)", "component_code": "LEAVE", "component_type": "Variable", "is_selected": False},
                {"component_name": "Bonus (Bonus)", "component_code": "BONUS", "component_type": "Variable", "is_selected": False},
                {"component_name": "Conveyance Allowance (CA)", "component_code": "CA", "component_type": "Payable Days", "is_selected": False},
                {"component_name": "Telephone Allowance (TA)", "component_code": "TA", "component_type": "Payable Days", "is_selected": False},
                {"component_name": "Gratuity (Graty)", "component_code": "GRATY", "component_type": "Variable", "is_selected": True},
                {"component_name": "Loan (Loan)", "component_code": "LOAN", "component_type": "Variable", "is_selected": False},
            ]
            
            # Create Professional Tax Settings
            pt_settings = ProfessionalTaxSettings(
                business_id=business.id,
                is_enabled=True,
                calculation_base="Gross Salary"
            )
            db.add(pt_settings)
            db.flush()
            
            # Add component mappings (include business_id to satisfy NOT NULL constraint)
            for comp in default_components:
                mapping = PTComponentMapping(
                    business_id=business.id,
                    pt_settings_id=pt_settings.id,
                    **comp
                )
                db.add(mapping)
            
            # Add sample Professional Tax rates for major states
            pt_rates = [
                # Telangana State Professional Tax Rates
                {"state": "Telangana", "effective_from": date(2024, 1, 1), "salary_above": 0.0, "month": "All Months", "gender": "All Genders", "tax_amount": 0.0},
                {"state": "Telangana", "effective_from": date(2024, 1, 1), "salary_above": 15000.0, "month": "All Months", "gender": "All Genders", "tax_amount": 150.0},
                {"state": "Telangana", "effective_from": date(2024, 1, 1), "salary_above": 25000.0, "month": "All Months", "gender": "All Genders", "tax_amount": 200.0},
                
                # Andhra Pradesh State Professional Tax Rates
                {"state": "Andhra Pradesh", "effective_from": date(2024, 1, 1), "salary_above": 0.0, "month": "All Months", "gender": "All Genders", "tax_amount": 0.0},
                {"state": "Andhra Pradesh", "effective_from": date(2024, 1, 1), "salary_above": 10000.0, "month": "All Months", "gender": "All Genders", "tax_amount": 100.0},
                {"state": "Andhra Pradesh", "effective_from": date(2024, 1, 1), "salary_above": 15000.0, "month": "All Months", "gender": "All Genders", "tax_amount": 150.0},
                {"state": "Andhra Pradesh", "effective_from": date(2024, 1, 1), "salary_above": 25000.0, "month": "All Months", "gender": "All Genders", "tax_amount": 200.0},
                
                # Karnataka State Professional Tax Rates
                {"state": "Karnataka", "effective_from": date(2024, 1, 1), "salary_above": 0.0, "month": "All Months", "gender": "All Genders", "tax_amount": 0.0},
                {"state": "Karnataka", "effective_from": date(2024, 1, 1), "salary_above": 15000.0, "month": "All Months", "gender": "All Genders", "tax_amount": 200.0},
                
                # Maharashtra State Professional Tax Rates
                {"state": "Maharashtra", "effective_from": date(2024, 1, 1), "salary_above": 0.0, "month": "All Months", "gender": "All Genders", "tax_amount": 0.0},
                {"state": "Maharashtra", "effective_from": date(2024, 1, 1), "salary_above": 21000.0, "month": "All Months", "gender": "All Genders", "tax_amount": 175.0},
                
                # West Bengal State Professional Tax Rates (with monthly variations)
                {"state": "West Bengal", "effective_from": date(2024, 1, 1), "salary_above": 0.0, "month": "All Months", "gender": "All Genders", "tax_amount": 0.0},
                {"state": "West Bengal", "effective_from": date(2024, 1, 1), "salary_above": 10000.0, "month": "All Months", "gender": "All Genders", "tax_amount": 110.0},
                {"state": "West Bengal", "effective_from": date(2024, 1, 1), "salary_above": 15000.0, "month": "All Months", "gender": "All Genders", "tax_amount": 130.0},
                {"state": "West Bengal", "effective_from": date(2024, 1, 1), "salary_above": 25000.0, "month": "All Months", "gender": "All Genders", "tax_amount": 150.0},
                
                # Tamil Nadu State Professional Tax Rates
                {"state": "Tamil Nadu", "effective_from": date(2024, 1, 1), "salary_above": 0.0, "month": "All Months", "gender": "All Genders", "tax_amount": 0.0},
                {"state": "Tamil Nadu", "effective_from": date(2024, 1, 1), "salary_above": 21000.0, "month": "All Months", "gender": "All Genders", "tax_amount": 208.33},
            ]
            
            for rate_data in pt_rates:
                rate = ProfessionalTaxRate(
                    business_id=business.id,
                    pt_settings_id=pt_settings.id,
                    **rate_data
                )
                db.add(rate)
            
            db.commit()
            
            logger.info(f"[OK] Created Professional Tax settings for business {business.id}")
            logger.info(f"  - Components: {len(default_components)}")
            logger.info(f"  - Tax rates: {len(pt_rates)}")
            logger.info(f"  - Enabled components: {sum(1 for c in default_components if c['is_selected'])}")
            logger.info(f"  - States covered: {len(set(rate['state'] for rate in pt_rates))}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create Professional Tax settings sample data: {e}")
        return False


def create_lwf_sample_data():
    """Create sample Labour Welfare Fund (LWF) data for testing"""
    logger.info("\nStep 26.3.1: Creating LWF sample data...")
    
    try:
        with get_db_context() as db:
            # Check if sample data already exists
            from app.models.lwf_models import LWFSettings, LWFRate
            existing_lwf = db.query(LWFSettings).first()
            if existing_lwf:
                logger.info("LWF sample data already exists, skipping...")
                return True
            
            # Get the first business
            from app.models.business import Business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found for LWF")
                return False
            
            # Create LWF Settings
            lwf_settings = LWFSettings(
                business_id=business.id,
                is_enabled=False
            )
            db.add(lwf_settings)
            db.flush()
            
            # Add sample LWF rates for major states
            lwf_rates = [
                # Telangana State LWF Rates
                {
                    "state": "Telangana",
                    "effective_from": date(2024, 1, 1),
                    "employee_contribution": 20.0,
                    "employer_contribution": 40.0,
                    "frequency": "Half-Yearly",
                    "lwf_settings_id": lwf_settings.id,
                    "business_id": business.id
                },
                # Andhra Pradesh State LWF Rates
                {
                    "state": "Andhra Pradesh",
                    "effective_from": date(2024, 1, 1),
                    "employee_contribution": 20.0,
                    "employer_contribution": 40.0,
                    "frequency": "Half-Yearly",
                    "lwf_settings_id": lwf_settings.id,
                    "business_id": business.id
                },
                # Karnataka State LWF Rates
                {
                    "state": "Karnataka",
                    "effective_from": date(2024, 1, 1),
                    "employee_contribution": 20.0,
                    "employer_contribution": 20.0,
                    "frequency": "Half-Yearly",
                    "lwf_settings_id": lwf_settings.id,
                    "business_id": business.id
                },
                # Maharashtra State LWF Rates
                {
                    "state": "Maharashtra",
                    "effective_from": date(2024, 1, 1),
                    "employee_contribution": 6.0,
                    "employer_contribution": 12.0,
                    "frequency": "Monthly",
                    "lwf_settings_id": lwf_settings.id,
                    "business_id": business.id
                },
                # Tamil Nadu State LWF Rates
                {
                    "state": "Tamil Nadu",
                    "effective_from": date(2024, 1, 1),
                    "employee_contribution": 20.0,
                    "employer_contribution": 40.0,
                    "frequency": "Half-Yearly",
                    "lwf_settings_id": lwf_settings.id,
                    "business_id": business.id
                },
            ]
            
            for rate_data in lwf_rates:
                rate = LWFRate(**rate_data)
                db.add(rate)
            
            db.commit()
            
            logger.info(f"[OK] Created LWF settings for business {business.id}")
            logger.info(f"  - LWF enabled: {lwf_settings.is_enabled}")
            logger.info(f"  - LWF rates: {len(lwf_rates)}")
            logger.info(f"  - States covered: {len(set(rate['state'] for rate in lwf_rates))}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create LWF sample data: {e}")
        return False


def create_tax_settings_sample_data():
    """Create sample Tax settings data for testing"""
    logger.info("\nStep 26.4: Creating Tax settings sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.business import Business
            from app.models.tax_models import TDSSetting, FinancialYear, TaxRate
            
            # Check if sample data already exists
            existing_tds = db.query(TDSSetting).first()
            if existing_tds:
                logger.info("Tax settings sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Create TDS Settings
            tds_setting = TDSSetting(
                deduct_tds=False,
                business_id=business.id
            )
            db.add(tds_setting)
            
            # Create Financial Years
            financial_years = [
                FinancialYear(
                    year="2024-25",
                    open=True,
                    start_date=date(2024, 4, 1),
                    end_date=date(2025, 3, 31),
                    business_id=business.id
                ),
                FinancialYear(
                    year="2025-26",
                    open=False,
                    start_date=date(2025, 4, 1),
                    end_date=date(2026, 3, 31),
                    business_id=business.id
                ),
                FinancialYear(
                    year="2023-24",
                    open=False,
                    start_date=date(2023, 4, 1),
                    end_date=date(2024, 3, 31),
                    business_id=business.id
                )
            ]
            
            for fy in financial_years:
                db.add(fy)
            
            # Create Tax Rates for 2025-26
            tax_rates_2025_26 = [
                # Old Scheme
                TaxRate(
                    financial_year="2025-26",
                    scheme="Old Scheme",
                    category="< 60 Yr.",
                    income_from=250001,
                    fixed_tax=0,
                    progressive_rate=5,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2025-26",
                    scheme="Old Scheme",
                    category="< 60 Yr.",
                    income_from=500001,
                    fixed_tax=12500,
                    progressive_rate=20,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2025-26",
                    scheme="Old Scheme",
                    category="< 60 Yr.",
                    income_from=1000001,
                    fixed_tax=112500,
                    progressive_rate=30,
                    business_id=business.id
                ),
                # New Scheme
                TaxRate(
                    financial_year="2025-26",
                    scheme="New Scheme",
                    category="All",
                    income_from=300001,
                    fixed_tax=0,
                    progressive_rate=5,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2025-26",
                    scheme="New Scheme",
                    category="All",
                    income_from=700001,
                    fixed_tax=20000,
                    progressive_rate=10,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2025-26",
                    scheme="New Scheme",
                    category="All",
                    income_from=1000001,
                    fixed_tax=50000,
                    progressive_rate=15,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2025-26",
                    scheme="New Scheme",
                    category="All",
                    income_from=1200001,
                    fixed_tax=80000,
                    progressive_rate=20,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2025-26",
                    scheme="New Scheme",
                    category="All",
                    income_from=1500001,
                    fixed_tax=140000,
                    progressive_rate=30,
                    business_id=business.id
                )
            ]
            
            # Create Tax Rates for 2024-25
            tax_rates_2024_25 = [
                # Old Scheme
                TaxRate(
                    financial_year="2024-25",
                    scheme="Old Scheme",
                    category="< 60 Yr.",
                    income_from=250001,
                    fixed_tax=0,
                    progressive_rate=5,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2024-25",
                    scheme="Old Scheme",
                    category="< 60 Yr.",
                    income_from=500001,
                    fixed_tax=12500,
                    progressive_rate=20,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2024-25",
                    scheme="Old Scheme",
                    category="< 60 Yr.",
                    income_from=1000001,
                    fixed_tax=112500,
                    progressive_rate=30,
                    business_id=business.id
                ),
                # New Scheme
                TaxRate(
                    financial_year="2024-25",
                    scheme="New Scheme",
                    category="All",
                    income_from=250001,
                    fixed_tax=0,
                    progressive_rate=5,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2024-25",
                    scheme="New Scheme",
                    category="All",
                    income_from=500001,
                    fixed_tax=12500,
                    progressive_rate=10,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2024-25",
                    scheme="New Scheme",
                    category="All",
                    income_from=750001,
                    fixed_tax=37500,
                    progressive_rate=15,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2024-25",
                    scheme="New Scheme",
                    category="All",
                    income_from=1000001,
                    fixed_tax=75000,
                    progressive_rate=20,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2024-25",
                    scheme="New Scheme",
                    category="All",
                    income_from=1250001,
                    fixed_tax=125000,
                    progressive_rate=25,
                    business_id=business.id
                ),
                TaxRate(
                    financial_year="2024-25",
                    scheme="New Scheme",
                    category="All",
                    income_from=1500001,
                    fixed_tax=187500,
                    progressive_rate=30,
                    business_id=business.id
                )
            ]
            
            # Add all tax rates
            for rate in tax_rates_2025_26 + tax_rates_2024_25:
                db.add(rate)
            
            db.commit()
            
            logger.info(f"[OK] Created Tax settings for business {business.id}")
            logger.info(f"  - TDS Setting: Created")
            logger.info(f"  - Financial Years: {len(financial_years)}")
            logger.info(f"  - Tax Rates 2025-26: {len(tax_rates_2025_26)}")
            logger.info(f"  - Tax Rates 2024-25: {len(tax_rates_2024_25)}")
            logger.info(f"  - Total Tax Rates: {len(tax_rates_2025_26 + tax_rates_2024_25)}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create Tax settings sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_tds24q_sample_data():
    """Create sample TDS 24Q Info data for testing"""
    logger.info("\nStep 26.5: Creating TDS 24Q Info sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.business import Business
            from app.models.tds24q_models import TDS24Q
            
            # Check if sample data already exists
            existing_tds24q = db.query(TDS24Q).first()
            if existing_tds24q:
                logger.info("TDS 24Q sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Create sample TDS 24Q records
            tds24q_records = [
                TDS24Q(
                    business_id=business.id,
                    # General Info
                    deductor_type="Company",
                    section_code="92B - Employees other than Govt.",
                    state="TELANGANA",
                    ministry="Not Applicable",
                    ministry_name=None,
                    ain_number=None,
                    pao_code=None,
                    pao_registration=None,
                    ddo_code=None,
                    ddo_registration=None,
                    
                    # Employer Details
                    employer_name="Levitica Technologies Private Limited",
                    branch="Head Office - Hyderabad",
                    address1="123 Tech Park, HITEC City",
                    address2="Madhapur",
                    address3="Hyderabad",
                    address4="Telangana",
                    address5="India",
                    employer_state="TELANGANA",
                    pin="500081",
                    pan="ABCDE1234F",
                    tan="HYDE12345A",
                    email="hr@levitica.com",
                    std_code="040",
                    phone="12345678",
                    alt_email="accounts@levitica.com",
                    alt_std_code="040",
                    alt_phone="87654321",
                    gst="36ABCDE1234F1Z5",
                    
                    # Responsible Person Details
                    name="John Doe",
                    designation="HR Manager",
                    res_address1="456 Residential Colony",
                    res_address2="Jubilee Hills",
                    res_address3="Hyderabad",
                    res_address4="Telangana",
                    res_address5="India",
                    res_state="TELANGANA",
                    res_pin="500033",
                    res_pan="FGHIJ5678K",
                    res_mobile="9876543210",
                    res_email="john.doe@levitica.com",
                    res_std_code="040",
                    res_phone="11223344",
                    res_alt_email="john.personal@gmail.com",
                    res_alt_std_code="040",
                    res_alt_phone="44332211"
                ),
                TDS24Q(
                    business_id=business.id,
                    # General Info
                    deductor_type="Branch / Division of Company",
                    section_code="92B - Employees other than Govt.",
                    state="KARNATAKA",
                    ministry="Not Applicable",
                    ministry_name=None,
                    ain_number=None,
                    pao_code=None,
                    pao_registration=None,
                    ddo_code=None,
                    ddo_registration=None,
                    
                    # Employer Details
                    employer_name="Levitica Technologies Private Limited",
                    branch="Bangalore Branch Office",
                    address1="789 Software Park",
                    address2="Electronic City",
                    address3="Bangalore",
                    address4="Karnataka",
                    address5="India",
                    employer_state="KARNATAKA",
                    pin="560100",
                    pan="ABCDE1234F",
                    tan="BLRE67890B",
                    email="bangalore@levitica.com",
                    std_code="080",
                    phone="98765432",
                    alt_email="accounts.blr@levitica.com",
                    alt_std_code="080",
                    alt_phone="23456789",
                    gst="29ABCDE1234F1Z5",
                    
                    # Responsible Person Details
                    name="Jane Smith",
                    designation="Branch Manager",
                    res_address1="321 Garden View Apartments",
                    res_address2="Koramangala",
                    res_address3="Bangalore",
                    res_address4="Karnataka",
                    res_address5="India",
                    res_state="KARNATAKA",
                    res_pin="560034",
                    res_pan="KLMNO9012P",
                    res_mobile="8765432109",
                    res_email="jane.smith@levitica.com",
                    res_std_code="080",
                    res_phone="55667788",
                    res_alt_email="jane.personal@gmail.com",
                    res_alt_std_code="080",
                    res_alt_phone="88776655"
                )
            ]
            
            # Add all records
            for record in tds24q_records:
                db.add(record)
            
            db.commit()
            
            logger.info(f"[OK] Created TDS 24Q Info sample data for business {business.id}")
            logger.info(f"  - TDS 24Q Records: {len(tds24q_records)}")
            logger.info(f"  - Head Office (Hyderabad): 1 record")
            logger.info(f"  - Branch Office (Bangalore): 1 record")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create TDS 24Q sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_gratuity_sample_data():
    """Create sample gratuity data for testing"""
    logger.info("\nStep 27: Creating gratuity sample data...")
    
    try:
        with get_db_context() as db:
            # Import Gratuity model
            from app.models.payroll import Gratuity
            
            # Check if sample data already exists
            existing_gratuity = db.query(Gratuity).first()
            if existing_gratuity:
                logger.info("Gratuity sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get employees
            employees = db.query(Employee).filter(Employee.business_id == business.id).all()
            if not employees:
                logger.info("No employees found, skipping gratuity sample data")
                return True
            
            # Get payroll periods
            periods = db.query(PayrollPeriod).filter(PayrollPeriod.business_id == business.id).all()
            if not periods:
                logger.error("No payroll periods found")
                return False
            
            # Get first employee for created_by
            first_employee = employees[0]
            
            # Create sample gratuity records
            gratuities_data = [
                {
                    "period_id": periods[0].id,
                    "employee_id": employees[0].id,
                    "min_years": 5,
                    "payable_days": 15,
                    "month_days": 26,
                    "exit_only": False,
                    "year_rounding": "round_down",
                    "years_of_service": Decimal('6.5'),
                    "base_salary": Decimal('35000'),
                    "gratuity_amount": Decimal('31250.00'),
                    "salary_components": ["Basic Salary", "House Rent Allowance", "Special Allowance"],
                    "is_processed": True,
                    "processed_date": datetime.now() - timedelta(days=3)
                },
                {
                    "period_id": periods[0].id,
                    "employee_id": employees[1].id if len(employees) > 1 else employees[0].id,
                    "min_years": 5,
                    "payable_days": 15,
                    "month_days": 26,
                    "exit_only": False,
                    "year_rounding": "round_down",
                    "years_of_service": Decimal('8.2'),
                    "base_salary": Decimal('42000'),
                    "gratuity_amount": Decimal('49615.38'),
                    "salary_components": ["Basic Salary", "House Rent Allowance", "Special Allowance", "Medical Allowance"],
                    "is_processed": True,
                    "processed_date": datetime.now() - timedelta(days=3)
                },
                {
                    "period_id": periods[1].id if len(periods) > 1 else periods[0].id,
                    "employee_id": employees[2].id if len(employees) > 2 else employees[0].id,
                    "min_years": 5,
                    "payable_days": 15,
                    "month_days": 26,
                    "exit_only": False,
                    "year_rounding": "round_up",
                    "years_of_service": Decimal('7.8'),
                    "base_salary": Decimal('38000'),
                    "gratuity_amount": Decimal('43846.15'),
                    "salary_components": ["Basic Salary", "House Rent Allowance", "Special Allowance"],
                    "is_processed": False,
                    "processed_date": None
                },
                {
                    "period_id": periods[1].id if len(periods) > 1 else periods[0].id,
                    "employee_id": employees[3].id if len(employees) > 3 else employees[0].id,
                    "min_years": 5,
                    "payable_days": 15,
                    "month_days": 26,
                    "exit_only": True,
                    "year_rounding": "round_down",
                    "years_of_service": Decimal('12.3'),
                    "base_salary": Decimal('55000'),
                    "gratuity_amount": Decimal('97115.38'),
                    "salary_components": ["Basic Salary", "House Rent Allowance", "Special Allowance", "Medical Allowance", "Conveyance Allowance"],
                    "is_processed": False,
                    "processed_date": None
                },
                {
                    "period_id": periods[2].id if len(periods) > 2 else periods[0].id,
                    "employee_id": employees[4].id if len(employees) > 4 else employees[0].id,
                    "min_years": 5,
                    "payable_days": 15,
                    "month_days": 26,
                    "exit_only": False,
                    "year_rounding": "round_down",
                    "years_of_service": Decimal('9.7'),
                    "base_salary": Decimal('48000'),
                    "gratuity_amount": Decimal('66923.08'),
                    "salary_components": ["Basic Salary", "House Rent Allowance", "Special Allowance", "Medical Allowance"],
                    "is_processed": False,
                    "processed_date": None
                },
                {
                    "period_id": periods[2].id if len(periods) > 2 else periods[0].id,
                    "employee_id": employees[5].id if len(employees) > 5 else employees[0].id,
                    "min_years": 8,
                    "payable_days": 30,
                    "month_days": 15,
                    "exit_only": False,
                    "year_rounding": "round_up",
                    "years_of_service": Decimal('11.4'),
                    "base_salary": Decimal('52000'),
                    "gratuity_amount": Decimal('118400.00'),
                    "salary_components": ["Basic Salary", "House Rent Allowance", "Special Allowance", "Telephone Allowance"],
                    "is_processed": False,
                    "processed_date": None
                }
            ]
            
            created_gratuities = []
            for gratuity_data in gratuities_data:
                gratuity = Gratuity(
                    business_id=business.id,
                    period_id=gratuity_data["period_id"],
                    employee_id=gratuity_data["employee_id"],
                    created_by=first_employee.id,
                    min_years=gratuity_data["min_years"],
                    payable_days=gratuity_data["payable_days"],
                    month_days=gratuity_data["month_days"],
                    exit_only=gratuity_data["exit_only"],
                    year_rounding=gratuity_data["year_rounding"],
                    years_of_service=gratuity_data["years_of_service"],
                    base_salary=gratuity_data["base_salary"],
                    gratuity_amount=gratuity_data["gratuity_amount"],
                    salary_components=gratuity_data["salary_components"],
                    is_processed=gratuity_data["is_processed"],
                    processed_date=gratuity_data["processed_date"]
                )
                db.add(gratuity)
                created_gratuities.append(gratuity)
            
            db.commit()
            
            # Calculate statistics
            processed_count = sum(1 for g in created_gratuities if g.is_processed)
            pending_count = len(created_gratuities) - processed_count
            total_amount = sum(float(g.gratuity_amount) for g in created_gratuities)
            
            logger.info(f"[OK] Created {len(created_gratuities)} sample gratuity records")
            logger.info(f"  - Processed: {processed_count}")
            logger.info(f"  - Pending: {pending_count}")
            logger.info(f"  - Total Amount: ${total_amount:,.2f}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create gratuity sample data: {e}")
        return False


def create_payroll_run_sample_data():
    """Create sample payroll run data for testing"""
    logger.info("\nStep 28: Creating payroll run sample data...")
    
    try:
        with get_db_context() as db:
            # Import PayrollRun model
            from app.models.payroll import PayrollRun, PayrollRunStatus
            
            # Check if sample data already exists
            existing_run = db.query(PayrollRun).first()
            if existing_run:
                logger.info("Payroll run sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get employees
            employees = db.query(Employee).filter(Employee.business_id == business.id).all()
            if not employees:
                logger.info("No employees found, skipping payroll run sample data")
                return True
            
            # Get payroll periods
            periods = db.query(PayrollPeriod).filter(PayrollPeriod.business_id == business.id).all()
            if not periods:
                logger.error("No payroll periods found")
                return False
            
            # Get first employee for created_by
            first_employee = employees[0]
            
            # Create sample payroll run records with realistic variation
            import random
            from decimal import Decimal
            
            runs_data = []
            
            # Generate 6 realistic payroll runs with variation
            base_dates = [5, 35, 65, 95, 125, 155]  # Days ago
            periods_to_use = periods[:6] if len(periods) >= 6 else periods * 2
            
            for i, days_ago in enumerate(base_dates):
                # Realistic employee count variation
                total_employees = random.randint(45, 95)
                processed_employees = total_employees - random.randint(0, 3)
                failed_employees = total_employees - processed_employees
                
                # Calculate realistic salary totals with variation
                # Use different salary ranges for different runs (business growth/changes)
                base_avg_gross = random.uniform(48000, 58000)  # $48K-$58K average gross
                base_avg_deductions = base_avg_gross * random.uniform(0.16, 0.22)  # 16-22% deductions
                
                # Add individual employee variation
                total_gross = Decimal('0')
                total_deductions = Decimal('0')
                
                for emp in range(processed_employees):
                    # Individual variation (±25%)
                    emp_gross = base_avg_gross * random.uniform(0.75, 1.25)
                    emp_deductions = base_avg_deductions * random.uniform(0.8, 1.2)
                    
                    total_gross += Decimal(str(int(emp_gross)))
                    total_deductions += Decimal(str(int(emp_deductions)))
                
                total_net = total_gross - total_deductions
                
                # Runtime variation
                runtime_seconds = random.randint(25, 45)
                
                # Period selection
                period_id = periods_to_use[i % len(periods_to_use)].id
                
                run_data = {
                    "period_id": period_id,
                    "run_date": datetime.now() - timedelta(days=days_ago),
                    "status": PayrollRunStatus.COMPLETED.value,
                    "runtime_seconds": runtime_seconds,
                    "total_employees": total_employees,
                    "processed_employees": processed_employees,
                    "failed_employees": failed_employees,
                    "total_gross_salary": total_gross,
                    "total_deductions": total_deductions,
                    "total_net_salary": total_net,
                    "log_file_path": f"logs/payroll_run_{i+1}.log",
                    "notes": f"Payroll run #{i+1} - {processed_employees} employees processed"
                }
                
                runs_data.append(run_data)
                
                # Log the realistic data being created
                avg_net = float(total_net) / processed_employees if processed_employees > 0 else 0
                logger.info(f"Creating run {i+1}: {processed_employees} employees, avg net: ${avg_net:,.2f}")
            
            # Create the payroll run records
            created_runs = []
            for run_data in runs_data:
                payroll_run = PayrollRun(
                    business_id=business.id,
                    period_id=run_data["period_id"],
                    created_by=first_employee.id,
                    run_date=run_data["run_date"],
                    status=run_data["status"],
                    runtime_seconds=run_data["runtime_seconds"],
                    total_employees=run_data["total_employees"],
                    processed_employees=run_data["processed_employees"],
                    failed_employees=run_data["failed_employees"],
                    total_gross_salary=run_data["total_gross_salary"],
                    total_deductions=run_data["total_deductions"],
                    total_net_salary=run_data["total_net_salary"],
                    log_file_path=run_data["log_file_path"],
                    notes=run_data["notes"]
                )
                db.add(payroll_run)
                created_runs.append(payroll_run)
            
            db.commit()
            
            # Calculate statistics
            completed_count = len([r for r in created_runs if r.status == PayrollRunStatus.COMPLETED.value])
            total_net_amount = sum(float(r.total_net_salary) for r in created_runs)
            
            logger.info(f"[OK] Created {len(created_runs)} sample payroll run records")
            logger.info(f"  - Completed: {completed_count}")
            logger.info(f"  - Total Net Payroll: ${total_net_amount:,.2f}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create payroll run sample data: {e}")
        return False


def create_hold_salary_sample_data():
    """Create sample hold salary data for testing"""
    logger.info("\nStep 29: Creating hold salary sample data...")
    
    try:
        with get_db_context() as db:
            # Import HoldSalary model
            from app.models.payroll import HoldSalary
            
            # Check if sample data already exists
            existing_hold = db.query(HoldSalary).first()
            if existing_hold:
                logger.info("Hold salary sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get employees
            employees = db.query(Employee).filter(Employee.business_id == business.id).all()
            if not employees:
                logger.info("No employees found, skipping hold salary sample data")
                return True
            
            # Get first employee for created_by
            first_employee = employees[0]
            
            # Create sample hold salary records
            holds_data = [
                {
                    "employee_id": employees[0].id,
                    "hold_start_date": date(2025, 10, 29),
                    "hold_end_date": None,
                    "reason": "test",
                    "notes": "test",
                    "is_active": True
                },
                {
                    "employee_id": employees[1].id if len(employees) > 1 else employees[0].id,
                    "hold_start_date": date(2025, 11, 15),
                    "hold_end_date": None,
                    "reason": "Performance review pending",
                    "notes": "Hold salary until performance review completion",
                    "is_active": True
                },
                {
                    "employee_id": employees[2].id if len(employees) > 2 else employees[0].id,
                    "hold_start_date": date(2025, 9, 1),
                    "hold_end_date": date(2025, 9, 30),
                    "reason": "Documentation pending",
                    "notes": "Hold resolved after document submission",
                    "is_active": False
                },
                {
                    "employee_id": employees[3].id if len(employees) > 3 else employees[0].id,
                    "hold_start_date": date(2025, 12, 1),
                    "hold_end_date": None,
                    "reason": "Disciplinary action",
                    "notes": "Salary hold due to disciplinary proceedings",
                    "is_active": True
                },
                {
                    "employee_id": employees[4].id if len(employees) > 4 else employees[0].id,
                    "hold_start_date": date(2025, 8, 15),
                    "hold_end_date": date(2025, 8, 31),
                    "reason": "Leave without approval",
                    "notes": "Hold resolved after leave regularization",
                    "is_active": False
                }
            ]
            
            created_holds = []
            for hold_data in holds_data:
                hold_salary = HoldSalary(
                    business_id=business.id,
                    employee_id=hold_data["employee_id"],
                    created_by=first_employee.id,
                    hold_start_date=hold_data["hold_start_date"],
                    hold_end_date=hold_data["hold_end_date"],
                    reason=hold_data["reason"],
                    notes=hold_data["notes"],
                    is_active=hold_data["is_active"]
                )
                db.add(hold_salary)
                created_holds.append(hold_salary)
            
            db.commit()
            
            # Calculate statistics
            active_count = sum(1 for h in created_holds if h.is_active)
            inactive_count = len(created_holds) - active_count
            
            logger.info(f"[OK] Created {len(created_holds)} sample hold salary records")
            logger.info(f"  - Active: {active_count}")
            logger.info(f"  - Inactive: {inactive_count}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create hold salary sample data: {e}")
        return False


def create_sample_lwf_data():
    """Create sample Labour Welfare Fund data"""
    logger.info("\nStep 39: Creating sample Labour Welfare Fund data...")
    
    try:
        with get_db_context() as db:
            from app.models.business import Business
            from app.models.employee import Employee, EmployeeProfile
            from app.models.reports import SalaryReport
            from app.models.lwf_models import LWFRate
            from app.models.location import Location
            from datetime import datetime, date
            from decimal import Decimal
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Create LWF rates for different states
            lwf_rates_data = [
                {
                    "state": "Telangana",
                    "employee_contribution": Decimal('20.00'),
                    "employer_contribution": Decimal('20.00'),
                    "effective_from": date(2024, 1, 1),
                    "frequency": "Monthly"
                },
                {
                    "state": "Andhra Pradesh", 
                    "employee_contribution": Decimal('20.00'),
                    "employer_contribution": Decimal('20.00'),
                    "effective_from": date(2024, 1, 1),
                    "frequency": "Monthly"
                },
                {
                    "state": "Karnataka",
                    "employee_contribution": Decimal('25.00'),
                    "employer_contribution": Decimal('25.00'),
                    "effective_from": date(2024, 1, 1),
                    "frequency": "Monthly"
                },
                {
                    "state": "Tamil Nadu",
                    "employee_contribution": Decimal('30.00'),
                    "employer_contribution": Decimal('30.00'),
                    "effective_from": date(2024, 1, 1),
                    "frequency": "Monthly"
                },
                {
                    "state": "Default",
                    "employee_contribution": Decimal('20.00'),
                    "employer_contribution": Decimal('20.00'),
                    "effective_from": date(2024, 1, 1),
                    "frequency": "Monthly"
                }
            ]
            
            # Create LWF rates
            lwf_rates_created = 0
            for rate_data in lwf_rates_data:
                # Check if rate already exists
                existing_rate = db.query(LWFRate).filter(
                    LWFRate.business_id == business.id,
                    LWFRate.state == rate_data["state"],
                    LWFRate.effective_from == rate_data["effective_from"]
                ).first()
                
                if not existing_rate:
                    lwf_rate = LWFRate(
                        business_id=business.id,
                        **rate_data
                    )
                    db.add(lwf_rate)
                    lwf_rates_created += 1
            
            # Get active employees and update their profiles with state information
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == 'active'
            ).limit(10).all()
            
            if not employees:
                logger.info("No active employees found for LWF data")
                return True
            
            # State mapping for employees
            states = ["Telangana", "Andhra Pradesh", "Karnataka", "Tamil Nadu"]
            
            employees_updated = 0
            for idx, employee in enumerate(employees):
                # Get or create employee profile
                employee_profile = db.query(EmployeeProfile).filter(
                    EmployeeProfile.employee_id == employee.id
                ).first()
                
                if not employee_profile:
                    # Create employee profile with state
                    employee_profile = EmployeeProfile(
                        employee_id=employee.id,
                        state=states[idx % len(states)],
                        esi_number=f"{employee.id:06d}",
                        uan_number=f"UAN{employee.id:06d}",
                        profile_image_url=f"https://randomuser.me/api/portraits/men/{(employee.id % 10) + 1}.jpg",
                        created_at=datetime.now()
                    )
                    db.add(employee_profile)
                else:
                    # Update existing profile with state if not set
                    if not employee_profile.state:
                        employee_profile.state = states[idx % len(states)]
                
                employees_updated += 1
            
            # Update salary reports to include LWF deductions
            current_date = datetime.now()
            period = current_date.strftime('%Y-%m')
            
            salary_reports_updated = 0
            for employee in employees:
                # Get employee profile for state
                employee_profile = db.query(EmployeeProfile).filter(
                    EmployeeProfile.employee_id == employee.id
                ).first()
                
                employee_state = employee_profile.state if employee_profile else "Default"
                
                # Get LWF rate for employee's state
                lwf_rate = db.query(LWFRate).filter(
                    LWFRate.business_id == business.id,
                    LWFRate.state == employee_state
                ).first()
                
                if not lwf_rate:
                    # Use default rate
                    lwf_rate = db.query(LWFRate).filter(
                        LWFRate.business_id == business.id,
                        LWFRate.state == "Default"
                    ).first()
                
                # Get or update salary report
                salary_report = db.query(SalaryReport).filter(
                    SalaryReport.employee_id == employee.id,
                    SalaryReport.report_period == period
                ).first()
                
                if salary_report:
                    # Update existing salary report with LWF deduction
                    deductions = salary_report.deductions or {}
                    
                    # Only add LWF if salary is above threshold (15000)
                    if salary_report.gross_salary >= Decimal('15000'):
                        lwf_deduction = lwf_rate.employee_contribution if lwf_rate else Decimal('20.00')
                        deductions['Labour Welfare Fund'] = float(lwf_deduction)
                        
                        # Update deductions
                        salary_report.deductions = deductions
                        
                        # Recalculate total deductions and net salary
                        total_deductions = sum(deductions.values())
                        salary_report.total_deductions = Decimal(str(total_deductions))
                        salary_report.net_salary = salary_report.gross_salary - salary_report.total_deductions
                        
                        salary_reports_updated += 1
            
            db.commit()
            logger.info(f"[OK] Created LWF data:")
            logger.info(f"  - LWF rates created: {lwf_rates_created}")
            logger.info(f"  - Employee profiles updated: {employees_updated}")
            logger.info(f"  - Salary reports updated with LWF: {salary_reports_updated}")
            logger.info(f"  - States covered: Telangana, Andhra Pradesh, Karnataka, Tamil Nadu")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create LWF data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_email_settings_sample_data():
    """Create sample email settings data."""
    logger.info("Creating email settings sample data...")
    
    try:
        with get_db_context() as db:
            from app.core.security import encrypt_sensitive_data
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found for email settings")
                return False
            
            # Check if email mailbox already exists
            existing_mailbox = db.query(EmailMailbox).filter(
                EmailMailbox.business_id == business.id
            ).first()
            
            if existing_mailbox:
                logger.info("Email settings sample data already exists")
                return True
            
            # Create sample email mailbox
            sample_mailbox = EmailMailbox(
                business_id=business.id,
                tenant_id=None,
                display_name="Levitica Technologies HRMS",
                email_address="hr@leviticatechnologies.com",
                is_active=True,
                selected_provider=EmailProvider.SMTP
            )
            db.add(sample_mailbox)
            db.commit()
            db.refresh(sample_mailbox)
            
            # Create sample SMTP configuration
            sample_smtp = EmailSmtpConfig(
                mailbox_id=sample_mailbox.id,
                username="hr@leviticatechnologies.com",
                encrypted_password=encrypt_sensitive_data("sample_password_123"),
                server="smtp.gmail.com",
                port=587,
                use_ssl=True
            )
            db.add(sample_smtp)
            
            # Create sample OAuth configurations (not configured)
            gmail_oauth = EmailOAuthConfig(
                mailbox_id=sample_mailbox.id,
                provider=EmailOAuthProvider.GMAIL,
                is_configured=False
            )
            db.add(gmail_oauth)
            
            microsoft_oauth = EmailOAuthConfig(
                mailbox_id=sample_mailbox.id,
                provider=EmailOAuthProvider.MICROSOFT,
                is_configured=False
            )
            db.add(microsoft_oauth)
            
            # Create sample test log
            test_log = EmailTestLog(
                mailbox_id=sample_mailbox.id,
                provider=EmailProvider.SMTP,
                status="SUCCESS",
                message="Test email sent successfully via SMTP"
            )
            db.add(test_log)
            
            db.commit()
            
            logger.info("[OK] Email settings sample data created")
            logger.info(f"  - Mailbox: {sample_mailbox.display_name} ({sample_mailbox.email_address})")
            logger.info(f"  - SMTP configured for: {sample_smtp.server}:{sample_smtp.port}")
            logger.info(f"  - OAuth providers: Gmail (not configured), Microsoft (not configured)")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create email settings sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_biometric_device_sample_data():
    """Create sample biometric device data."""
    logger.info("Creating biometric device sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.setup.Integrations.biometricsync import BiometricDevice, BiometricSyncLog
            from app.models.business import Business
            from datetime import datetime, timedelta
            import random
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found for biometric devices")
                return False
            
            # Check if biometric devices already exist
            existing_devices = db.query(BiometricDevice).filter(
                BiometricDevice.business_id == business.id
            ).first()
            
            if existing_devices:
                logger.info("Biometric device sample data already exists")
                return True
            
            # Create sample biometric devices
            devices_data = [
                {
                    "name": "Main Gate Biometric",
                    "device_code": "BIO001",
                    "host_url": "https://in2.runtimehrms.com",
                    "activated": True,
                    "app_version": "2.1.0",
                    "last_seen": datetime.now() - timedelta(minutes=5),
                },
                {
                    "name": "Office Floor 1 Device",
                    "device_code": "BIO002", 
                    "host_url": "https://in2.runtimehrms.com",
                    "activated": True,
                    "app_version": "2.0.5",
                    "last_seen": datetime.now() - timedelta(minutes=15),
                },
                {
                    "name": "Cafeteria Entrance",
                    "device_code": "BIO003",
                    "host_url": "https://in2.runtimehrms.com",
                    "activated": False,
                    "app_version": "1.9.2",
                    "last_seen": datetime.now() - timedelta(hours=2),
                },
            ]
            
            created_devices = []
            for device_data in devices_data:
                # Check for existing device globally (due to unique constraint on device_code)
                existing_device = db.query(BiometricDevice).filter(
                    BiometricDevice.device_code == device_data["device_code"]
                ).first()
                if not existing_device:
                    device = BiometricDevice(
                        business_id=business.id,
                        tenant_id=None,
                        **device_data
                    )
                    db.add(device)
                    created_devices.append(device)
                else:
                    created_devices.append(existing_device)
            
            db.commit()
            
            # Create sample sync logs for each device
            log_statuses = ["SUCCESS", "FAILED", "SUCCESS", "PARTIAL"]
            log_messages = [
                "Attendance data synced successfully - 45 records processed",
                "Connection timeout - device unreachable",
                "Sync completed - 23 new punch records added",
                "Partial sync - 12 records processed, 2 failed"
            ]
            
            for i, device in enumerate(created_devices):
                db.refresh(device)
                
                # Create 3-5 sample logs per device
                num_logs = random.randint(3, 5)
                for j in range(num_logs):
                    log_time = datetime.now() - timedelta(
                        hours=random.randint(1, 72),
                        minutes=random.randint(0, 59)
                    )
                    
                    status = random.choice(log_statuses)
                    message = random.choice(log_messages)
                    
                    sync_log = BiometricSyncLog(
                        device_id=device.id,
                        synced_at=log_time,
                        status=status,
                        message=message
                    )
                    db.add(sync_log)
            
            db.commit()
            
            logger.info("[OK] Biometric device sample data created")
            logger.info(f"  - Created {len(created_devices)} biometric devices")
            logger.info(f"  - Device codes: {', '.join([d.device_code for d in created_devices])}")
            logger.info(f"  - Active devices: {sum(1 for d in created_devices if d.activated)}")
            logger.info(f"  - Sample sync logs created for each device")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create biometric device sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_gatekeeper_device_sample_data():
    """Create sample gatekeeper device data."""
    logger.info("Creating gatekeeper device sample data...")
    
    try:
        with get_db_context() as db:
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found for gatekeeper devices")
                return False
            
            # Check if gatekeeper devices already exist
            existing_devices = db.query(GatekeeperDevice).filter(
                GatekeeperDevice.business_id == business.id
            ).first()
            
            if existing_devices:
                logger.info("Gatekeeper device sample data already exists")
                return True
            
            # Create sample gatekeeper devices
            devices_data = [
                {
                    "name": "Main Gate Scanner",
                    "device_model": "GK-101",
                    "device_code": "MITGQC",
                    "app_version": "Not Activated",
                    "activated": False,
                    "last_seen": None
                },
                {
                    "name": "Employee Entrance",
                    "device_model": "GK-202",
                    "device_code": "EMPGAT",
                    "app_version": "v2.1.5",
                    "activated": True,
                    "last_seen": datetime.now() - timedelta(minutes=10)
                },
                {
                    "name": "Visitor Reception",
                    "device_model": "GK-150",
                    "device_code": "VISREC",
                    "app_version": "v2.0.8",
                    "activated": True,
                    "last_seen": datetime.now() - timedelta(hours=1)
                },
                {
                    "name": "Parking Gate Control",
                    "device_model": "GK-300",
                    "device_code": "PARKGT",
                    "app_version": "Not Activated",
                    "activated": False,
                    "last_seen": None
                },
                {
                    "name": "Emergency Exit Monitor",
                    "device_model": "GK-180",
                    "device_code": "EMRGEX",
                    "app_version": "v1.9.2",
                    "activated": True,
                    "last_seen": datetime.now() - timedelta(minutes=30)
                }
            ]
            
            created_devices = []
            for device_data in devices_data:
                # Check for existing device globally (due to unique constraint on device_code)
                existing_device = db.query(GatekeeperDevice).filter(
                    GatekeeperDevice.device_code == device_data["device_code"]
                ).first()
                if not existing_device:
                    device = GatekeeperDevice(
                        business_id=business.id,
                        tenant_id=None,
                        **device_data
                    )
                    db.add(device)
                    created_devices.append(device)
                else:
                    created_devices.append(existing_device)
            
            db.commit()
            
            logger.info("[OK] Gatekeeper device sample data created")
            logger.info(f"  - Created {len(created_devices)} gatekeeper devices")
            logger.info(f"  - Device codes: {', '.join([d.device_code for d in created_devices])}")
            logger.info(f"  - Active devices: {sum(1 for d in created_devices if d.activated)}")
            logger.info(f"  - Device models: {', '.join(set(d.device_model for d in created_devices))}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create gatekeeper device sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_sqlserver_source_sample_data():
    """Create sample SQL Server source data."""
    logger.info("Creating SQL Server source sample data...")
    
    try:
        with get_db_context() as db:
            from app.core.security import encrypt_sensitive_data
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found for SQL Server sources")
                return False
            
            # Check if SQL Server sources already exist
            existing_sources = db.query(SqlServerSource).filter(
                SqlServerSource.business_id == business.id
            ).first()
            
            if existing_sources:
                logger.info("SQL Server source sample data already exists")
                return True
            
            # Create sample SQL Server sources
            sources_data = [
                {
                    "source_name": "Main Office Attendance",
                    "server_address": "192.168.1.100",
                    "database_name": "attendance_db",
                    "database_username": "admin",
                    "database_password": encrypt_sensitive_data("admin123"),
                    "table_name": "attendance_%M_%YY",
                    "user_id_column": "employee_id",
                    "time_column": "punch_time",
                    "is_active": True
                },
                {
                    "source_name": "Branch Office System",
                    "server_address": "10.0.0.50",
                    "database_name": "branch_attendance",
                    "database_username": "branch_user",
                    "database_password": encrypt_sensitive_data("branch_pass"),
                    "table_name": "daily_attendance",
                    "user_id_column": "emp_code",
                    "time_column": "timestamp",
                    "is_active": True
                },
                {
                    "source_name": "Legacy System Import",
                    "server_address": "legacy.company.local",
                    "database_name": "old_hrms",
                    "database_username": "readonly",
                    "database_password": encrypt_sensitive_data("readonly123"),
                    "table_name": "employee_punches",
                    "user_id_column": "badge_number",
                    "time_column": "punch_datetime",
                    "is_active": False
                }
            ]
            
            created_sources = []
            for source_data in sources_data:
                source = SqlServerSource(
                    business_id=business.id,
                    tenant_id=None,
                    **source_data
                )
                db.add(source)
                created_sources.append(source)
            
            db.commit()
            
            # Create sample sync logs for each source
            log_statuses = ["SUCCESS", "FAILED", "SUCCESS", "WARNING"]
            log_messages = [
                "Successfully synced 150 attendance records",
                "Connection timeout - unable to reach database server",
                "Partial sync completed - 89 records processed, 3 duplicates skipped",
                "Sync completed with warnings - invalid timestamp format in 5 records"
            ]
            
            for i, source in enumerate(created_sources):
                db.refresh(source)
                
                # Create 2-4 sample logs per source
                num_logs = random.randint(2, 4)
                for j in range(num_logs):
                    log_time = datetime.now() - timedelta(
                        hours=random.randint(1, 168),  # Last week
                        minutes=random.randint(0, 59)
                    )
                    
                    status = random.choice(log_statuses)
                    message = random.choice(log_messages)
                    
                    sync_log = SqlServerSyncLog(
                        source_id=source.id,
                        synced_at=log_time,
                        status=status,
                        message=message
                    )
                    db.add(sync_log)
            
            db.commit()
            
            logger.info("[OK] SQL Server source sample data created")
            logger.info(f"  - Created {len(created_sources)} SQL Server sources")
            logger.info(f"  - Source names: {', '.join([s.source_name for s in created_sources])}")
            logger.info(f"  - Active sources: {sum(1 for s in created_sources if s.is_active)}")
            logger.info(f"  - Sample sync logs created for each source")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create SQL Server source sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_maintenance_sample_data():
    """Create sample maintenance data for testing maintenance operations"""
    logger.info("\nStep 42: Creating sample maintenance data...")
    
    try:
        with get_db_context() as db:
            from app.models.business import Business
            from app.models.employee import Employee, EmployeeSalary
            from datetime import datetime
            from decimal import Decimal
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get active employees
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == 'active'
            ).limit(15).all()
            
            if not employees:
                logger.info("No active employees found for maintenance data")
                return True
            
            maintenance_records_created = 0
            
            # Create some employees with incomplete work profiles for testing
            incomplete_profile_count = 0
            for i, employee in enumerate(employees[:5]):
                # Make some employees have incomplete profiles
                if i % 2 == 0:  # Every other employee
                    employee.location_id = None
                    employee.department_id = None
                    incomplete_profile_count += 1
                    maintenance_records_created += 1
            
            # Create some employees without salary details for testing
            missing_salary_count = 0
            for employee in employees[5:10]:
                # Check if salary details exist
                existing_salary = db.query(EmployeeSalary).filter(
                    EmployeeSalary.employee_id == employee.id
                ).first()
                
                if existing_salary:
                    # Remove salary details to test recalculation
                    db.delete(existing_salary)
                    missing_salary_count += 1
                    maintenance_records_created += 1
            
            # Create some inconsistent salary data for testing recalculation
            inconsistent_salary_count = 0
            for employee in employees[10:15]:
                # Get or create salary details with inconsistent data
                salary_details = db.query(EmployeeSalary).filter(
                    EmployeeSalary.employee_id == employee.id
                ).first()
                
                if not salary_details:
                    salary_details = EmployeeSalary(
                        employee_id=employee.id,
                        basic_salary=Decimal('15000.0'),
                        gross_salary=Decimal('0.0'),  # Inconsistent - should be calculated
                        ctc=Decimal('0.0'),           # Inconsistent - should be calculated
                        effective_from=datetime.now().date(),
                        is_active=True,
                        created_at=datetime.now()
                    )
                    db.add(salary_details)
                else:
                    # Make existing salary data inconsistent
                    salary_details.gross_salary = Decimal('0.0')
                    salary_details.ctc = Decimal('0.0')
                
                inconsistent_salary_count += 1
                maintenance_records_created += 1
            
            # Create some duplicate employee codes for testing (use unique codes)
            duplicate_codes_count = 0
            if len(employees) >= 3:
                # Instead of creating actual duplicates, just mark them for testing
                # We'll create a scenario where codes need to be regenerated
                original_code = employees[0].employee_code
                
                # Check if the duplicate code already exists to avoid constraint violation
                duplicate_code = f"{original_code}_DUP"
                existing_duplicate = db.query(Employee).filter(
                    Employee.employee_code == duplicate_code
                ).first()
                
                if not existing_duplicate:
                    # Use a different unique code that simulates the need for maintenance
                    employees[1].employee_code = duplicate_code
                    duplicate_codes_count += 1
                    maintenance_records_created += 1
                else:
                    logger.info(f"Duplicate code {duplicate_code} already exists, skipping...")
            
            db.commit()
            
            logger.info(f"[OK] Created maintenance test data:")
            logger.info(f"  - Employees with incomplete profiles: {incomplete_profile_count}")
            logger.info(f"  - Employees without salary details: {missing_salary_count}")
            logger.info(f"  - Employees with inconsistent salary data: {inconsistent_salary_count}")
            logger.info(f"  - Duplicate employee codes: {duplicate_codes_count}")
            logger.info(f"  - Total maintenance records: {maintenance_records_created}")
            logger.info("  - This data is designed to test maintenance operations")
            
            return True
    
    except Exception as e:
        logger.error(f"Failed to create maintenance sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_subscription_sample_data():
    """Create sample subscription data for testing"""
    logger.info("\nStep 43: Creating subscription sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.subscription import Subscription, SubscriptionPlan
            from datetime import datetime, timedelta
            import random
            
            # Check if subscription plans exist
            existing_plans = db.query(SubscriptionPlan).count()
            if existing_plans == 0:
                # Create subscription plans (INR pricing for Indian market)
                plans_data = [
                    {
                        "name": "Basic",
                        "display_name": "Basic Plan",
                        "description": "For small businesses",
                        "monthly_price": 99.00,
                        "yearly_price": 1188.00,  # 99 * 12
                        "currency": "INR",
                        "max_employees": 50,
                        "max_businesses": 1,
                        "features": '["Employee Database", "Attendance Management", "Leave Management", "Basic Payroll", "Payslip Generation", "Email Support"]',
                        "trial_days": 14,
                        "is_active": True,
                        "is_popular": False,
                        "sort_order": 1
                    },
                    {
                        "name": "Professional",
                        "display_name": "Professional Plan",
                        "description": "For growing companies",
                        "monthly_price": 149.00,
                        "yearly_price": 1788.00,  # 149 * 12
                        "currency": "INR",
                        "max_employees": 200,
                        "max_businesses": 3,
                        "features": '["All Basic Features", "Biometric Integration", "Shift Management", "Statutory Compliance", "Performance Management", "Custom Reports", "Priority Support"]',
                        "trial_days": 14,
                        "is_active": True,
                        "is_popular": True,
                        "sort_order": 2
                    },
                    {
                        "name": "Enterprise",
                        "display_name": "Enterprise Plan",
                        "description": "For large organizations",
                        "monthly_price": 0.00,  # Custom pricing
                        "yearly_price": 0.00,  # Custom pricing
                        "currency": "INR",
                        "max_employees": 0,  # Unlimited
                        "max_businesses": 10,
                        "features": '["All Professional Features", "Multi-location Support", "Advanced Analytics", "API Access", "Custom Integrations", "Dedicated Account Manager", "24/7 Support"]',
                        "trial_days": 30,
                        "is_active": True,
                        "is_popular": False,
                        "sort_order": 3
                    }
                ]
                
                for plan_data in plans_data:
                    plan = SubscriptionPlan(**plan_data)
                    db.add(plan)
                
                db.commit()
                logger.info("[OK] Created 3 subscription plans (INR pricing)")
            else:
                logger.info("[SKIP] Subscription plans already exist, skipping...")
            
            # Check if subscriptions exist
            existing_subscriptions = db.query(Subscription).count()
            if existing_subscriptions == 0:
                # Get all businesses and plans
                businesses = db.query(Business).all()
                plans = db.query(SubscriptionPlan).all()
                
                if businesses and plans:
                    # Create sample subscriptions
                    subscription_data = []
                    
                    # Sample company names for variety
                    company_names = [
                        "BrightWave Innovations", "Stellar Dynamics", "Dell Advance",
                        "Grand Stream", "Casio", "Airtel Nexus", "Paytm Nexus",
                        "Aircel", "Bajajaliance"
                    ]
                    
                    payment_methods = ["Credit Card", "PayPal", "Debit Card", "Bank Transfer"]
                    statuses = ["Active", "Paid", "Active", "Paid", "Active"]  # Mostly active/paid
                    
                    for i in range(min(9, len(company_names))):
                        # Use existing business or create subscription data
                        if i < len(businesses):
                            business = businesses[i % len(businesses)]
                        else:
                            business = businesses[0]  # Fallback to first business
                        
                        plan = random.choice(plans)
                        plan_type = random.choice(["Monthly", "Yearly"])
                        
                        # Calculate amount based on plan and type
                        amount = plan.monthly_price if plan_type == "Monthly" else plan.yearly_price
                        
                        # Calculate dates
                        start_date = datetime.utcnow() - timedelta(days=random.randint(30, 365))
                        if plan_type == "Monthly":
                            end_date = start_date + timedelta(days=30)
                            billing_cycle = "30 Days"
                        else:
                            end_date = start_date + timedelta(days=365)
                            billing_cycle = "365 Days"
                        
                        next_billing = end_date + timedelta(days=30 if plan_type == "Monthly" else 365)
                        
                        subscription_data.append({
                            "business_id": business.id,
                            "user_id": business.owner_id,
                            "plan_name": plan.name,
                            "plan_type": plan_type,
                            "billing_cycle": billing_cycle,
                            "payment_method": random.choice(payment_methods),
                            "amount": amount,
                            "currency": "INR",  # Changed from USD to INR for consistency
                            "payment_id": str(100000 + random.randint(0, 899999)),
                            "start_date": start_date,
                            "end_date": end_date,
                            "next_billing_date": next_billing,
                            "status": random.choice(statuses),
                            "is_active": True,
                            "auto_renew": True,
                            "notes": f"Subscription for {company_names[i]}"
                        })
                    
                    # Create subscriptions
                    for sub_data in subscription_data:
                        subscription = Subscription(**sub_data)
                        db.add(subscription)
                    
                    db.commit()
                    logger.info(f"[OK] Created {len(subscription_data)} sample subscriptions")
                    
                    # Create expired subscriptions for dashboard testing
                    expired_subs = [
                        {
                            "business_id": businesses[0].id,
                            "user_id": businesses[0].owner_id,
                            "plan_name": "Basic",
                            "plan_type": "Monthly",
                            "billing_cycle": "30 Days",
                            "payment_method": "Credit Card",
                            "amount": 1000.00,
                            "currency": "INR",
                            "payment_id": "PAY_EXP_001",
                            "start_date": datetime.utcnow() - timedelta(days=60),
                            "end_date": datetime.utcnow() - timedelta(days=30),
                            "status": "Expired",
                            "is_active": False,
                            "auto_renew": False,
                            "notes": "Expired subscription for testing"
                        },
                        {
                            "business_id": businesses[0].id,
                            "user_id": businesses[0].owner_id,
                            "plan_name": "Enterprise",
                            "plan_type": "Yearly",
                            "billing_cycle": "365 Days",
                            "payment_method": "Bank Transfer",
                            "amount": 12000.00,
                            "currency": "INR",
                            "payment_id": "PAY_EXP_002",
                            "start_date": datetime.utcnow() - timedelta(days=400),
                            "end_date": datetime.utcnow() - timedelta(days=35),
                            "status": "Expired",
                            "is_active": False,
                            "auto_renew": False,
                            "notes": "Expired subscription for testing"
                        }
                    ]
                    
                    for exp_sub in expired_subs:
                        subscription = Subscription(**exp_sub)
                        db.add(subscription)
                    
                    db.commit()
                    logger.info(f"[OK] Created {len(expired_subs)} expired subscriptions for dashboard")
                    
                else:
                    logger.info("No businesses or plans found, skipping subscription creation")
            else:
                logger.info("Subscription sample data already exists, skipping...")
            
            return True
    
    except Exception as e:
        logger.error(f"Failed to create subscription sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_domain_sample_data():
    """Create sample domain data for testing"""
    logger.info("\nStep 43.5: Creating domain sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.domain import DomainRequest, DomainConfiguration, DomainUsageLog
            from datetime import datetime, timedelta
            import random
            
            # Check if domain requests exist
            existing_domains = db.query(DomainRequest).count()
            if existing_domains == 0:
                # Get all businesses for domain requests
                businesses = db.query(Business).all()
                
                # Ensure we have at least 3 businesses for domain testing
                if len(businesses) < 3:
                    logger.info("Creating additional test businesses for domain module...")
                    
                    # Get superadmin user
                    superadmin = db.query(User).filter(User.email == "superadmin@levitica.com").first()
                    
                    if superadmin:
                        # Create test businesses if they don't exist
                        test_businesses = [
                            {
                                "business_name": "BrightWave Innovations",
                                "gstin": "27AAAAA1111A1Z1",
                                "business_url": "bwi.example.com"
                            },
                            {
                                "business_name": "UrbanPulse Design",
                                "gstin": "27AAAAA2222A1Z2",
                                "business_url": "upd.example.com"
                            },
                            {
                                "business_name": "Quantum Nexus",
                                "gstin": "27AAAAA3333A1Z3",
                                "business_url": "qn.example.com"
                            }
                        ]
                        
                        for biz_data in test_businesses:
                            # Check if business already exists
                            existing = db.query(Business).filter(
                                Business.business_name == biz_data["business_name"]
                            ).first()
                            
                            if not existing:
                                new_business = Business(
                                    owner_id=superadmin.id,
                                    business_name=biz_data["business_name"],
                                    gstin=biz_data["gstin"],
                                    pan="AAAAA0000A",
                                    address="Test Address, Business Park",
                                    city="Hyderabad",
                                    pincode="500001",
                                    state="Telangana",
                                    constitution="Private Limited",
                                    product="HRMS",
                                    plan="Basic",
                                    billing_frequency="Monthly",
                                    business_url=biz_data["business_url"],
                                    is_authorized=True,
                                    is_active=True,
                                    created_at=datetime.utcnow()
                                )
                                db.add(new_business)
                        
                        db.commit()
                        logger.info("[OK] Created test businesses for domain module")
                        
                        # Refresh businesses list
                        businesses = db.query(Business).all()
                
                if businesses and len(businesses) >= 3:
                    # Sample domain data
                    domain_data = [
                        {
                            "business_id": businesses[0].id,
                            "user_id": businesses[0].owner_id,
                            "requested_domain": "bwi.example.com",
                            "domain_type": "subdomain",
                            "plan_name": "Advanced",
                            "plan_type": "Monthly",
                            "price": 200.00,
                            "currency": "USD",
                            "status": "Approved",
                            "start_date": datetime.utcnow() - timedelta(days=30),
                            "expiry_date": datetime.utcnow() + timedelta(days=335),
                            "ssl_enabled": True,
                            "dns_configured": True,
                            "is_active": True,
                            "auto_renew": True,
                            "notes": "Domain for BrightWave Innovations"
                        },
                        {
                            "business_id": businesses[1].id,
                            "user_id": businesses[1].owner_id,
                            "requested_domain": "upd.example.com",
                            "domain_type": "subdomain",
                            "plan_name": "Basic",
                            "plan_type": "Yearly",
                            "price": 150.00,
                            "currency": "USD",
                            "status": "Pending",
                            "ssl_enabled": True,
                            "dns_configured": False,
                            "is_active": False,
                            "auto_renew": True,
                            "notes": "Domain for UrbanPulse Design"
                        },
                        {
                            "business_id": businesses[2].id,
                            "user_id": businesses[2].owner_id,
                            "requested_domain": "qn.example.com",
                            "domain_type": "subdomain",
                            "plan_name": "Pro",
                            "plan_type": "Monthly",
                            "price": 300.00,
                            "currency": "USD",
                            "status": "Rejected",
                            "rejection_reason": "Domain name conflicts with existing trademark",
                            "ssl_enabled": True,
                            "dns_configured": False,
                            "is_active": False,
                            "auto_renew": False,
                            "notes": "Domain for Quantum Nexus"
                        }
                    ]
                    
                    # Create domain requests
                    created_domains = []
                    for domain_info in domain_data:
                        domain = DomainRequest(**domain_info)
                        db.add(domain)
                        db.flush()  # Get the ID
                        created_domains.append(domain)
                    
                    db.commit()
                    logger.info(f"[OK] Created {len(created_domains)} domain requests")
                    
                    # Create domain configurations for approved domains
                    for domain in created_domains:
                        if domain.status == "Approved":
                            config = DomainConfiguration(
                                domain_request_id=domain.id,
                                cname_record=f"{domain.requested_domain}.cdn.example.com",
                                a_record="192.168.1.100",
                                txt_record=f"v=spf1 include:_spf.example.com ~all",
                                ssl_certificate_id=f"ssl-cert-{domain.id}",
                                ssl_status="active",
                                ssl_expiry=datetime.utcnow() + timedelta(days=90),
                                load_balancer_id=f"lb-{domain.id}",
                                backend_servers='["192.168.1.10", "192.168.1.11"]',
                                health_status="healthy",
                                uptime_percentage=99.95,
                                is_configured=True,
                                configuration_notes="Fully configured and operational"
                            )
                            db.add(config)
                            
                            # Create usage logs for the last 7 days
                            for i in range(7):
                                log_date = datetime.utcnow() - timedelta(days=i)
                                usage_log = DomainUsageLog(
                                    domain_request_id=domain.id,
                                    log_date=log_date,
                                    page_views=random.randint(100, 1000),
                                    unique_visitors=random.randint(50, 500),
                                    bandwidth_mb=random.uniform(10.0, 100.0),
                                    avg_response_time=random.uniform(100.0, 500.0),
                                    error_count=random.randint(0, 10),
                                    uptime_minutes=1440 - random.randint(0, 60),  # Almost full day
                                    top_countries='["United States", "India", "United Kingdom"]',
                                    top_cities='["New York", "Mumbai", "London"]'
                                )
                                db.add(usage_log)
                    
                    db.commit()
                    logger.info("[OK] Created domain configurations and usage logs")
                else:
                    logger.warning(f"Not enough businesses found ({len(businesses)}), need at least 3 for domain testing")
            else:
                logger.info("Domain sample data already exists, skipping...")
            
            return True
    
    except Exception as e:
        logger.error(f"Failed to create domain sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_purchase_transaction_sample_data():
    """Create sample purchase transaction data for testing"""
    logger.info("\nStep 43.6: Creating purchase transaction sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.purchase_transaction import PurchaseTransaction, TransactionLineItem, PaymentLog
            from app.models.business import Business
            from app.models.user import User
            from datetime import datetime, timedelta
            import random
            
            # Check if purchase transactions exist
            existing_transactions = db.query(PurchaseTransaction).count()
            if existing_transactions == 0:
                # Get all businesses for transactions
                businesses = db.query(Business).all()
                users = db.query(User).all()
                
                if businesses and users:
                    # Sample transaction data
                    transaction_data = [
                        {
                            "business_id": businesses[0].id,
                            "user_id": users[0].id,
                            "invoice_id": "INV001",
                            "transaction_date": datetime.utcnow() - timedelta(days=30),
                            "due_date": datetime.utcnow() + timedelta(days=20),
                            "subtotal": 1800.00,
                            "tax_amount": 200.00,
                            "total_amount": 2000.00,
                            "currency": "INR",
                            "payment_method": "Credit Card",
                            "payment_status": "Paid",
                            "payment_reference": "CC_REF_001",
                            "payment_date": datetime.utcnow() - timedelta(days=25),
                            "plan_name": "Premium Plan",
                            "billing_cycle": "Monthly",
                            "service_start_date": datetime.utcnow() - timedelta(days=30),
                            "service_end_date": datetime.utcnow() + timedelta(days=335),
                            "invoice_from_name": "DCM",
                            "invoice_from_address": "456 Green St, Hyderabad",
                            "invoice_from_email": "info@dcm.com",
                            "invoice_to_name": businesses[0].business_name,
                            "invoice_to_address": "123 Tech Park, Bangalore",
                            "invoice_to_email": "contact@brightwave.com",
                            "description": "Premium Plan Subscription",
                            "notes": "Monthly subscription payment",
                            "is_active": True
                        },
                        {
                            "business_id": businesses[1].id if len(businesses) > 1 else businesses[0].id,
                            "user_id": users[1].id if len(users) > 1 else users[0].id,
                            "invoice_id": "INV002",
                            "transaction_date": datetime.utcnow() - timedelta(days=60),
                            "due_date": datetime.utcnow() + timedelta(days=15),
                            "subtotal": 4500.00,
                            "tax_amount": 500.00,
                            "total_amount": 5000.00,
                            "currency": "INR",
                            "payment_method": "Bank Transfer",
                            "payment_status": "Unpaid",
                            "payment_reference": None,
                            "payment_date": None,
                            "plan_name": "Enterprise Plan",
                            "billing_cycle": "Yearly",
                            "service_start_date": datetime.utcnow() - timedelta(days=60),
                            "service_end_date": datetime.utcnow() + timedelta(days=305),
                            "invoice_from_name": "DCM",
                            "invoice_from_address": "22 Creative Hub, Chennai",
                            "invoice_from_email": "contact@dcm.com",
                            "invoice_to_name": businesses[1].business_name if len(businesses) > 1 else businesses[0].business_name,
                            "invoice_to_address": "88 Market Rd, Delhi",
                            "invoice_to_email": "contact@urbanpulse.com",
                            "description": "Enterprise Plan Subscription",
                            "notes": "Yearly subscription payment - pending",
                            "is_active": True
                        },
                        {
                            "business_id": businesses[2].id if len(businesses) > 2 else businesses[0].id,
                            "user_id": users[2].id if len(users) > 2 else users[0].id,
                            "invoice_id": "INV003",
                            "transaction_date": datetime.utcnow() - timedelta(days=15),
                            "due_date": datetime.utcnow() + timedelta(days=30),
                            "subtotal": 900.00,
                            "tax_amount": 100.00,
                            "total_amount": 1000.00,
                            "currency": "INR",
                            "payment_method": "PayPal",
                            "payment_status": "Paid",
                            "payment_reference": "PP_REF_003",
                            "payment_date": datetime.utcnow() - timedelta(days=10),
                            "plan_name": "Basic Plan",
                            "billing_cycle": "Monthly",
                            "service_start_date": datetime.utcnow() - timedelta(days=15),
                            "service_end_date": datetime.utcnow() + timedelta(days=345),
                            "invoice_from_name": "DCM",
                            "invoice_from_address": "789 Business Center, Mumbai",
                            "invoice_from_email": "billing@dcm.com",
                            "invoice_to_name": businesses[2].business_name if len(businesses) > 2 else businesses[0].business_name,
                            "invoice_to_address": "456 Corporate Ave, Pune",
                            "invoice_to_email": "info@techcorp.com",
                            "description": "Basic Plan Subscription",
                            "notes": "Monthly subscription payment - completed",
                            "is_active": True
                        }
                    ]
                    
                    # Create purchase transactions
                    created_transactions = []
                    for transaction_info in transaction_data:
                        transaction = PurchaseTransaction(**transaction_info)
                        db.add(transaction)
                        db.flush()  # Get the ID
                        created_transactions.append(transaction)
                    
                    db.commit()
                    logger.info(f"[OK] Created {len(created_transactions)} purchase transactions")
                    
                    # Create line items for transactions
                    for transaction in created_transactions:
                        line_item = TransactionLineItem(
                            transaction_id=transaction.id,
                            item_name=transaction.plan_name,
                            item_description=f"{transaction.billing_cycle} subscription to {transaction.plan_name}",
                            quantity=1,
                            unit_price=transaction.subtotal,
                            total_price=transaction.subtotal,
                            item_type="subscription",
                            item_reference=f"plan_{transaction.plan_name.lower().replace(' ', '_')}"
                        )
                        db.add(line_item)
                    
                    db.commit()
                    logger.info(f"[OK] Created line items for transactions")
                    
                    # Create payment logs for transactions
                    for transaction in created_transactions:
                        # Initial log
                        initial_log = PaymentLog(
                            transaction_id=transaction.id,
                            payment_gateway="mock_gateway",
                            gateway_transaction_id=f"TXN_{transaction.invoice_id}",
                            gateway_response=f"Transaction initiated for {transaction.invoice_id}",
                            status="initiated",
                            attempt_number=1,
                            processed_at=transaction.transaction_date,
                            ip_address="192.168.1.100",
                            user_agent="Mozilla/5.0 (Test Browser)"
                        )
                        db.add(initial_log)
                        
                        # Payment completion log for paid transactions
                        if transaction.payment_status == "Paid":
                            completion_log = PaymentLog(
                                transaction_id=transaction.id,
                                payment_gateway="mock_gateway",
                                gateway_transaction_id=f"TXN_{transaction.invoice_id}_COMPLETE",
                                gateway_response=f"Payment completed successfully for {transaction.invoice_id}",
                                status="success",
                                attempt_number=2,
                                processed_at=transaction.payment_date,
                                ip_address="192.168.1.100",
                                user_agent="Mozilla/5.0 (Test Browser)"
                            )
                            db.add(completion_log)
                    
                    db.commit()
                    logger.info(f"[OK] Created payment logs for transactions")
                    
                else:
                    logger.warning("No businesses or users found. Cannot create purchase transaction sample data.")
            else:
                logger.info(f"Purchase transactions already exist ({existing_transactions} found). Skipping creation.")
            
            return True  # Always return True for successful completion or skipping
    
    except Exception as e:
        logger.error(f"Failed to create purchase transaction sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_project_management_sample_data():
    """Create sample project management data for testing"""
    logger.info("\nStep 44: Creating project management sample data...")
    
    try:
        with get_db_context() as db:
            try:
                from app.models.project_management import (
                    Project, Task, TimeEntry, ProjectMember, ProjectActivityLog,
                    ProjectStatus, TaskStatus, MemberRole
                )
            except ImportError as e:
                logger.info(f"Project management models not available: {e}, skipping...")
                return True
                
            from app.models.employee import Employee
            from app.models.business import Business
            from app.models.user import User
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if projects already exist
            existing_projects = db.execute(text("SELECT COUNT(*) FROM projects WHERE business_id = :business_id"), 
                                         {"business_id": business.id}).scalar()
            
            if existing_projects > 0:
                logger.info(f"Projects already exist ({existing_projects} found), skipping...")
                return True
            
            # Get employees and users
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == 'active'
            ).limit(10).all()
            
            users = db.query(User).limit(5).all()
            
            if not employees or not users:
                logger.info("No employees or users found for project management data")
                return True
            
            # Create sample projects
            projects_data = [
                {
                    'name': 'Interior Designing',
                    'client': 'Internal Runtime Software',
                    'description': 'Complete interior design project for office space renovation',
                    'start_date': date.today() - timedelta(days=30),
                    'end_date': date.today() + timedelta(days=60),
                    'status': ProjectStatus.ACTIVE
                },
                {
                    'name': 'POS Setup & Go Live',
                    'client': 'Retail Solutions Inc',
                    'description': 'Point of Sale system implementation and deployment',
                    'start_date': date.today() - timedelta(days=15),
                    'end_date': date.today() + timedelta(days=45),
                    'status': ProjectStatus.ACTIVE
                },
                {
                    'name': 'Improve onboarding steps',
                    'client': 'HR Department',
                    'description': 'Streamline and improve employee onboarding process',
                    'start_date': date.today() - timedelta(days=10),
                    'end_date': date.today() + timedelta(days=30),
                    'status': ProjectStatus.ACTIVE
                },
                {
                    'name': 'Sales Capture Improvements',
                    'client': 'Sales Team',
                    'description': 'Enhance sales data capture and reporting mechanisms',
                    'start_date': date.today() - timedelta(days=45),
                    'end_date': date.today() - timedelta(days=5),
                    'status': ProjectStatus.COMPLETED,
                    'is_completed': True,
                    'completed_at': date.today() - timedelta(days=5)
                },
                {
                    'name': 'Hero project Vikesh',
                    'client': 'Marketing Department',
                    'description': 'Special marketing campaign project led by Vikesh',
                    'start_date': date.today() + timedelta(days=5),
                    'end_date': date.today() + timedelta(days=90),
                    'status': ProjectStatus.ACTIVE
                }
            ]
            
            created_projects = []
            for project_data in projects_data:
                project = Project(
                    business_id=business.id,
                    name=project_data['name'],
                    client=project_data['client'],
                    description=project_data['description'],
                    start_date=project_data['start_date'],
                    end_date=project_data['end_date'],
                    status=project_data['status'],
                    is_active=project_data.get('is_active', True),
                    is_completed=project_data.get('is_completed', False),
                    completed_at=project_data.get('completed_at'),
                    created_by=random.choice(users).id
                )
                db.add(project)
                db.flush()
                created_projects.append(project)
                
                # Create activity log
                activity_log = ProjectActivityLog(
                    project_id=project.id,
                    message="Project created",
                    activity_type="general",
                    created_by=project.created_by
                )
                db.add(activity_log)
            
            # Create sample tasks for each project
            task_templates = [
                {
                    'name': 'Requirements Analysis',
                    'description': 'Analyze and document project requirements',
                    'days_offset_start': 0,
                    'days_offset_end': 7,
                    'projected_days': 0,
                    'projected_hours': 16,
                    'projected_minutes': 0,
                    'status': TaskStatus.COMPLETED
                },
                {
                    'name': 'Design Phase',
                    'description': 'Create design mockups and prototypes',
                    'days_offset_start': 5,
                    'days_offset_end': 20,
                    'projected_days': 1,
                    'projected_hours': 8,
                    'projected_minutes': 30,
                    'status': TaskStatus.IN_PROGRESS
                },
                {
                    'name': 'Development',
                    'description': 'Core development and implementation',
                    'days_offset_start': 15,
                    'days_offset_end': 45,
                    'projected_days': 3,
                    'projected_hours': 4,
                    'projected_minutes': 0,
                    'status': TaskStatus.IN_PROGRESS
                },
                {
                    'name': 'Testing & QA',
                    'description': 'Quality assurance and testing phase',
                    'days_offset_start': 40,
                    'days_offset_end': 55,
                    'projected_days': 1,
                    'projected_hours': 12,
                    'projected_minutes': 0,
                    'status': TaskStatus.ON_HOLD
                },
                {
                    'name': 'Deployment',
                    'description': 'Deploy to production environment',
                    'days_offset_start': 50,
                    'days_offset_end': 60,
                    'projected_days': 0,
                    'projected_hours': 8,
                    'projected_minutes': 0,
                    'status': TaskStatus.RUNNING
                }
            ]
            
            created_tasks = []
            for project in created_projects[:3]:  # Add tasks to first 3 projects
                for i, task_template in enumerate(task_templates[:3]):  # 3 tasks per project
                    task_start = project.start_date + timedelta(days=task_template['days_offset_start'])
                    task_end = project.start_date + timedelta(days=task_template['days_offset_end'])
                    
                    # Calculate total projected minutes
                    total_projected_minutes = (
                        task_template['projected_days'] * 24 * 60 +
                        task_template['projected_hours'] * 60 +
                        task_template['projected_minutes']
                    )
                    
                    # Calculate working days and validation
                    working_days = 0
                    current = task_start
                    while current <= task_end:
                        if current.weekday() < 5:  # Monday to Friday
                            working_days += 1
                        current += timedelta(days=1)
                    
                    available_hours = Decimal(working_days * 8)
                    projected_hours = Decimal(total_projected_minutes) / 60
                    
                    task = Task(
                        project_id=project.id,
                        name=task_template['name'],
                        description=task_template['description'],
                        start_date=task_start,
                        end_date=task_end,
                        status=task_template['status'],
                        is_completed=task_template['status'] == TaskStatus.COMPLETED,
                        projected_days=task_template['projected_days'],
                        projected_hours=task_template['projected_hours'],
                        projected_minutes=task_template['projected_minutes'],
                        total_projected_minutes=total_projected_minutes,
                        date_range_display=f"{task_start.strftime('%d %b %Y')} to {task_end.strftime('%d %b %Y')}",
                        projected_time_display=f"{task_template['projected_days']:02d}d {task_template['projected_hours']:02d}h {task_template['projected_minutes']:02d}m",
                        time_spent_display="00h 00m",
                        available_working_days=working_days,
                        available_working_hours=available_hours,
                        has_time_mismatch=projected_hours > available_hours,
                        time_shortage_hours=max(Decimal(0), projected_hours - available_hours),
                        time_buffer_hours=max(Decimal(0), available_hours - projected_hours),
                        created_by=random.choice(users).id
                    )
                    db.add(task)
                    db.flush()
                    created_tasks.append(task)
                    
                    # Create activity log for task
                    activity_log = ProjectActivityLog(
                        project_id=project.id,
                        message=f"Task '{task.name}' created",
                        activity_type="task",
                        task_id=task.id,
                        created_by=task.created_by
                    )
                    db.add(activity_log)
            
            # Create sample time entries for completed tasks
            for task in created_tasks:
                if task.status == TaskStatus.COMPLETED:
                    # Add some time entries
                    for day_offset in range(0, 5):  # 5 days of work
                        entry_date = task.start_date + timedelta(days=day_offset)
                        if entry_date.weekday() < 5:  # Only weekdays
                            hours = random.randint(2, 8)
                            minutes = random.choice([0, 15, 30, 45])
                            total_minutes = hours * 60 + minutes
                            
                            time_entry = TimeEntry(
                                task_id=task.id,
                                date=entry_date,
                                hours=hours,
                                minutes=minutes,
                                total_minutes=total_minutes,
                                duration_display=f"{hours:02d}h {minutes:02d}m",
                                description=f"Work on {task.name}",
                                created_by=random.choice(users).id
                            )
                            db.add(time_entry)
                    
                    # Update task time spent
                    total_time_spent = db.execute(
                        text("SELECT COALESCE(SUM(total_minutes), 0) FROM time_entries WHERE task_id = :task_id"),
                        {"task_id": task.id}
                    ).scalar()
                    
                    task.time_spent_minutes = total_time_spent
                    hours_spent = total_time_spent // 60
                    minutes_spent = total_time_spent % 60
                    task.time_spent_display = f"{hours_spent:02d}h {minutes_spent:02d}m"
            
            # Create project members
            for project in created_projects:
                # Add 2-3 members per project
                selected_employees = random.sample(employees, min(3, len(employees)))
                for employee in selected_employees:
                    member = ProjectMember(
                        project_id=project.id,
                        employee_id=employee.id,
                        role=random.choice([MemberRole.DEVELOPER, MemberRole.DESIGNER, MemberRole.TESTER]),
                        joined_date=project.start_date + timedelta(days=random.randint(0, 5)),
                        created_by=random.choice(users).id
                    )
                    db.add(member)
            
            # Update project metrics
            for project in created_projects:
                # Count tasks
                total_tasks = db.execute(
                    text("SELECT COUNT(*) FROM tasks WHERE project_id = :project_id"),
                    {"project_id": project.id}
                ).scalar() or 0
                
                completed_tasks = db.execute(
                    text("SELECT COUNT(*) FROM tasks WHERE project_id = :project_id AND is_completed = true"),
                    {"project_id": project.id}
                ).scalar() or 0
                
                # Count members
                total_members = db.execute(
                    text("SELECT COUNT(*) FROM project_members WHERE project_id = :project_id AND is_active = true"),
                    {"project_id": project.id}
                ).scalar() or 0
                
                # Calculate work hours
                total_work_minutes = db.execute(
                    text("""
                        SELECT COALESCE(SUM(te.total_minutes), 0) 
                        FROM time_entries te 
                        JOIN tasks t ON te.task_id = t.id 
                        WHERE t.project_id = :project_id
                    """),
                    {"project_id": project.id}
                ).scalar() or 0
                
                project.total_tasks = total_tasks
                project.completed_tasks = completed_tasks
                project.total_members = total_members
                project.total_work_hours = Decimal(total_work_minutes) / 60
            
            db.commit()
            
            logger.info(f"[OK] Created {len(created_projects)} projects")
            logger.info(f"[OK] Created {len(created_tasks)} tasks")
            logger.info(f"[OK] Created time entries for completed tasks")
            logger.info(f"[OK] Created project members")
            logger.info("[OK] Project management sample data created successfully")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create project management sample data: {str(e)}")
        logger.info("Continuing setup despite project management data creation failure...")
        return True  # Continue setup even if this fails


def create_notes_sample_data():
    """Create sample notes data for testing"""
    logger.info("\nStep 45: Creating notes sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.notes import Note, NoteShare, NoteCategory, NotePriority
            from app.models.employee import Employee
            from app.models.business import Business
            from app.models.user import User
            import json
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if notes already exist
            existing_notes = db.execute(text("SELECT COUNT(*) FROM notes WHERE business_id = :business_id"), 
                                      {"business_id": business.id}).scalar()
            
            if existing_notes > 0:
                logger.info(f"Notes already exist ({existing_notes} found), skipping...")
                return True
            
            # Get users
            users = db.query(User).limit(5).all()
            
            if not users:
                logger.info("No users found for notes data")
                return True
            
            # Create sample notes
            notes_data = [
                {
                    'title': 'Welcome to Notes',
                    'content': 'This is your first note! You can use notes to keep track of important information, ideas, meeting notes, and more. Notes support categories, priorities, tags, and sharing with team members.',
                    'category': NoteCategory.GENERAL,
                    'priority': NotePriority.MEDIUM,
                    'tags': json.dumps(['welcome', 'getting-started', 'tutorial']),
                    'is_pinned': True,
                    'color': '#e3f2fd'
                },
                {
                    'title': 'Project Meeting Notes - Q1 Planning',
                    'content': 'Meeting Date: Today\nAttendees: Team leads, Product Manager\n\nKey Discussion Points:\n- Q1 roadmap review\n- Resource allocation\n- Timeline adjustments\n- Risk mitigation strategies\n\nAction Items:\n- Update project timeline by Friday\n- Schedule follow-up with stakeholders\n- Review budget allocation',
                    'category': NoteCategory.MEETING,
                    'priority': NotePriority.HIGH,
                    'tags': json.dumps(['meeting', 'q1-planning', 'roadmap', 'action-items']),
                    'is_favorite': True,
                    'color': '#fff3e0'
                },
                {
                    'title': 'New Feature Ideas',
                    'content': 'Brainstorming session results:\n\n1. Dark mode theme\n2. Advanced search filters\n3. Mobile app improvements\n4. Integration with third-party tools\n5. Automated reporting features\n\nNext steps: Prioritize based on user feedback and technical feasibility.',
                    'category': NoteCategory.IDEA,
                    'priority': NotePriority.MEDIUM,
                    'tags': json.dumps(['ideas', 'features', 'brainstorming', 'product']),
                    'color': '#f3e5f5'
                },
                {
                    'title': 'Important Reminders',
                    'content': 'Things to remember:\n\n- Submit monthly reports by 5th\n- Team performance reviews due next week\n- Update security certificates\n- Schedule quarterly business review\n- Renew software licenses',
                    'category': NoteCategory.REMINDER,
                    'priority': NotePriority.HIGH,
                    'tags': json.dumps(['reminders', 'deadlines', 'admin']),
                    'reminder_date': datetime.now() + timedelta(days=7),
                    'color': '#ffebee'
                },
                {
                    'title': 'Code Review Checklist',
                    'content': 'Before submitting code for review:\n\n[OK] Code follows style guidelines\n[OK] All tests pass\n[OK] Documentation updated\n[OK] No console.log statements\n[OK] Error handling implemented\n[OK] Performance considerations\n[OK] Security best practices\n[OK] Accessibility compliance',
                    'category': NoteCategory.WORK,
                    'priority': NotePriority.MEDIUM,
                    'tags': json.dumps(['development', 'checklist', 'code-review', 'quality']),
                    'color': '#e8f5e8'
                },
                {
                    'title': 'Personal Learning Goals',
                    'content': 'Learning objectives for this quarter:\n\n1. Master advanced Python concepts\n2. Learn cloud architecture patterns\n3. Improve presentation skills\n4. Study data science fundamentals\n5. Get certified in project management\n\nResources:\n- Online courses\n- Technical books\n- Mentorship program\n- Practice projects',
                    'category': NoteCategory.PERSONAL,
                    'priority': NotePriority.LOW,
                    'tags': json.dumps(['learning', 'goals', 'development', 'skills']),
                    'color': '#fff8e1'
                },
                {
                    'title': 'Client Feedback Summary',
                    'content': 'Recent client feedback analysis:\n\nPositive:\n- User interface improvements\n- Faster response times\n- Better customer support\n\nAreas for improvement:\n- Mobile experience\n- Report generation speed\n- Integration capabilities\n\nRecommendations:\n- Prioritize mobile optimization\n- Invest in performance improvements\n- Expand API offerings',
                    'category': NoteCategory.WORK,
                    'priority': NotePriority.HIGH,
                    'tags': json.dumps(['client', 'feedback', 'analysis', 'improvements']),
                    'is_shared': True,
                    'color': '#e1f5fe'
                },
                {
                    'title': 'Team Building Event Ideas',
                    'content': 'Ideas for upcoming team building activities:\n\n1. Escape room challenge\n2. Cooking class\n3. Outdoor adventure day\n4. Game tournament\n5. Volunteer activity\n6. Workshop series\n\nBudget: $2000\nPreferred dates: Next month\nTeam size: 15 people',
                    'category': NoteCategory.GENERAL,
                    'priority': NotePriority.LOW,
                    'tags': json.dumps(['team-building', 'events', 'planning', 'fun']),
                    'color': '#fce4ec'
                },
                {
                    'title': 'Security Best Practices',
                    'content': 'Important security guidelines:\n\n- Use strong, unique passwords\n- Enable two-factor authentication\n- Keep software updated\n- Be cautious with email attachments\n- Use VPN for remote work\n- Regular security training\n- Report suspicious activities\n- Backup important data\n\nContact IT security team for questions.',
                    'category': NoteCategory.WORK,
                    'priority': NotePriority.URGENT,
                    'tags': json.dumps(['security', 'guidelines', 'best-practices', 'it']),
                    'is_pinned': True,
                    'color': '#ffcdd2'
                },
                {
                    'title': 'Archived Project Notes',
                    'content': 'Notes from the completed project:\n\nProject: Legacy System Migration\nDuration: 6 months\nTeam: 8 developers\n\nLessons learned:\n- Better planning reduces risks\n- Regular communication is key\n- Testing early saves time\n- Documentation is crucial\n\nThese notes are archived for future reference.',
                    'category': NoteCategory.PROJECT,
                    'priority': NotePriority.LOW,
                    'tags': json.dumps(['archived', 'project', 'lessons-learned', 'migration']),
                    'is_archived': True,
                    'color': '#f5f5f5'
                }
            ]
            
            created_notes = []
            for i, note_data in enumerate(notes_data):
                note = Note(
                    business_id=business.id,
                    title=note_data['title'],
                    content=note_data['content'],
                    category=note_data['category'],
                    priority=note_data['priority'],
                    tags=note_data['tags'],
                    is_pinned=note_data.get('is_pinned', False),
                    is_archived=note_data.get('is_archived', False),
                    is_favorite=note_data.get('is_favorite', False),
                    is_shared=note_data.get('is_shared', False),
                    color=note_data['color'],
                    reminder_date=note_data.get('reminder_date'),
                    created_by=random.choice(users).id
                )
                db.add(note)
                db.flush()
                created_notes.append(note)
            
            # Create some note shares for shared notes
            shared_notes = [note for note in created_notes if note.is_shared]
            for note in shared_notes:
                # Share with 1-2 other users
                other_users = [u for u in users if u.id != note.created_by]
                share_count = min(2, len(other_users))
                shared_with = random.sample(other_users, share_count)
                
                for user in shared_with:
                    share = NoteShare(
                        note_id=note.id,
                        shared_with_user_id=user.id,
                        can_edit=random.choice([True, False]),
                        can_delete=False,
                        shared_by=note.created_by
                    )
                    db.add(share)
            
            db.commit()
            
            logger.info(f"[OK] Created {len(created_notes)} notes")
            logger.info(f"[OK] Created note shares for shared notes")
            logger.info("[OK] Notes sample data created successfully")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create notes sample data: {str(e)}")
        logger.info("Continuing setup despite notes data creation failure...")
        return True  # Continue setup even if this fails


def create_calendar_sample_data():
    """Create sample calendar data for testing"""
    logger.info("\nStep 43: Creating calendar sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.calendar import CalendarEvent, CalendarEventAttendee, CalendarView
            from app.models.employee import Employee
            from app.models.business import Business
            from app.models.user import User
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if calendar events already exist
            existing_events = db.execute(text("SELECT COUNT(*) FROM calendar_events WHERE business_id = :business_id"), 
                                       {"business_id": business.id}).scalar()
            
            if existing_events > 0:
                logger.info(f"Calendar events already exist ({existing_events} found), skipping...")
                return True
            
            # Get employees and users
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == 'active'
            ).limit(10).all()
            
            # Get users (admin users who can organize events)
            users = db.query(User).limit(5).all()
            
            if not employees or not users:
                logger.info("No employees or users found for calendar data")
                return True
            
            # Create sample calendar events
            events_data = [
                {
                    'title': 'Team Meeting',
                    'description': 'Weekly team sync meeting',
                    'event_type': 'meeting',
                    'start_date': date.today() + timedelta(days=1),
                    'start_time': datetime.combine(date.today() + timedelta(days=1), datetime.min.time().replace(hour=10)),
                    'end_time': datetime.combine(date.today() + timedelta(days=1), datetime.min.time().replace(hour=11)),
                    'location': 'Conference Room A',
                    'priority': 'medium',
                    'color': '#3788d8'
                },
                {
                    'title': 'Project Deadline',
                    'description': 'Final submission for Q1 project',
                    'event_type': 'deadline',
                    'start_date': date.today() + timedelta(days=7),
                    'is_all_day': True,
                    'priority': 'high',
                    'color': '#e74c3c'
                },
                {
                    'title': 'Training Session',
                    'description': 'New employee orientation training',
                    'event_type': 'training',
                    'start_date': date.today() + timedelta(days=3),
                    'start_time': datetime.combine(date.today() + timedelta(days=3), datetime.min.time().replace(hour=14)),
                    'end_time': datetime.combine(date.today() + timedelta(days=3), datetime.min.time().replace(hour=17)),
                    'location': 'Training Room',
                    'priority': 'medium',
                    'color': '#f39c12'
                },
                {
                    'title': 'Company Event',
                    'description': 'Annual company picnic',
                    'event_type': 'company_event',
                    'start_date': date.today() + timedelta(days=14),
                    'is_all_day': True,
                    'location': 'City Park',
                    'priority': 'low',
                    'color': '#27ae60'
                },
                {
                    'title': 'Board Meeting',
                    'description': 'Monthly board meeting',
                    'event_type': 'meeting',
                    'start_date': date.today() + timedelta(days=21),
                    'start_time': datetime.combine(date.today() + timedelta(days=21), datetime.min.time().replace(hour=9)),
                    'end_time': datetime.combine(date.today() + timedelta(days=21), datetime.min.time().replace(hour=12)),
                    'location': 'Boardroom',
                    'priority': 'high',
                    'color': '#8e44ad'
                },
                {
                    'title': 'System Maintenance',
                    'description': 'Scheduled system maintenance window',
                    'event_type': 'reminder',
                    'start_date': date.today() + timedelta(days=30),
                    'start_time': datetime.combine(date.today() + timedelta(days=30), datetime.min.time().replace(hour=2)),
                    'end_time': datetime.combine(date.today() + timedelta(days=30), datetime.min.time().replace(hour=6)),
                    'priority': 'urgent',
                    'color': '#e67e22'
                }
            ]
            
            created_events = []
            for event_data in events_data:
                event = CalendarEvent(
                    business_id=business.id,
                    title=event_data['title'],
                    description=event_data['description'],
                    event_type=event_data['event_type'],
                    start_date=event_data['start_date'],
                    end_date=event_data.get('end_date'),
                    start_time=event_data.get('start_time'),
                    end_time=event_data.get('end_time'),
                    is_all_day=event_data.get('is_all_day', False),
                    priority=event_data['priority'],
                    status='scheduled',
                    location=event_data.get('location'),
                    organizer_id=random.choice(users).id,
                    color=event_data['color'],
                    is_public=True,
                    reminder_minutes=30,
                    created_by=random.choice(users).id
                )
                db.add(event)
                db.flush()
                created_events.append(event)
            
            # Add attendees to some events
            for event in created_events[:3]:  # Add attendees to first 3 events
                selected_employees = random.sample(employees, min(3, len(employees)))
                for employee in selected_employees:
                    attendee = CalendarEventAttendee(
                        event_id=event.id,
                        employee_id=employee.id,
                        status=random.choice(['invited', 'accepted', 'declined', 'tentative'])
                    )
                    db.add(attendee)
            
            # Create calendar view preferences for users
            for user in users:
                view = CalendarView(
                    user_id=user.id,
                    business_id=business.id,
                    default_view=random.choice(['month', 'week', 'day']),
                    start_day_of_week=1,  # Monday
                    time_format='12h',
                    show_holidays=True,
                    show_birthdays=True,
                    show_work_anniversaries=True,
                    show_leaves=True,
                    show_meetings=True,
                    show_company_events=True
                )
                db.add(view)
            
            db.commit()
            
            logger.info(f"[OK] Created {len(created_events)} calendar events")
            logger.info(f"[OK] Created {len(users)} calendar view preferences")
            logger.info("[OK] Calendar sample data created successfully")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create calendar sample data: {str(e)}")
        logger.info("Continuing setup despite calendar data creation failure...")
        return True  # Continue setup even if this fails


def create_todo_sample_data():
    """Create sample TODO/Task data for testing"""
    logger.info("\nStep 44: Creating TODO/Task sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.todo import Task
            from app.models.user import User
            from app.models.business import Business
            from datetime import date, timedelta
            import random
            
            # Get users
            users = db.query(User).limit(5).all()
            if not users:
                logger.info("No users found for TODO data")
                return True
            
            # Get business
            business = db.query(Business).first()
            
            # Check if tasks already exist
            existing_tasks = db.execute(text("SELECT COUNT(*) FROM todo_tasks WHERE user_id = :user_id"), 
                                       {"user_id": users[0].id}).scalar()
            
            if existing_tasks > 0:
                logger.info(f"Tasks already exist ({existing_tasks} found), skipping...")
                return True
            
            # Create sample tasks for first user
            tasks_data = [
                {
                    'title': 'Review employee performance reports',
                    'description': 'Complete quarterly performance review for all team members',
                    'category': 'work',
                    'status': 'todo',
                    'priority': 'high',
                    'due_date': date.today() + timedelta(days=3),
                    'is_pinned': True
                },
                {
                    'title': 'Prepare monthly payroll',
                    'description': 'Process payroll for all employees and verify deductions',
                    'category': 'work',
                    'status': 'in_progress',
                    'priority': 'urgent',
                    'due_date': date.today() + timedelta(days=1),
                    'is_pinned': True
                },
                {
                    'title': 'Schedule team meeting',
                    'description': 'Organize weekly team sync meeting',
                    'category': 'meeting',
                    'status': 'todo',
                    'priority': 'medium',
                    'due_date': date.today() + timedelta(days=2),
                    'tags': 'meeting,team,weekly'
                },
                {
                    'title': 'Update employee handbook',
                    'description': 'Review and update company policies in employee handbook',
                    'category': 'work',
                    'status': 'todo',
                    'priority': 'low',
                    'due_date': date.today() + timedelta(days=14),
                    'tags': 'documentation,policies'
                },
                {
                    'title': 'Follow up on leave requests',
                    'description': 'Review and approve pending leave requests',
                    'category': 'follow_up',
                    'status': 'todo',
                    'priority': 'medium',
                    'due_date': date.today() + timedelta(days=1),
                    'tags': 'leave,approval'
                },
                {
                    'title': 'Complete training module',
                    'description': 'Finish HR compliance training course',
                    'category': 'personal',
                    'status': 'in_progress',
                    'priority': 'medium',
                    'due_date': date.today() + timedelta(days=7)
                },
                {
                    'title': 'Submit expense report',
                    'description': 'Submit monthly expense report with receipts',
                    'category': 'deadline',
                    'status': 'todo',
                    'priority': 'high',
                    'due_date': date.today() + timedelta(days=2),
                    'tags': 'expenses,finance'
                },
                {
                    'title': 'Review job applications',
                    'description': 'Screen applications for open positions',
                    'category': 'work',
                    'status': 'completed',
                    'priority': 'medium',
                    'due_date': date.today() - timedelta(days=2),
                    'tags': 'recruitment,hiring'
                }
            ]
            
            created_tasks = []
            for task_data in tasks_data:
                task = Task(
                    user_id=users[0].id,
                    business_id=business.id if business else None,
                    title=task_data['title'],
                    description=task_data['description'],
                    category=task_data['category'],
                    status=task_data['status'],
                    priority=task_data['priority'],
                    due_date=task_data['due_date'],
                    is_pinned=task_data.get('is_pinned', False),
                    tags=task_data.get('tags'),
                    completed_at=datetime.now() if task_data['status'] == 'completed' else None
                )
                db.add(task)
                created_tasks.append(task)
            
            db.commit()
            
            logger.info(f"[OK] Created {len(created_tasks)} TODO/Task items")
            logger.info("[OK] TODO sample data created successfully")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create TODO sample data: {str(e)}")
        logger.info("Continuing setup despite TODO data creation failure...")
        return True  # Continue setup even if this fails


def create_crm_sample_data():
    """Create comprehensive CRM sample data"""
    logger.info("Creating CRM sample data...")
    
    try:
        with get_db_context() as db:
            # Check if CRM companies already exist
            existing_companies = db.query(CRMCompany).count()
            
            # Check if CRM pipelines already exist
            existing_pipelines = db.query(CRMPipeline).count()
            
            # Check if CRM activities already exist
            existing_activities = db.query(CRMActivity).count()
            
            # Skip only if ALL data exists (companies, pipelines, AND activities)
            if existing_companies > 0 and existing_pipelines > 0 and existing_activities > 0:
                logger.info("CRM sample data already exists (companies, pipelines, activities), skipping...")
                return True
            
            # Get superadmin user for created_by
            superadmin = db.query(User).filter(User.email == "superadmin@levitica.com").first()
            if not superadmin:
                logger.error("Superadmin user not found")
                return False
            
            # Create companies only if they don't exist
            if existing_companies == 0:
                logger.info("Creating CRM companies...")
            else:
                logger.info(f"CRM companies already exist ({existing_companies} found), skipping company creation...")
            
            # Create sample companies (only if needed)
            if existing_companies == 0:
                companies_data = [
                    {
                        "name": "BrightWave Innovations",
                        "email": "contact@brightwave.com",
                        "phone": "+1-555-0101",
                        "phone2": "+1-555-0102",
                        "fax": "+1-555-0103",
                        "website": "https://brightwave.com",
                    "ratings": Decimal("4.5"),
                    "owner_id": superadmin.id,
                    "tags": '["Technology", "Innovation", "AI"]',
                    "deals_info": "Collins",
                    "industry": "Technology",
                    "source": "Website",
                    "currency": "USD",
                    "language": "English",
                    "about": "Leading technology innovation company specializing in AI and machine learning solutions.",
                    "contact_person": "Darlee Robertson",
                    "address": "123 Innovation Drive",
                    "country": "USA",
                    "state": "California",
                    "city": "San Francisco",
                    "postal_code": "94105",
                    "facebook_url": "https://facebook.com/brightwave",
                    "twitter_url": "https://twitter.com/brightwave",
                    "linkedin_url": "https://linkedin.com/company/brightwave",
                    "skype_handle": "brightwave.support",
                    "whatsapp": "+1-555-0104",
                    "instagram_url": "https://instagram.com/brightwave",
                    "visibility": "public",
                    "status": "Active",
                    "annual_revenue": Decimal("5000000.00"),
                    "employee_count": 150,
                    "description": "Leading technology innovation company specializing in AI and machine learning solutions."
                },
                {
                    "name": "Stellar Dynamics",
                    "email": "info@stellardynamics.com",
                    "phone": "+1-555-0201",
                    "phone2": "+1-555-0202",
                    "fax": "+1-555-0203",
                    "website": "https://stellardynamics.com",
                    "ratings": Decimal("4.2"),
                    "owner_id": superadmin.id,
                    "tags": '["Space", "Technology", "Research"]',
                    "deals_info": "Konopelski",
                    "industry": "Aerospace",
                    "source": "Referral",
                    "currency": "USD",
                    "language": "English",
                    "about": "Aerospace technology company focused on satellite systems and space exploration.",
                    "contact_person": "Sharon Roy",
                    "address": "456 Space Center Blvd",
                    "country": "USA",
                    "state": "Texas",
                    "city": "Houston",
                    "postal_code": "77058",
                    "facebook_url": "https://facebook.com/stellardynamics",
                    "twitter_url": "https://twitter.com/stellardynamics",
                    "linkedin_url": "https://linkedin.com/company/stellardynamics",
                    "skype_handle": "stellar.support",
                    "whatsapp": "+1-555-0204",
                    "instagram_url": "https://instagram.com/stellardynamics",
                    "visibility": "public",
                    "status": "Active",
                    "annual_revenue": Decimal("3200000.00"),
                    "employee_count": 85,
                    "description": "Aerospace technology company focused on satellite systems and space exploration."
                },
                {
                    "name": "Quantum Nexus",
                    "email": "hello@quantumnexus.com",
                    "phone": "+91-98765-43210",
                    "phone2": "+91-98765-43211",
                    "fax": "+91-98765-43212",
                    "website": "https://quantumnexus.com",
                    "ratings": Decimal("4.7"),
                    "owner_id": superadmin.id,
                    "tags": '["Quantum", "Computing", "Research"]',
                    "deals_info": "Adams",
                    "industry": "Technology",
                    "source": "Social Media",
                    "currency": "USD",
                    "language": "English",
                    "about": "Quantum computing research and development company pushing the boundaries of computational science.",
                    "contact_person": "Vaughan",
                    "address": "789 Quantum Plaza",
                    "country": "India",
                    "state": "Karnataka",
                    "city": "Bangalore",
                    "postal_code": "560001",
                    "facebook_url": "https://facebook.com/quantumnexus",
                    "twitter_url": "https://twitter.com/quantumnexus",
                    "linkedin_url": "https://linkedin.com/company/quantumnexus",
                    "skype_handle": "quantum.support",
                    "whatsapp": "+91-98765-43213",
                    "instagram_url": "https://instagram.com/quantumnexus",
                    "visibility": "public",
                    "status": "Active",
                    "annual_revenue": Decimal("2800000.00"),
                    "employee_count": 65,
                    "description": "Quantum computing research and development company pushing the boundaries of computational science."
                },
                {
                    "name": "EcoVision Enterprises",
                    "email": "contact@ecovision.ca",
                    "phone": "+1-416-555-0301",
                    "phone2": "+1-416-555-0302",
                    "fax": "+1-416-555-0303",
                    "website": "https://ecovision.ca",
                    "ratings": Decimal("4.3"),
                    "owner_id": superadmin.id,
                    "tags": '["Environment", "Sustainability", "Green"]',
                    "deals_info": "Collins",
                    "industry": "Environmental Services",
                    "source": "Phone Calls",
                    "currency": "USD",
                    "language": "English",
                    "about": "Environmental consulting and sustainability solutions for businesses worldwide.",
                    "contact_person": "Jessica",
                    "address": "321 Green Street",
                    "country": "Canada",
                    "state": "Ontario",
                    "city": "Toronto",
                    "postal_code": "M5V 3A8",
                    "facebook_url": "https://facebook.com/ecovision",
                    "twitter_url": "https://twitter.com/ecovision",
                    "linkedin_url": "https://linkedin.com/company/ecovision",
                    "skype_handle": "eco.support",
                    "whatsapp": "+1-416-555-0304",
                    "instagram_url": "https://instagram.com/ecovision",
                    "visibility": "public",
                    "status": "Active",
                    "annual_revenue": Decimal("1800000.00"),
                    "employee_count": 45,
                    "description": "Environmental consulting and sustainability solutions for businesses worldwide."
                },
                {
                    "name": "Aurora Technologies",
                    "email": "info@auroratech.de",
                    "phone": "+49-30-555-0401",
                    "phone2": "+49-30-555-0402",
                    "fax": "+49-30-555-0403",
                    "website": "https://auroratech.de",
                    "ratings": Decimal("4.6"),
                    "owner_id": superadmin.id,
                    "tags": '["Software", "Enterprise", "Solutions"]',
                    "deals_info": "Konopelski",
                    "industry": "Software Development",
                    "source": "Web Analytics",
                    "currency": "Euro",
                    "language": "English",
                    "about": "Enterprise software solutions provider specializing in business automation and digital transformation.",
                    "contact_person": "Carol Thomas",
                    "address": "654 Tech Park",
                    "country": "Germany",
                    "state": "Berlin",
                    "city": "Berlin",
                    "postal_code": "10115",
                    "facebook_url": "https://facebook.com/auroratech",
                    "twitter_url": "https://twitter.com/auroratech",
                    "linkedin_url": "https://linkedin.com/company/auroratech",
                    "skype_handle": "aurora.support",
                    "whatsapp": "+49-30-555-0404",
                    "instagram_url": "https://instagram.com/auroratech",
                    "visibility": "public",
                    "status": "Active",
                    "annual_revenue": Decimal("4200000.00"),
                    "employee_count": 120,
                    "description": "Enterprise software solutions provider specializing in business automation and digital transformation."
                }
            ]
            
                created_companies = []
                for company_data in companies_data:
                    company = CRMCompany(
                        **company_data,
                        created_by=superadmin.id
                    )
                    db.add(company)
                    created_companies.append(company)
            
                db.commit()
                logger.info(f"Created {len(created_companies)} companies")
            else:
                # Companies already exist, fetch them for contact/deal creation
                created_companies = db.query(CRMCompany).limit(5).all()
                logger.info(f"Using existing {len(created_companies)} companies for relationships")
            
            # Create sample contacts with all frontend required fields (including leads)
            # Wrap in try-except to allow pipeline creation even if contacts fail
            try:
                existing_contacts = db.query(CRMContact).count()
                if existing_contacts == 0:
                    contacts_data = [
                # Contacted Leads
                {
                    "first_name": "Linda",
                    "last_name": "White",
                    "email": "linda@gmail.com",
                    "phone": "(193) 7839 748",
                    "mobile": "(193) 7839 748",
                    "job_title": "Marketing Manager",
                    "department": "Marketing",
                    "contact_type": ContactType.LEAD,
                    "lead_status": LeadStatus.CONTACTED,
                    "company_id": created_companies[0].id,
                    "rating": 4,
                    "owner_id": superadmin.id,
                    "tags": '["Marketing", "Contacted"]',
                    "profile_image_url": "/assets/img/users/user-49.jpg",
                    "currency": "USD",
                    "language": "English",
                    "industry": "Technology",
                    "deals_info": "Collins",
                    "lead_source": "Website",
                    "location": "Austin, United States",
                    "city": "Austin",
                    "state": "Texas",
                    "country": "United States",
                    "postal_code": "73301",
                    "linkedin_url": "https://linkedin.com/in/linda-white",
                    "facebook_url": "https://facebook.com/linda.white",
                    "visibility": "public",
                    "status": "Active",
                    "value": Decimal("350000.00")
                },
                {
                    "first_name": "Chris",
                    "last_name": "Johnson",
                    "email": "chris@gmail.com",
                    "phone": "(162) 8920 713",
                    "mobile": "(162) 8920 713",
                    "job_title": "Sales Director",
                    "department": "Sales",
                    "contact_type": ContactType.LEAD,
                    "lead_status": LeadStatus.CONTACTED,
                    "company_id": created_companies[1].id,
                    "rating": 4,
                    "owner_id": superadmin.id,
                    "tags": '["Sales", "Contacted"]',
                    "profile_image_url": "/assets/img/users/user-13.jpg",
                    "currency": "USD",
                    "language": "English",
                    "industry": "Aerospace",
                    "deals_info": "Konopelski",
                    "lead_source": "Referral",
                    "location": "Atlanta, United States",
                    "city": "Atlanta",
                    "state": "Georgia",
                    "country": "United States",
                    "postal_code": "30301",
                    "linkedin_url": "https://linkedin.com/in/chris-johnson",
                    "facebook_url": "https://facebook.com/chris.johnson",
                    "visibility": "public",
                    "status": "Active",
                    "value": Decimal("350000.00")
                },
                # Not Contacted Leads
                {
                    "first_name": "Emily",
                    "last_name": "Johnson",
                    "email": "emily@gmail.com",
                    "phone": "(179) 7382 829",
                    "mobile": "(179) 7382 829",
                    "job_title": "Product Manager",
                    "department": "Product",
                    "contact_type": ContactType.LEAD,
                    "lead_status": LeadStatus.NEW,
                    "company_id": created_companies[2].id,
                    "rating": 3,
                    "owner_id": superadmin.id,
                    "tags": '["Product", "New"]',
                    "profile_image_url": "/assets/img/users/user-32.jpg",
                    "currency": "USD",
                    "language": "English",
                    "industry": "Technology",
                    "deals_info": "Adams",
                    "lead_source": "Social Media",
                    "location": "Newyork, United States",
                    "city": "New York",
                    "state": "New York",
                    "country": "United States",
                    "postal_code": "10001",
                    "linkedin_url": "https://linkedin.com/in/emily-johnson",
                    "facebook_url": "https://facebook.com/emily.johnson",
                    "visibility": "public",
                    "status": "Active",
                    "value": Decimal("350000.00")
                },
                {
                    "first_name": "Maria",
                    "last_name": "Garcia",
                    "email": "maria@gmail.com",
                    "phone": "(120) 3728 039",
                    "mobile": "(120) 3728 039",
                    "job_title": "Environmental Consultant",
                    "department": "Consulting",
                    "contact_type": ContactType.LEAD,
                    "lead_status": LeadStatus.NEW,
                    "company_id": created_companies[3].id,
                    "rating": 4,
                    "owner_id": superadmin.id,
                    "tags": '["Environment", "New"]',
                    "profile_image_url": "/assets/img/users/user-22.jpg",
                    "currency": "USD",
                    "language": "English",
                    "industry": "Environmental Services",
                    "deals_info": "Collins",
                    "lead_source": "Phone Calls",
                    "location": "Denver, United States",
                    "city": "Denver",
                    "state": "Colorado",
                    "country": "United States",
                    "postal_code": "80201",
                    "linkedin_url": "https://linkedin.com/in/maria-garcia",
                    "facebook_url": "https://facebook.com/maria.garcia",
                    "visibility": "public",
                    "status": "Active",
                    "value": Decimal("410000.00")
                },
                # Closed Leads
                {
                    "first_name": "John",
                    "last_name": "Smith",
                    "email": "john@gmail.com",
                    "phone": "(123) 4567 890",
                    "mobile": "(123) 4567 890",
                    "job_title": "Software Engineer",
                    "department": "Engineering",
                    "contact_type": ContactType.LEAD,
                    "lead_status": LeadStatus.CLOSED_WON,
                    "company_id": created_companies[4].id,
                    "rating": 5,
                    "owner_id": superadmin.id,
                    "tags": '["Software", "Won"]',
                    "profile_image_url": "/assets/img/users/user-40.jpg",
                    "currency": "USD",
                    "language": "English",
                    "industry": "Software Development",
                    "deals_info": "Konopelski",
                    "lead_source": "Web Analytics",
                    "location": "Chester, United Kingdom",
                    "city": "Chester",
                    "state": "England",
                    "country": "United Kingdom",
                    "postal_code": "CH1 1AA",
                    "linkedin_url": "https://linkedin.com/in/john-smith",
                    "facebook_url": "https://facebook.com/john.smith",
                    "visibility": "public",
                    "status": "Active",
                    "value": Decimal("320000.00")
                },
                {
                    "first_name": "David",
                    "last_name": "Lee",
                    "email": "david@gmail.com",
                    "phone": "(183) 9302 890",
                    "mobile": "(183) 9302 890",
                    "job_title": "Business Development",
                    "department": "Sales",
                    "contact_type": ContactType.LEAD,
                    "lead_status": LeadStatus.CLOSED_WON,
                    "company_id": created_companies[0].id,
                    "rating": 4,
                    "owner_id": superadmin.id,
                    "tags": '["Business", "Won"]',
                    "profile_image_url": "/assets/img/users/user-08.jpg",
                    "currency": "USD",
                    "language": "English",
                    "industry": "Technology",
                    "deals_info": "Collins",
                    "lead_source": "Website",
                    "location": "Charlotte, United States",
                    "city": "Charlotte",
                    "state": "North Carolina",
                    "country": "United States",
                    "postal_code": "28201",
                    "linkedin_url": "https://linkedin.com/in/david-lee",
                    "facebook_url": "https://facebook.com/david.lee",
                    "visibility": "public",
                    "status": "Active",
                    "value": Decimal("310000.00")
                },
                {
                    "first_name": "Robert",
                    "last_name": "Martinez",
                    "email": "robert@gmail.com",
                    "phone": "(163) 2459 315",
                    "mobile": "(163) 2459 315",
                    "job_title": "Energy Specialist",
                    "department": "Operations",
                    "contact_type": ContactType.LEAD,
                    "lead_status": LeadStatus.CLOSED_WON,
                    "company_id": created_companies[1].id,
                    "rating": 5,
                    "owner_id": superadmin.id,
                    "tags": '["Energy", "Won"]',
                    "profile_image_url": "/assets/img/users/user-12.jpg",
                    "currency": "USD",
                    "language": "English",
                    "industry": "Energy",
                    "deals_info": "Konopelski",
                    "lead_source": "Referral",
                    "location": "Bristol, United Kingdom",
                    "city": "Bristol",
                    "state": "England",
                    "country": "United Kingdom",
                    "postal_code": "BS1 1AA",
                    "linkedin_url": "https://linkedin.com/in/robert-martinez",
                    "facebook_url": "https://facebook.com/robert.martinez",
                    "visibility": "public",
                    "status": "Active",
                    "value": Decimal("450000.00")
                },
                # Lost Leads
                {
                    "first_name": "Michael",
                    "last_name": "Brown",
                    "email": "micael@gmail.com",
                    "phone": "(184) 2719 738",
                    "mobile": "(184) 2719 738",
                    "job_title": "Design Director",
                    "department": "Design",
                    "contact_type": ContactType.LEAD,
                    "lead_status": LeadStatus.CLOSED_LOST,
                    "company_id": created_companies[2].id,
                    "rating": 2,
                    "owner_id": superadmin.id,
                    "tags": '["Design", "Lost"]',
                    "profile_image_url": "/assets/img/users/user-38.jpg",
                    "currency": "USD",
                    "language": "English",
                    "industry": "Design",
                    "deals_info": "Adams",
                    "lead_source": "Social Media",
                    "location": "London, United Kingdom",
                    "city": "London",
                    "state": "England",
                    "country": "United Kingdom",
                    "postal_code": "SW1A 1AA",
                    "linkedin_url": "https://linkedin.com/in/michael-brown",
                    "facebook_url": "https://facebook.com/michael.brown",
                    "visibility": "public",
                    "status": "Active",
                    "value": Decimal("410000.00")
                },
                {
                    "first_name": "Karen",
                    "last_name": "Davis",
                    "email": "darleeo@gmail.com",
                    "phone": "(163) 2459 315",
                    "mobile": "(163) 2459 315",
                    "job_title": "Network Administrator",
                    "department": "IT",
                    "contact_type": ContactType.LEAD,
                    "lead_status": LeadStatus.CLOSED_LOST,
                    "company_id": created_companies[3].id,
                    "rating": 2,
                    "owner_id": superadmin.id,
                    "tags": '["Network", "Lost"]',
                    "profile_image_url": "/assets/img/users/user-49.jpg",
                    "currency": "USD",
                    "language": "English",
                    "industry": "Technology",
                    "deals_info": "Collins",
                    "lead_source": "Phone Calls",
                    "location": "Detroit, United States",
                    "city": "Detroit",
                    "state": "Michigan",
                    "country": "United States",
                    "postal_code": "48201",
                    "linkedin_url": "https://linkedin.com/in/karen-davis",
                    "facebook_url": "https://facebook.com/karen.davis",
                    "visibility": "public",
                    "status": "Active",
                    "value": Decimal("400000.00")
                },
                {
                    "first_name": "James",
                    "last_name": "Anderson",
                    "email": "james@gmail.com",
                    "phone": "(168) 8392 823",
                    "mobile": "(168) 8392 823",
                    "job_title": "Food Service Manager",
                    "department": "Operations",
                    "contact_type": ContactType.LEAD,
                    "lead_status": LeadStatus.CLOSED_LOST,
                    "company_id": created_companies[4].id,
                    "rating": 2,
                    "owner_id": superadmin.id,
                    "tags": '["Food", "Lost"]',
                    "profile_image_url": "/assets/img/users/user-32.jpg",
                    "currency": "USD",
                    "language": "English",
                    "industry": "Food Service",
                    "deals_info": "Konopelski",
                    "lead_source": "Web Analytics",
                    "location": "Manchester, United Kingdom",
                    "city": "Manchester",
                    "state": "England",
                    "country": "United Kingdom",
                    "postal_code": "M1 1AA",
                    "linkedin_url": "https://linkedin.com/in/james-anderson",
                    "facebook_url": "https://facebook.com/james.anderson",
                    "visibility": "public",
                    "status": "Active",
                    "value": Decimal("340000.00")
                }
            ]
            
                    created_contacts = []
                    for contact_data in contacts_data:
                        contact = CRMContact(
                            **contact_data,
                            created_by=superadmin.id
                        )
                        db.add(contact)
                        created_contacts.append(contact)
            
                    db.commit()
                    logger.info(f"Created {len(created_contacts)} contacts")
                else:
                    logger.info(f"CRM contacts already exist ({existing_contacts} found), skipping contact creation...")
                    # Fetch existing contacts for activity relationships
                    created_contacts = db.query(CRMContact).limit(10).all()
            except Exception as e:
                logger.warning(f"Failed to create contacts: {e}")
                logger.info("Continuing with pipeline creation...")
                # Ensure created_contacts is defined even if creation fails
                created_contacts = db.query(CRMContact).limit(10).all()
            
            # Create sample pipelines (always attempt this)
            if existing_pipelines == 0:
                logger.info("Creating CRM pipelines...")
                pipelines_data = [
                {
                    "name": "Sales",
                    "description": "Primary sales pipeline for direct sales activities",
                    "is_default": True,
                    "is_active": True,
                    "stages_config": '["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]',
                    "total_deal_value": Decimal("450000.00"),
                    "deal_count": 315,
                    "current_stage": "Won",
                    "stage_color": "success",
                    "status": "Active"
                },
                {
                    "name": "Marketing",
                    "description": "Marketing qualified leads pipeline",
                    "is_default": False,
                    "is_active": True,
                    "stages_config": '["Lead Generation", "Lead Qualification", "Marketing Qualified", "Sales Qualified"]',
                    "total_deal_value": Decimal("315000.00"),
                    "deal_count": 447,
                    "current_stage": "In Pipeline",
                    "stage_color": "primary",
                    "status": "Active"
                },
                {
                    "name": "Email",
                    "description": "Email marketing campaign pipeline",
                    "is_default": False,
                    "is_active": True,
                    "stages_config": '["Email Sent", "Opened", "Clicked", "Responded", "Converted"]',
                    "total_deal_value": Decimal("610000.00"),
                    "deal_count": 545,
                    "current_stage": "Conversation",
                    "stage_color": "info",
                    "status": "Active"
                },
                {
                    "name": "Operational",
                    "description": "Operational excellence pipeline for process improvements",
                    "is_default": False,
                    "is_active": True,
                    "stages_config": '["Assessment", "Planning", "Implementation", "Review", "Follow Up"]',
                    "total_deal_value": Decimal("550000.00"),
                    "deal_count": 787,
                    "current_stage": "Follow Up",
                    "stage_color": "warning",
                    "status": "Active"
                },
                {
                    "name": "Identify",
                    "description": "Customer identification and targeting pipeline",
                    "is_default": False,
                    "is_active": True,
                    "stages_config": '["Research", "Identification", "Contact", "Qualification", "Lost"]',
                    "total_deal_value": Decimal("740000.00"),
                    "deal_count": 128,
                    "current_stage": "Lost",
                    "stage_color": "danger",
                    "status": "Active"
                },
                {
                    "name": "Collaborative",
                    "description": "Partnership and collaboration pipeline",
                    "is_default": False,
                    "is_active": False,
                    "stages_config": '["Initial Contact", "Partnership Discussion", "Agreement", "Implementation", "Won"]',
                    "total_deal_value": Decimal("500000.00"),
                    "deal_count": 315,
                    "current_stage": "Won",
                    "stage_color": "success",
                    "status": "Inactive"
                },
                {
                    "name": "Calls",
                    "description": "Phone call based sales pipeline",
                    "is_default": False,
                    "is_active": True,
                    "stages_config": '["Cold Call", "Interest", "Follow Up", "Proposal", "Won"]',
                    "total_deal_value": Decimal("840000.00"),
                    "deal_count": 654,
                    "current_stage": "Won",
                    "stage_color": "success",
                    "status": "Active"
                },
                {
                    "name": "Interact",
                    "description": "Interactive engagement pipeline",
                    "is_default": False,
                    "is_active": True,
                    "stages_config": '["Engagement", "Interaction", "Interest", "Conversion", "Won"]',
                    "total_deal_value": Decimal("620000.00"),
                    "deal_count": 664,
                    "current_stage": "Won",
                    "stage_color": "success",
                    "status": "Active"
                },
                {
                    "name": "Chats",
                    "description": "Chat-based customer engagement pipeline",
                    "is_default": False,
                    "is_active": True,
                    "stages_config": '["Chat Initiated", "Engagement", "Interest", "Qualification", "Won"]',
                    "total_deal_value": Decimal("470000.00"),
                    "deal_count": 787,
                    "current_stage": "Won",
                    "stage_color": "success",
                    "status": "Active"
                },
                {
                    "name": "Differentiate",
                    "description": "Product differentiation and positioning pipeline",
                    "is_default": False,
                    "is_active": True,
                    "stages_config": '["Analysis", "Positioning", "Differentiation", "Service Planning", "Schedule Service"]',
                    "total_deal_value": Decimal("450000.00"),
                    "deal_count": 478,
                    "current_stage": "Schedule Service",
                    "stage_color": "secondary",
                    "status": "Active"
                }
            ]
            
                created_pipelines = []
                for pipeline_data in pipelines_data:
                    pipeline = CRMPipeline(
                        **pipeline_data,
                        created_by=superadmin.id
                    )
                    db.add(pipeline)
                    created_pipelines.append(pipeline)
            
                db.commit()
                logger.info(f"Created {len(created_pipelines)} pipelines")
            else:
                logger.info(f"CRM pipelines already exist ({existing_pipelines} found), skipping pipeline creation...")
            
            # Create sample deals (always check if they exist)
            existing_deals = db.query(CRMDeal).count()
            if existing_deals == 0 and len(created_companies) >= 5:
                logger.info("Creating CRM deals...")
                
                # Ensure we have contacts to link deals to
                if not contacts_data or len(created_contacts) == 0:
                    created_contacts = db.query(CRMContact).limit(5).all()
                
                deals_data = [
                    {
                        "name": "Website Redesign",
                        "description": "Complete website redesign and development project",
                        "value": Decimal("450000.00"),
                        "currency": "USD",
                        "stage": DealStage.NEGOTIATION,
                        "probability": 85,
                        "expected_close_date": datetime.now() + timedelta(days=30),
                        "company_id": created_companies[0].id,
                        "contact_id": created_contacts[0].id,
                        "lead_source": "Website",
                        "next_step": "Schedule final presentation with decision makers",
                        "pipeline": "Sales",
                        "status": "Open",
                        "owner": "Sushanth"
                    },
                    {
                        "name": "Cloud Backup Solution",
                        "description": "Enterprise cloud backup and disaster recovery solution",
                        "value": Decimal("500000.00"),
                        "currency": "USD",
                        "stage": DealStage.PROSPECTING,
                        "probability": 15,
                        "expected_close_date": datetime.now() + timedelta(days=45),
                        "company_id": created_companies[1].id,
                        "contact_id": created_contacts[1].id,
                        "lead_source": "Referral",
                        "next_step": "Send detailed proposal and timeline",
                        "pipeline": "Marketing",
                        "status": "Open",
                        "owner": "Raghav"
                    },
                    {
                        "name": "Email Marketing Campaign",
                        "description": "Comprehensive email marketing automation setup",
                        "value": Decimal("740000.00"),
                        "currency": "USD",
                        "stage": DealStage.PROSPECTING,
                        "probability": 95,
                        "expected_close_date": datetime.now() + timedelta(days=60),
                        "company_id": created_companies[2].id,
                        "contact_id": created_contacts[2].id,
                        "lead_source": "Social Media",
                        "next_step": "Conduct technical requirements assessment",
                        "pipeline": "Marketing",
                        "status": "Open",
                        "owner": "Siddhartha"
                    },
                    {
                        "name": "App Development Project",
                        "description": "Mobile application development for iOS and Android",
                        "value": Decimal("315000.00"),
                        "currency": "USD",
                        "stage": DealStage.PROPOSAL,
                        "probability": 95,
                        "expected_close_date": datetime.now() + timedelta(days=30),
                        "company_id": created_companies[3].id,
                        "contact_id": created_contacts[3].id,
                        "lead_source": "Conference",
                        "next_step": "Final contract review",
                        "pipeline": "Sales",
                        "status": "Open",
                        "owner": "Jahnavi"
                    },
                    {
                        "name": "Cloud Migration Services",
                        "description": "Complete cloud infrastructure migration and setup",
                        "value": Decimal("180000.00"),
                        "currency": "USD",
                        "stage": DealStage.CLOSED_WON,
                        "probability": 100,
                        "expected_close_date": datetime.now() - timedelta(days=15),
                        "actual_close_date": datetime.now() - timedelta(days=15),
                        "company_id": created_companies[4].id if len(created_companies) > 4 else created_companies[0].id,
                        "contact_id": created_contacts[4].id if len(created_contacts) > 4 else created_contacts[0].id,
                        "lead_source": "Website",
                        "is_won": True,
                        "pipeline": "Sales",
                        "status": "Won",
                        "owner": "Keerthi Suresh"
                    }
                ]
                
                created_deals = []
                for deal_data in deals_data:
                    deal = CRMDeal(
                        **deal_data,
                        created_by=superadmin.id
                    )
                    db.add(deal)
                    created_deals.append(deal)
                
                db.commit()
                logger.info(f"Created {len(created_deals)} deals")
            else:
                logger.info(f"CRM deals already exist ({existing_deals} found) or insufficient companies, skipping deal creation...")
                # Fetch existing deals for activity relationships
                created_deals = db.query(CRMDeal).limit(5).all()
            
            # Create sample activities (always check if they exist)
            existing_activities = db.query(CRMActivity).count()
            if existing_activities == 0 and len(created_companies) >= 5:
                logger.info("Creating CRM activities...")
                
                # Ensure we have contacts for relationships
                if not created_contacts or len(created_contacts) == 0:
                    created_contacts = db.query(CRMContact).limit(10).all()
                
                activities_data = [
                    {
                        "subject": "We scheduled a meeting for next week",
                        "description": "Meeting scheduled to discuss project requirements and timeline",
                        "activity_type": ActivityType.MEETING,
                        "priority": Priority.HIGH,
                        "due_date": datetime.now() + timedelta(days=7),
                        "owner": "Durga prasad",
                        "time": "10:00",
                        "remainder": "1 day before",
                        "remainder_type": "Work",
                        "guests": "Team Members",
                        "deals": "Enterprise Deal",
                        "contacts": "John Smith",
                        "companies": "BrightWave Innovations",
                        "company_id": created_companies[0].id,
                        "contact_id": created_contacts[0].id if created_contacts else None,
                        "deal_id": created_deals[0].id if created_deals else None
                    },
                    {
                        "subject": "Analysing latest time estimation for new project",
                        "description": "Review and analyze time estimates for the new project deliverables",
                        "activity_type": ActivityType.TASK,
                        "priority": Priority.HIGH,
                        "due_date": datetime.now() + timedelta(days=5),
                        "owner": "Hruthik",
                        "time": "09:00",
                        "remainder": "2 hours before",
                        "remainder_type": "Work",
                        "deals": "Quantum Project",
                        "contacts": "Sarah Wilson",
                        "companies": "Quantum Nexus",
                        "company_id": created_companies[2].id if len(created_companies) > 2 else created_companies[0].id,
                        "contact_id": created_contacts[2].id if len(created_contacts) > 2 else created_contacts[0].id,
                        "deal_id": created_deals[2].id if len(created_deals) > 2 else None
                    },
                    {
                        "subject": "Store and manage contact data",
                        "description": "Email regarding contact data management and storage solutions",
                        "activity_type": ActivityType.EMAIL,
                        "priority": Priority.MEDIUM,
                        "due_date": datetime.now() + timedelta(days=2),
                        "owner": "Swetha",
                        "time": "11:00",
                        "remainder": "1 day before",
                        "remainder_type": "Work",
                        "deals": "Data Management Deal",
                        "contacts": "Mike Davis",
                        "companies": "DataFlow Systems",
                        "company_id": created_companies[3].id if len(created_companies) > 3 else created_companies[0].id,
                        "contact_id": created_contacts[3].id if len(created_contacts) > 3 else created_contacts[0].id,
                        "deal_id": created_deals[0].id if created_deals else None
                    },
                    {
                        "subject": "Call John and discuss about project",
                        "description": "Follow-up call with John to discuss project status and requirements",
                        "activity_type": ActivityType.CALL,
                        "priority": Priority.HIGH,
                        "due_date": datetime.now() + timedelta(days=1),
                        "owner": "Kranthi",
                        "time": "15:00",
                        "remainder": "15 minutes before",
                        "remainder_type": "Work",
                        "deals": "John's Project",
                        "contacts": "John Anderson",
                        "companies": "Anderson Corp",
                        "company_id": created_companies[4].id if len(created_companies) > 4 else created_companies[0].id,
                        "contact_id": created_contacts[4].id if len(created_contacts) > 4 else created_contacts[0].id,
                        "deal_id": created_deals[1].id if len(created_deals) > 1 else None
                    },
                    {
                        "subject": "Will have a meeting before project start",
                        "description": "Pre-project kickoff meeting to align on objectives and deliverables",
                        "activity_type": ActivityType.MEETING,
                        "priority": Priority.HIGH,
                        "due_date": datetime.now() + timedelta(days=10),
                        "owner": "Naveen",
                        "time": "10:30",
                        "remainder": "2 hours before",
                        "remainder_type": "Work",
                        "guests": "Project Stakeholders",
                        "deals": "Kickoff Project",
                        "contacts": "Lisa Chen",
                        "companies": "TechStart Inc",
                        "company_id": created_companies[5].id if len(created_companies) > 5 else created_companies[0].id,
                        "contact_id": created_contacts[5].id if len(created_contacts) > 5 else created_contacts[0].id,
                        "deal_id": created_deals[2].id if len(created_deals) > 2 else None,
                        "location": "Main Conference Room"
                    },
                    {
                        "subject": "Built landing pages",
                        "description": "Email update on landing page development progress",
                        "activity_type": ActivityType.EMAIL,
                        "priority": Priority.MEDIUM,
                        "due_date": datetime.now() + timedelta(days=4),
                        "is_completed": True,
                        "completed_at": datetime.now() - timedelta(days=2),
                        "owner": "Sameer",
                        "time": "16:00",
                        "remainder": "1 hour before",
                        "remainder_type": "Work",
                        "outcome": "Landing pages completed and deployed successfully",
                        "deals": "Web Development Deal",
                        "contacts": "Tom Wilson",
                        "companies": "WebCorp Solutions",
                        "company_id": created_companies[0].id,
                        "contact_id": created_contacts[6].id if len(created_contacts) > 6 else created_contacts[0].id,
                        "deal_id": created_deals[0].id if created_deals else None
                    },
                    {
                        "subject": "Discussed budget proposal with Edwin",
                        "description": "Call to review and finalize budget proposal details",
                        "activity_type": ActivityType.CALL,
                        "priority": Priority.HIGH,
                        "due_date": datetime.now() + timedelta(days=6),
                        "is_completed": True,
                        "completed_at": datetime.now() - timedelta(days=3),
                        "owner": "Afran",
                        "time": "13:30",
                        "remainder": "30 minutes before",
                        "remainder_type": "Work",
                        "outcome": "Budget approved with minor adjustments",
                        "deals": "Budget Proposal Deal",
                        "contacts": "Edwin Rodriguez",
                        "companies": "Finance Plus",
                        "company_id": created_companies[0].id,
                        "contact_id": created_contacts[7].id if len(created_contacts) > 7 else created_contacts[0].id,
                        "deal_id": created_deals[1].id if len(created_deals) > 1 else None
                    }
                ]
                
                created_activities = []
                for activity_data in activities_data:
                    activity = CRMActivity(
                        **activity_data,
                        created_by=superadmin.id
                    )
                    db.add(activity)
                    created_activities.append(activity)
                
                db.commit()
                logger.info(f"Created {len(created_activities)} activities")
            else:
                logger.info(f"CRM activities already exist ({existing_activities} found) or insufficient companies, skipping activity creation...")
            
            logger.info("[OK] CRM sample data created successfully")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create CRM sample data: {str(e)}")
        logger.info("Continuing setup despite CRM data creation failure...")
        return True  # Continue setup even if this fails


def create_employee_profiles_data():
    """Create clean employee profiles data from CSV with no NULL values"""
    logger.info("\nStep CSV: Creating clean employee profiles data...")
    
    try:
        try:
            import pandas as pd
        except ImportError:
            logger.warning("Pandas not installed. Creating sample data instead. Install with: pip install pandas")
            return create_sample_employee_profiles()
            
        import os
        from datetime import datetime, date
        import random
        
        # Check if CSV file exists
        csv_file = "employee_profiles.csv"
        if not os.path.exists(csv_file):
            logger.warning(f"CSV file {csv_file} not found, creating sample data...")
            return create_sample_employee_profiles()
        
        with get_db_context() as db:
            # Get default business
            business = db.query(Business).first()
            if not business:
                logger.error("[ERROR] No business found in database")
                return False
            
            # Get superadmin user
            superadmin = db.query(User).filter(User.email == settings.SUPERADMIN_EMAIL).first()
            if not superadmin:
                logger.error("[ERROR] Superadmin not found")
                return False
            
            # Read CSV file
            logger.info(f"📖 Reading {csv_file}...")
            df = pd.read_csv(csv_file)
            logger.info(f"[DATA] Found {len(df)} employee profiles in CSV")
            
            # Clean data and remove NULL values
            logger.info("🧹 Cleaning data and removing NULL values...")
            
            # Sample data for filling NULL values
            cities_data = [
                {"city": "Hyderabad", "state": "Telangana", "country": "India", "pincode": "500001"},
                {"city": "Bangalore", "state": "Karnataka", "country": "India", "pincode": "560001"},
                {"city": "Mumbai", "state": "Maharashtra", "country": "India", "pincode": "400001"},
                {"city": "Chennai", "state": "Tamil Nadu", "country": "India", "pincode": "600001"},
                {"city": "Delhi", "state": "Delhi", "country": "India", "pincode": "110001"},
                {"city": "Pune", "state": "Maharashtra", "country": "India", "pincode": "411001"},
                {"city": "Kolkata", "state": "West Bengal", "country": "India", "pincode": "700001"}
            ]
            
            banks_data = [
                {"name": "HDFC Bank", "ifsc": "HDFC0001234", "branch": "HDFC Main Branch"},
                {"name": "ICICI Bank", "ifsc": "ICIC0001234", "branch": "ICICI Main Branch"},
                {"name": "State Bank of India", "ifsc": "SBIN0001234", "branch": "SBI Main Branch"},
                {"name": "Axis Bank", "ifsc": "UTIB0001234", "branch": "Axis Main Branch"},
                {"name": "Kotak Mahindra Bank", "ifsc": "KKBK0001234", "branch": "Kotak Main Branch"},
                {"name": "Punjab National Bank", "ifsc": "PUNB0001234", "branch": "PNB Main Branch"},
                {"name": "Union Bank of India", "ifsc": "UBIN0001234", "branch": "Union Bank Main Branch"}
            ]
            
            relationships = ["Father", "Mother", "Spouse", "Brother", "Sister", "Uncle", "Aunt"]
            vaccination_statuses = ["Vaccinated", "Not Vaccinated", "Partially Vaccinated"]
            workman_versions = ["7.5.33", "7.5.32", "7.5.31", "7.4.28", "7.4.27", "Not Installed"]
            
            profiles_created = 0
            profiles_updated = 0
            
            for index, row in df.iterrows():
                try:
                    employee_id = int(row['employee_id'])
                    
                    # Check if employee exists
                    employee = db.query(Employee).filter(Employee.id == employee_id).first()
                    if not employee:
                        logger.warning(f"[WARNING] Employee ID {employee_id} not found, skipping...")
                        continue
                    
                    logger.info(f"Processing Employee Profile for ID {employee_id}: {employee.full_name}")
                    
                    # Check if profile already exists
                    existing_profile = db.query(EmployeeProfile).filter(
                        EmployeeProfile.employee_id == employee_id
                    ).first()
                    
                    # Select random city and bank data for NULL values
                    city_data = random.choice(cities_data)
                    bank_data = random.choice(banks_data)
                    
                    # Determine workman_installed first for later use
                    workman_installed = (
                        bool(row['workman_installed']) if pd.notna(row['workman_installed'])
                        else random.choice([True, False])
                    )
                    
                    # Clean and prepare data with no NULL values
                    profile_data = {
                        'employee_id': employee_id,
                        
                        # Present Address - Clean NULL values
                        'present_address_line1': (
                            row['present_address_line1'] if pd.notna(row['present_address_line1']) and row['present_address_line1'] != 'Address not provided'
                            else f"Flat {random.randint(101, 999)}, Building {random.randint(1, 50)}"
                        ),
                        'present_address_line2': (
                            row['present_address_line2'] if pd.notna(row['present_address_line2'])
                            else f"Street {random.randint(1, 100)}, Area {random.randint(1, 20)}"
                        ),
                        'present_city': (
                            row['present_city'] if pd.notna(row['present_city'])
                            else city_data["city"]
                        ),
                        'present_state': (
                            row['present_state'] if pd.notna(row['present_state'])
                            else city_data["state"]
                        ),
                        'present_country': (
                            row['present_country'] if pd.notna(row['present_country'])
                            else city_data["country"]
                        ),
                        'present_pincode': (
                            row['present_pincode'] if pd.notna(row['present_pincode'])
                            else city_data["pincode"]
                        ),
                        
                        # Permanent Address - Clean NULL values
                        'permanent_address_line1': (
                            row['permanent_address_line1'] if pd.notna(row['permanent_address_line1']) and row['permanent_address_line1'] != 'Address not provided'
                            else f"H.No {random.randint(1, 999)}-{random.randint(1, 999)}, Colony {random.randint(1, 50)}"
                        ),
                        'permanent_address_line2': (
                            row['permanent_address_line2'] if pd.notna(row['permanent_address_line2'])
                            else f"Road No {random.randint(1, 50)}, Sector {random.randint(1, 20)}"
                        ),
                        'permanent_city': (
                            row['permanent_city'] if pd.notna(row['permanent_city'])
                            else city_data["city"]
                        ),
                        'permanent_state': (
                            row['permanent_state'] if pd.notna(row['permanent_state'])
                            else city_data["state"]
                        ),
                        'permanent_country': (
                            row['permanent_country'] if pd.notna(row['permanent_country'])
                            else city_data["country"]
                        ),
                        'permanent_pincode': (
                            row['permanent_pincode'] if pd.notna(row['permanent_pincode'])
                            else city_data["pincode"]
                        ),
                        
                        # Statutory Information - Clean NULL values
                        'pan_number': (
                            row['pan_number'] if pd.notna(row['pan_number']) and row['pan_number'] != ''
                            else f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=5))}{random.randint(1000, 9999)}{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=1))}"
                        ),
                        'aadhaar_number': (
                            row['aadhaar_number'] if pd.notna(row['aadhaar_number']) and row['aadhaar_number'] != ''
                            else f"{random.randint(100000000000, 999999999999)}"
                        ),
                        'uan_number': (
                            row['uan_number'] if pd.notna(row['uan_number']) and row['uan_number'] != ''
                            else f"{random.randint(100000000000, 999999999999)}"
                        ),
                        'esi_number': (
                            row['esi_number'] if pd.notna(row['esi_number']) and row['esi_number'] != ''
                            else f"{random.randint(1000000000, 9999999999)}"
                        ),
                        
                        # Bank Information - Clean NULL values
                        'bank_name': (
                            row['bank_name'] if pd.notna(row['bank_name']) and row['bank_name'] != ''
                            else bank_data["name"]
                        ),
                        'bank_account_number': (
                            row['bank_account_number'] if pd.notna(row['bank_account_number']) and row['bank_account_number'] != ''
                            else f"{random.randint(100000000000, 999999999999)}"
                        ),
                        'bank_ifsc_code': (
                            row['bank_ifsc_code'] if pd.notna(row['bank_ifsc_code']) and row['bank_ifsc_code'] != ''
                            else bank_data["ifsc"]
                        ),
                        'bank_branch': (
                            row['bank_branch'] if pd.notna(row['bank_branch']) and row['bank_branch'] != ''
                            else bank_data["branch"]
                        ),
                        
                        # Emergency Contact - Clean NULL values
                        'emergency_contact_name': (
                            row['emergency_contact_name'] if pd.notna(row['emergency_contact_name']) and row['emergency_contact_name'] != ''
                            else f"{employee.first_name} Emergency Contact"
                        ),
                        'emergency_contact_relationship': (
                            row['emergency_contact_relationship'] if pd.notna(row['emergency_contact_relationship']) and row['emergency_contact_relationship'] != ''
                            else random.choice(relationships)
                        ),
                        'emergency_contact_mobile': (
                            row['emergency_contact_mobile'] if pd.notna(row['emergency_contact_mobile']) and row['emergency_contact_mobile'] != ''
                            else f"+91-{random.randint(7000000000, 9999999999)}"
                        ),
                        'emergency_contact_address': (
                            row['emergency_contact_address'] if pd.notna(row['emergency_contact_address']) and row['emergency_contact_address'] != ''
                            else f"Emergency Contact Address for {employee.full_name}"
                        ),
                        
                        # Additional Information - Clean NULL values
                        'profile_image_url': (
                            row['profile_image_url'] if pd.notna(row['profile_image_url']) and row['profile_image_url'] != ''
                            else f"https://randomuser.me/api/portraits/{'women' if employee.gender == Gender.FEMALE else 'men'}/{(employee_id % 10) + 1}.jpg"
                        ),
                        'bio': (
                            row['bio'] if pd.notna(row['bio']) and row['bio'] != ''
                            else f"Experienced professional working at {business.business_name} with expertise in {employee.designation.name if employee.designation else 'various technologies'}."
                        ),
                        'skills': (
                            row['skills'] if pd.notna(row['skills']) and row['skills'] != ''
                            else '["Python", "SQL", "Data Analysis", "Project Management", "Communication"]'
                        ),
                        'certifications': (
                            row['certifications'] if pd.notna(row['certifications']) and row['certifications'] != ''
                            else '["Professional Certification", "Technical Training", "Industry Standards"]'
                        ),
                        
                        # Wedding Date - Handle NULL
                        'wedding_date': (
                            datetime.strptime(row['wedding_date'], '%Y-%m-%d').date() 
                            if pd.notna(row['wedding_date']) and row['wedding_date'] != ''
                            else (
                                date(
                                    datetime.now().year - random.randint(1, 10),
                                    random.randint(1, 12),
                                    random.randint(1, 28)
                                ) if employee.marital_status == MaritalStatus.MARRIED else None
                            )
                        ),
                        
                        # Vaccination Status - Clean NULL values
                        'vaccination_status': (
                            row['vaccination_status'] if pd.notna(row['vaccination_status']) and row['vaccination_status'] != ''
                            else random.choice(vaccination_statuses)
                        ),
                        
                        # Workman Information - Clean NULL values
                        'workman_installed': workman_installed,
                        'workman_version': (
                            row['workman_version'] if pd.notna(row['workman_version']) and row['workman_version'] != ''
                            else random.choice(workman_versions)
                        ),
                        'workman_last_seen': (
                            datetime.fromisoformat(row['workman_last_seen'].replace('+05:30', ''))
                            if pd.notna(row['workman_last_seen']) and row['workman_last_seen'] != ''
                            else (
                                datetime.now() - timedelta(days=random.randint(0, 30))
                                if workman_installed else None
                            )
                        ),
                        
                        # System fields
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    }
                    
                    if existing_profile:
                        # Update existing profile
                        for key, value in profile_data.items():
                            if key != 'employee_id':  # Don't update the foreign key
                                setattr(existing_profile, key, value)
                        profiles_updated += 1
                        logger.info(f"[OK] Updated profile for Employee ID {employee_id}")
                    else:
                        # Create new profile
                        new_profile = EmployeeProfile(**profile_data)
                        db.add(new_profile)
                        profiles_created += 1
                        logger.info(f"[OK] Created profile for Employee ID {employee_id}")
                
                except Exception as e:
                    logger.error(f"[ERROR] Error processing Employee ID {employee_id}: {e}")
                    continue
            
            # Commit all changes
            db.commit()
            
            logger.info("[OK] Employee profiles data creation completed successfully!")
            logger.info(f"[DATA] Summary:")
            logger.info(f"   - Profiles created: {profiles_created}")
            logger.info(f"   - Profiles updated: {profiles_updated}")
            logger.info(f"   - Total processed: {profiles_created + profiles_updated}")
            
            return True
    
    except Exception as e:
        logger.error(f"[ERROR] Failed to create employee profiles data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_sample_employee_profiles():
    """Create sample employee profiles when CSV is not available"""
    logger.info("[NOTE] Creating sample employee profiles...")
    
    try:
        with get_db_context() as db:
            # Get default business
            business = db.query(Business).first()
            if not business:
                logger.error("[ERROR] No business found in database")
                return False
            
            # Get employees that need profiles
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == EmployeeStatus.ACTIVE
            ).limit(20).all()
            
            if not employees:
                logger.info("ℹ️ No employees found for profile creation")
                return True
            
            # Sample data
            cities_data = [
                {"city": "Hyderabad", "state": "Telangana", "country": "India", "pincode": "500001"},
                {"city": "Bangalore", "state": "Karnataka", "country": "India", "pincode": "560001"},
                {"city": "Mumbai", "state": "Maharashtra", "country": "India", "pincode": "400001"},
                {"city": "Chennai", "state": "Tamil Nadu", "country": "India", "pincode": "600001"},
                {"city": "Delhi", "state": "Delhi", "country": "India", "pincode": "110001"}
            ]
            
            banks_data = [
                {"name": "HDFC Bank", "ifsc": "HDFC0001234", "branch": "HDFC Main Branch"},
                {"name": "ICICI Bank", "ifsc": "ICIC0001234", "branch": "ICICI Main Branch"},
                {"name": "State Bank of India", "ifsc": "SBIN0001234", "branch": "SBI Main Branch"},
                {"name": "Axis Bank", "ifsc": "UTIB0001234", "branch": "Axis Main Branch"},
                {"name": "Kotak Mahindra Bank", "ifsc": "KKBK0001234", "branch": "Kotak Main Branch"}
            ]
            
            relationships = ["Father", "Mother", "Spouse", "Brother", "Sister"]
            vaccination_statuses = ["Vaccinated", "Not Vaccinated", "Partially Vaccinated"]
            workman_versions = ["7.5.33", "7.5.32", "7.5.31", "Not Installed"]
            
            profiles_created = 0
            
            for employee in employees:
                # Check if profile already exists
                existing_profile = db.query(EmployeeProfile).filter(
                    EmployeeProfile.employee_id == employee.id
                ).first()
                
                if existing_profile:
                    continue
                
                # Select random data
                city_data = random.choice(cities_data)
                bank_data = random.choice(banks_data)
                
                # Create comprehensive profile with no NULL values
                profile = EmployeeProfile(
                    employee_id=employee.id,
                    
                    # Present Address
                    present_address_line1=f"Flat {random.randint(101, 999)}, Building {random.randint(1, 50)}",
                    present_address_line2=f"Street {random.randint(1, 100)}, Area {random.randint(1, 20)}",
                    present_city=city_data["city"],
                    present_state=city_data["state"],
                    present_country=city_data["country"],
                    present_pincode=city_data["pincode"],
                    
                    # Permanent Address
                    permanent_address_line1=f"H.No {random.randint(1, 999)}-{random.randint(1, 999)}, Colony {random.randint(1, 50)}",
                    permanent_address_line2=f"Road No {random.randint(1, 50)}, Sector {random.randint(1, 20)}",
                    permanent_city=city_data["city"],
                    permanent_state=city_data["state"],
                    permanent_country=city_data["country"],
                    permanent_pincode=city_data["pincode"],
                    
                    # Statutory Information
                    pan_number=f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=5))}{random.randint(1000, 9999)}{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=1))}",
                    aadhaar_number=f"{random.randint(100000000000, 999999999999)}",
                    uan_number=f"{random.randint(100000000000, 999999999999)}",
                    esi_number=f"{random.randint(1000000000, 9999999999)}",
                    
                    # Bank Information
                    bank_name=bank_data["name"],
                    bank_account_number=f"{random.randint(100000000000, 999999999999)}",
                    bank_ifsc_code=bank_data["ifsc"],
                    bank_branch=bank_data["branch"],
                    
                    # Emergency Contact
                    emergency_contact_name=f"{employee.first_name} Emergency Contact",
                    emergency_contact_relationship=random.choice(relationships),
                    emergency_contact_mobile=f"+91-{random.randint(7000000000, 9999999999)}",
                    emergency_contact_address=f"Emergency Contact Address for {employee.full_name}",
                    
                    # Additional Information
                    profile_image_url=f"https://randomuser.me/api/portraits/{'women' if employee.gender == Gender.FEMALE else 'men'}/{(employee.id % 10) + 1}.jpg",
                    bio=f"Experienced professional working at {business.business_name} with expertise in various technologies.",
                    skills='["Python", "SQL", "Data Analysis", "Project Management", "Communication"]',
                    certifications='["Professional Certification", "Technical Training", "Industry Standards"]',
                    
                    # Wedding Date (for married employees)
                    wedding_date=(
                        date(
                            datetime.now().year - random.randint(1, 10),
                            random.randint(1, 12),
                            random.randint(1, 28)
                        ) if employee.marital_status == MaritalStatus.MARRIED else None
                    ),
                    
                    # Vaccination Status
                    vaccination_status=random.choice(vaccination_statuses),
                    
                    # Workman Information
                    workman_installed=random.choice([True, False]),
                    workman_version=random.choice(workman_versions),
                    workman_last_seen=(
                        datetime.now() - timedelta(days=random.randint(0, 30))
                        if random.choice([True, False]) else None
                    ),
                    
                    created_at=datetime.now()
                )
                
                db.add(profile)
                profiles_created += 1
                logger.info(f"[OK] Created sample profile for {employee.full_name}")
            
            db.commit()
            logger.info(f"[OK] Sample employee profiles created: {profiles_created}")
            return True
    
    except Exception as e:
        logger.error(f"[ERROR] Failed to create sample employee profiles: {e}")
        import traceback
        traceback.print_exc()
        return False


def populate_employee_events_data():
    """
    Populate employee events data (birthdays and wedding dates) for Employee Events module
    
    This function ensures all employees have the necessary date fields populated for the
    Employee Events report module, which displays three types of events:
    
    1. Birthdays (from Employee.date_of_birth)
    2. Work Anniversaries (from Employee.date_of_joining) 
    3. Wedding Anniversaries (from EmployeeProfile.wedding_date)
    
    The function:
    - Generates random birthdays (1980-2000) for employees without date_of_birth
    - Generates random wedding dates (2010-2023) for married employees or 70% of others
    - Creates EmployeeProfile records if they don't exist
    - Only updates NULL/missing values, preserves existing data
    
    This ensures the Employee Events module has complete data to display.
    """
    logger.info("\nStep: Populating employee events data...")
    
    try:
        with get_db_context() as db:
            # Get all employees
            employees = db.query(Employee).all()
            
            if not employees:
                logger.warning("No employees found!")
                return True
            
            logger.info(f"Found {len(employees)} employees")
            
            # Months for variety
            months = list(range(1, 13))
            days = list(range(1, 29))  # Safe range for all months
            
            updated_count = 0
            
            for employee in employees:
                # Update date_of_birth if not set
                if not employee.date_of_birth:
                    # Generate random birthday between 1980-2000
                    year = random.randint(1980, 2000)
                    month = random.choice(months)
                    day = random.choice(days)
                    employee.date_of_birth = date(year, month, day)
                    logger.info(f"  Updated {employee.employee_code} birthday: {employee.date_of_birth}")
                    updated_count += 1
                
                # Get or create employee profile
                profile = db.query(EmployeeProfile).filter(
                    EmployeeProfile.employee_id == employee.id
                ).first()
                
                if not profile:
                    profile = EmployeeProfile(employee_id=employee.id)
                    db.add(profile)
                    db.flush()
                
                # Update wedding_date if not set (for married employees or 70% of others)
                if not profile.wedding_date:
                    # Add wedding date for married employees or 70% of others
                    if employee.marital_status == MaritalStatus.MARRIED or random.random() > 0.3:
                        # Generate random wedding date between 2010-2023
                        year = random.randint(2010, 2023)
                        month = random.choice(months)
                        day = random.choice(days)
                        profile.wedding_date = date(year, month, day)
                        logger.info(f"  Updated {employee.employee_code} wedding date: {profile.wedding_date}")
                        updated_count += 1
            
            db.commit()
            logger.info(f"\n✓ Successfully updated {updated_count} event records")
            
            # Verify the updates
            logger.info("\nVerifying updates...")
            employees_with_birthdays = db.query(Employee).filter(Employee.date_of_birth.isnot(None)).count()
            profiles_with_wedding = db.query(EmployeeProfile).filter(EmployeeProfile.wedding_date.isnot(None)).count()
            employees_with_joining = db.query(Employee).filter(Employee.date_of_joining.isnot(None)).count()
            
            logger.info(f"  Employees with birthdays: {employees_with_birthdays}")
            logger.info(f"  Employees with wedding dates: {profiles_with_wedding}")
            logger.info(f"  Employees with work anniversaries: {employees_with_joining}")
            
            return True
            
    except Exception as e:
        logger.error(f"✗ Error populating employee events data: {e}")
        import traceback
        traceback.print_exc()
        return False


def import_employees_from_csv():
    """Import employees from Employee_Register(Sheet1).csv"""
    logger.info("\nStep CSV: Importing employees from Employee_Register CSV...")
    
    try:
        import os
        import csv
        
        # Check if CSV file exists
        csv_file = "Employee_Register(Sheet1).csv"
        if not os.path.exists(csv_file):
            logger.warning(f"CSV file {csv_file} not found, skipping import...")
            return True
        
        with get_db_context() as db:
            # Check if employees from Employee_Register already exist
            existing_lev_employees = db.query(Employee).filter(Employee.employee_code.like('LEV%')).count()
            if existing_lev_employees > 0:
                logger.info(f"✅ Employee_Register employees already imported ({existing_lev_employees} found), skipping...")
                return True
            
            # Read CSV file
            logger.info(f"📖 Reading {csv_file}...")
            df = pd.read_csv(csv_file)
            
            logger.info(f"[DATA] Found {len(df)} employees in CSV")
            
            # Check if CSV has required columns
            required_columns = ['id', 'employee_code', 'first_name', 'last_name', 'email']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.warning(f"CSV is missing required columns: {missing_columns}")
                logger.warning(f"Available columns: {list(df.columns)}")
                logger.warning("Skipping CSV import - please ensure CSV has the correct format")
                return True
            
            # Get default business
            business = db.query(Business).first()
            if not business:
                logger.error("[ERROR] No business found in database")
                return False
            
            def parse_date(date_str):
                """Parse date string in M/D/YYYY format"""
                if not date_str or pd.isna(date_str) or date_str == 'NULL':
                    return None
                
                try:
                    return datetime.strptime(str(date_str), '%m/%d/%Y').date()
                except:
                    try:
                        return datetime.strptime(str(date_str), '%Y-%m-%d').date()
                    except:
                        return None
            
            imported_count = 0
            updated_count = 0
            profile_created_count = 0
            
            for index, row in df.iterrows():
                employee_id = row['id']
                
                logger.info(f"Processing Employee ID {employee_id}: {row['first_name']} {row['last_name']}")
                
                # Check if employee already exists
                existing_employee = db.query(Employee).filter(Employee.id == employee_id).first()
                
                if existing_employee:
                    employee = existing_employee
                    updated_count += 1
                else:
                    employee = Employee()
                    imported_count += 1
                
                # Update employee fields
                employee.id = employee_id
                employee.employee_code = row['employee_code']
                employee.first_name = row['first_name']
                employee.last_name = row['last_name']
                employee.middle_name = row['middle_name'] if row['middle_name'] != 'NULL' else None
                employee.email = row['email']
                employee.mobile = str(row['mobile']).replace('-', '') if not pd.isna(row['mobile']) else None
                employee.alternate_mobile = str(row['alternate_mobile']).replace('-', '') if not pd.isna(row['alternate_mobile']) else None
                
                # Parse dates
                employee.date_of_birth = parse_date(row['date_of_birth'])
                employee.date_of_joining = parse_date(row['date_of_joining'])
                employee.date_of_confirmation = parse_date(row['date_of_confirmation'])
                employee.date_of_termination = parse_date(row['date_of_termination'])
                employee.date_of_marriage = parse_date(row['date_of_marriage'])
                
                # Set enum fields
                if not pd.isna(row['gender']) and row['gender'] != 'NULL':
                    employee.gender = row['gender'].lower()
                
                if not pd.isna(row['marital_status']) and row['marital_status'] != 'NULL':
                    employee.marital_status = row['marital_status'].lower()
                
                if not pd.isna(row['employee_status']) and row['employee_status'] != 'NULL':
                    employee.employee_status = row['employee_status'].lower()
                
                # Set other fields
                employee.blood_group = row['blood_group'] if row['blood_group'] != 'NULL' else None
                employee.nationality = row['nationality'] if row['nationality'] != 'NULL' else None
                employee.religion = row['religion'] if row['religion'] != 'NULL' else None
                
                # Set organizational fields
                employee.business_id = row['business_id'] if not pd.isna(row['business_id']) else business.id
                employee.department_id = row['department_id'] if not pd.isna(row['department_id']) else None
                employee.designation_id = row['designation_id'] if not pd.isna(row['designation_id']) else None
                employee.location_id = row['location_id'] if not pd.isna(row['location_id']) else None
                employee.cost_center_id = row['cost_center_id'] if not pd.isna(row['cost_center_id']) else None
                employee.grade_id = row['grade_id'] if not pd.isna(row['grade_id']) else None
                employee.shift_policy_id = row['shift_policy_id'] if not pd.isna(row['shift_policy_id']) else None
                employee.weekoff_policy_id = row['weekoff_policy_id'] if not pd.isna(row['weekoff_policy_id']) else None
                employee.reporting_manager_id = row['reporting_manager_id'] if not pd.isna(row['reporting_manager_id']) else None
                
                # Set additional fields from CSV
                employee.office_phone = row['office_phone'] if row['office_phone'] != 'NULL' else None
                employee.official_email = row['official_email'] if row['official_email'] != 'NULL' else None
                employee.current_address = row['current_address'] if row['current_address'] != 'NULL' else None
                employee.permanent_address = row['permanent_address'] if row['permanent_address'] != 'NULL' else None
                employee.pan_number = row['pan_number'] if row['pan_number'] != 'NULL' else None
                employee.aadhar_number = row['aadhar_number'] if row['aadhar_number'] != 'NULL' else None
                employee.passport_number = row['passport_number'] if row['passport_number'] != 'NULL' else None
                employee.passport_expiry = parse_date(row['passport_expiry'])
                employee.driving_license = row['driving_license'] if row['driving_license'] != 'NULL' else None
                employee.license_expiry = parse_date(row['license_expiry'])
                employee.emergency_contact = row['emergency_contact'] if row['emergency_contact'] != 'NULL' else None
                employee.emergency_phone = row['emergency_phone'] if row['emergency_phone'] != 'NULL' else None
                employee.father_name = row['father_name'] if row['father_name'] != 'NULL' else None
                employee.mother_name = row['mother_name'] if row['mother_name'] != 'NULL' else None
                employee.notice_period_days = int(row['notice_period_days']) if not pd.isna(row['notice_period_days']) else None
                
                # Set system fields
                employee.biometric_code = row['biometric_code'] if row['biometric_code'] != 'NULL' else None
                employee.send_mobile_login = bool(row['send_mobile_login']) if not pd.isna(row['send_mobile_login']) else False
                employee.send_web_login = bool(row['send_web_login']) if not pd.isna(row['send_web_login']) else True
                employee.is_active = bool(row['is_active']) if not pd.isna(row['is_active']) else True
                employee.created_by = int(row['created_by']) if not pd.isna(row['created_by']) else 1
                employee.updated_by = int(row['updated_by']) if not pd.isna(row['updated_by']) else 1
                
                # Set timestamps
                if not pd.isna(row['created_at']):
                    try:
                        employee.created_at = datetime.fromisoformat(str(row['created_at']).replace('+05:30', ''))
                    except:
                        employee.created_at = datetime.now()
                else:
                    employee.created_at = datetime.now()
                
                if not pd.isna(row['updated_at']):
                    try:
                        employee.updated_at = datetime.fromisoformat(str(row['updated_at']).replace('+05:30', ''))
                    except:
                        employee.updated_at = datetime.now()
                else:
                    employee.updated_at = datetime.now()
                
                # Add to session if new
                if not existing_employee:
                    db.add(employee)
                
                # Create or update employee profile
                from app.models.employee import EmployeeProfile
                existing_profile = db.query(EmployeeProfile).filter(EmployeeProfile.employee_id == employee_id).first()
                
                if not existing_profile:
                    profile = EmployeeProfile(
                        employee_id=employee_id,
                        profile_image_url=f"https://randomuser.me/api/portraits/{'women' if employee.gender == 'female' else 'men'}/{(employee_id % 10) + 1}.jpg",
                        created_at=datetime.now()
                    )
                    db.add(profile)
                    profile_created_count += 1
            
            # Commit all changes
            db.commit()
            
            logger.info("[OK] Employee CSV import completed successfully!")
            logger.info(f"[DATA] Summary:")
            logger.info(f"  - New employees imported: {imported_count}")
            logger.info(f"  - Existing employees updated: {updated_count}")
            logger.info(f"  - Employee profiles created: {profile_created_count}")
            
            return True
            
    except Exception as e:
        logger.error(f"[ERROR] Error importing employees from CSV: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_default_business():
    """Create default business if it doesn't exist"""
    logger.info("\nStep 4.5: Creating default business...")
    
    try:
        with get_db_context() as db:
            # Check if business already exists
            business = db.query(Business).first()
            if business:
                logger.info(f"Business already exists: {business.business_name}")
                return True
            
            # Get superadmin user
            superadmin = db.query(User).filter(User.email == settings.SUPERADMIN_EMAIL).first()
            if not superadmin:
                logger.error("Superadmin not found")
                return False
            
            # Create default business
            business = Business(
                owner_id=superadmin.id,
                business_name="Levitica Technologies Private Limited",
                gstin="22AAAAA0000A1Z5",
                is_authorized=True,
                pan="ABCDE1234F",
                address="123 Business Street, Tech City, Karnataka",
                city="Bangalore",
                pincode="560001",
                state="Karnataka",
                constitution="Private Limited Company",
                product="HRMS Suite",
                plan="Professional",
                employee_count=50,
                billing_frequency="Monthly (1 month)",
                business_url="levitica-tech",
                biometric_license_count=3,
                is_active=True
            )
            
            db.add(business)
            db.commit()
            db.refresh(business)
            
            logger.info(f"[OK] Created default business: {business.business_name}")
            logger.info(f"  - Business ID: {business.id}")
            logger.info(f"  - Owner: {superadmin.email}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create business: {e}")
        import traceback
        traceback.print_exc()
        return False


def update_master_data_employee_counts():
    """Update employee counts for all master data tables"""
    logger.info("\nUpdating master data employee counts...")
    
    try:
        with get_db_context() as db:
            from sqlalchemy import func
            from app.models.employee import Employee
            from app.models.department import Department
            from app.models.designations import Designation
            from app.models.grades import Grade
            from app.models.cost_center import CostCenter
            from app.models.location import Location
            from app.models.business_unit import BusinessUnit
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Update Department employee counts
            departments = db.query(Department).filter(Department.business_id == business.id).all()
            for dept in departments:
                count = db.query(func.count(Employee.id)).filter(
                    Employee.department_id == dept.id,
                    Employee.employee_status == 'active'
                ).scalar()
                dept.employees = count or 0
            
            # Update Designation employee counts
            designations = db.query(Designation).filter(Designation.business_id == business.id).all()
            for desig in designations:
                count = db.query(func.count(Employee.id)).filter(
                    Employee.designation_id == desig.id,
                    Employee.employee_status == 'active'
                ).scalar()
                desig.employees = count or 0
            
            # Update Grade employee counts
            grades = db.query(Grade).filter(Grade.business_id == business.id).all()
            for grade in grades:
                count = db.query(func.count(Employee.id)).filter(
                    Employee.grade_id == grade.id,
                    Employee.employee_status == 'active'
                ).scalar()
                grade.employees = count or 0
            
            # Update Cost Center employee counts
            cost_centers = db.query(CostCenter).filter(CostCenter.business_id == business.id).all()
            for cc in cost_centers:
                count = db.query(func.count(Employee.id)).filter(
                    Employee.cost_center_id == cc.id,
                    Employee.employee_status == 'active'
                ).scalar()
                cc.employees = count or 0
            
            # Update Location employee counts
            locations = db.query(Location).filter(Location.business_id == business.id).all()
            for loc in locations:
                count = db.query(func.count(Employee.id)).filter(
                    Employee.location_id == loc.id,
                    Employee.employee_status == 'active'
                ).scalar()
                loc.employees = count or 0
            
            # Update Business Unit employee counts
            # Note: Employee model doesn't have business_unit_id field, skipping this update
            # business_units = db.query(BusinessUnit).filter(BusinessUnit.business_id == business.id).all()
            # for bu in business_units:
            #     count = db.query(func.count(Employee.id)).filter(
            #         Employee.business_unit_id == bu.id,
            #         Employee.employee_status == 'active'
            #     ).scalar()
            #     bu.employees = count or 0
            
            db.commit()
            logger.info("[OK] Master data employee counts updated successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error updating master data employee counts: {str(e)}")
        return False


def create_approval_settings_sample_data():
    """Create sample ESS Approval Settings data"""
    logger.info("\nStep 41: Creating sample ESS Approval Settings data...")
    
    try:
        with get_db_context() as db:
            from app.models.approval_settings import ApprovalSettings
            from app.models.business import Business
            
            # Check if approval settings already exist
            existing_settings = db.query(ApprovalSettings).first()
            
            if existing_settings:
                logger.info("ESS Approval Settings sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found. Please create business data first.")
                return False
            
            # Create approval settings
            approval_settings = ApprovalSettings(
                business_id=business.id,
                leave_request="manager",
                missed_punch="Reporting Manager",
                missed_punch_days=7,
                comp_off="Reporting Manager",
                comp_off_lapse_days=30,
                lapse_monthly=False,
                remote_punch=True,
                remote_location=False,
                selfie_punch=True,
                selfie_location=False,
                time_relaxation="Reporting Manager",
                time_requests=5,
                time_hours=10,
                travel_calc="calculated",
                shift_change_level1="Reporting Manager",
                shift_change_level2="HR Manager",
                shift_change_level3="",
                shift_change_approvals_required=1,
                weekoff_change_level1="Reporting Manager",
                weekoff_change_level2="HR Manager",
                weekoff_change_level3="",
                weekoff_change_approvals_required=1,
                is_active=True
            )
            db.add(approval_settings)
            db.commit()
            
            # Count created records
            total_settings = db.query(ApprovalSettings).count()
            logger.info(f"[OK] ESS Approval Settings setup complete - {total_settings} settings created")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create ESS Approval Settings sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_real_employees_from_data():
    """Create real employees from hardcoded data (from Employee_Register CSV)"""
    logger.info("\nStep: Creating real employee data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee, EmployeeStatus, Gender, MaritalStatus
            from app.models.business import Business
            from app.models.department import Department
            from app.models.designations import Designation
            from app.models.location import Location
            from datetime import date
            
            # Check if real employees already exist
            existing_lev_count = db.query(Employee).filter(Employee.employee_code.like('LEV%')).count()
            if existing_lev_count > 10:  # If more than 10 LEV employees exist
                logger.info(f"✅ Real employees already exist ({existing_lev_count} found), skipping...")
                return True
            
            # Get default business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get or create default department, designation, location
            dept = db.query(Department).filter(Department.name == "General").first()
            if not dept:
                dept = Department(
                    name="General", 
                    business_id=business.id, 
                    head="Admin",  # Required field
                    deputy_head="",
                    is_active=True
                )
                db.add(dept)
                db.flush()
            
            designation = db.query(Designation).filter(Designation.name == "Employee").first()
            if not designation:
                designation = Designation(name="Employee", business_id=business.id, default=False)
                db.add(designation)
                db.flush()
            
            location = db.query(Location).filter(Location.name == "Head Office").first()
            if not location:
                location = Location(
                    name="Head Office", 
                    business_id=business.id, 
                    state="Telangana",  # Required field
                    is_active=True
                )
                db.add(location)
                db.flush()
            
            # Real employee data from CSV
            employees_data = [
                ("LEV029", "Abhilash", "Gurrampally", "Mani Kiran Kopanathi"),
                ("LEV039", "Anusha", "Enigalla", "Durgaprasad Medipudi"),
                ("LEV122", "ARAVELLY", "THARUN", "Anusha Enigalla"),
                ("LEV047", "Ashok", "Kota", "Sameer Shaik"),
                ("LEV121", "Baluguri Ashritha", "Rao", "Durgaprasad Medipudi"),
                ("LEV116", "Bhargava Sai", "Kolli", "Kallamadi Kranti Kumar reddy"),
                ("LEV027", "Bogala", "Chandramouli", "Durgaprasad Medipudi"),
                ("LEV023", "Burri", "Gowtham", "Mani Kiran Kopanathi"),
                ("LEV001", "CHANDU", "THOTA", "Durgaprasad Medipudi"),
                ("LEV038", "Cheekati", "Abhinaya", "Durgaprasad Medipudi"),
                ("LEV014", "Chodisetti Sri Rama", "Sai", "Mani Kiran Kopanathi"),
                ("LEV123", "DHANIKELA", "BRAHMAM", "Anusha Enigalla"),
                ("LEV012", "DHEERAJ KRISHNA", "JAKKULA", "Mani Kiran Kopanathi"),
                ("LEV028", "Dorasala Nagendra", "Reddy", "Mani Kiran Kopanathi"),
                ("LEV017", "Dubbaka", "Bharath", "Sameer Shaik"),
                ("LEV026", "Durga Sai Vara Prasad", "Chandragiri", "Durgaprasad Medipudi"),
                ("LEV031", "Gorle Leela Sai", "Kumar", "Durgaprasad Medipudi"),
                ("LEV127", "Gubba", "Vasini", "Anusha Enigalla"),
                ("LEV005", "Gurajapu", "Pavani", "Nagendra Uggirala"),
                ("LEV118", "Hari Charan Teja", "Gudapati", "Anusha Enigalla"),
                ("LEV050", "Harsha Vardhan Naidu", "Dasireddy", "Kallamadi Kranti Kumar reddy"),
                ("LEV044", "Hemant Tukaram", "Pawade", "Mani Kiran Kopanathi"),
                ("LEV008", "Hruthik Venkata Sai Ganesh", "Jamanu", "Chandu Thota"),
                ("LEV033", "Jagadeesh", "Bedolla", "Sameer Shaik"),
                ("LEV128", "Jothi Lakshmi", "A", "Anusha Enigalla"),
                ("LEV013", "KALLAMADI", "KOWSIK REDDY", "Durgaprasad Medipudi"),
                ("LEV011", "Kallamadi Kranti Kumar", "reddy", "Durgaprasad Medipudi"),
                ("LEV004", "Kallamadi", "keerthi", "Nagendra Uggirala"),
                ("LEV003", "Kandepuneni Swetha Naga", "Durga", "Chandu Thota"),
                ("LEV036", "KASARAPU", "RAJESWAR REDDY", "Sameer Shaik"),
                ("LEV019", "Keerthi Ranjani", "Maddala", "Sameer Shaik"),
                ("LEV032", "Khuswanth Rao", "Jadav", "Sameer Shaik"),
                ("LEV034", "Kishore", "Tiruveedhula", "Mani Kiran Kopanathi"),
                ("LEV046", "Kondareddy", "Revathi", "Sameer Shaik"),
                ("LEV126", "Korada", "Kavya", "Anusha Enigalla"),
                ("LEV035", "Kothapalli sai Avinash", "Varma", "Mani Kiran Kopanathi"),
                ("LEV048", "Lokeshwar Reddy", "Kondappagari", "Kallamadi Kranti Kumar reddy"),
                ("LEV010", "MANI KIRAN", "KOPANATHI", "Durgaprasad Medipudi"),
                ("LEV020", "Manikanta", "Nedunuri", "Mani Kiran Kopanathi"),
                ("LEV120", "Medipudi", "Durgaprasad", ""),
                ("LEV002", "Minal Devidas", "Mahajan", "Durgaprasad Medipudi"),
                ("LEV041", "Mohammad Aslam Yakub", "Khan", "Durgaprasad Medipudi"),
                ("LEV042", "Muniganti Sai", "sumiran", "Sameer Shaik"),
                ("LEV117", "N Sairam Srinivasa Chakravarthi", "Pothureddy", "Kallamadi Kranti Kumar reddy"),
                ("LEV040", "Nagadurga", "Sarnala", "Mani Kiran Kopanathi"),
                ("LEV024", "Nagendra", "Uggirala", "Durgaprasad Medipudi"),
                ("LEV015", "Nani venkata Ravi teja", "Maddala", "Sameer Shaik"),
                ("LEV022", "Naveen Sai", "Koppereddy", "Nagendra Uggirala"),
                ("LEV025", "Nollu Lalith", "Kumar", "Sameer Shaik"),
                ("LEV021", "Pagadala", "Anitha", "Sameer Shaik"),
                ("LEV018", "Peddireddy Sai Kumar", "Reddy", "Sameer Shaik"),
                ("LEV037", "Pesaru", "Kireeti", "Sameer Shaik"),
                ("LEV049", "Pillala Sukanya", "Sukanya", "Kallamadi Kranti Kumar reddy"),
                ("LEV006", "Potnuri Naveen", "Bhargav", "Chandu Thota"),
                ("LEV051", "Pradeep", "Bantapalli", "Kallamadi Kranti Kumar reddy"),
                ("LEV016", "Pramod Kumar", "Sindhe", "Sameer Shaik"),
                ("LEV009", "Sameer", "Shaik", "Durgaprasad Medipudi"),
                ("LEV030", "Sasi kumar Reddy", "Chintala", "Mani Kiran Kopanathi"),
                ("LEV043", "Satya Kiran", "Chelluboina", "Mani Kiran Kopanathi"),
                ("LEV124", "Sumathi", "Mittapalli", "Anusha Enigalla"),
                ("LEV007", "Syed Afran", "Ali", "Chandu Thota"),
                ("LEV119", "Vamshi Hasanabada", "Vamshi", "Kallamadi Kranti Kumar reddy"),
                ("LEV125", "Vijay Ram", "Maddukuri", "Anusha Enigalla"),
            ]
            
            # Create employees
            employee_map = {}
            created_count = 0
            
            for emp_code, first_name, last_name, manager_name in employees_data:
                # Check if exists
                existing = db.query(Employee).filter(Employee.employee_code == emp_code).first()
                if existing:
                    employee_map[emp_code] = existing
                    continue
                
                employee = Employee(
                    employee_code=emp_code,
                    first_name=first_name,
                    last_name=last_name,
                    email=f"{emp_code.lower()}@levitica.com",
                    mobile="9999999999",  # Required field - default mobile
                    business_id=business.id,
                    department_id=dept.id,
                    designation_id=designation.id,
                    location_id=location.id,
                    employee_status=EmployeeStatus.ACTIVE,
                    is_active=True,
                    date_of_joining=date(2024, 1, 1),
                    gender=Gender.MALE,
                    marital_status=MaritalStatus.SINGLE,
                    created_by=1
                )
                db.add(employee)
                db.flush()
                employee_map[emp_code] = employee
                created_count += 1
            
            db.commit()
            logger.info(f"[OK] Created {created_count} real employees")
            
            # Set up reporting relationships
            manager_count = 0
            for emp_code, first_name, last_name, manager_name in employees_data:
                if manager_name and emp_code in employee_map:
                    # Find manager by name
                    for code, emp in employee_map.items():
                        full_name = f"{emp.first_name} {emp.last_name}".strip()
                        if manager_name.lower() in full_name.lower() or full_name.lower() in manager_name.lower():
                            employee_map[emp_code].reporting_manager_id = emp.id
                            manager_count += 1
                            break
            
            db.commit()
            logger.info(f"[OK] Set up {manager_count} reporting relationships")
            logger.info(f"[OK] Total LEV employees: {db.query(Employee).filter(Employee.employee_code.like('LEV%')).count()}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create real employees: {e}")
        import traceback
        traceback.print_exc()


def create_contact_inquiry_sample_data():
    """Create sample contact inquiry data for landing page"""
    logger.info("Creating contact inquiry sample data...")
    
    try:
        with get_db_context() as db:
            # Check if data already exists
            existing_count = db.query(ContactInquiry).count()
            if existing_count > 0:
                logger.info(f"[SKIP] Contact inquiries already exist ({existing_count} records)")
                return True
            
            # Sample inquiry data
            inquiries_data = [
                {
                    "full_name": "Rajesh Kumar",
                    "email": "rajesh.kumar@techcorp.com",
                    "phone": "+91-9876543210",
                    "company_name": "TechCorp Solutions",
                    "number_of_employees": "51-200",
                    "industry": "Information Technology",
                    "message": "Looking for a comprehensive HRMS solution for our growing team. Need payroll, attendance, and leave management.",
                    "source": InquirySource.LANDING_PAGE,
                    "status": InquiryStatus.NEW,
                    "is_priority": True,
                    "created_at": datetime.utcnow() - timedelta(hours=2)
                },
                {
                    "full_name": "Priya Sharma",
                    "email": "priya.sharma@manufacturing.in",
                    "phone": "+91-9123456789",
                    "company_name": "Sharma Manufacturing Ltd",
                    "number_of_employees": "201-500",
                    "industry": "Manufacturing",
                    "message": "Need biometric integration and shift management for factory workers.",
                    "source": InquirySource.LANDING_PAGE,
                    "status": InquiryStatus.CONTACTED,
                    "contacted_at": datetime.utcnow() - timedelta(hours=12),
                    "created_at": datetime.utcnow() - timedelta(days=1)
                },
                {
                    "full_name": "Amit Patel",
                    "email": "amit@retailchain.com",
                    "phone": "+91-9988776655",
                    "company_name": "Retail Chain India",
                    "number_of_employees": "501-1000",
                    "industry": "Retail",
                    "message": "Multi-location retail chain looking for cloud-based HRMS with mobile app support.",
                    "source": InquirySource.DEMO_REQUEST,
                    "status": InquiryStatus.QUALIFIED,
                    "contacted_at": datetime.utcnow() - timedelta(days=2),
                    "follow_up_date": datetime.utcnow() + timedelta(days=2),
                    "notes": "Interested in enterprise plan. Schedule demo for next week.",
                    "created_at": datetime.utcnow() - timedelta(days=3)
                },
                {
                    "full_name": "Sneha Reddy",
                    "email": "sneha.reddy@healthcare.org",
                    "phone": "+91-9876512345",
                    "company_name": "HealthCare Plus",
                    "number_of_employees": "11-50",
                    "industry": "Healthcare",
                    "message": "Small healthcare facility needs simple attendance and payroll system.",
                    "source": InquirySource.LANDING_PAGE,
                    "status": InquiryStatus.NEW,
                    "created_at": datetime.utcnow() - timedelta(hours=5)
                },
                {
                    "full_name": "Vikram Singh",
                    "email": "vikram@construction.co.in",
                    "phone": "+91-9123498765",
                    "company_name": "Singh Construction Co",
                    "number_of_employees": "1000+",
                    "industry": "Construction",
                    "message": "Large construction company with multiple project sites. Need attendance tracking for field workers.",
                    "source": InquirySource.CONTACT_FORM,
                    "status": InquiryStatus.CONTACTED,
                    "contacted_at": datetime.utcnow() - timedelta(days=1),
                    "is_priority": True,
                    "created_at": datetime.utcnow() - timedelta(days=2)
                },
                {
                    "full_name": "Meera Iyer",
                    "email": "meera@edutech.in",
                    "phone": "+91-9876501234",
                    "company_name": "EduTech Learning",
                    "number_of_employees": "11-50",
                    "industry": "Education",
                    "message": "Educational institution looking for leave management and payroll automation.",
                    "source": InquirySource.LANDING_PAGE,
                    "status": InquiryStatus.CONVERTED,
                    "contacted_at": datetime.utcnow() - timedelta(days=10),
                    "notes": "Successfully onboarded. Using basic plan.",
                    "created_at": datetime.utcnow() - timedelta(days=15)
                },
                {
                    "full_name": "Arjun Mehta",
                    "email": "arjun@logistics.com",
                    "phone": "+91-9988123456",
                    "company_name": "Mehta Logistics",
                    "number_of_employees": "201-500",
                    "industry": "Logistics",
                    "message": "Transportation company needs GPS-based attendance and driver management.",
                    "source": InquirySource.REFERRAL,
                    "status": InquiryStatus.QUALIFIED,
                    "contacted_at": datetime.utcnow() - timedelta(days=3),
                    "follow_up_date": datetime.utcnow() + timedelta(days=1),
                    "notes": "Referred by TechCorp Solutions. High potential client.",
                    "is_priority": True,
                    "created_at": datetime.utcnow() - timedelta(days=4)
                },
                {
                    "full_name": "Kavita Desai",
                    "email": "kavita@pharma.in",
                    "phone": "+91-9123456780",
                    "company_name": "Desai Pharmaceuticals",
                    "number_of_employees": "51-200",
                    "industry": "Pharmaceuticals",
                    "message": "Pharma company needs compliance-focused HRMS with statutory reporting.",
                    "source": InquirySource.LANDING_PAGE,
                    "status": InquiryStatus.NEW,
                    "created_at": datetime.utcnow() - timedelta(hours=8)
                },
                {
                    "full_name": "Rahul Verma",
                    "email": "rahul@hospitality.com",
                    "phone": "+91-9876543219",
                    "company_name": "Verma Hotels Group",
                    "number_of_employees": "501-1000",
                    "industry": "Hospitality",
                    "message": "Hotel chain with 24/7 operations. Need shift scheduling and rostering.",
                    "source": InquirySource.DEMO_REQUEST,
                    "status": InquiryStatus.CONTACTED,
                    "contacted_at": datetime.utcnow() - timedelta(hours=18),
                    "follow_up_date": datetime.utcnow() + timedelta(days=3),
                    "created_at": datetime.utcnow() - timedelta(days=1)
                },
                {
                    "full_name": "Anita Gupta",
                    "email": "anita@finance.co.in",
                    "phone": "+91-9988776644",
                    "company_name": "Gupta Financial Services",
                    "number_of_employees": "11-50",
                    "industry": "Financial Services",
                    "message": "Financial services firm needs secure HRMS with role-based access control.",
                    "source": InquirySource.LANDING_PAGE,
                    "status": InquiryStatus.CLOSED,
                    "contacted_at": datetime.utcnow() - timedelta(days=7),
                    "notes": "Client went with competitor. Price was the deciding factor.",
                    "created_at": datetime.utcnow() - timedelta(days=10)
                }
            ]
            
            # Create inquiries
            created_count = 0
            for inquiry_data in inquiries_data:
                inquiry = ContactInquiry(**inquiry_data)
                db.add(inquiry)
                created_count += 1
            
            db.commit()
            logger.info(f"[OK] Created {created_count} contact inquiries")
            
            # Log statistics
            stats = {
                "total": db.query(ContactInquiry).count(),
                "new": db.query(ContactInquiry).filter(ContactInquiry.status == InquiryStatus.NEW).count(),
                "contacted": db.query(ContactInquiry).filter(ContactInquiry.status == InquiryStatus.CONTACTED).count(),
                "qualified": db.query(ContactInquiry).filter(ContactInquiry.status == InquiryStatus.QUALIFIED).count(),
                "converted": db.query(ContactInquiry).filter(ContactInquiry.status == InquiryStatus.CONVERTED).count(),
                "priority": db.query(ContactInquiry).filter(ContactInquiry.is_priority == True).count()
            }
            
            logger.info(f"[OK] Contact Inquiry Statistics:")
            logger.info(f"     Total: {stats['total']}")
            logger.info(f"     New: {stats['new']}")
            logger.info(f"     Contacted: {stats['contacted']}")
            logger.info(f"     Qualified: {stats['qualified']}")
            logger.info(f"     Converted: {stats['converted']}")
            logger.info(f"     Priority: {stats['priority']}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create contact inquiry sample data: {e}")
        import traceback
        traceback.print_exc()
        return False
        return False


def main():
    """Run complete setup."""
    print("\n" + "=" * 70)
    print("LEVITICA HR - Database Setup")
    print("=" * 70)
    print(f"Database: {settings.DB_NAME}")
    print(f"Host: {settings.DB_HOST}:{settings.DB_PORT}")
    print(f"User: {settings.DB_USER}")
    print("=" * 70)
    
    # Run setup steps
    steps = [
        create_database_if_needed,
        clean_existing_objects,
        create_tables,
        add_ncp_columns_if_missing,  # Add NCP columns if missing
        create_superadmin,
        create_user_preferences,  # Create default preferences for all users
        create_default_business,  # Create business before any employee operations
        import_employees_from_csv,  # Import employees from CSV first (skipped if CSV format wrong)
        create_real_employees_from_data,  # Create real employees from hardcoded data
        fix_employee_statuses,  # Fix employee statuses before creating relationships
        create_employee_profiles_data,  # Create clean employee profiles data
        populate_employee_events_data,  # Populate employee events data (birthdays, wedding dates)
        create_sample_manager_relationships,  # Create manager relationships after employees are imported
        create_sample_onboarding_data,
        create_credit_system_data,
        create_attendance_sample_data,
        create_remote_punch_sample_data,
        create_manual_updates_sample_data,
        create_employee_register_sample_data,
        create_separation_sample_data,
        create_extra_days_sample_data,
        create_leave_balance_sample_data,
        create_comprehensive_request_sample_data,
        create_roster_sample_data,  # Week Roster and Shift Roster sample data
        create_salary_units_sample_data,
        create_salary_details_sample_data,
        create_salary_deductions_sample_data,
        create_work_profile_sample_data,
        create_deduction_sample_data,
        create_tds_challan_sample_data,
        create_tds_return_sample_data,
        create_income_tax_tds_sample_data,
        create_extra_hours_sample_data,
        create_loan_sample_data,
        create_it_declaration_sample_data,
        create_biometric_code_sample_data,
        create_bank_details_sample_data,
        create_hrmanagement_sample_data,
        create_payroll_periods_sample_data,
        create_leave_encashment_sample_data,
        create_payroll_recalculation_sample_data,
        create_statutory_bonus_sample_data,
        create_esi_settings_sample_data,
        create_epf_settings_sample_data,
        create_professional_tax_sample_data,
        create_lwf_sample_data,
        create_tax_settings_sample_data,
        create_tds24q_sample_data,
        create_gratuity_sample_data,
        create_payroll_run_sample_data,
        create_hold_salary_sample_data,
        create_salary_deduction_types_sample_data,
        create_salary_components_sample_data,
        create_salary_structures_sample_data,
        create_time_salary_sample_data,
        create_overtime_sample_data,
        create_attendance_settings_sample_data,
        create_leave_types_sample_data,
        create_leave_policies_sample_data,
        create_compoff_rules_sample_data,
        create_esi_settings_sample_data,
        create_reports_sample_data,
        create_sap_mapping_sample_data,
        create_api_access_sample_data,
        create_attendance_register_sample_data,
        create_leave_register_sample_data,
        create_time_register_sample_data,
        create_strike_register_sample_data,
        create_travel_register_sample_data,
        create_time_punches_sample_data,
        create_sample_assets,
        create_business_information_sample_data,
        create_visit_types_sample_data,
        create_helpdesk_categories_sample_data,
        create_workflows_sample_data,
        create_remote_sessions_sample_data,
        create_help_articles_sample_data,
        create_employee_code_settings_sample_data,
        create_sample_employee_documents,
        create_sample_relatives,
        create_sample_additional_info,
        create_sample_permissions,
        create_sample_employee_access,
        create_sample_activity_logs,
        create_sample_inactive_employees,
        # create_sample_esi_deduction_data,  # Commented out - data already created manually
        # create_sample_pf_deduction_data,
        # create_sample_lwf_data,
        create_form16_sample_data,
        create_email_settings_sample_data,
        create_biometric_device_sample_data,
        create_gatekeeper_device_sample_data,
        create_sqlserver_source_sample_data,
        create_maintenance_sample_data,
        create_subscription_sample_data,
        create_domain_sample_data,
        create_purchase_transaction_sample_data,
        create_project_management_sample_data,
        create_notes_sample_data,
        create_calendar_sample_data,
        create_todo_sample_data,
        create_crm_sample_data,
        create_contact_inquiry_sample_data,  # Contact inquiry for landing page
        create_approval_settings_sample_data,
        update_master_data_employee_counts,  # Update employee counts after all data is created
    ]
    
    for step in steps:
        if not step():
            logger.error("\nSetup failed!")
            return False
    
    # Success
    print("\n" + "=" * 70)
    print("[OK] Setup completed successfully!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Start the application:")
    print("     uvicorn app.main:app --reload")
    print("")
    print("  2. Open API documentation:")
    print("     http://localhost:8000/docs")
    print("")
    print("  3. Login with superadmin:")
    print(f"     Email: {settings.SUPERADMIN_EMAIL}")
    print(f"     Password: {settings.SUPERADMIN_PASSWORD}")
    print("")
    print("  4. Test onboarding endpoints:")
    print("     GET /api/v1/onboarding/dashboard")
    print("     GET /api/v1/onboarding/")
    print("     GET /api/v1/onboarding/templates")
    print("     GET /api/v1/onboarding/settings")
    print("")
    print("  [WARNING]  Change the default password immediately!")
    print("=" * 70)
    
    return True


def create_sample_assets():
    """Create sample assets for employees"""
    logger.info("\nStep 34: Creating sample assets data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee
            from app.models.business import Business
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if assets already exist
            existing_assets = db.execute(text("SELECT COUNT(*) FROM assets WHERE business_id = :business_id"), 
                                       {"business_id": business.id}).scalar()
            
            if existing_assets > 0:
                logger.info(f"Assets already exist ({existing_assets} found), skipping...")
                return True
            
            # Get employees
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status == 'active'
            ).limit(10).all()
            
            if not employees:
                logger.info("No employees found for asset assignment")
                return True
            
            # Asset types and their details
            asset_types = [
                {
                    'type': 'LAPTOP',
                    'brands': ['Dell', 'HP', 'Lenovo', 'Asus'],
                    'models': ['Latitude 5520', 'EliteBook 840', 'ThinkPad E14', 'VivoBook 15'],
                    'price_range': (40000, 80000)
                },
                {
                    'type': 'DESKTOP',
                    'brands': ['Dell', 'HP', 'Lenovo'],
                    'models': ['OptiPlex 7090', 'ProDesk 400', 'ThinkCentre M70q'],
                    'price_range': (30000, 60000)
                },
                {
                    'type': 'MONITOR',
                    'brands': ['Dell', 'Samsung', 'LG', 'Acer'],
                    'models': ['P2419H', 'F24T450FQN', '24MK430H', 'SB220Q'],
                    'price_range': (8000, 25000)
                },
                {
                    'type': 'MOBILE',
                    'brands': ['Samsung', 'Apple', 'OnePlus'],
                    'models': ['Galaxy S21', 'iPhone 13', 'OnePlus 9'],
                    'price_range': (25000, 80000)
                }
            ]
            
            assets_created = 0
            
            # Get existing asset codes to avoid duplicates
            existing_codes = set()
            existing_codes_result = db.execute(text("SELECT asset_code FROM assets")).fetchall()
            for row in existing_codes_result:
                existing_codes.add(row[0])
            
            asset_counter = 1
            
            for i, employee in enumerate(employees):
                # Each employee gets 1-3 assets
                num_assets = random.randint(1, 3)
                
                for j in range(num_assets):
                    asset_type_data = random.choice(asset_types)
                    brand = random.choice(asset_type_data['brands'])
                    model = random.choice(asset_type_data['models'])
                    
                    # Generate unique asset code
                    while True:
                        asset_code = f"AST{asset_counter:04d}"
                        if asset_code not in existing_codes:
                            existing_codes.add(asset_code)
                            break
                        asset_counter += 1
                    
                    asset_counter += 1
                    serial_number = f"{brand[:3].upper()}{random.randint(100000, 999999)}"
                    
                    # Purchase and warranty dates
                    purchase_date = employee.date_of_joining + timedelta(days=random.randint(-30, 30))
                    warranty_start = purchase_date
                    warranty_end = warranty_start + timedelta(days=random.randint(365, 1095))  # 1-3 years
                    
                    # Assigned date (within 7 days of purchase)
                    assigned_date = purchase_date + timedelta(days=random.randint(0, 7))
                    
                    # Price
                    min_price, max_price = asset_type_data['price_range']
                    purchase_cost = random.randint(min_price, max_price)
                    estimated_value = purchase_cost * random.uniform(0.6, 0.9)  # Depreciated value
                    
                    # Create asset using raw SQL since we don't have the Asset model imported
                    asset_sql = """
                        INSERT INTO assets (
                            asset_code, name, asset_type, brand, model, serial_number,
                            description, purchase_date, purchase_cost, estimated_value,
                            warranty_start_date, warranty_end_date, warranty_provider,
                            status, condition, current_location, assigned_employee_id,
                            assigned_date, business_id, created_at
                        ) VALUES (
                            :asset_code, :name, :asset_type, :brand, :model, :serial_number,
                            :description, :purchase_date, :purchase_cost, :estimated_value,
                            :warranty_start_date, :warranty_end_date, :warranty_provider,
                            :status, :condition, :current_location, :assigned_employee_id,
                            :assigned_date, :business_id, :created_at
                        )
                    """
                    
                    try:
                        db.execute(text(asset_sql), {
                            'asset_code': asset_code,
                            'name': f"{brand} {model}",
                            'asset_type': asset_type_data['type'],
                            'brand': brand,
                            'model': model,
                            'serial_number': serial_number,
                            'description': f"{asset_type_data['type'].title()} assigned to {employee.first_name} {employee.last_name}",
                            'purchase_date': purchase_date,
                            'purchase_cost': purchase_cost,
                            'estimated_value': estimated_value,
                            'warranty_start_date': warranty_start,
                            'warranty_end_date': warranty_end,
                            'warranty_provider': f"{brand} Warranty Services",
                            'status': 'ACTIVE',
                            'condition': random.choice(['EXCELLENT', 'GOOD', 'FAIR']),
                            'current_location': employee.location.name if employee.location else 'Office',
                            'assigned_employee_id': employee.id,
                            'assigned_date': assigned_date,
                            'business_id': business.id,
                            'created_at': datetime.now()
                        })
                        
                        assets_created += 1
                        
                    except Exception as asset_error:
                        logger.warning(f"Failed to create asset {asset_code}: {asset_error}")
                        continue
            
            db.commit()
            logger.info(f"[OK] Created {assets_created} sample assets")
            logger.info(f"  - Assets assigned to {len(employees)} employees")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample assets: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def create_business_information_sample_data():
    """Create sample business information data for testing"""
    logger.info("\nStep 35: Creating business information sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.business_info import BusinessInformation
            from app.models.business import Business
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if business information already exists
            existing_info = db.query(BusinessInformation).filter(
                BusinessInformation.business_id == business.id
            ).first()
            
            if existing_info:
                logger.info("Business information already exists, skipping...")
                return True
            
            # Create comprehensive business information
            business_info = BusinessInformation(
                business_id=business.id,
                
                # Bank Details
                bank_name="State Bank of India",
                bank_branch="Hyderabad Main Branch",
                bank_ifsc="SBIN0001234",
                bank_account="12345678901234",
                
                # Statutory Information
                pan="ABCDE1234F",
                tan="HYDD12345E",
                gstin="36ABCDE1234F1Z5",
                esi="12345678901",
                pf="AP/HYD/123456",
                shop_act="SA/HYD/2023/001",
                labour_act="LA/HYD/2023/001",
                
                # Employee Additional Info
                employee_info=[
                    "Employee Code",
                    "Badge Number", 
                    "Biometric ID",
                    "Emergency Contact",
                    "Blood Group",
                    "Marital Status",
                    "Spouse Name",
                    "Father Name",
                    "Mother Name",
                    "Nationality"
                ]
            )
            
            db.add(business_info)
            db.commit()
            db.refresh(business_info)
            
            logger.info("[OK] Created business information sample data")
            logger.info(f"  - Business ID: {business.id}")
            logger.info(f"  - Bank: {business_info.bank_name}")
            logger.info(f"  - PAN: {business_info.pan}")
            logger.info(f"  - GSTIN: {business_info.gstin}")
            return True
    
    except Exception as e:
        logger.error(f"Error creating business information sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_visit_types_sample_data():
    """Create sample visit types data for testing"""
    logger.info("\nStep 36: Creating visit types sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.visit_type import VisitType
            from app.models.business import Business
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if visit types already exist
            existing_visit_types = db.query(VisitType).filter(
                VisitType.business_id == business.id
            ).first()
            
            if existing_visit_types:
                logger.info("Visit types already exist, skipping...")
                return True
            
            # Create comprehensive visit types
            visit_types_data = [
                {
                    "name": "Client Meeting",
                    "business_id": business.id
                },
                {
                    "name": "Site Visit",
                    "business_id": business.id
                },
                {
                    "name": "Vendor Meeting",
                    "business_id": business.id
                },
                {
                    "name": "Training Session",
                    "business_id": business.id
                },
                {
                    "name": "Project Review",
                    "business_id": business.id
                },
                {
                    "name": "Business Development",
                    "business_id": business.id
                },
                {
                    "name": "Technical Support",
                    "business_id": business.id
                },
                {
                    "name": "Sales Call",
                    "business_id": business.id
                },
                {
                    "name": "Audit Visit",
                    "business_id": business.id
                },
                {
                    "name": "Maintenance Check",
                    "business_id": business.id
                }
            ]
            
            created_count = 0
            for visit_type_data in visit_types_data:
                visit_type = VisitType(**visit_type_data)
                db.add(visit_type)
                created_count += 1
            
            db.commit()
            
            logger.info(f"[OK] Created {created_count} visit types sample data")
            logger.info(f"  - Business ID: {business.id}")
            logger.info(f"  - Visit types: {', '.join([vt['name'] for vt in visit_types_data])}")
            return True
    
    except Exception as e:
        logger.error(f"Error creating visit types sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_helpdesk_categories_sample_data():
    """Create sample helpdesk categories data for testing"""
    logger.info("\nStep 37: Creating helpdesk categories sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.helpdesk_category import HelpdeskCategory
            from app.models.business import Business
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if helpdesk categories already exist
            existing_categories = db.query(HelpdeskCategory).filter(
                HelpdeskCategory.business_id == business.id
            ).first()
            
            if existing_categories:
                logger.info("Helpdesk categories already exist, skipping...")
                return True
            
            # Create comprehensive helpdesk categories
            categories_data = [
                {
                    "name": "IT Support",
                    "business_id": business.id,
                    "primary_approver": "IT Manager",
                    "backup_approver": "System Administrator",
                    "is_active": True
                },
                {
                    "name": "HR Issues",
                    "business_id": business.id,
                    "primary_approver": "HR Manager",
                    "backup_approver": "HR Executive",
                    "is_active": True
                },
                {
                    "name": "Facilities",
                    "business_id": business.id,
                    "primary_approver": "Facilities Manager",
                    "backup_approver": "Admin Executive",
                    "is_active": True
                },
                {
                    "name": "Finance & Accounts",
                    "business_id": business.id,
                    "primary_approver": "Finance Manager",
                    "backup_approver": "Accounts Executive",
                    "is_active": True
                },
                {
                    "name": "General Inquiry",
                    "business_id": business.id,
                    "primary_approver": "Admin Manager",
                    "backup_approver": "Reception",
                    "is_active": True
                },
                {
                    "name": "Security",
                    "business_id": business.id,
                    "primary_approver": "Security Head",
                    "backup_approver": "Security Officer",
                    "is_active": True
                },
                {
                    "name": "Training & Development",
                    "business_id": business.id,
                    "primary_approver": "Training Manager",
                    "backup_approver": "HR Manager",
                    "is_active": True
                },
                {
                    "name": "Procurement",
                    "business_id": business.id,
                    "primary_approver": "Procurement Manager",
                    "backup_approver": "Purchase Executive",
                    "is_active": True
                },
                {
                    "name": "Legal & Compliance",
                    "business_id": business.id,
                    "primary_approver": "Legal Head",
                    "backup_approver": "Compliance Officer",
                    "is_active": True
                },
                {
                    "name": "Travel & Transport",
                    "business_id": business.id,
                    "primary_approver": "Admin Manager",
                    "backup_approver": "Travel Coordinator",
                    "is_active": True
                }
            ]
            
            created_count = 0
            for category_data in categories_data:
                category = HelpdeskCategory(**category_data)
                db.add(category)
                created_count += 1
            
            db.commit()
            
            logger.info(f"[OK] Created {created_count} helpdesk categories sample data")
            logger.info(f"  - Business ID: {business.id}")
            logger.info(f"  - Categories: {', '.join([cat['name'] for cat in categories_data])}")
            return True
    
    except Exception as e:
        logger.error(f"Error creating helpdesk categories sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_workflows_sample_data():
    """Create sample workflows data for testing"""
    logger.info("\nStep 38: Creating workflows sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.workflow import Workflow
            from app.models.business import Business
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if workflows already exist
            existing_workflows = db.query(Workflow).filter(
                Workflow.business_id == business.id
            ).first()
            
            if existing_workflows:
                logger.info("Workflows already exist, skipping...")
                return True
            
            # Create comprehensive workflows
            workflows_data = [
                {
                    "name": "Leave Approval Workflow",
                    "business_id": business.id,
                    "description": "Multi-step approval process for employee leave requests with manager and HR approval",
                    "fields": 5,
                    "steps": 3,
                    "is_active": True
                },
                {
                    "name": "Expense Reimbursement Workflow",
                    "business_id": business.id,
                    "description": "Automated expense claim processing with receipt validation and finance approval",
                    "fields": 7,
                    "steps": 4,
                    "is_active": True
                },
                {
                    "name": "Document Approval Workflow",
                    "business_id": business.id,
                    "description": "Document review and approval process for policies, contracts, and official documents",
                    "fields": 4,
                    "steps": 2,
                    "is_active": True
                },
                {
                    "name": "Employee Onboarding Workflow",
                    "business_id": business.id,
                    "description": "Comprehensive onboarding process for new employees including documentation and training",
                    "fields": 8,
                    "steps": 5,
                    "is_active": True
                },
                {
                    "name": "IT Asset Request Workflow",
                    "business_id": business.id,
                    "description": "Hardware and software request approval process with IT department validation",
                    "fields": 6,
                    "steps": 3,
                    "is_active": True
                },
                {
                    "name": "Performance Review Workflow",
                    "business_id": business.id,
                    "description": "Annual performance evaluation process with self-assessment and manager review",
                    "fields": 10,
                    "steps": 4,
                    "is_active": True
                },
                {
                    "name": "Training Request Workflow",
                    "business_id": business.id,
                    "description": "Employee training and development request approval with budget consideration",
                    "fields": 5,
                    "steps": 2,
                    "is_active": True
                },
                {
                    "name": "Vendor Approval Workflow",
                    "business_id": business.id,
                    "description": "New vendor registration and approval process with compliance verification",
                    "fields": 9,
                    "steps": 4,
                    "is_active": True
                },
                {
                    "name": "Project Approval Workflow",
                    "business_id": business.id,
                    "description": "Project proposal review and approval with resource allocation and timeline validation",
                    "fields": 12,
                    "steps": 5,
                    "is_active": True
                },
                {
                    "name": "Policy Change Workflow",
                    "business_id": business.id,
                    "description": "Company policy modification and approval process with stakeholder review",
                    "fields": 6,
                    "steps": 3,
                    "is_active": True
                }
            ]
            
            created_count = 0
            for workflow_data in workflows_data:
                workflow = Workflow(**workflow_data)
                db.add(workflow)
                created_count += 1
            
            db.commit()
            
            logger.info(f"[OK] Created {created_count} workflows sample data")
            logger.info(f"  - Business ID: {business.id}")
            logger.info(f"  - Workflows: {', '.join([wf['name'] for wf in workflows_data])}")
            return True
    
    except Exception as e:
        logger.error(f"Error creating workflows sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_remote_sessions_sample_data():
    """Create sample remote sessions data for testing"""
    logger.info("\nStep 38.5: Creating remote sessions sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.remote_session import RemoteSession, RemoteSessionStatus, RemoteSessionType
            from app.models.business import Business
            from app.models.employee import Employee
            from datetime import datetime, timedelta
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if remote sessions already exist
            existing_sessions = db.query(RemoteSession).filter(
                RemoteSession.business_id == business.id
            ).first()
            
            if existing_sessions:
                logger.info("Remote sessions already exist, skipping...")
                return True
            
            # Get employees for assignment
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.employee_status.in_(["active", "ACTIVE"])
            ).limit(10).all()
            
            if not employees or len(employees) < 2:
                logger.warning("Not enough employees found for remote session assignment")
                return True
            
            # Get superadmin user for created_by
            superadmin = db.query(User).filter(User.email == settings.SUPERADMIN_EMAIL).first()
            created_by_id = superadmin.id if superadmin else None
            
            # Create sample remote sessions
            sessions_data = [
                {
                    "business_id": business.id,
                    "employee_id": employees[0].id,
                    "support_agent_id": employees[1].id if len(employees) > 1 else None,
                    "session_type": RemoteSessionType.TECHNICAL_SUPPORT,
                    "title": "Unable to access company VPN",
                    "description": "I'm unable to connect to the company VPN from my home network. Getting error 'Connection timeout'. Need urgent help as I have important work to complete.",
                    "status": RemoteSessionStatus.COMPLETED,
                    "requested_date": datetime.now() - timedelta(days=5),
                    "scheduled_date": datetime.now() - timedelta(days=4),
                    "started_at": datetime.now() - timedelta(days=4, hours=2),
                    "completed_at": datetime.now() - timedelta(days=4, hours=1),
                    "computer_name": "DESKTOP-ABC123",
                    "ip_address": "192.168.1.100",
                    "operating_system": "Windows 11 Pro",
                    "issue_category": "Network",
                    "agent_notes": "Checked VPN configuration. Found firewall blocking VPN port. Configured firewall rules.",
                    "resolution_notes": "Issue resolved by adding VPN exception in Windows Firewall. Tested connection successfully.",
                    "rating": 5,
                    "feedback": "Excellent support! Agent was very helpful and resolved the issue quickly.",
                    "created_by": created_by_id,
                    "updated_by": created_by_id
                },
                {
                    "business_id": business.id,
                    "employee_id": employees[2].id if len(employees) > 2 else employees[0].id,
                    "support_agent_id": employees[1].id if len(employees) > 1 else None,
                    "session_type": RemoteSessionType.SOFTWARE_INSTALLATION,
                    "title": "Need help installing Microsoft Office 365",
                    "description": "Received new laptop. Need assistance installing Microsoft Office 365 and configuring email client.",
                    "status": RemoteSessionStatus.SCHEDULED,
                    "requested_date": datetime.now() - timedelta(days=2),
                    "scheduled_date": datetime.now() + timedelta(days=1),
                    "started_at": None,
                    "completed_at": None,
                    "computer_name": "LAPTOP-XYZ789",
                    "ip_address": "192.168.1.105",
                    "operating_system": "Windows 11 Home",
                    "issue_category": "Software",
                    "agent_notes": "Session scheduled for tomorrow 2 PM. Will install Office 365 and configure Outlook.",
                    "resolution_notes": None,
                    "rating": None,
                    "feedback": None,
                    "created_by": created_by_id,
                    "updated_by": created_by_id
                },
                {
                    "business_id": business.id,
                    "employee_id": employees[3].id if len(employees) > 3 else employees[0].id,
                    "support_agent_id": None,
                    "session_type": RemoteSessionType.TROUBLESHOOTING,
                    "title": "Computer running very slow",
                    "description": "My computer has been running extremely slow for the past week. Applications take forever to open and system freezes frequently.",
                    "status": RemoteSessionStatus.PENDING,
                    "requested_date": datetime.now() - timedelta(hours=3),
                    "scheduled_date": None,
                    "started_at": None,
                    "completed_at": None,
                    "computer_name": "DESKTOP-DEF456",
                    "ip_address": "192.168.1.110",
                    "operating_system": "Windows 10 Pro",
                    "issue_category": "Performance",
                    "agent_notes": None,
                    "resolution_notes": None,
                    "rating": None,
                    "feedback": None,
                    "created_by": created_by_id,
                    "updated_by": created_by_id
                },
                {
                    "business_id": business.id,
                    "employee_id": employees[4].id if len(employees) > 4 else employees[0].id,
                    "support_agent_id": employees[1].id if len(employees) > 1 else None,
                    "session_type": RemoteSessionType.TRAINING,
                    "title": "Training on new HRMS system",
                    "description": "Need training on how to use the new HRMS system for attendance marking and leave applications.",
                    "status": RemoteSessionStatus.IN_PROGRESS,
                    "requested_date": datetime.now() - timedelta(days=1),
                    "scheduled_date": datetime.now(),
                    "started_at": datetime.now() - timedelta(minutes=30),
                    "completed_at": None,
                    "computer_name": "LAPTOP-GHI789",
                    "ip_address": "192.168.1.115",
                    "operating_system": "Windows 11 Pro",
                    "issue_category": "Training",
                    "agent_notes": "Currently conducting training session. Covering attendance and leave modules.",
                    "resolution_notes": None,
                    "rating": None,
                    "feedback": None,
                    "created_by": created_by_id,
                    "updated_by": created_by_id
                },
                {
                    "business_id": business.id,
                    "employee_id": employees[5].id if len(employees) > 5 else employees[0].id,
                    "support_agent_id": employees[1].id if len(employees) > 1 else None,
                    "session_type": RemoteSessionType.SYSTEM_MAINTENANCE,
                    "title": "System updates and antivirus scan",
                    "description": "Need help with Windows updates and running full system antivirus scan. System showing pending updates notification.",
                    "status": RemoteSessionStatus.COMPLETED,
                    "requested_date": datetime.now() - timedelta(days=7),
                    "scheduled_date": datetime.now() - timedelta(days=6),
                    "started_at": datetime.now() - timedelta(days=6, hours=3),
                    "completed_at": datetime.now() - timedelta(days=6, hours=2),
                    "computer_name": "DESKTOP-JKL012",
                    "ip_address": "192.168.1.120",
                    "operating_system": "Windows 10 Pro",
                    "issue_category": "Maintenance",
                    "agent_notes": "Installed all pending Windows updates. Ran full antivirus scan. No threats found.",
                    "resolution_notes": "System fully updated and secured. Recommended enabling automatic updates.",
                    "rating": 4,
                    "feedback": "Good service. Took a bit longer than expected but thorough work.",
                    "created_by": created_by_id,
                    "updated_by": created_by_id
                },
                {
                    "business_id": business.id,
                    "employee_id": employees[6].id if len(employees) > 6 else employees[0].id,
                    "support_agent_id": None,
                    "session_type": RemoteSessionType.OTHER,
                    "title": "Printer not working",
                    "description": "Office printer not responding. Tried restarting but still not working. Need remote assistance to diagnose the issue.",
                    "status": RemoteSessionStatus.PENDING,
                    "requested_date": datetime.now() - timedelta(hours=1),
                    "scheduled_date": None,
                    "started_at": None,
                    "completed_at": None,
                    "computer_name": "DESKTOP-MNO345",
                    "ip_address": "192.168.1.125",
                    "operating_system": "Windows 11 Pro",
                    "issue_category": "Hardware",
                    "agent_notes": None,
                    "resolution_notes": None,
                    "rating": None,
                    "feedback": None,
                    "created_by": created_by_id,
                    "updated_by": created_by_id
                }
            ]
            
            created_count = 0
            for session_data in sessions_data:
                session = RemoteSession(**session_data)
                db.add(session)
                created_count += 1
            
            db.commit()
            
            logger.info(f"[OK] Created {created_count} remote sessions sample data")
            logger.info(f"  - Business ID: {business.id}")
            logger.info(f"  - Statuses: Pending (2), Scheduled (1), In Progress (1), Completed (2)")
            return True
    
    except Exception as e:
        logger.error(f"Error creating remote sessions sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_help_articles_sample_data():
    """Create sample help articles data for testing"""
    logger.info("\nStep 38.6: Creating help articles sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.help_article import HelpArticle, ArticleCategory, ArticleType
            from app.models.business import Business
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if help articles already exist
            existing_articles = db.query(HelpArticle).filter(
                HelpArticle.business_id == business.id
            ).first()
            
            if existing_articles:
                logger.info("Help articles already exist, skipping...")
                return True
            
            # Get superadmin user for created_by
            superadmin = db.query(User).filter(User.email == settings.SUPERADMIN_EMAIL).first()
            created_by_id = superadmin.id if superadmin else None
            
            # Create sample help articles
            articles_data = [
                {
                    "business_id": business.id,
                    "title": "Getting Started with Levitica HRMS",
                    "slug": "getting-started-with-levitica-hrms",
                    "category": ArticleCategory.GETTING_STARTED.value,
                    "article_type": ArticleType.GUIDE.value,
                    "summary": "Learn the basics of using Levitica HRMS system including navigation, dashboard overview, and key features.",
                    "content": """# Getting Started with Levitica HRMS

Welcome to Levitica HRMS! This guide will help you get started with the system.

## Dashboard Overview
The dashboard provides a quick overview of your HR metrics including:
- Employee count and status
- Attendance summary
- Leave requests
- Pending approvals

## Navigation
Use the sidebar menu to access different modules:
- **Employees**: Manage employee records
- **Attendance**: Track attendance and punches
- **Leave**: Manage leave requests and policies
- **Payroll**: Process salaries and deductions
- **Reports**: Generate various HR reports

## Quick Actions
- Click the profile icon to access your settings
- Use the search bar to quickly find employees
- Access notifications from the bell icon

For more detailed information, explore our other help articles.""",
                    "thumbnail_url": None,
                    "video_url": None,
                    "tags": "getting started, basics, dashboard, navigation",
                    "views": 150,
                    "helpful_count": 45,
                    "not_helpful_count": 2,
                    "is_published": True,
                    "is_featured": True,
                    "meta_description": "Complete guide to getting started with Levitica HRMS",
                    "meta_keywords": "HRMS, getting started, tutorial, guide",
                    "created_by": created_by_id,
                    "updated_by": created_by_id
                },
                {
                    "business_id": business.id,
                    "title": "How to Mark Attendance",
                    "slug": "how-to-mark-attendance",
                    "category": ArticleCategory.ATTENDANCE.value,
                    "article_type": ArticleType.TUTORIAL.value,
                    "summary": "Step-by-step guide on marking attendance, handling missed punches, and viewing attendance reports.",
                    "content": """# How to Mark Attendance

## Marking Daily Attendance
1. Navigate to **Attendance** > **Mark Attendance**
2. Click on **Punch In** when you start work
3. Click on **Punch Out** when you finish work

## Handling Missed Punches
If you forgot to punch in or out:
1. Go to **Requests** > **Missed Punch Request**
2. Fill in the date and time
3. Provide a reason
4. Submit for approval

## Viewing Attendance History
- Go to **Attendance** > **My Attendance**
- Select date range
- View detailed punch records

## Attendance Policies
- Regular working hours: 9:00 AM - 6:00 PM
- Grace period: 15 minutes
- Half-day: Less than 4 hours
- Full-day: 8+ hours""",
                    "thumbnail_url": None,
                    "video_url": None,
                    "tags": "attendance, punch, missed punch, tutorial",
                    "views": 230,
                    "helpful_count": 78,
                    "not_helpful_count": 5,
                    "is_published": True,
                    "is_featured": True,
                    "meta_description": "Learn how to mark attendance and handle missed punches",
                    "meta_keywords": "attendance, punch in, punch out, missed punch",
                    "created_by": created_by_id,
                    "updated_by": created_by_id
                },
                {
                    "business_id": business.id,
                    "title": "Applying for Leave",
                    "slug": "applying-for-leave",
                    "category": ArticleCategory.LEAVE_MANAGEMENT.value,
                    "article_type": ArticleType.TUTORIAL.value,
                    "summary": "Complete guide on how to apply for different types of leaves and track leave balance.",
                    "content": """# Applying for Leave

## Steps to Apply for Leave
1. Go to **Leave** > **Apply Leave**
2. Select leave type (Casual, Sick, Earned, etc.)
3. Choose start and end dates
4. Enter reason for leave
5. Click **Submit**

## Leave Types
- **Casual Leave**: For personal reasons
- **Sick Leave**: For medical reasons
- **Earned Leave**: Accumulated leave
- **Comp Off**: Compensatory off for overtime

## Checking Leave Balance
- Navigate to **Leave** > **Leave Balance**
- View available leaves by type
- See leave history and pending requests

## Leave Approval Process
1. Request submitted
2. Manager reviews
3. HR approves (if required)
4. Status updated

## Tips
- Apply for leave in advance
- Attach medical certificate for sick leave > 2 days
- Check leave policy for restrictions""",
                    "thumbnail_url": None,
                    "video_url": None,
                    "tags": "leave, apply leave, leave balance, leave types",
                    "views": 310,
                    "helpful_count": 95,
                    "not_helpful_count": 3,
                    "is_published": True,
                    "is_featured": True,
                    "meta_description": "Step-by-step guide to applying for leave in HRMS",
                    "meta_keywords": "leave application, leave balance, leave types",
                    "created_by": created_by_id,
                    "updated_by": created_by_id
                },
                {
                    "business_id": business.id,
                    "title": "Understanding Your Payslip",
                    "slug": "understanding-your-payslip",
                    "category": ArticleCategory.PAYROLL.value,
                    "article_type": ArticleType.GUIDE.value,
                    "summary": "Detailed explanation of payslip components including earnings, deductions, and net salary calculation.",
                    "content": """# Understanding Your Payslip

## Payslip Components

### Earnings
- **Basic Salary**: Fixed component
- **HRA**: House Rent Allowance
- **Special Allowance**: Additional allowances
- **Overtime**: Extra hours worked

### Deductions
- **PF**: Provident Fund (12% of basic)
- **ESI**: Employee State Insurance
- **Professional Tax**: State tax
- **TDS**: Tax Deducted at Source
- **LWF**: Labour Welfare Fund

### Net Salary Calculation
```
Gross Salary = Sum of all earnings
Total Deductions = Sum of all deductions
Net Salary = Gross Salary - Total Deductions
```

## Viewing Payslip
1. Go to **Payroll** > **My Payslips**
2. Select month and year
3. Download PDF

## Common Questions
- **Why is my salary different?**: Check attendance and leaves
- **TDS calculation**: Based on annual income
- **PF contribution**: 12% employee + 12% employer""",
                    "thumbnail_url": None,
                    "video_url": None,
                    "tags": "payslip, salary, earnings, deductions, payroll",
                    "views": 420,
                    "helpful_count": 125,
                    "not_helpful_count": 8,
                    "is_published": True,
                    "is_featured": False,
                    "meta_description": "Understand your payslip components and salary calculation",
                    "meta_keywords": "payslip, salary, earnings, deductions",
                    "created_by": created_by_id,
                    "updated_by": created_by_id
                },
                {
                    "business_id": business.id,
                    "title": "FAQ: Common HRMS Questions",
                    "slug": "faq-common-hrms-questions",
                    "category": ArticleCategory.FAQ.value,
                    "article_type": ArticleType.FAQ.value,
                    "summary": "Frequently asked questions about using the HRMS system.",
                    "content": """# Frequently Asked Questions

## Account & Login
**Q: I forgot my password. What should I do?**
A: Click on "Forgot Password" on the login page and follow the instructions.

**Q: Can I change my email address?**
A: Contact HR to update your email address.

## Attendance
**Q: What if I forget to punch in/out?**
A: Submit a missed punch request with the correct time and reason.

**Q: How is overtime calculated?**
A: Hours worked beyond 8 hours per day are considered overtime.

## Leave
**Q: How many leaves do I have?**
A: Check your leave balance in the Leave module.

**Q: Can I cancel a leave request?**
A: Yes, if it's not yet approved. Go to pending requests and cancel.

## Payroll
**Q: When will I receive my salary?**
A: Salaries are processed on the last working day of the month.

**Q: How can I download my Form 16?**
A: Go to Payroll > Tax Documents > Form 16.

## Technical Issues
**Q: The system is slow. What should I do?**
A: Clear your browser cache or try a different browser.

**Q: I can't upload documents.**
A: Check file size (max 10MB) and format (PDF, JPG, PNG).""",
                    "thumbnail_url": None,
                    "video_url": None,
                    "tags": "faq, questions, help, support",
                    "views": 580,
                    "helpful_count": 165,
                    "not_helpful_count": 12,
                    "is_published": True,
                    "is_featured": False,
                    "meta_description": "Frequently asked questions about HRMS",
                    "meta_keywords": "FAQ, questions, help, support",
                    "created_by": created_by_id,
                    "updated_by": created_by_id
                },
                {
                    "business_id": business.id,
                    "title": "Troubleshooting Login Issues",
                    "slug": "troubleshooting-login-issues",
                    "category": ArticleCategory.TROUBLESHOOTING.value,
                    "article_type": ArticleType.QUICK_TIP.value,
                    "summary": "Quick tips to resolve common login problems.",
                    "content": """# Troubleshooting Login Issues

## Common Login Problems

### Invalid Credentials
- Double-check your email and password
- Ensure Caps Lock is off
- Try copying and pasting credentials

### Account Locked
- After 5 failed attempts, account is locked for 30 minutes
- Contact HR to unlock immediately

### Browser Issues
- Clear browser cache and cookies
- Try incognito/private mode
- Use a different browser (Chrome, Firefox, Edge)

### Network Problems
- Check internet connection
- Try mobile data if WiFi isn't working
- Disable VPN if enabled

### Password Reset
1. Click "Forgot Password"
2. Enter your email
3. Check inbox for reset link
4. Create new password

## Still Having Issues?
Contact IT support:
- Email: support@levitica.com
- Phone: +91-9876543210
- Helpdesk: Submit a ticket""",
                    "thumbnail_url": None,
                    "video_url": None,
                    "tags": "troubleshooting, login, password, issues",
                    "views": 190,
                    "helpful_count": 52,
                    "not_helpful_count": 7,
                    "is_published": True,
                    "is_featured": False,
                    "meta_description": "Resolve common login issues quickly",
                    "meta_keywords": "troubleshooting, login issues, password reset",
                    "created_by": created_by_id,
                    "updated_by": created_by_id
                }
            ]
            
            created_count = 0
            for article_data in articles_data:
                article = HelpArticle(**article_data)
                db.add(article)
                created_count += 1
            
            db.commit()
            
            logger.info(f"[OK] Created {created_count} help articles sample data")
            logger.info(f"  - Business ID: {business.id}")
            logger.info(f"  - Categories: Getting Started, Attendance, Leave, Payroll, FAQ, Troubleshooting")
            return True
    
    except Exception as e:
        logger.error(f"Error creating help articles sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_employee_code_settings_sample_data():
    """Create sample employee code settings data for testing"""
    logger.info("\nStep 39: Creating employee code settings sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee_code_config import EmployeeCodeSetting
            from app.models.business import Business
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if employee code settings already exist
            existing_settings = db.query(EmployeeCodeSetting).filter(
                EmployeeCodeSetting.business_id == business.id
            ).first()
            
            if existing_settings:
                logger.info("Employee code settings already exist, skipping...")
                return True
            
            # Create default employee code settings
            settings_data = {
                "business_id": business.id,
                "auto_code": True,
                "prefix": "LEV",
                "length": 3,
                "suffix": ""
            }
            
            settings = EmployeeCodeSetting(**settings_data)
            db.add(settings)
            db.commit()
            
            logger.info(f"[OK] Created employee code settings sample data")
            logger.info(f"  - Business ID: {business.id}")
            logger.info(f"  - Auto Code: {settings.auto_code}")
            logger.info(f"  - Prefix: {settings.prefix}")
            logger.info(f"  - Length: {settings.length}")
            logger.info(f"  - Suffix: '{settings.suffix}'")
            return True
    
    except Exception as e:
        logger.error(f"Error creating employee code settings sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_salary_deduction_types_sample_data():
    """Create comprehensive salary deduction types sample data for testing"""
    logger.info("\nStep 30.6: Creating salary deduction types sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.setup.salary_and_deductions.salary_deduction import SalaryDeduction
            from app.models.business import Business
            from datetime import datetime
            
            # Check if salary deduction types already exist
            existing_deduction_types = db.query(SalaryDeduction).first()
            if existing_deduction_types:
                logger.info("Salary deduction types sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Create comprehensive salary deduction types
            salary_deduction_types_data = [
                {
                    "business_id": business.id,
                    "name": "Group Insurance",
                    "code": "GI",
                    "type": "Fixed",
                    "active": True,
                    "payback_on_exit": False,
                    "status": "Active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Gratuity",
                    "code": "GRATUITY",
                    "type": "Fixed",
                    "active": True,
                    "payback_on_exit": True,
                    "status": "Active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Provident Fund",
                    "code": "PF",
                    "type": "Fixed",
                    "active": True,
                    "payback_on_exit": True,
                    "status": "Active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Employee State Insurance",
                    "code": "ESI",
                    "type": "Fixed",
                    "active": True,
                    "payback_on_exit": False,
                    "status": "Active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Professional Tax",
                    "code": "PT",
                    "type": "Fixed",
                    "active": True,
                    "payback_on_exit": False,
                    "status": "Active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Income Tax",
                    "code": "IT",
                    "type": "Variable",
                    "active": True,
                    "payback_on_exit": False,
                    "status": "Active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Loan Deduction",
                    "code": "LOAN",
                    "type": "Variable",
                    "active": True,
                    "payback_on_exit": False,
                    "status": "Active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Advance Deduction",
                    "code": "ADVANCE",
                    "type": "Variable",
                    "active": True,
                    "payback_on_exit": False,
                    "status": "Active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Canteen Deduction",
                    "code": "CANTEEN",
                    "type": "Variable",
                    "active": True,
                    "payback_on_exit": False,
                    "status": "Active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Transport Deduction",
                    "code": "TRANSPORT",
                    "type": "Fixed",
                    "active": True,
                    "payback_on_exit": False,
                    "status": "Active",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
            ]
            
            created_count = 0
            for deduction_data in salary_deduction_types_data:
                salary_deduction = SalaryDeduction(**deduction_data)
                db.add(salary_deduction)
                created_count += 1
            
            db.commit()
            logger.info(f"[OK] Created {created_count} salary deduction types")
            return True
    
    except Exception as e:
        logger.error(f"Error creating salary deduction types sample data: {e}")
        return False


def create_salary_components_sample_data():
    """Create comprehensive salary components sample data for testing"""
    logger.info("\nStep 30.5: Creating salary components sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.setup.salary_and_deductions.salary_component import SalaryComponent
            from app.models.business import Business
            from datetime import datetime
            
            # Check if salary components already exist
            existing_components = db.query(SalaryComponent).first()
            if existing_components:
                logger.info("Salary components sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Create comprehensive salary components
            salary_components_data = [
                {
                    "business_id": business.id,
                    "name": "Basic Salary",
                    "alias": "BASIC",
                    "component_type": "Fixed",
                    "unit_type": "Paid Days",
                    "is_active": True,
                    "exclude_holidays": False,
                    "exclude_weekoffs": False,
                    "exclude_from_gross": False,
                    "hide_in_ctc": False,
                    "not_payable": False,
                    "is_lwf_applicable": False,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "House Rent Allowance",
                    "alias": "HRA",
                    "component_type": "Fixed",
                    "unit_type": "Paid Days",
                    "is_active": True,
                    "exclude_holidays": False,
                    "exclude_weekoffs": False,
                    "exclude_from_gross": False,
                    "hide_in_ctc": False,
                    "not_payable": False,
                    "is_lwf_applicable": True,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Special Allowance",
                    "alias": "SA",
                    "component_type": "Fixed",
                    "unit_type": "Paid Days",
                    "is_active": True,
                    "exclude_holidays": False,
                    "exclude_weekoffs": False,
                    "exclude_from_gross": False,
                    "hide_in_ctc": False,
                    "not_payable": False,
                    "is_lwf_applicable": True,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Medical Allowance",
                    "alias": "MDA",
                    "component_type": "Fixed",
                    "unit_type": "Paid Days",
                    "is_active": True,
                    "exclude_holidays": False,
                    "exclude_weekoffs": False,
                    "exclude_from_gross": False,
                    "hide_in_ctc": False,
                    "not_payable": False,
                    "is_lwf_applicable": False,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Conveyance Allowance",
                    "alias": "CA",
                    "component_type": "Fixed",
                    "unit_type": "Paid Days",
                    "is_active": True,
                    "exclude_holidays": False,
                    "exclude_weekoffs": False,
                    "exclude_from_gross": False,
                    "hide_in_ctc": False,
                    "not_payable": False,
                    "is_lwf_applicable": False,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Telephone Allowance",
                    "alias": "TA",
                    "component_type": "Fixed",
                    "unit_type": "Paid Days",
                    "is_active": True,
                    "exclude_holidays": False,
                    "exclude_weekoffs": False,
                    "exclude_from_gross": False,
                    "hide_in_ctc": False,
                    "not_payable": False,
                    "is_lwf_applicable": False,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Leave Encashment",
                    "alias": "LE",
                    "component_type": "Variable",
                    "unit_type": "Casual Days",
                    "is_active": True,
                    "exclude_holidays": True,
                    "exclude_weekoffs": True,
                    "exclude_from_gross": False,
                    "hide_in_ctc": False,
                    "not_payable": False,
                    "is_lwf_applicable": False,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Bonus",
                    "alias": "BONUS",
                    "component_type": "Variable",
                    "unit_type": "Paid Days",
                    "is_active": True,
                    "exclude_holidays": False,
                    "exclude_weekoffs": False,
                    "exclude_from_gross": False,
                    "hide_in_ctc": True,
                    "not_payable": False,
                    "is_lwf_applicable": False,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Gratuity",
                    "alias": "GRATUITY",
                    "component_type": "Variable",
                    "unit_type": "Paid Days",
                    "is_active": True,
                    "exclude_holidays": False,
                    "exclude_weekoffs": False,
                    "exclude_from_gross": True,
                    "hide_in_ctc": True,
                    "not_payable": False,
                    "is_lwf_applicable": False,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Overtime (Hours)",
                    "alias": "OT_HRS",
                    "component_type": "Variable",
                    "unit_type": "Paid Days",
                    "is_active": True,
                    "exclude_holidays": False,
                    "exclude_weekoffs": False,
                    "exclude_from_gross": False,
                    "hide_in_ctc": False,
                    "not_payable": False,
                    "is_lwf_applicable": False,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Overtime (Days)",
                    "alias": "OT_DAYS",
                    "component_type": "Variable",
                    "unit_type": "Casual Days",
                    "is_active": True,
                    "exclude_holidays": True,
                    "exclude_weekoffs": True,
                    "exclude_from_gross": False,
                    "hide_in_ctc": False,
                    "not_payable": False,
                    "is_lwf_applicable": False,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Retention Bonus",
                    "alias": "RET_BONUS",
                    "component_type": "Variable",
                    "unit_type": "Paid Days",
                    "is_active": True,
                    "exclude_holidays": False,
                    "exclude_weekoffs": False,
                    "exclude_from_gross": False,
                    "hide_in_ctc": True,
                    "not_payable": False,
                    "is_lwf_applicable": False,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                },
                {
                    "business_id": business.id,
                    "name": "Loan Recovery",
                    "alias": "LOAN",
                    "component_type": "Deduction",
                    "unit_type": "Paid Days",
                    "is_active": True,
                    "exclude_holidays": False,
                    "exclude_weekoffs": False,
                    "exclude_from_gross": True,
                    "hide_in_ctc": True,
                    "not_payable": True,
                    "is_lwf_applicable": False,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
            ]
            
            created_count = 0
            for component_data in salary_components_data:
                salary_component = SalaryComponent(**component_data)
                db.add(salary_component)
                created_count += 1
            
            db.commit()
            logger.info(f"[OK] Created {created_count} salary components")
            return True
    
    except Exception as e:
        logger.error(f"Error creating salary components sample data: {e}")
        return False


def create_salary_structures_sample_data():
    """Create comprehensive salary structures sample data for testing"""
    logger.info("\nStep 30.7: Creating salary structures sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.setup.salary_and_deductions.salary_structure import SalaryStructure
            from app.models.setup.salary_and_deductions.salary_structure_rule import SalaryStructureRule
            from app.models.setup.salary_and_deductions.salary_component import SalaryComponent
            from app.models.business import Business
            from datetime import datetime
            
            # Check if salary structures already exist
            existing_structures = db.query(SalaryStructure).first()
            if existing_structures:
                logger.info("Salary structures sample data already exists, skipping...")
                return True
            
            # Get the first business
            business = db.query(Business).first()
            if not business:
                logger.warning("No business found. Creating sample business first...")
                return False
            
            # Get salary components for rules
            components = db.query(SalaryComponent).filter(
                SalaryComponent.business_id == business.id
            ).all()
            
            # If we don't have enough components, create the missing ones
            if len(components) < 5:
                logger.info(f"Found {len(components)} salary components. Creating additional components for salary structures...")
                
                # Define the components we need
                required_components = [
                    {"name": "Basic Salary", "alias": "Basic", "component_type": "Fixed", "unit_type": "Paid Days"},
                    {"name": "House Rent Allowance", "alias": "HRA", "component_type": "Variable", "unit_type": "Paid Days"},
                    {"name": "Special Allowance", "alias": "SA", "component_type": "Fixed", "unit_type": "Paid Days"},
                    {"name": "Medical Allowance", "alias": "MA", "component_type": "Fixed", "unit_type": "Paid Days"},
                    {"name": "Conveyance Allowance", "alias": "CA", "component_type": "Fixed", "unit_type": "Paid Days"}
                ]
                
                # Get existing component names to avoid duplicates
                existing_names = {comp.name for comp in components}
                
                # Create missing components
                for comp_data in required_components:
                    if comp_data["name"] not in existing_names:
                        component = SalaryComponent(
                            business_id=business.id,
                            name=comp_data["name"],
                            alias=comp_data["alias"],
                            component_type=comp_data["component_type"],
                            unit_type=comp_data["unit_type"],
                            is_active=True
                        )
                        db.add(component)
                
                db.commit()
                
                # Re-fetch components
                components = db.query(SalaryComponent).filter(
                    SalaryComponent.business_id == business.id
                ).all()
                logger.info(f"Now have {len(components)} salary components")
            
            if len(components) < 3:
                logger.error(f"Still only {len(components)} salary components found. Cannot create salary structures.")
                return False
            
            # Create comprehensive salary structures
            salary_structures_data = [
                {
                    "name": "Junior Level Structure",
                    "business_id": business.id,
                    "rules": [
                        {"component_id": components[0].id, "calculation_type": "Fixed", "value": 25000.0, "sequence": 1},
                        {"component_id": components[1].id, "calculation_type": "Percentage", "value": 40.0, "sequence": 2},
                        {"component_id": components[2].id, "calculation_type": "Fixed", "value": 2000.0, "sequence": 3},
                    ]
                },
                {
                    "name": "Mid Level Structure",
                    "business_id": business.id,
                    "rules": [
                        {"component_id": components[0].id, "calculation_type": "Fixed", "value": 40000.0, "sequence": 1},
                        {"component_id": components[1].id, "calculation_type": "Percentage", "value": 50.0, "sequence": 2},
                        {"component_id": components[2].id, "calculation_type": "Fixed", "value": 3000.0, "sequence": 3},
                        {"component_id": components[min(3, len(components)-1)].id, "calculation_type": "Fixed", "value": 1500.0, "sequence": 4},
                    ]
                },
                {
                    "name": "Senior Level Structure",
                    "business_id": business.id,
                    "rules": [
                        {"component_id": components[0].id, "calculation_type": "Fixed", "value": 60000.0, "sequence": 1},
                        {"component_id": components[1].id, "calculation_type": "Percentage", "value": 50.0, "sequence": 2},
                        {"component_id": components[2].id, "calculation_type": "Fixed", "value": 5000.0, "sequence": 3},
                        {"component_id": components[min(3, len(components)-1)].id, "calculation_type": "Fixed", "value": 2500.0, "sequence": 4},
                        {"component_id": components[min(4, len(components)-1)].id, "calculation_type": "Fixed", "value": 2000.0, "sequence": 5},
                    ]
                },
                {
                    "name": "Executive Level Structure",
                    "business_id": business.id,
                    "rules": [
                        {"component_id": components[0].id, "calculation_type": "Fixed", "value": 80000.0, "sequence": 1},
                        {"component_id": components[1].id, "calculation_type": "Percentage", "value": 50.0, "sequence": 2},
                        {"component_id": components[2].id, "calculation_type": "Fixed", "value": 8000.0, "sequence": 3},
                        {"component_id": components[min(3, len(components)-1)].id, "calculation_type": "Fixed", "value": 4000.0, "sequence": 4},
                        {"component_id": components[min(4, len(components)-1)].id, "calculation_type": "Fixed", "value": 3000.0, "sequence": 5},
                    ]
                },
                {
                    "name": "Trainee Structure",
                    "business_id": business.id,
                    "rules": [
                        {"component_id": components[0].id, "calculation_type": "Fixed", "value": 18000.0, "sequence": 1},
                        {"component_id": components[1].id, "calculation_type": "Percentage", "value": 30.0, "sequence": 2},
                        {"component_id": components[2].id, "calculation_type": "Fixed", "value": 1000.0, "sequence": 3},
                    ]
                }
            ]
            
            created_count = 0
            for structure_data in salary_structures_data:
                # Create the salary structure
                salary_structure = SalaryStructure(
                    name=structure_data["name"],
                    business_id=structure_data["business_id"]
                )
                db.add(salary_structure)
                db.flush()  # Get the ID
                
                # Create the rules for this structure
                for rule_data in structure_data["rules"]:
                    salary_rule = SalaryStructureRule(
                        business_id=structure_data["business_id"],
                        structure_id=salary_structure.id,
                        component_id=rule_data["component_id"],
                        calculation_type=rule_data["calculation_type"],
                        value=rule_data["value"],
                        sequence=rule_data["sequence"]
                    )
                    db.add(salary_rule)
                
                created_count += 1
            
            db.commit()
            logger.info(f"[OK] Created {created_count} salary structures with rules")
            return True
    
    except Exception as e:
        logger.error(f"Error creating salary structures sample data: {e}")
        return False


def create_time_salary_sample_data():
    """Create sample time salary rules data for ALL active salary components"""
    logger.info("\nStep 31: Creating time salary sample data for ALL components...")
    
    try:
        with get_db_context() as db:
            from app.models.setup.salary_and_deductions.time_salary import TimeSalaryRule
            from app.models.setup.salary_and_deductions.salary_component import SalaryComponent
            from app.models.business import Business
            from datetime import time
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get ALL active salary components
            all_components = db.query(SalaryComponent).filter(
                SalaryComponent.business_id == business.id,
                SalaryComponent.is_active == True
            ).all()
            
            if not all_components:
                logger.error("No active salary components found")
                return False
            
            logger.info(f"Found {len(all_components)} active salary components")
            
            # Define time salary rule templates (will be applied to each component)
            rule_templates = [
                {
                    "attendance": "Present",
                    "shift": "Regular Shift",
                    "early_coming_minutes": 15,
                    "in_office_time": time(9, 0),  # 9:00 AM
                    "out_office_time": time(18, 0),  # 6:00 PM
                    "lunch_always_minutes": 60,
                    "lunch_working_minutes": 30,
                    "late_going_minutes": 15,
                    "limit_shift_hours": 8
                },
                {
                    "attendance": "Present",
                    "shift": "Night Shift",
                    "early_coming_minutes": 10,
                    "in_office_time": time(22, 0),  # 10:00 PM
                    "out_office_time": time(6, 0),   # 6:00 AM
                    "lunch_always_minutes": 45,
                    "lunch_working_minutes": 30,
                    "late_going_minutes": 10,
                    "limit_shift_hours": 8
                },
                {
                    "attendance": "Half Day",
                    "shift": "Regular Shift",
                    "early_coming_minutes": 15,
                    "in_office_time": time(9, 0),  # 9:00 AM
                    "out_office_time": time(13, 0),  # 1:00 PM
                    "lunch_always_minutes": 0,
                    "lunch_working_minutes": 0,
                    "late_going_minutes": 15,
                    "limit_shift_hours": 4
                }
            ]
            
            created_count = 0
            skipped_count = 0
            
            # Create time salary rules for EACH component
            for component in all_components:
                # Check if rules already exist for this component
                existing_rules = db.query(TimeSalaryRule).filter(
                    TimeSalaryRule.business_id == business.id,
                    TimeSalaryRule.component_id == component.id
                ).first()
                
                if existing_rules:
                    logger.info(f"  Skipping {component.name} - rules already exist")
                    skipped_count += 1
                    continue
                
                # Create rules for this component
                for template in rule_templates:
                    rule_data = {
                        "business_id": business.id,
                        "component_id": component.id,
                        **template
                    }
                    time_rule = TimeSalaryRule(**rule_data)
                    db.add(time_rule)
                    created_count += 1
                
                logger.info(f"  Created 3 rules for: {component.name}")
            
            db.commit()
            logger.info(f"[OK] Created {created_count} time salary rules for {len(all_components) - skipped_count} components")
            if skipped_count > 0:
                logger.info(f"[INFO] Skipped {skipped_count} components (rules already exist)")
            return True
    
    except Exception as e:
        logger.error(f"Error creating time salary sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_overtime_sample_data():
    """Create comprehensive overtime policies and rules sample data for testing"""
def create_overtime_sample_data():
    """Create comprehensive overtime policies and rules sample data for testing"""
    logger.info("\nStep 31.1: Creating overtime sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.setup.salary_and_deductions.overtime import OvertimePolicy, OvertimeRule
            from app.models.business import Business
            from datetime import datetime
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if overtime policies already exist
            existing_policies = db.query(OvertimePolicy).first()
            if existing_policies:
                logger.info("Overtime sample data already exists, skipping...")
                return True
            
            # Create overtime policies
            overtime_policies_data = [
                {
                    "business_id": business.id,
                    "policy_name": "Not Applicable"
                },
                {
                    "business_id": business.id,
                    "policy_name": "Standard Overtime Policy"
                },
                {
                    "business_id": business.id,
                    "policy_name": "Premium Overtime Policy"
                }
            ]
            
            created_policies = []
            for policy_data in overtime_policies_data:
                overtime_policy = OvertimePolicy(**policy_data)
                db.add(overtime_policy)
                db.flush()  # Get the ID
                created_policies.append(overtime_policy)
            
            # Create overtime rules for policies (skip "Not Applicable")
            overtime_rules_data = [
                # Standard Overtime Policy Rules
                {
                    "business_id": business.id,
                    "policy_id": created_policies[1].id,  # Standard Overtime Policy
                    "attendance_type": "Present",
                    "time_basis": "Early Coming",
                    "from_hrs": 0,
                    "from_mins": 15,
                    "to_hrs": 1,
                    "to_mins": 0,
                    "calculation_method": "Exclusive",
                    "multiplier": 2,
                    "overtime_mins_type": "Actual",
                    "fixed_mins": None
                },
                {
                    "business_id": business.id,
                    "policy_id": created_policies[1].id,
                    "attendance_type": "Present",
                    "time_basis": "Late Going",
                    "from_hrs": 0,
                    "from_mins": 30,
                    "to_hrs": 2,
                    "to_mins": 0,
                    "calculation_method": "Progressive",
                    "multiplier": 2,
                    "overtime_mins_type": "Actual",
                    "fixed_mins": None
                },
                {
                    "business_id": business.id,
                    "policy_id": created_policies[1].id,
                    "attendance_type": "Present",
                    "time_basis": "Late Going",
                    "from_hrs": 2,
                    "from_mins": 0,
                    "to_hrs": 4,
                    "to_mins": 0,
                    "calculation_method": "Progressive",
                    "multiplier": 3,
                    "overtime_mins_type": "Actual",
                    "fixed_mins": None
                },
                # Premium Overtime Policy Rules
                {
                    "business_id": business.id,
                    "policy_id": created_policies[2].id,  # Premium Overtime Policy
                    "attendance_type": "Present",
                    "time_basis": "Early Coming",
                    "from_hrs": 0,
                    "from_mins": 30,
                    "to_hrs": 2,
                    "to_mins": 0,
                    "calculation_method": "Exclusive",
                    "multiplier": 3,
                    "overtime_mins_type": "Fixed",
                    "fixed_mins": 60
                },
                {
                    "business_id": business.id,
                    "policy_id": created_policies[2].id,
                    "attendance_type": "Present",
                    "time_basis": "Late Going",
                    "from_hrs": 1,
                    "from_mins": 0,
                    "to_hrs": 3,
                    "to_mins": 0,
                    "calculation_method": "Progressive",
                    "multiplier": 4,
                    "overtime_mins_type": "Actual",
                    "fixed_mins": None
                },
                {
                    "business_id": business.id,
                    "policy_id": created_policies[2].id,
                    "attendance_type": "Half Day",
                    "time_basis": "Late Going",
                    "from_hrs": 0,
                    "from_mins": 30,
                    "to_hrs": 2,
                    "to_mins": 0,
                    "calculation_method": "Exclusive",
                    "multiplier": 2,
                    "overtime_mins_type": "Above",
                    "fixed_mins": None
                }
            ]
            
            created_rules_count = 0
            for rule_data in overtime_rules_data:
                overtime_rule = OvertimeRule(**rule_data)
                db.add(overtime_rule)
                created_rules_count += 1
            
            db.commit()
            logger.info(f"[OK] Created {len(created_policies)} overtime policies with {created_rules_count} rules")
            return True
    
    except Exception as e:
        logger.error(f"Error creating overtime sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_attendance_settings_sample_data():
    """Create comprehensive attendance settings sample data for testing"""
    logger.info("\nStep 31.2: Creating attendance settings sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.attendance_settings import AttendanceSettings
            from app.models.business import Business
            from datetime import datetime
            
            # Check if attendance settings already exist
            existing_settings = db.query(AttendanceSettings).first()
            if existing_settings:
                logger.info("Attendance settings sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Create comprehensive attendance settings
            attendance_settings = AttendanceSettings(
                business_id=business.id,
                default_attendance="PRESENT",  # Must be uppercase
                mark_out_on_punch=True,
                punch_count=2,
                enable_manual_attendance=True,
                no_holiday_if_absent=True,
                apply_holiday_one_side=False,
                apply_holiday_either=False,
                no_week_off_if_absent=True,
                apply_week_off_one_side=True,
                apply_week_off_either=False
            )
            
            db.add(attendance_settings)
            db.commit()
            
            logger.info("[OK] Created attendance settings with comprehensive configuration")
            logger.info(f"  - Default attendance: {attendance_settings.default_attendance}")
            logger.info(f"  - Mark out on punch: {attendance_settings.mark_out_on_punch}")
            logger.info(f"  - Manual attendance: {attendance_settings.enable_manual_attendance}")
            logger.info(f"  - Holiday rules: no_if_absent={attendance_settings.no_holiday_if_absent}")
            logger.info(f"  - Week off rules: no_if_absent={attendance_settings.no_week_off_if_absent}")
            return True
    
    except Exception as e:
        logger.error(f"Error creating attendance settings sample data: {e}")
        return False


def create_leave_types_sample_data():
    """Create comprehensive leave types sample data for testing"""
    logger.info("\nStep 31.3: Creating leave types sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.leave_type import LeaveType
            from app.models.business import Business
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Define comprehensive leave types
            leave_types_data = [
                {
                    "name": "Annual Leave",
                    "alias": "AL",
                    "color": "#4CAF50",
                    "paid": True,
                    "track_balance": True,
                    "probation": "Allow",
                    "allow_requests": True,
                    "allow_future_requests": True,
                    "advance_leaves": 5,
                    "past_days": 30,
                    "monthly_limit": 2
                },
                {
                    "name": "Casual Leave",
                    "alias": "CL",
                    "color": "#2196F3",
                    "paid": True,
                    "track_balance": True,
                    "probation": "Allow",
                    "allow_requests": True,
                    "allow_future_requests": True,
                    "advance_leaves": 2,
                    "past_days": 7,
                    "monthly_limit": 1
                },
                {
                    "name": "Sick Leave",
                    "alias": "SL",
                    "color": "#FF9800",
                    "paid": True,
                    "track_balance": True,
                    "probation": "Allow",
                    "allow_requests": True,
                    "allow_future_requests": False,
                    "advance_leaves": 0,
                    "past_days": 3,
                    "monthly_limit": 2
                },
                {
                    "name": "Maternity Leave",
                    "alias": "ML",
                    "color": "#E91E63",
                    "paid": True,
                    "track_balance": False,
                    "probation": "Disallow",
                    "allow_requests": True,
                    "allow_future_requests": True,
                    "advance_leaves": 0,
                    "past_days": 0,
                    "monthly_limit": 0
                },
                {
                    "name": "Paternity Leave",
                    "alias": "PL",
                    "color": "#9C27B0",
                    "paid": True,
                    "track_balance": False,
                    "probation": "Disallow",
                    "allow_requests": True,
                    "allow_future_requests": True,
                    "advance_leaves": 0,
                    "past_days": 0,
                    "monthly_limit": 0
                },
                {
                    "name": "Emergency Leave",
                    "alias": "EL",
                    "color": "#F44336",
                    "paid": False,
                    "track_balance": True,
                    "probation": "Allow",
                    "allow_requests": True,
                    "allow_future_requests": False,
                    "advance_leaves": 0,
                    "past_days": 1,
                    "monthly_limit": 1
                },
                {
                    "name": "Compensatory Off",
                    "alias": "CO",
                    "color": "#607D8B",
                    "paid": True,
                    "track_balance": True,
                    "probation": "Allow",
                    "allow_requests": True,
                    "allow_future_requests": True,
                    "advance_leaves": 0,
                    "past_days": 90,
                    "monthly_limit": 4
                },
                {
                    "name": "Loss of Pay",
                    "alias": "LOP",
                    "color": "#795548",
                    "paid": False,
                    "track_balance": False,
                    "probation": "Allow",
                    "allow_requests": True,
                    "allow_future_requests": True,
                    "advance_leaves": 0,
                    "past_days": 7,
                    "monthly_limit": 0
                },
                {
                    "name": "Study Leave",
                    "alias": "STL",
                    "color": "#3F51B5",
                    "paid": False,
                    "track_balance": False,
                    "probation": "Disallow",
                    "allow_requests": True,
                    "allow_future_requests": True,
                    "advance_leaves": 0,
                    "past_days": 0,
                    "monthly_limit": 0
                },
                {
                    "name": "Bereavement Leave",
                    "alias": "BL",
                    "color": "#424242",
                    "paid": True,
                    "track_balance": False,
                    "probation": "Allow",
                    "allow_requests": True,
                    "allow_future_requests": False,
                    "advance_leaves": 0,
                    "past_days": 3,
                    "monthly_limit": 0
                }
            ]
            
            # Get existing leave types
            existing_leave_types = db.query(LeaveType).filter(LeaveType.business_id == business.id).all()
            existing_aliases = {lt.alias for lt in existing_leave_types}
            
            created_count = 0
            updated_count = 0
            
            for leave_type_data in leave_types_data:
                alias = leave_type_data["alias"]
                
                # Check if leave type with this alias already exists
                existing_leave_type = next((lt for lt in existing_leave_types if lt.alias == alias), None)
                
                if existing_leave_type:
                    # Update existing leave type
                    for key, value in leave_type_data.items():
                        setattr(existing_leave_type, key, value)
                    updated_count += 1
                else:
                    # Create new leave type
                    leave_type = LeaveType(
                        business_id=business.id,
                        **leave_type_data
                    )
                    db.add(leave_type)
                    created_count += 1
            
            db.commit()
            
            logger.info(f"[OK] Created {created_count} new leave types, updated {updated_count} existing leave types")
            return True
    
    except Exception as e:
        logger.error(f"Error creating leave types sample data: {e}")
        return False


def create_leave_policies_sample_data():
    """Create comprehensive leave policies sample data for testing"""
    logger.info("\nStep 31.4: Creating leave policies sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.leave_policy import LeavePolicy
            from app.models.business import Business
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Define comprehensive leave policies
            leave_policies_data = [
                {
                    "leave_type": "Annual Leave",
                    "policy_name": "Annual Leave Policy",
                    "description": "Annual leave entitlement for all employees with monthly accrual",
                    "grant_enabled": True,
                    "grant_condition": 20,  # Minimum 20 days present
                    "monthly_grant_leaves": [2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0],  # 2 days per month
                    "reset_negative_balance": True,
                    "lapse_enabled": True,
                    "monthly_lapse_limits": [30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0],  # Max 30 days
                    "do_not_apply_during_probation": False,
                    "do_not_apply_after_probation": False,
                    "auto_apply": True
                },
                {
                    "leave_type": "Casual Leave",
                    "policy_name": "Casual Leave Policy",
                    "description": "Casual leave for personal work and emergencies",
                    "grant_enabled": True,
                    "grant_condition": 15,  # Minimum 15 days present
                    "monthly_grant_leaves": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],  # 1 day per month
                    "reset_negative_balance": False,
                    "lapse_enabled": True,
                    "monthly_lapse_limits": [12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0],  # Max 12 days
                    "do_not_apply_during_probation": False,
                    "do_not_apply_after_probation": False,
                    "auto_apply": True
                },
                {
                    "leave_type": "Sick Leave",
                    "policy_name": "Sick Leave Policy",
                    "description": "Medical leave for illness and health issues",
                    "grant_enabled": True,
                    "grant_condition": 10,  # Minimum 10 days present
                    "monthly_grant_leaves": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],  # 1 day per month
                    "reset_negative_balance": False,
                    "lapse_enabled": False,
                    "monthly_lapse_limits": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # No lapse
                    "do_not_apply_during_probation": False,
                    "do_not_apply_after_probation": False,
                    "auto_apply": True
                },
                {
                    "leave_type": "Maternity Leave",
                    "policy_name": "Maternity Leave Policy",
                    "description": "Maternity leave as per statutory requirements",
                    "grant_enabled": False,  # Manual grant
                    "grant_condition": 0,
                    "monthly_grant_leaves": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                    "reset_negative_balance": False,
                    "lapse_enabled": False,
                    "monthly_lapse_limits": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                    "do_not_apply_during_probation": True,
                    "do_not_apply_after_probation": False,
                    "auto_apply": False
                },
                {
                    "leave_type": "Compensatory Off",
                    "policy_name": "Compensatory Off Policy",
                    "description": "Compensatory leave for overtime and holiday work",
                    "grant_enabled": False,  # Manual grant based on overtime
                    "grant_condition": 0,
                    "monthly_grant_leaves": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                    "reset_negative_balance": False,
                    "lapse_enabled": True,
                    "monthly_lapse_limits": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0],  # Max 10 days
                    "do_not_apply_during_probation": False,
                    "do_not_apply_after_probation": False,
                    "auto_apply": False
                }
            ]
            
            # Get existing leave policies
            existing_leave_policies = db.query(LeavePolicy).filter(LeavePolicy.business_id == business.id).all()
            existing_types = {lp.leave_type for lp in existing_leave_policies}
            
            created_count = 0
            updated_count = 0
            
            for policy_data in leave_policies_data:
                leave_type = policy_data["leave_type"]
                
                # Check if leave policy with this type already exists
                existing_policy = next((lp for lp in existing_leave_policies if lp.leave_type == leave_type), None)
                
                if existing_policy:
                    # Update existing leave policy
                    for key, value in policy_data.items():
                        setattr(existing_policy, key, value)
                    updated_count += 1
                else:
                    # Create new leave policy
                    leave_policy = LeavePolicy(
                        business_id=business.id,
                        **policy_data
                    )
                    db.add(leave_policy)
                    created_count += 1
            
            db.commit()
            
            logger.info(f"[OK] Created {created_count} new leave policies, updated {updated_count} existing leave policies")
            return True
    
    except Exception as e:
        logger.error(f"Error creating leave policies sample data: {e}")
        return False


def create_compoff_rules_sample_data():
    """Create comprehensive comp off rules sample data for testing"""
    logger.info("\nStep 31.5: Creating comp off rules sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.compoff_rule import CompOffRule
            from app.models.business import Business
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if comp off rules already exist
            existing_rules = db.query(CompOffRule).filter(CompOffRule.business_id == business.id).all()
            if existing_rules:
                logger.info("Comp off rules sample data already exists, skipping...")
                return True
            
            # Define comp off rules
            compoff_rules_data = [
                {
                    "name": "Weekly Comp Off",
                    "rule_type": "weekly_offs",
                    "auto_grant_enabled": True,
                    "half_day_hours": 4,
                    "half_day_mins": 0,
                    "full_day_hours": 8,
                    "full_day_mins": 0,
                    "grant_type": "grant_comp_off",
                    "max_days": 0,
                    "expiry_days": 0,
                    "is_active": True
                },
                {
                    "name": "Holiday Comp Off",
                    "rule_type": "holidays",
                    "auto_grant_enabled": True,
                    "half_day_hours": 4,
                    "half_day_mins": 30,
                    "full_day_hours": 9,
                    "full_day_mins": 0,
                    "grant_type": "grant_comp_off",
                    "max_days": 0,
                    "expiry_days": 0,
                    "is_active": True
                }
            ]
            
            # Create comp off rules
            for rule_data in compoff_rules_data:
                compoff_rule = CompOffRule(
                    business_id=business.id,
                    **rule_data
                )
                db.add(compoff_rule)
            
            db.commit()
            
            logger.info(f"[OK] Created {len(compoff_rules_data)} comp off rules")
            for rule in compoff_rules_data:
                logger.info(f"  - {rule['name']}: auto_grant={rule['auto_grant_enabled']}, half_day={rule['half_day_hours']}h {rule['half_day_mins']}m, full_day={rule['full_day_hours']}h {rule['full_day_mins']}m")
            
            return True
    
    except Exception as e:
        logger.error(f"Error creating comp off rules sample data: {e}")
        return False


def create_esi_settings_sample_data():
    """Create ESI settings sample data for testing"""
    logger.info("\nStep 31.6: Creating ESI settings sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.esi_settings import ESISettings, ESIComponentMapping, ESIRateChange
            from app.models.business import Business
            from datetime import date
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Check if ESI settings already exist
            existing_settings = db.query(ESISettings).filter(ESISettings.business_id == business.id).first()
            if existing_settings:
                logger.info("ESI settings sample data already exists, skipping...")
                return True
            
            # Create ESI settings
            esi_settings = ESISettings(
                business_id=business.id,
                is_enabled=True,
                calculation_base="Gross Salary"
            )
            db.add(esi_settings)
            db.flush()
            
            # Create component mappings
            components_data = [
                {"component_name": "Basic Salary - Basic", "component_code": "BASIC", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "House Rent Allowance - HRA", "component_code": "HRA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Special Allowance - SA", "component_code": "SA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Medical Allowance - MDA", "component_code": "MDA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Leave Encashment - Leave", "component_code": "LEAVE", "component_type": "Variable", "is_selected": False},
                {"component_name": "Bonus - Bonus", "component_code": "BONUS", "component_type": "Variable", "is_selected": False},
                {"component_name": "Conveyance Allowance - CA", "component_code": "CA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Telephone Allowance - TA", "component_code": "TA", "component_type": "Paid Days", "is_selected": False},
                {"component_name": "Gratuity - Graty", "component_code": "GRATY", "component_type": "Variable", "is_selected": False},
                {"component_name": "Loan - Loan", "component_code": "LOAN", "component_type": "System", "is_selected": False},
                {"component_name": "Overtime (Hours) - OT", "component_code": "OT", "component_type": "System", "is_selected": False},
                {"component_name": "Overtime (Days) - OTD", "component_code": "OTD", "component_type": "System", "is_selected": False},
                {"component_name": "Retention Bonus - RTB", "component_code": "RTB", "component_type": "System", "is_selected": False},
            ]
            
            for comp_data in components_data:
                component = ESIComponentMapping(
                    esi_settings_id=esi_settings.id,
                    **comp_data
                )
                db.add(component)
            
            # Create sample rate change
            rate_change = ESIRateChange(
                esi_settings_id=esi_settings.id,
                status="Disabled",
                effective_from=date(2019, 7, 1),
                employee_rate=0.75,
                employer_rate=3.25,
                wage_limit=21000
            )
            db.add(rate_change)
            
            db.commit()
            
            logger.info(f"[OK] ESI settings created successfully")
            logger.info(f"  - Components: {len(components_data)}")
            logger.info(f"  - Rate changes: 1")
            return True
            
    except Exception as e:
        logger.error(f"Error creating ESI settings sample data: {e}")
        return False


def create_reports_sample_data():
    """Create comprehensive sample reports data for testing"""
    logger.info("\nStep 30: Creating reports sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.reports import (
                AIReportQuery, ReportTemplate, GeneratedReport, SalaryReport,
                AttendanceReport, EmployeeReport, StatutoryReport, AnnualReport,
                ActivityLog, UserFeedback, SystemAlert
            )
            from app.models.user import User
            from app.models.employee import Employee
            from app.models.business import Business
            from datetime import datetime, date, timedelta
            from decimal import Decimal
            import json
            import random
            
            # Get existing users and employees
            users = db.query(User).all()
            employees = db.query(Employee).all()
            
            # Get business first (needed throughout the function)
            business = db.query(Business).first()
            if not business:
                logger.error("No business found for reports data creation")
                return False
            
            # Get superadmin user (needed for created_by fields)
            superadmin = db.query(User).filter(User.email == "superadmin@levitica.com").first()
            if not superadmin:
                superadmin = users[0] if users else None
            
            if not users:
                logger.warning("No users found, skipping reports sample data")
                return True
            
            if not employees:
                logger.warning("No employees found, creating minimal employee data")
                # Create a basic employee for testing
                from app.models.employee import Employee
                
                test_employee = Employee(
                    business_id=business.id,
                    first_name="Test",
                    last_name="Employee",
                    email="test.employee@company.com",
                    mobile="9876543210",
                    employee_code="EMP001",
                    date_of_joining=date.today() - timedelta(days=365),
                    employee_status="ACTIVE"
                )
                db.add(test_employee)
                db.commit()
                employees = [test_employee]
            
            user = users[0]  # Use first user
            
            # 1. Create AI Report Queries
            ai_queries_data = [
                {
                    "query_text": "Show me list of employees who joined this year",
                    "response_data": {
                        "query_type": "employee_joining",
                        "result": {
                            "total_employees": 45,
                            "joined_this_year": 12,
                            "recent_joinings": [
                                {"name": "John Doe", "join_date": "2024-01-15", "department": "IT"},
                                {"name": "Jane Smith", "join_date": "2024-02-01", "department": "HR"},
                                {"name": "Mike Johnson", "join_date": "2024-02-15", "department": "Finance"}
                            ]
                        },
                        "visualization": "table",
                        "export_available": True
                    },
                    "status": "completed",
                    "processed_at": datetime.utcnow() - timedelta(minutes=5)
                },
                {
                    "query_text": "What is the average salary by department?",
                    "response_data": {
                        "query_type": "salary_analysis",
                        "result": {
                            "average_salary": 75000,
                            "total_payroll": 3375000,
                            "salary_distribution": {
                                "IT": 85000,
                                "HR": 65000,
                                "Finance": 78000,
                                "Operations": 62000
                            }
                        },
                        "visualization": "chart",
                        "export_available": True
                    },
                    "status": "completed",
                    "processed_at": datetime.utcnow() - timedelta(hours=2)
                },
                {
                    "query_text": "Show attendance trends for last month",
                    "response_data": {
                        "query_type": "attendance_analysis",
                        "result": {
                            "overall_attendance": 92.5,
                            "present_today": 42,
                            "absent_today": 3,
                            "monthly_trend": [88, 90, 92, 94, 92]
                        },
                        "visualization": "chart",
                        "export_available": True
                    },
                    "status": "completed",
                    "processed_at": datetime.utcnow() - timedelta(hours=1)
                }
            ]
            
            created_ai_queries = []
            for query_data in ai_queries_data:
                ai_query = AIReportQuery(
                    user_id=user.id,
                    **query_data
                )
                db.add(ai_query)
                created_ai_queries.append(ai_query)
            
            # 2. Create Report Templates
            report_templates_data = [
                {
                    "name": "Monthly Salary Summary",
                    "category": "salary",
                    "description": "Monthly salary summary with department breakdown",
                    "template_config": {
                        "fields": ["employee_name", "department", "basic_salary", "gross_salary", "net_salary"],
                        "filters": ["department", "location", "date_range"],
                        "grouping": "department",
                        "format": "excel"
                    }
                },
                {
                    "name": "Attendance Register",
                    "category": "attendance",
                    "description": "Daily attendance register with punch details",
                    "template_config": {
                        "fields": ["employee_name", "date", "check_in", "check_out", "total_hours", "status"],
                        "filters": ["date_range", "department", "status"],
                        "grouping": "date",
                        "format": "pdf"
                    }
                },
                {
                    "name": "Employee Master Report",
                    "category": "employee",
                    "description": "Complete employee master data report",
                    "template_config": {
                        "fields": ["employee_code", "name", "department", "designation", "joining_date", "status"],
                        "filters": ["department", "status", "joining_date"],
                        "grouping": "department",
                        "format": "excel"
                    }
                }
            ]
            
            created_templates = []
            for template_data in report_templates_data:
                template = ReportTemplate(**template_data)
                db.add(template)
                created_templates.append(template)
            
            # 3. Create Generated Reports
            generated_reports_data = [
                {
                    "report_name": "December 2024 Salary Summary",
                    "report_type": "salary_summary",
                    "parameters": {"period": "2024-12", "department": "all"},
                    "file_path": "/reports/salary_summary_202412.xlsx",
                    "status": "completed",
                    "completed_at": datetime.utcnow() - timedelta(days=1)
                },
                {
                    "report_name": "November Attendance Register",
                    "report_type": "attendance_register",
                    "parameters": {"start_date": "2024-11-01", "end_date": "2024-11-30"},
                    "file_path": "/reports/attendance_register_202411.pdf",
                    "status": "completed",
                    "completed_at": datetime.utcnow() - timedelta(days=5)
                },
                {
                    "report_name": "Employee Master Data Export",
                    "report_type": "employee_master",
                    "parameters": {"status": "active", "format": "excel"},
                    "file_path": "/reports/employee_master_20241215.xlsx",
                    "status": "completed",
                    "completed_at": datetime.utcnow() - timedelta(hours=3)
                }
            ]
            
            created_generated_reports = []
            for report_data in generated_reports_data:
                generated_report = GeneratedReport(
                    user_id=user.id,
                    template_id=created_templates[0].id if created_templates else None,
                    **report_data
                )
                db.add(generated_report)
                created_generated_reports.append(generated_report)
            
            # Ensure we have proper master data for salary summary
            from app.models.department import Department
            from app.models.designations import Designation
            from app.models.location import Location
            from app.models.grades import Grade
            
            # Create/get departments
            dept_data = [
                {"name": "OD Team", "head": "John Manager"},
                {"name": "Product Development Team", "head": "Sarah Tech Lead"},
                {"name": "Technical Support", "head": "Mike Support Head"},
                {"name": "HR Department", "head": "Lisa HR Head"},
                {"name": "Finance Department", "head": "David Finance Head"}
            ]
            departments = {}
            for dept_info in dept_data:
                # Check for existing department with business_id filter
                dept = db.query(Department).filter(
                    Department.name == dept_info["name"],
                    Department.business_id == business.id
                ).first()
                if not dept:
                    dept = Department(
                        name=dept_info["name"], 
                        head=dept_info["head"],
                        business_id=business.id, 
                        is_active=True,
                        created_by=superadmin.id,
                        updated_by=superadmin.id
                    )
                    db.add(dept)
                    db.commit()
                    db.refresh(dept)
                departments[dept_info["name"]] = dept
            
            # Create/get designations (cost centers)
            designation_data = [
                {"name": "Associate Software Engineer"},
                {"name": "HR Executive"},
                {"name": "Software Engineer"},
                {"name": "Senior Engineer"},
                {"name": "Manager"}
            ]
            designations = {}
            for desig_info in designation_data:
                # Check for existing designation globally (due to unique constraint on name)
                desig = db.query(Designation).filter(
                    Designation.name == desig_info["name"]
                ).first()
                if not desig:
                    desig = Designation(
                        name=desig_info["name"], 
                        business_id=business.id, 
                        created_by=superadmin.id,
                        updated_by=superadmin.id
                    )
                    db.add(desig)
                    db.commit()
                    db.refresh(desig)
                designations[desig_info["name"]] = desig
            
            # Create/get locations
            location_data = [
                {"name": "Hyderabad", "state": "Telangana"},
                {"name": "Bangalore", "state": "Karnataka"},
                {"name": "Mumbai", "state": "Maharashtra"}
            ]
            locations = {}
            for loc_info in location_data:
                # Check for existing location with business_id filter
                loc = db.query(Location).filter(
                    Location.name == loc_info["name"],
                    Location.business_id == business.id
                ).first()
                if not loc:
                    loc = Location(
                        name=loc_info["name"], 
                        state=loc_info["state"],
                        business_id=business.id, 
                        is_active=True,
                        created_by=superadmin.id,
                        updated_by=superadmin.id
                    )
                    db.add(loc)
                    db.commit()
                    db.refresh(loc)
                locations[loc_info["name"]] = loc
            
            # Create/get grades
            grade_data = [
                {"name": "Associate"},
                {"name": "Engineer"},
                {"name": "Senior Engineer"},
                {"name": "Manager"},
                {"name": "Executive"},
                {"name": "Default Grade"},
                {"name": "Supervisor"},
                {"name": "Testing Engineer"},
                {"name": "Trainee"}
            ]
            grades = {}
            for grade_info in grade_data:
                # Check for existing grade globally (due to unique constraint on name)
                grade = db.query(Grade).filter(
                    Grade.name == grade_info["name"]
                ).first()
                if not grade:
                    grade = Grade(
                        name=grade_info["name"], 
                        business_id=business.id,
                        created_by=superadmin.id,
                        updated_by=superadmin.id
                    )
                    db.add(grade)
                    db.commit()
                    db.refresh(grade)
                grades[grade_info["name"]] = grade
            
            # Update existing employees with proper relationships
            for i, employee in enumerate(employees[:10]):
                if not employee.department_id:
                    dept_name = random.choice(list(departments.keys()))
                    employee.department_id = departments[dept_name].id
                
                if not employee.designation_id:
                    desig_name = random.choice(list(designations.keys()))
                    employee.designation_id = designations[desig_name].id
                
                if not employee.location_id:
                    loc_name = random.choice(list(locations.keys()))
                    employee.location_id = locations[loc_name].id
                
                if not employee.grade_id:
                    grade_name = random.choice(list(grades.keys()))
                    employee.grade_id = grades[grade_name].id
            
            db.commit()
            
            # 4. Create Salary Reports
            salary_reports_data = []
            for i, employee in enumerate(employees[:10]):  # Create for first 10 employees
                for month_offset in range(3):  # Last 3 months
                    report_date = date.today().replace(day=1) - timedelta(days=month_offset * 30)
                    period = report_date.strftime('%Y-%m')
                    
                    # Check if salary report already exists for this employee and period
                    existing_report = db.query(SalaryReport).filter(
                        SalaryReport.employee_id == employee.id,
                        SalaryReport.report_period == period
                    ).first()
                    
                    if existing_report:
                        continue  # Skip if already exists
                    
                    basic_salary = Decimal(random.randint(30000, 80000))
                    allowances = basic_salary * Decimal('0.4')  # 40% allowances
                    gross_salary = basic_salary + allowances
                    deductions = gross_salary * Decimal('0.15')  # 15% deductions
                    net_salary = gross_salary - deductions
                    
                    salary_reports_data.append({
                        "employee_id": employee.id,
                        "report_period": period,
                        "basic_salary": basic_salary,
                        "gross_salary": gross_salary,
                        "net_salary": net_salary,
                        "total_deductions": deductions,
                        "overtime_amount": Decimal(random.randint(0, 5000)),
                        "bonus_amount": Decimal(random.randint(0, 10000)),
                        "allowances": {
                            "hra": float(basic_salary * Decimal('0.2')),
                            "transport": 2000,
                            "medical": 1500
                        },
                        "deductions": {
                            "pf": float(basic_salary * Decimal('0.12')),
                            "esi": float(gross_salary * Decimal('0.0175')),
                            "tax": float(gross_salary * Decimal('0.05'))
                        },
                        "ncp_days": 0,
                        "working_days": 30,
                        "created_at": datetime.now()
                    })
            
            created_salary_reports = []
            for salary_data in salary_reports_data:
                salary_report = SalaryReport(**salary_data)
                db.add(salary_report)
                created_salary_reports.append(salary_report)
            
            # 5. Create Attendance Reports
            attendance_reports_data = []
            for employee in employees[:10]:  # First 10 employees
                for day_offset in range(30):  # Last 30 days
                    report_date = date.today() - timedelta(days=day_offset)
                    
                    # Skip weekends for some variety
                    if report_date.weekday() >= 5 and random.random() < 0.7:
                        continue
                    
                    status = random.choices(
                        ["present", "absent", "half_day", "leave"],
                        weights=[80, 5, 10, 5]
                    )[0]
                    
                    if status == "present":
                        check_in = datetime.combine(report_date, datetime.min.time().replace(hour=9, minute=random.randint(0, 30)))
                        check_out = datetime.combine(report_date, datetime.min.time().replace(hour=18, minute=random.randint(0, 30)))
                        total_hours = Decimal((check_out - check_in).seconds / 3600)
                        overtime_hours = max(Decimal('0'), total_hours - Decimal('8'))
                    else:
                        check_in = None
                        check_out = None
                        total_hours = Decimal('0')
                        overtime_hours = Decimal('0')
                    
                    attendance_reports_data.append({
                        "employee_id": employee.id,
                        "report_date": report_date,
                        "check_in_time": check_in,
                        "check_out_time": check_out,
                        "total_hours": total_hours,
                        "overtime_hours": overtime_hours,
                        "status": status,
                        "location": random.choice(["Office", "Remote", "Client Site"]),
                        "is_remote": random.choice([True, False])
                    })
            
            created_attendance_reports = []
            for attendance_data in attendance_reports_data:
                attendance_report = AttendanceReport(**attendance_data)
                db.add(attendance_report)
                created_attendance_reports.append(attendance_report)
            
            # 6. Create Employee Reports
            employee_reports_data = []
            for employee in employees:  # All employees
                # Joining report
                employee_reports_data.append({
                    "employee_id": employee.id,
                    "report_type": "joining",
                    "report_data": {
                        "joining_date": employee.date_of_joining.isoformat() if employee.date_of_joining else None,
                        "department": "IT",
                        "designation": "Software Engineer",
                        "reporting_manager": "John Manager",
                        "probation_period": 6
                    },
                    "effective_date": employee.date_of_joining,
                    "status": "active"
                })
                
                # Create promotion reports for all employees with different dates
                if employee.date_of_joining:
                    # First promotion (1-2 years after joining)
                    first_promotion_days = random.randint(365, 730)  # 1-2 years
                    first_promotion_date = employee.date_of_joining + timedelta(days=first_promotion_days)
                    
                    if first_promotion_date <= date.today():
                        employee_reports_data.append({
                            "employee_id": employee.id,
                            "report_type": "promotion",
                            "report_data": {
                                "previous_designation": "Junior Software Engineer",
                                "new_designation": "Software Engineer",
                                "salary_increase": 15000,
                                "effective_date": first_promotion_date.isoformat()
                            },
                            "effective_date": first_promotion_date,
                            "status": "active"
                        })
                    
                    # Second promotion (2-4 years after first promotion)
                    if random.random() < 0.7:  # 70% chance of second promotion
                        second_promotion_days = random.randint(730, 1460)  # 2-4 years after first
                        second_promotion_date = first_promotion_date + timedelta(days=second_promotion_days)
                        
                        if second_promotion_date <= date.today():
                            employee_reports_data.append({
                                "employee_id": employee.id,
                                "report_type": "promotion",
                                "report_data": {
                                    "previous_designation": "Software Engineer",
                                    "new_designation": "Senior Software Engineer",
                                    "salary_increase": 20000,
                                    "effective_date": second_promotion_date.isoformat()
                                },
                                "effective_date": second_promotion_date,
                                "status": "active"
                            })
                    
                    # Third promotion (3-5 years after second promotion)
                    if random.random() < 0.4:  # 40% chance of third promotion
                        third_promotion_days = random.randint(1095, 1825)  # 3-5 years after second
                        third_promotion_date = second_promotion_date + timedelta(days=third_promotion_days) if 'second_promotion_date' in locals() else first_promotion_date + timedelta(days=third_promotion_days)
                        
                        if third_promotion_date <= date.today():
                            employee_reports_data.append({
                                "employee_id": employee.id,
                                "report_type": "promotion",
                                "report_data": {
                                    "previous_designation": "Senior Software Engineer",
                                    "new_designation": "Team Lead",
                                    "salary_increase": 25000,
                                    "effective_date": third_promotion_date.isoformat()
                                },
                                "effective_date": third_promotion_date,
                                "status": "active"
                            })
                
                # Create increment reports for all employees with different dates
                if employee.date_of_joining:
                    # First increment (6 months to 1 year after joining)
                    first_increment_days = random.randint(180, 365)  # 6 months to 1 year
                    first_increment_date = employee.date_of_joining + timedelta(days=first_increment_days)
                    
                    if first_increment_date <= date.today():
                        employee_reports_data.append({
                            "employee_id": employee.id,
                            "report_type": "increment",
                            "report_data": {
                                "increment_type": "Annual Increment",
                                "increment_percentage": random.randint(8, 15),
                                "increment_amount": random.randint(3000, 8000),
                                "effective_date": first_increment_date.isoformat(),
                                "reason": "Annual performance increment"
                            },
                            "effective_date": first_increment_date,
                            "status": "active"
                        })
                    
                    # Second increment (1-2 years after first increment)
                    if random.random() < 0.8:  # 80% chance of second increment
                        second_increment_days = random.randint(365, 730)  # 1-2 years after first
                        second_increment_date = first_increment_date + timedelta(days=second_increment_days)
                        
                        if second_increment_date <= date.today():
                            employee_reports_data.append({
                                "employee_id": employee.id,
                                "report_type": "increment",
                                "report_data": {
                                    "increment_type": "Performance Increment",
                                    "increment_percentage": random.randint(10, 18),
                                    "increment_amount": random.randint(5000, 12000),
                                    "effective_date": second_increment_date.isoformat(),
                                    "reason": "Performance-based increment"
                                },
                                "effective_date": second_increment_date,
                                "status": "active"
                            })
                    
                    # Third increment (1-3 years after second increment)
                    if random.random() < 0.6:  # 60% chance of third increment
                        third_increment_days = random.randint(365, 1095)  # 1-3 years after second
                        third_increment_date = second_increment_date + timedelta(days=third_increment_days) if 'second_increment_date' in locals() else first_increment_date + timedelta(days=third_increment_days)
                        
                        if third_increment_date <= date.today():
                            employee_reports_data.append({
                                "employee_id": employee.id,
                                "report_type": "increment",
                                "report_data": {
                                    "increment_type": "Special Increment",
                                    "increment_percentage": random.randint(12, 20),
                                    "increment_amount": random.randint(8000, 15000),
                                    "effective_date": third_increment_date.isoformat(),
                                    "reason": "Special recognition increment"
                                },
                                "effective_date": third_increment_date,
                                "status": "active"
                            })
                    
                    # Fourth increment (1-2 years after third increment)
                    if random.random() < 0.4:  # 40% chance of fourth increment
                        fourth_increment_days = random.randint(365, 730)  # 1-2 years after third
                        fourth_increment_date = third_increment_date + timedelta(days=fourth_increment_days) if 'third_increment_date' in locals() else first_increment_date + timedelta(days=fourth_increment_days)
                        
                        if fourth_increment_date <= date.today():
                            employee_reports_data.append({
                                "employee_id": employee.id,
                                "report_type": "increment",
                                "report_data": {
                                    "increment_type": "Annual Increment",
                                    "increment_percentage": random.randint(15, 25),
                                    "increment_amount": random.randint(10000, 20000),
                                    "effective_date": fourth_increment_date.isoformat(),
                                    "reason": "Annual increment with market adjustment"
                                },
                                "effective_date": fourth_increment_date,
                                "status": "active"
                            })
            
            # Ensure some employees have no increments (for "Never" case testing)
            # Remove increment data for 20% of employees randomly
            employees_with_no_increments = random.sample(employees, min(len(employees) // 5, 3))
            for emp in employees_with_no_increments:
                employee_reports_data = [
                    report for report in employee_reports_data 
                    if not (report["employee_id"] == emp.id and report["report_type"] == "increment")
                ]
            
            created_employee_reports = []
            for emp_report_data in employee_reports_data:
                employee_report = EmployeeReport(**emp_report_data)
                db.add(employee_report)
                created_employee_reports.append(employee_report)
            
            # 7. Create Statutory Reports
            statutory_reports_data = []
            for employee in employees[:8]:  # First 8 employees
                for month_offset in range(3):  # Last 3 months
                    report_date = date.today().replace(day=1) - timedelta(days=month_offset * 30)
                    period = report_date.strftime('%Y-%m')
                    
                    # ESI Report
                    gross_salary = Decimal(random.randint(40000, 90000))
                    esi_employee = gross_salary * Decimal('0.0175')
                    esi_employer = gross_salary * Decimal('0.0325')
                    
                    statutory_reports_data.append({
                        "employee_id": employee.id,
                        "report_period": period,
                        "report_type": "esi",
                        "employee_contribution": esi_employee,
                        "employer_contribution": esi_employer,
                        "total_contribution": esi_employee + esi_employer,
                        "statutory_data": {
                            "gross_salary": float(gross_salary),
                            "esi_rate_employee": 1.75,
                            "esi_rate_employer": 3.25
                        }
                    })
                    
                    # PF Report
                    basic_salary = gross_salary * Decimal('0.6')
                    pf_employee = basic_salary * Decimal('0.12')
                    pf_employer = basic_salary * Decimal('0.12')
                    
                    statutory_reports_data.append({
                        "employee_id": employee.id,
                        "report_period": period,
                        "report_type": "pf",
                        "employee_contribution": pf_employee,
                        "employer_contribution": pf_employer,
                        "total_contribution": pf_employee + pf_employer,
                        "statutory_data": {
                            "basic_salary": float(basic_salary),
                            "pf_rate": 12.0
                        }
                    })
            
            created_statutory_reports = []
            for statutory_data in statutory_reports_data:
                statutory_report = StatutoryReport(**statutory_data)
                db.add(statutory_report)
                created_statutory_reports.append(statutory_report)
            
            # 8. Create Annual Reports
            annual_reports_data = []
            for employee in employees[:5]:  # First 5 employees
                # Annual salary report
                annual_reports_data.append({
                    "employee_id": employee.id,
                    "report_year": 2024,
                    "report_type": "salary",
                    "annual_data": {
                        "total_gross": 720000,
                        "total_net": 612000,
                        "total_deductions": 108000,
                        "monthly_breakdown": [
                            {"month": "Jan", "gross": 60000, "net": 51000},
                            {"month": "Feb", "gross": 60000, "net": 51000},
                            {"month": "Mar", "gross": 60000, "net": 51000}
                        ]
                    },
                    "total_amount": Decimal('612000'),
                    "total_days": 365
                })
                
                # Annual attendance report
                annual_reports_data.append({
                    "employee_id": employee.id,
                    "report_year": 2024,
                    "report_type": "attendance",
                    "annual_data": {
                        "total_working_days": 250,
                        "present_days": 235,
                        "absent_days": 5,
                        "leave_days": 10,
                        "attendance_percentage": 94.0
                    },
                    "total_amount": Decimal('0'),
                    "total_days": 235
                })
            
            created_annual_reports = []
            for annual_data in annual_reports_data:
                annual_report = AnnualReport(**annual_data)
                db.add(annual_report)
                created_annual_reports.append(annual_report)
            
            # 9. Create Activity Logs
            activity_logs_data = [
                {
                    "action": "Onboarding Form Approved",
                    "module": "Onboarding",
                    "details": {
                        "form_id": "1744",
                        "candidate_name": "Mohammad Aslam",
                        "approved_by": user.name
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                {
                    "action": "Onboarding Form Deleted",
                    "module": "Onboarding",
                    "details": {
                        "form_id": "1743",
                        "deleted_by": user.name
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                {
                    "action": "Payroll Period Modified",
                    "module": "Payroll",
                    "details": {
                        "period": "JUL-2025",
                        "modified_by": user.name
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                {
                    "action": "Reporting Period Allowed",
                    "module": "Payroll",
                    "details": {
                        "period": "JUL-2025",
                        "allowed_by": user.name
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                {
                    "action": "Attendance Manually Updated",
                    "module": "Attendance",
                    "details": {
                        "employee_name": "Syed Afran Ali",
                        "employee_code": "LEV074",
                        "date": "2025-07-15",
                        "status": "Present",
                        "updated_by": user.name,
                        "timestamp": "Aug 02,2025 18:21:15"
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                {
                    "action": "Attendance Manually Updated",
                    "module": "Attendance",
                    "details": {
                        "employee_name": "Sasi Kumar Reddy Chintala",
                        "employee_code": "LEV099",
                        "date": "2025-07-15",
                        "status": "Present",
                        "updated_by": user.name,
                        "timestamp": "Aug 02,2025 18:21:02"
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                {
                    "action": "Leave Request Approved",
                    "module": "Leave Management",
                    "details": {
                        "employee_name": "John Doe",
                        "leave_type": "Annual Leave",
                        "approved_by": user.name
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                {
                    "action": "Salary Processed",
                    "module": "Payroll",
                    "details": {
                        "period": "JUL-2025",
                        "processed_by": user.name
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                {
                    "action": "Document Uploaded",
                    "module": "Document Management",
                    "details": {
                        "document_name": "Employment Contract",
                        "employee_name": "Jane Smith",
                        "uploaded_by": user.name
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                {
                    "action": "Policy Updated",
                    "module": "HR Policies",
                    "details": {
                        "policy_name": "Leave Policy",
                        "updated_by": user.name
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                {
                    "action": "User Access Granted",
                    "module": "User Management",
                    "details": {
                        "target_user": "Mike Johnson",
                        "granted_by": user.name
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                {
                    "action": "Employee Profile Updated",
                    "module": "Employee Management",
                    "details": {
                        "employee_name": "Sarah Wilson",
                        "updated_by": user.name
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            ]
            
            created_activity_logs = []
            for log_data in activity_logs_data:
                activity_log = ActivityLog(
                    user_id=user.id,
                    **log_data
                )
                db.add(activity_log)
                created_activity_logs.append(activity_log)
            
            # 10. Create User Feedback
            feedback_data = [
                {
                    "feedback_type": "suggestion",
                    "subject": "Improve Report Export Speed",
                    "description": "The report export functionality is quite slow for large datasets. It would be great if this could be optimized to handle exports faster, especially for monthly payroll reports.",
                    "rating": 4,
                    "status": "open",
                    "created_at": datetime.utcnow() - timedelta(days=1)
                },
                {
                    "feedback_type": "bug",
                    "subject": "Chart Display Issue in Dashboard",
                    "description": "The attendance chart is not displaying correctly in the dashboard. The bars are overlapping and the legend is cut off on smaller screens.",
                    "rating": 2,
                    "status": "in_progress",
                    "created_at": datetime.utcnow() - timedelta(days=3)
                },
                {
                    "feedback_type": "feature_request",
                    "subject": "Add More Report Templates",
                    "description": "Please add more pre-built report templates for statutory compliance reports like ESI, PF, and TDS returns. This would save a lot of time.",
                    "rating": 5,
                    "status": "resolved",
                    "resolved_at": datetime.utcnow() - timedelta(days=2),
                    "created_at": datetime.utcnow() - timedelta(days=7)
                },
                {
                    "feedback_type": "suggestion",
                    "subject": "Mobile App for Employee Self-Service",
                    "description": "It would be great to have a mobile application where employees can view their payslips, apply for leaves, and check attendance records.",
                    "rating": 5,
                    "status": "open",
                    "created_at": datetime.utcnow() - timedelta(days=5)
                },
                {
                    "feedback_type": "bug",
                    "subject": "Salary Calculation Error",
                    "description": "There seems to be an issue with overtime calculation in the payroll module. The overtime hours are not being calculated correctly for night shift employees.",
                    "rating": 1,
                    "status": "resolved",
                    "resolved_at": datetime.utcnow() - timedelta(hours=6),
                    "created_at": datetime.utcnow() - timedelta(days=2)
                },
                {
                    "feedback_type": "feature_request",
                    "subject": "Bulk Employee Data Import",
                    "description": "Need a feature to import employee data in bulk from Excel files. Currently adding employees one by one is very time-consuming.",
                    "rating": 4,
                    "status": "in_progress",
                    "created_at": datetime.utcnow() - timedelta(days=4)
                },
                {
                    "feedback_type": "suggestion",
                    "subject": "Improve User Interface Design",
                    "description": "The current UI looks a bit outdated. Consider updating to a more modern design with better color schemes and typography.",
                    "rating": 3,
                    "status": "open",
                    "created_at": datetime.utcnow() - timedelta(days=6)
                },
                {
                    "feedback_type": "bug",
                    "subject": "Login Session Timeout Issue",
                    "description": "Users are getting logged out too frequently. The session timeout seems to be too short, causing inconvenience during long report generation tasks.",
                    "rating": 2,
                    "status": "closed",
                    "resolved_at": datetime.utcnow() - timedelta(days=1),
                    "created_at": datetime.utcnow() - timedelta(days=8)
                },
                {
                    "feedback_type": "feature_request",
                    "subject": "Advanced Search and Filters",
                    "description": "Add advanced search functionality with multiple filters for employee records, attendance data, and payroll information.",
                    "rating": 4,
                    "status": "open",
                    "created_at": datetime.utcnow() - timedelta(days=9)
                },
                {
                    "feedback_type": "suggestion",
                    "subject": "Email Notifications for Payslips",
                    "description": "Implement automatic email notifications to employees when their payslips are generated. This would improve communication and reduce manual work.",
                    "rating": 5,
                    "status": "resolved",
                    "resolved_at": datetime.utcnow() - timedelta(days=3),
                    "created_at": datetime.utcnow() - timedelta(days=10)
                },
                {
                    "feedback_type": "bug",
                    "subject": "Report Generation Memory Error",
                    "description": "Getting memory errors when generating large reports with more than 1000 employees. The system crashes and needs to be restarted.",
                    "rating": 1,
                    "status": "in_progress",
                    "created_at": datetime.utcnow() - timedelta(days=11)
                },
                {
                    "feedback_type": "feature_request",
                    "subject": "Integration with Biometric Devices",
                    "description": "Need integration with various biometric attendance devices to automatically sync attendance data without manual intervention.",
                    "rating": 5,
                    "status": "open",
                    "created_at": datetime.utcnow() - timedelta(days=12)
                }
            ]
            
            created_feedback = []
            for feedback_item in feedback_data:
                user_feedback = UserFeedback(
                    user_id=user.id,
                    **feedback_item
                )
                db.add(user_feedback)
                created_feedback.append(user_feedback)
            
            # 11. Create System Alerts
            alerts_data = [
                {
                    "alert_type": "info",
                    "title": "System Maintenance Scheduled",
                    "message": "System maintenance is scheduled for this weekend from 2 AM to 4 AM. Users may experience brief service interruptions during this time.",
                    "module": "System",
                    "is_resolved": False,
                    "created_at": datetime.utcnow() - timedelta(hours=2)
                },
                {
                    "alert_type": "warning",
                    "title": "High Report Generation Load",
                    "message": "The system is experiencing high load due to multiple report generations. Some reports may take longer to process than usual.",
                    "module": "Reports",
                    "is_resolved": False,
                    "created_at": datetime.utcnow() - timedelta(hours=4)
                },
                {
                    "alert_type": "error",
                    "title": "Database Connection Issue",
                    "message": "Temporary database connection issue resolved. All services are now operational and functioning normally.",
                    "module": "Database",
                    "is_resolved": True,
                    "resolved_at": datetime.utcnow() - timedelta(hours=1),
                    "resolved_by": user.id,
                    "created_at": datetime.utcnow() - timedelta(hours=6)
                },
                {
                    "alert_type": "critical",
                    "title": "Payroll Processing Failure",
                    "message": "Critical error in payroll processing for JUL-2025. Multiple employee salary calculations failed. Immediate attention required.",
                    "module": "Payroll",
                    "is_resolved": True,
                    "resolved_at": datetime.utcnow() - timedelta(hours=3),
                    "resolved_by": user.id,
                    "created_at": datetime.utcnow() - timedelta(hours=8)
                },
                {
                    "alert_type": "warning",
                    "title": "High Absence Rate Detected",
                    "message": "Employee LEV074 has exceeded 5 consecutive absences. HR intervention may be required to address attendance issues.",
                    "module": "Attendance",
                    "is_resolved": False,
                    "created_at": datetime.utcnow() - timedelta(hours=12)
                },
                {
                    "alert_type": "info",
                    "title": "Backup Completed Successfully",
                    "message": "Daily database backup completed successfully at 3:00 AM. All data has been securely backed up to cloud storage.",
                    "module": "System",
                    "is_resolved": True,
                    "resolved_at": datetime.utcnow() - timedelta(hours=5),
                    "resolved_by": user.id,
                    "created_at": datetime.utcnow() - timedelta(hours=18)
                },
                {
                    "alert_type": "error",
                    "title": "Email Service Disruption",
                    "message": "Email notification service is experiencing intermittent failures. Some payslip notifications may not be delivered.",
                    "module": "Email",
                    "is_resolved": False,
                    "created_at": datetime.utcnow() - timedelta(hours=6)
                },
                {
                    "alert_type": "warning",
                    "title": "Storage Space Running Low",
                    "message": "Server storage space is at 85% capacity. Consider archiving old files or expanding storage to prevent service disruption.",
                    "module": "System",
                    "is_resolved": False,
                    "created_at": datetime.utcnow() - timedelta(days=1)
                },
                {
                    "alert_type": "critical",
                    "title": "Security Breach Attempt Detected",
                    "message": "Multiple failed login attempts detected from suspicious IP addresses. Security protocols have been activated.",
                    "module": "Security",
                    "is_resolved": True,
                    "resolved_at": datetime.utcnow() - timedelta(hours=2),
                    "resolved_by": user.id,
                    "created_at": datetime.utcnow() - timedelta(days=1, hours=2)
                },
                {
                    "alert_type": "info",
                    "title": "Software Update Available",
                    "message": "A new software update is available with security patches and performance improvements. Update recommended during next maintenance window.",
                    "module": "System",
                    "is_resolved": False,
                    "created_at": datetime.utcnow() - timedelta(days=2)
                },
                {
                    "alert_type": "warning",
                    "title": "Biometric Device Offline",
                    "message": "Biometric attendance device at Hyderabad office is offline. Employees may need to use manual attendance entry.",
                    "module": "Attendance",
                    "is_resolved": True,
                    "resolved_at": datetime.utcnow() - timedelta(hours=4),
                    "resolved_by": user.id,
                    "created_at": datetime.utcnow() - timedelta(days=2, hours=6)
                },
                {
                    "alert_type": "error",
                    "title": "Report Generation Timeout",
                    "message": "Large attendance reports are timing out during generation. System performance optimization may be required.",
                    "module": "Reports",
                    "is_resolved": False,
                    "created_at": datetime.utcnow() - timedelta(days=3)
                },
                {
                    "alert_type": "critical",
                    "title": "Data Synchronization Failure",
                    "message": "Critical failure in data synchronization between primary and backup servers. Data integrity check required immediately.",
                    "module": "Database",
                    "is_resolved": True,
                    "resolved_at": datetime.utcnow() - timedelta(days=1),
                    "resolved_by": user.id,
                    "created_at": datetime.utcnow() - timedelta(days=3, hours=8)
                },
                {
                    "alert_type": "info",
                    "title": "Monthly Report Generation Complete",
                    "message": "All monthly reports for JUL-2025 have been successfully generated and are available for download.",
                    "module": "Reports",
                    "is_resolved": True,
                    "resolved_at": datetime.utcnow() - timedelta(days=2),
                    "resolved_by": user.id,
                    "created_at": datetime.utcnow() - timedelta(days=4)
                },
                {
                    "alert_type": "warning",
                    "title": "License Expiration Warning",
                    "message": "Software license for HR management system will expire in 30 days. Renewal required to maintain service continuity.",
                    "module": "System",
                    "is_resolved": False,
                    "created_at": datetime.utcnow() - timedelta(days=5)
                }
            ]
            
            created_alerts = []
            for alert_data in alerts_data:
                system_alert = SystemAlert(**alert_data)
                db.add(system_alert)
                created_alerts.append(system_alert)
            
            # Commit all data
            db.commit()
            
            # Log statistics
            logger.info(f"[OK] Created {len(created_ai_queries)} AI report queries")
            logger.info(f"[OK] Created {len(created_templates)} report templates")
            logger.info(f"[OK] Created {len(created_generated_reports)} generated reports")
            logger.info(f"[OK] Created {len(created_salary_reports)} salary reports")
            logger.info(f"[OK] Created {len(created_attendance_reports)} attendance reports")
            logger.info(f"[OK] Created {len(created_employee_reports)} employee reports")
            logger.info(f"[OK] Created {len(created_statutory_reports)} statutory reports")
            logger.info(f"[OK] Created {len(created_annual_reports)} annual reports")
            logger.info(f"[OK] Created {len(created_activity_logs)} activity logs")
            logger.info(f"[OK] Created {len(created_feedback)} user feedback entries")
            logger.info(f"[OK] Created {len(created_alerts)} system alerts")
            
            total_records = (len(created_ai_queries) + len(created_templates) + 
                           len(created_generated_reports) + len(created_salary_reports) +
                           len(created_attendance_reports) + len(created_employee_reports) +
                           len(created_statutory_reports) + len(created_annual_reports) +
                           len(created_activity_logs) + len(created_feedback) + len(created_alerts))
            
            logger.info(f"[OK] Total reports sample data records created: {total_records}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create reports sample data: {e}")
        return False


def create_sap_mapping_sample_data():
    """Create sample SAP mapping configuration data"""
    logger.info("\nStep 35: Creating SAP mapping sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.business import Business
            from app.models.user import User
            
            # Get business and user
            business = db.query(Business).first()
            if not business:
                logger.error("No business found for SAP mapping")
                return False
            
            user = db.query(User).filter(User.email == settings.SUPERADMIN_EMAIL).first()
            if not user:
                logger.error("Superadmin user not found for SAP mapping")
                return False
            
            # Check if SAP mapping already exists
            existing_mapping = db.query(SAPMapping).filter(
                SAPMapping.business_id == business.id
            ).first()
            
            if existing_mapping:
                logger.info("SAP mapping configuration already exists")
                return True
            
            # Create comprehensive SAP mapping configuration
            sap_mapping_data = {
                "business_id": business.id,
                "doc_type": "JE",  # Journal Entry
                "series": "JE-",
                "bpl": "1",  # Business Place
                "currency": "INR",
                "location_code": "HYD001",
                
                # Basic Salary Mapping
                "basic_salary_acct": "5001001",  # Basic Salary Account
                "basic_salary_tax": "2001001",   # Basic Salary Tax Account
                
                # HRA Mapping
                "hra_acct": "5001002",  # HRA Account
                "hra_tax": "2001002",   # HRA Tax Account
                
                # Special Allowance Mapping
                "special_allowance_acct": "5001003",
                "special_allowance_tax": "2001003",
                
                # Medical Allowance Mapping
                "medical_allowance_acct": "5001004",
                "medical_allowance_tax": "2001004",
                
                # Conveyance Mapping
                "conveyance_acct": "5001005",
                "conveyance_tax": "2001005",
                
                # Telephone Mapping
                "telephone_acct": "5001006",
                "telephone_tax": "2001006",
                
                # Bonus Mapping
                "bonus_acct": "5001007",
                "bonus_tax": "2001007",
                
                # Gratuity Mapping
                "gratuity_acct": "5001008",
                "gratuity_tax": "2001008",
                
                # Leave Encashment Mapping (correct field name)
                "leave_encash_acct": "5001009",
                "leave_encash_tax": "2001009",
                
                # Loan Mapping
                "loan_acct": "5001010",
                "loan_tax": "2001010",
                
                # Overtime Mapping
                "overtime_hours_acct": "5001011",
                "overtime_hours_tax": "2001011",
                "overtime_days_acct": "5001012",
                "overtime_days_tax": "2001012",
                
                # Retention Bonus Mapping
                "retention_bonus_acct": "5001013",
                "retention_bonus_tax": "2001013",
                
                # Deduction Mappings
                "esi_acct": "2002001",  # ESI Payable
                "esi_tax": "2002001",   # ESI Tax
                "pf_acct": "2002002",   # PF Payable
                "pf_tax": "2002002",    # PF Tax
                "voluntary_pf_acct": "2002003",  # Voluntary PF
                "voluntary_pf_tax": "2002003",   # Voluntary PF Tax
                "professional_tax_acct": "2002004",  # Professional Tax
                "professional_tax_tax": "2002004",   # Professional Tax Tax
                "income_tax_acct": "2002005",  # TDS Payable
                "income_tax_tax": "2002005",   # TDS Tax
                "loan_repayment_acct": "2002006",  # Loan Recovery
                "loan_repayment_tax": "2002006",   # Loan Recovery Tax
                "loan_interest_acct": "2002007",   # Loan Interest
                "loan_interest_tax": "2002007",    # Loan Interest Tax
                "group_insurance_acct": "2002008", # Group Insurance
                "group_insurance_tax": "2002008",  # Group Insurance Tax
                "pf_extra_cont_acct": "2002009",  # PF Extra Contribution
                "pf_extra_cont_tax": "2002009",   # PF Extra Contribution Tax
                "labour_welfare_acct": "2002010",  # Labour Welfare
                "labour_welfare_tax": "2002010",   # Labour Welfare Tax
                "gratuity_ded_acct": "2002011",  # Gratuity Deduction
                "gratuity_ded_tax": "2002011"    # Gratuity Deduction Tax
            }
            
            # Create SAP mapping record
            sap_mapping = SAPMapping(**sap_mapping_data)
            db.add(sap_mapping)
            db.commit()
            db.refresh(sap_mapping)
            
            logger.info(f"[OK] Created SAP mapping configuration with ID: {sap_mapping.id}")
            logger.info(f"  - Document Type: {sap_mapping.doc_type}")
            logger.info(f"  - Series: {sap_mapping.series}")
            logger.info(f"  - Currency: {sap_mapping.currency}")
            logger.info(f"  - Location Code: {sap_mapping.location_code}")
            logger.info(f"  - Basic Salary Account: {sap_mapping.basic_salary_acct}")
            logger.info(f"  - Leave Encash Account: {sap_mapping.leave_encash_acct}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create SAP mapping sample data: {e}")
        return False


def create_api_access_sample_data():
    """Create sample API access configuration data."""
    logger.info("Creating API access sample data...")
    
    try:
        with get_db_context() as db:
            import secrets
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found for API access")
                return False
            
            # Check if API access already exists
            existing_access = db.query(APIAccess).filter(
                APIAccess.business_id == business.id
            ).first()
            
            if existing_access:
                logger.info("API access sample data already exists")
                return True
            
            # Create sample API access configuration
            api_access = APIAccess(
                business_id=business.id,
                is_enabled=True,
                api_key="API-" + secrets.token_urlsafe(16)
            )
            
            db.add(api_access)
            db.commit()
            db.refresh(api_access)
            
            logger.info("[OK] API access sample data created")
            logger.info(f"  - Business ID: {api_access.business_id}")
            logger.info(f"  - API Enabled: {api_access.is_enabled}")
            logger.info(f"  - API Key: {api_access.api_key[:10]}...")  # Show only first 10 chars for security
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create API access sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_attendance_register_sample_data():
    """Create comprehensive attendance register sample data"""
    logger.info("\nStep 36: Creating attendance register sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.attendance import AttendanceRecord, AttendanceStatus
            from app.models.employee import Employee
            from datetime import datetime, timedelta
            import random
            
            # Get business first
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get all employees
            employees = db.query(Employee).all()
            if not employees:
                logger.info("No employees found for attendance register sample data")
                return True
            
            # Check if attendance data already exists
            existing_attendance = db.query(AttendanceRecord).first()
            if existing_attendance:
                logger.info("Attendance register sample data already exists, skipping...")
                return True
            
            # Generate attendance data for the last 3 months
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=90)  # Last 3 months
            
            attendance_records = []
            current_date = start_date
            
            while current_date <= end_date:
                for employee in employees:
                    # Skip weekends for some variety
                    if current_date.weekday() in [5, 6]:  # Saturday, Sunday
                        # 80% chance of weekend
                        if random.random() < 0.8:
                            status = AttendanceStatus.WEEKEND
                        else:
                            status = AttendanceStatus.PRESENT  # Some employees work weekends
                    else:
                        # Weekday attendance
                        rand = random.random()
                        if rand < 0.85:  # 85% present
                            status = AttendanceStatus.PRESENT
                        elif rand < 0.92:  # 7% on leave
                            status = AttendanceStatus.ON_LEAVE
                        else:  # 8% absent
                            status = AttendanceStatus.ABSENT
                    
                    # Generate realistic times for present days
                    check_in_time = None
                    check_out_time = None
                    total_hours = 0
                    overtime_hours = 0
                    
                    if status == AttendanceStatus.PRESENT:
                        # Random check-in time between 8:00 and 10:00
                        check_in_hour = random.randint(8, 9)
                        check_in_minute = random.randint(0, 59)
                        check_in_time = datetime.combine(current_date, datetime.min.time().replace(
                            hour=check_in_hour, minute=check_in_minute
                        ))
                        
                        # Check-out time (8-10 hours later)
                        work_hours = random.uniform(8.0, 10.5)
                        check_out_time = check_in_time + timedelta(hours=work_hours)
                        
                        total_hours = work_hours
                        if work_hours > 9:
                            overtime_hours = work_hours - 9
                    
                    attendance_record = AttendanceRecord(
                        employee_id=employee.id,
                        business_id=business.id,
                        attendance_date=current_date,
                        attendance_status=status,
                        punch_in_time=check_in_time,
                        punch_out_time=check_out_time,
                        total_hours=total_hours,
                        overtime_hours=overtime_hours,
                        punch_in_location="Office",
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    
                    attendance_records.append(attendance_record)
                
                current_date += timedelta(days=1)
            
            # Bulk insert attendance records
            db.bulk_save_objects(attendance_records)
            db.commit()
            
            logger.info(f"[OK] Created {len(attendance_records)} attendance records")
            logger.info(f"  - Date range: {start_date} to {end_date}")
            logger.info(f"  - Employees: {len(employees)}")
            logger.info(f"  - Days covered: {(end_date - start_date).days + 1}")
            
            # Calculate and log statistics
            present_count = len([r for r in attendance_records if r.attendance_status == AttendanceStatus.PRESENT])
            absent_count = len([r for r in attendance_records if r.attendance_status == AttendanceStatus.ABSENT])
            leave_count = len([r for r in attendance_records if r.attendance_status == AttendanceStatus.ON_LEAVE])
            weekoff_count = len([r for r in attendance_records if r.attendance_status == AttendanceStatus.WEEKEND])
            
            logger.info(f"  - Present: {present_count}")
            logger.info(f"  - Absent: {absent_count}")
            logger.info(f"  - On Leave: {leave_count}")
            logger.info(f"  - Week Off: {weekoff_count}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create attendance register sample data: {e}")
        return False


def create_leave_register_sample_data():
    """Create comprehensive leave register sample data"""
    logger.info("\nStep 37: Creating leave register sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee
            from app.models.attendance import AttendanceRecord, AttendanceStatus
            from app.models.reports import SalaryReport
            from datetime import datetime, date
            from calendar import monthrange
            import random
            
            # Get all employees
            employees = db.query(Employee).all()
            if not employees:
                logger.info("No employees found for leave register sample data")
                return True
            
            # Check if we already have sufficient data
            existing_attendance = db.query(AttendanceRecord).count()
            existing_salary = db.query(SalaryReport).count()
            
            if existing_attendance > 1000 and existing_salary > 50:
                logger.info("Leave register sample data already exists, skipping...")
                return True
            
            # Generate data for 2025 (Jan to Dec)
            year = 2025
            
            # Ensure we have salary reports for each month
            for month in range(1, 13):
                period = f"{year}-{month:02d}"
                
                for employee in employees:
                    # Check if salary report exists
                    existing_salary = db.query(SalaryReport).filter(
                        SalaryReport.employee_id == employee.id,
                        SalaryReport.report_period == period
                    ).first()
                    
                    if not existing_salary:
                        # Create salary report
                        base_salary = random.uniform(15000, 25000)
                        gross_salary = base_salary * 1.2
                        deductions = gross_salary * 0.15
                        net_salary = gross_salary - deductions
                        
                        salary_report = SalaryReport(
                            employee_id=employee.id,
                            report_period=period,
                            basic_salary=Decimal(str(base_salary)),
                            gross_salary=Decimal(str(gross_salary)),
                            net_salary=Decimal(str(net_salary)),
                            total_deductions=Decimal(str(deductions)),
                            overtime_amount=Decimal('0'),
                            bonus_amount=Decimal('0'),
                            allowances={
                                "HRA": base_salary * 0.4,
                                "Special Allowance": base_salary * 0.2,
                                "Medical": 1250,
                                "Conveyance": 1600
                            },
                            deductions={
                                "PF": base_salary * 0.12,
                                "Professional Tax": 200,
                                "ESI": gross_salary * 0.0075 if gross_salary <= 21000 else 0
                            },
                            created_at=datetime.now()
                        )
                        db.add(salary_report)
            
            # Ensure we have attendance records for each month
            for month in range(1, 13):
                days_in_month = monthrange(year, month)[1]
                
                for day in range(1, days_in_month + 1):
                    current_date = date(year, month, day)
                    
                    for employee in employees:
                        # Check if attendance record exists
                        existing_attendance = db.query(AttendanceRecord).filter(
                            AttendanceRecord.employee_id == employee.id,
                            AttendanceRecord.attendance_date == current_date
                        ).first()
                        
                        if not existing_attendance:
                            # Determine attendance status
                            if current_date.weekday() in [5, 6]:  # Weekend
                                status = AttendanceStatus.WEEKEND
                            else:
                                # Weekday - random attendance pattern
                                rand = random.random()
                                if rand < 0.80:  # 80% present
                                    status = AttendanceStatus.PRESENT
                                elif rand < 0.90:  # 10% on leave
                                    status = AttendanceStatus.ON_LEAVE
                                else:  # 10% absent
                                    status = AttendanceStatus.ABSENT
                            
                            # Generate realistic times for present days
                            punch_in_time = None
                            punch_out_time = None
                            total_hours = 0
                            
                            if status == AttendanceStatus.PRESENT:
                                # Random check-in time between 8:00 and 10:00
                                check_in_hour = random.randint(8, 9)
                                check_in_minute = random.randint(0, 59)
                                punch_in_time = datetime.combine(current_date, datetime.min.time().replace(
                                    hour=check_in_hour, minute=check_in_minute
                                ))
                                
                                # Check-out time (8-9 hours later)
                                work_hours = random.uniform(8.0, 9.5)
                                punch_out_time = punch_in_time + timedelta(hours=work_hours)
                                total_hours = work_hours
                            
                            attendance_record = AttendanceRecord(
                                employee_id=employee.id,
                                business_id=employee.business_id,
                                attendance_date=current_date,
                                attendance_status=status,
                                punch_in_time=punch_in_time,
                                punch_out_time=punch_out_time,
                                total_hours=total_hours,
                                overtime_hours=max(0, total_hours - 9) if total_hours > 9 else 0,
                                punch_in_location="Office",
                                created_at=datetime.now(),
                                updated_at=datetime.now()
                            )
                            db.add(attendance_record)
            
            # Commit all changes
            db.commit()
            
            # Count records created
            total_attendance = db.query(AttendanceRecord).count()
            total_salary = db.query(SalaryReport).count()
            
            logger.info(f"[OK] Leave register sample data created successfully")
            logger.info(f"  - Total attendance records: {total_attendance}")
            logger.info(f"  - Total salary reports: {total_salary}")
            logger.info(f"  - Year covered: {year}")
            logger.info(f"  - Employees: {len(employees)}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create leave register sample data: {e}")
        return False


def create_time_register_sample_data():
    """Create sample time register data for testing"""
    logger.info("\nStep 30: Creating time register sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.reports import SalaryReport
            from app.models.attendance import AttendanceRecord, AttendanceStatus
            from app.models.datacapture import ExtraHour
            from app.models.employee import Employee
            from sqlalchemy import func
            from datetime import datetime, timedelta
            import random
            
            # Get all active employees
            employees = db.query(Employee).filter(Employee.employee_status == 'ACTIVE').all()
            
            if not employees:
                logger.warning("No active employees found for time register data")
                return True
            
            # Create time register data for NOV-2025 (the period shown in frontend)
            target_date = datetime(2025, 11, 1)
            year = target_date.year
            month = target_date.month
            
            # Get number of working days in November 2025
            from calendar import monthrange
            days_in_month = monthrange(year, month)[1]
            
            # Create attendance records with time punch data for time register
            for employee in employees:
                # Create attendance records for the month
                for day in range(1, days_in_month + 1):
                    current_date = datetime(year, month, day).date()
                    
                    # Skip weekends (Saturday=5, Sunday=6)
                    if current_date.weekday() >= 5:
                        continue
                    
                    # 90% attendance rate
                    if random.random() < 0.9:
                        # Create punch times with variations for time register calculations
                        base_punch_in = datetime.combine(current_date, datetime.min.time().replace(hour=9, minute=0))
                        base_punch_out = datetime.combine(current_date, datetime.min.time().replace(hour=18, minute=0))
                        
                        # Add random variations for early/late calculations
                        punch_in_variation = random.randint(-30, 60)  # -30 to +60 minutes
                        punch_out_variation = random.randint(-60, 120)  # -60 to +120 minutes
                        
                        actual_punch_in = base_punch_in + timedelta(minutes=punch_in_variation)
                        actual_punch_out = base_punch_out + timedelta(minutes=punch_out_variation)
                        
                        # Calculate total hours
                        total_hours = (actual_punch_out - actual_punch_in).total_seconds() / 3600
                        total_hours = max(0, total_hours - 1)  # Subtract 1 hour for lunch
                        
                        # Check if attendance record already exists
                        existing_record = db.query(AttendanceRecord).filter(
                            AttendanceRecord.employee_id == employee.id,
                            AttendanceRecord.attendance_date == current_date
                        ).first()
                        
                        if not existing_record:
                            attendance_record = AttendanceRecord(
                                employee_id=employee.id,
                                business_id=employee.business_id,
                                attendance_date=current_date,
                                attendance_status=AttendanceStatus.PRESENT,
                                punch_in_time=actual_punch_in,
                                punch_out_time=actual_punch_out,
                                total_hours=total_hours,
                                overtime_hours=max(0, total_hours - 8),
                                punch_in_location="Office",
                                punch_out_location="Office",
                                created_at=datetime.now(),
                                updated_at=datetime.now()
                            )
                            db.add(attendance_record)
                
                # Create some extra hours (overtime) records
                overtime_days = random.randint(2, 8)  # 2-8 overtime days per employee
                for _ in range(overtime_days):
                    overtime_date = datetime(year, month, random.randint(1, min(days_in_month, 25))).date()
                    
                    # Skip weekends
                    if overtime_date.weekday() >= 5:
                        continue
                    
                    # Check if extra hour record already exists
                    existing_extra = db.query(ExtraHour).filter(
                        ExtraHour.employee_id == employee.id,
                        ExtraHour.work_date == overtime_date
                    ).first()
                    
                    if not existing_extra:
                        overtime_hours = random.uniform(1.0, 4.0)  # 1-4 hours overtime
                        
                        extra_hour = ExtraHour(
                            employee_id=employee.id,
                            business_id=employee.business_id,
                            work_date=overtime_date,
                            regular_hours=8.0,
                            extra_hours=overtime_hours,
                            overtime_rate=150.0,  # Rate per hour
                            total_amount=overtime_hours * 150.0,
                            work_description=f"Overtime work on {overtime_date}",
                            is_approved=True,
                            approved_by=1,  # Superadmin
                            approval_date=overtime_date,
                            created_at=datetime.now(),
                            updated_at=datetime.now(),
                            created_by=1
                        )
                        db.add(extra_hour)
            
            # Commit all changes
            db.commit()
            
            # Count records created
            total_attendance = db.query(AttendanceRecord).filter(
                func.extract('year', AttendanceRecord.attendance_date) == year,
                func.extract('month', AttendanceRecord.attendance_date) == month
            ).count()
            
            total_overtime = db.query(ExtraHour).filter(
                func.extract('year', ExtraHour.work_date) == year,
                func.extract('month', ExtraHour.work_date) == month
            ).count()
            
            logger.info(f"[OK] Time register sample data created successfully")
            logger.info(f"  - Attendance records for NOV-2025: {total_attendance}")
            logger.info(f"  - Overtime records for NOV-2025: {total_overtime}")
            logger.info(f"  - Employees covered: {len(employees)}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create time register sample data: {e}")
        return False


def create_strike_register_sample_data():
    """Create sample strike register data for testing"""
    logger.info("\nStep 31: Creating strike register sample data...")
    
    try:
        with get_db_context() as db:
            from app.models.attendance import AttendanceRecord, AttendanceStatus
            from app.models.strike_adjustment import StrikeAdjustment
            from app.models.strike_rule import StrikeRule
            from app.models.employee import Employee
            from sqlalchemy import func
            from datetime import datetime, timedelta, time
            import random
            
            # Get all active employees
            employees = db.query(Employee).filter(Employee.employee_status == 'ACTIVE').all()
            
            if not employees:
                logger.warning("No active employees found for strike register data")
                return True
            
            business_id = employees[0].business_id
            
            # Create strike rules if they don't exist
            existing_rules = db.query(StrikeRule).filter(StrikeRule.business_id == business_id).count()
            if existing_rules == 0:
                strike_rules_data = [
                    {
                        "rule_type": "Late Coming",
                        "minutes": 15,
                        "strike": "Green",
                        "full_day_only": False,
                        "time_adjustment": "No Adjustment",
                        "round_direction": "next",
                        "round_minutes": 5
                    },
                    {
                        "rule_type": "Late Coming",
                        "minutes": 30,
                        "strike": "Orange",
                        "full_day_only": False,
                        "time_adjustment": "Round",
                        "round_direction": "next",
                        "round_minutes": 15
                    },
                    {
                        "rule_type": "Early Going",
                        "minutes": 15,
                        "strike": "Green",
                        "full_day_only": False,
                        "time_adjustment": "No Adjustment",
                        "round_direction": "next",
                        "round_minutes": 5
                    },
                    {
                        "rule_type": "Early Going",
                        "minutes": 30,
                        "strike": "Red",
                        "full_day_only": True,
                        "time_adjustment": "Ignore Late/Early",
                        "round_direction": "previous",
                        "round_minutes": 10
                    },
                    {
                        "rule_type": "Late Lunch",
                        "minutes": 10,
                        "strike": "Yellow",
                        "full_day_only": False,
                        "time_adjustment": "Round",
                        "round_direction": "next",
                        "round_minutes": 5
                    }
                ]
                
                for rule_data in strike_rules_data:
                    strike_rule = StrikeRule(
                        business_id=business_id,
                        **rule_data
                    )
                    db.add(strike_rule)
            
            # Create strike adjustments if they don't exist
            existing_adjustments = db.query(StrikeAdjustment).filter(StrikeAdjustment.business_id == business_id).count()
            if existing_adjustments == 0:
                strike_adjustments_data = [
                    {
                        "strike_type": "Green",
                        "strike_range_from": 1,
                        "strike_range_to": 3,
                        "action": "Send Warning Only"
                    },
                    {
                        "strike_type": "Green",
                        "strike_range_from": 4,
                        "strike_range_to": 6,
                        "action": "Update Attendance"
                    },
                    {
                        "strike_type": "Red",
                        "strike_range_from": 1,
                        "strike_range_to": 2,
                        "action": "Update Attendance"
                    },
                    {
                        "strike_type": "Blue",
                        "strike_range_from": 1,
                        "strike_range_to": 5,
                        "action": "Send Warning Only"
                    }
                ]
                
                for adj_data in strike_adjustments_data:
                    strike_adjustment = StrikeAdjustment(
                        business_id=business_id,
                        **adj_data
                    )
                    db.add(strike_adjustment)
            
            # Create attendance records with strikes for JUL-2025 (the period shown in frontend)
            target_date = datetime(2025, 7, 1)
            year = target_date.year
            month = target_date.month
            
            # Get number of working days in July 2025
            from calendar import monthrange
            days_in_month = monthrange(year, month)[1]
            
            # Create attendance records with some strikes
            for employee in employees:
                strike_days = random.randint(2, 6)  # 2-6 strike days per employee
                strike_dates = random.sample(range(1, min(days_in_month, 25)), strike_days)
                
                for day in range(1, days_in_month + 1):
                    current_date = datetime(year, month, day).date()
                    
                    # Skip weekends (Saturday=5, Sunday=6)
                    if current_date.weekday() >= 5:
                        continue
                    
                    # Check if attendance record already exists
                    existing_record = db.query(AttendanceRecord).filter(
                        AttendanceRecord.employee_id == employee.id,
                        AttendanceRecord.attendance_date == current_date
                    ).first()
                    
                    if existing_record:
                        continue
                    
                    # Create strike scenarios
                    if day in strike_dates:
                        strike_type = random.choice(["late_coming", "early_going", "absent", "short_hours"])
                        
                        if strike_type == "late_coming":
                            # Late coming - punch in after 9:15 AM
                            late_minutes = random.randint(16, 60)
                            punch_in = datetime.combine(current_date, time(9, 0)) + timedelta(minutes=late_minutes)
                            punch_out = datetime.combine(current_date, time(18, 0))
                            total_hours = 8.0
                            status = AttendanceStatus.PRESENT
                            
                        elif strike_type == "early_going":
                            # Early going - punch out before 5:45 PM
                            early_minutes = random.randint(16, 60)
                            punch_in = datetime.combine(current_date, time(9, 0))
                            punch_out = datetime.combine(current_date, time(17, 45)) - timedelta(minutes=early_minutes)
                            total_hours = 7.5
                            status = AttendanceStatus.PRESENT
                            
                        elif strike_type == "absent":
                            # Absent
                            punch_in = None
                            punch_out = None
                            total_hours = 0
                            status = AttendanceStatus.ABSENT
                            
                        else:  # short_hours
                            # Short hours - less than 8 hours
                            punch_in = datetime.combine(current_date, time(9, 30))
                            punch_out = datetime.combine(current_date, time(16, 0))
                            total_hours = 6.5
                            status = AttendanceStatus.PRESENT
                    
                    else:
                        # Normal attendance
                        punch_in = datetime.combine(current_date, time(9, 0)) + timedelta(minutes=random.randint(-10, 10))
                        punch_out = datetime.combine(current_date, time(18, 0)) + timedelta(minutes=random.randint(-10, 10))
                        total_hours = 8.0
                        status = AttendanceStatus.PRESENT
                    
                    attendance_record = AttendanceRecord(
                        employee_id=employee.id,
                        business_id=employee.business_id,
                        attendance_date=current_date,
                        attendance_status=status,
                        punch_in_time=punch_in,
                        punch_out_time=punch_out,
                        total_hours=total_hours,
                        overtime_hours=max(0, total_hours - 8) if total_hours > 8 else 0,
                        punch_in_location="Office",
                        punch_out_location="Office",
                        is_late=(punch_in and punch_in.time() > time(9, 15)) if punch_in else False,
                        is_early_out=(punch_out and punch_out.time() < time(17, 45)) if punch_out else False,
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    db.add(attendance_record)
            
            # Commit all changes
            db.commit()
            
            # Count records created
            total_attendance = db.query(AttendanceRecord).filter(
                func.extract('year', AttendanceRecord.attendance_date) == year,
                func.extract('month', AttendanceRecord.attendance_date) == month
            ).count()
            
            total_strike_rules = db.query(StrikeRule).filter(StrikeRule.business_id == business_id).count()
            total_strike_adjustments = db.query(StrikeAdjustment).filter(StrikeAdjustment.business_id == business_id).count()
            
            logger.info(f"[OK] Strike register sample data created successfully")
            logger.info(f"  - Attendance records for JUL-2025: {total_attendance}")
            logger.info(f"  - Strike rules: {total_strike_rules}")
            logger.info(f"  - Strike adjustments: {total_strike_adjustments}")
            logger.info(f"  - Employees covered: {len(employees)}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create strike register sample data: {e}")
        return False


def create_travel_register_sample_data():
    """Create sample travel register data for testing"""
    logger.info("\nStep 32: Creating travel register sample data...")
    
    try:
        with get_db_context() as db:
            # Get business and employees
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            employees = db.query(Employee).filter(Employee.business_id == business.id).limit(10).all()
            if not employees:
                logger.info("No employees found, skipping travel register sample data")
                return True
            
            # Create travel request model if it doesn't exist (mock implementation)
            # Since TravelRequest model might not exist, we'll create sample data in a generic way
            from app.models.datacapture import TravelRequest
            
            # Sample travel data for different employees (use modulo to cycle through available employees)
            travel_data = [
                {
                    "employee_id": employees[0 % len(employees)].id,
                    "travel_date": date(2025, 11, 15),
                    "from_location": "Hyderabad Office",
                    "to_location": "Client Site - Gachibowli",
                    "purpose": "Client Meeting",
                    "calculated_distance": 15.5,
                    "approved_distance": 15.5,
                    "status": "Approved",
                    "travel_allowance": Decimal('310.00')  # 15.5 * 20 per km
                },
                {
                    "employee_id": employees[1 % len(employees)].id,
                    "travel_date": date(2025, 11, 16),
                    "from_location": "Hyderabad Office",
                    "to_location": "Airport",
                    "purpose": "Business Travel",
                    "calculated_distance": 25.5,
                    "approved_distance": 25.5,
                    "status": "Approved",
                    "travel_allowance": Decimal('510.00')
                },
                {
                    "employee_id": employees[2 % len(employees)].id,
                    "travel_date": date(2025, 11, 17),
                    "from_location": "Home",
                    "to_location": "Training Center",
                    "purpose": "Training Session",
                    "calculated_distance": 45.2,
                    "approved_distance": 45.2,
                    "status": "Approved",
                    "travel_allowance": Decimal('904.00')
                },
                {
                    "employee_id": employees[3 % len(employees)].id,
                    "travel_date": date(2025, 11, 18),
                    "from_location": "Office",
                    "to_location": "Bank",
                    "purpose": "Official Work",
                    "calculated_distance": 12.8,
                    "approved_distance": 12.8,
                    "status": "Approved",
                    "travel_allowance": Decimal('256.00')
                },
                {
                    "employee_id": employees[4 % len(employees)].id,
                    "travel_date": date(2025, 11, 19),
                    "from_location": "Office",
                    "to_location": "Vendor Office",
                    "purpose": "Vendor Meeting",
                    "calculated_distance": 33.7,
                    "approved_distance": 33.7,
                    "status": "Approved",
                    "travel_allowance": Decimal('674.00')
                },
                {
                    "employee_id": employees[5 % len(employees)].id,
                    "travel_date": date(2025, 11, 20),
                    "from_location": "Office",
                    "to_location": "Conference Hall",
                    "purpose": "Conference",
                    "calculated_distance": 18.3,
                    "approved_distance": 18.3,
                    "status": "Approved",
                    "travel_allowance": Decimal('366.00')
                },
                {
                    "employee_id": employees[6 % len(employees)].id,
                    "travel_date": date(2025, 11, 21),
                    "from_location": "Home",
                    "to_location": "Office",
                    "purpose": "Regular Commute",
                    "calculated_distance": 0.0,
                    "approved_distance": 0.0,
                    "status": "Approved",
                    "travel_allowance": Decimal('0.00')
                },
                {
                    "employee_id": employees[7 % len(employees)].id,
                    "travel_date": date(2025, 11, 22),
                    "from_location": "Office",
                    "to_location": "Client Site",
                    "purpose": "Project Work",
                    "calculated_distance": 28.5,
                    "approved_distance": 25.0,  # Reduced approved distance
                    "status": "Pending",
                    "travel_allowance": Decimal('500.00')
                },
                {
                    "employee_id": employees[8 % len(employees)].id,
                    "travel_date": date(2025, 11, 23),
                    "from_location": "Office",
                    "to_location": "Personal Location",
                    "purpose": "Personal Work",
                    "calculated_distance": 22.0,
                    "approved_distance": 0.0,
                    "status": "Rejected",
                    "travel_allowance": Decimal('0.00')
                },
                {
                    "employee_id": employees[9 % len(employees)].id,
                    "travel_date": date(2025, 11, 24),
                    "from_location": "Office",
                    "to_location": "Training Center",
                    "purpose": "Skill Development",
                    "calculated_distance": 35.8,
                    "approved_distance": 35.8,
                    "status": "Pending",
                    "travel_allowance": Decimal('716.00')
                }
            ]
            
            # Create travel requests
            for travel_info in travel_data:
                # Check if travel request already exists
                existing_travel = db.query(TravelRequest).filter(
                    TravelRequest.employee_id == travel_info["employee_id"],
                    TravelRequest.travel_date == travel_info["travel_date"]
                ).first()
                
                if not existing_travel:
                    travel_request = TravelRequest(
                        business_id=business.id,
                        employee_id=travel_info["employee_id"],
                        travel_date=travel_info["travel_date"],
                        from_location=travel_info["from_location"],
                        to_location=travel_info["to_location"],
                        purpose=travel_info["purpose"],
                        calculated_distance=travel_info["calculated_distance"],
                        approved_distance=travel_info["approved_distance"],
                        status=travel_info["status"],
                        travel_allowance=travel_info["travel_allowance"],
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    db.add(travel_request)
            
            # Commit all changes
            db.commit()
            
            # Count records created
            total_travel_requests = db.query(TravelRequest).filter(TravelRequest.business_id == business.id).count()
            
            logger.info(f"[OK] Travel register sample data created successfully")
            logger.info(f"  - Travel requests: {total_travel_requests}")
            logger.info(f"  - Employees with travel records: {len(travel_data)}")
            logger.info(f"  - Date range: NOV-2025")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create travel register sample data: {e}")
        return False


def create_time_punches_sample_data():
    """Create sample time punches data for testing"""
    logger.info("\nStep 33: Creating time punches sample data...")
    
    try:
        with get_db_context() as db:
            # Get business and employees
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            employees = db.query(Employee).filter(Employee.business_id == business.id).limit(5).all()
            if not employees:
                logger.info("No employees found, skipping time punches sample data")
                return True
            
            from app.models.attendance import AttendancePunch, AttendanceRecord, PunchType, AttendanceStatus
            
            # Sample punch data for the last 3 days
            punch_data = []
            
            # Generate punch data for each employee for the last 3 days
            from datetime import datetime, timedelta, time
            import random
            
            base_date = datetime.now().date()
            punch_methods = ['selfie', 'remote', 'web', 'biometric', 'manual']
            
            for i in range(3):  # Last 3 days
                punch_date = base_date - timedelta(days=i)
                
                for emp_idx, employee in enumerate(employees):
                    # Create attendance record first
                    existing_attendance = db.query(AttendanceRecord).filter(
                        AttendanceRecord.employee_id == employee.id,
                        AttendanceRecord.attendance_date == punch_date
                    ).first()
                    
                    if not existing_attendance:
                        # Random in/out times
                        in_hour = random.randint(8, 9)
                        in_minute = random.randint(0, 59)
                        out_hour = random.randint(17, 18)
                        out_minute = random.randint(0, 59)
                        
                        punch_in_time = datetime.combine(punch_date, time(in_hour, in_minute))
                        punch_out_time = datetime.combine(punch_date, time(out_hour, out_minute))
                        
                        # Calculate total hours
                        time_diff = punch_out_time - punch_in_time
                        total_hours = time_diff.total_seconds() / 3600
                        
                        attendance_record = AttendanceRecord(
                            business_id=business.id,
                            employee_id=employee.id,
                            attendance_date=punch_date,
                            punch_in_time=punch_in_time,
                            punch_out_time=punch_out_time,
                            total_hours=total_hours,
                            overtime_hours=max(0, total_hours - 8) if total_hours > 8 else 0,
                            attendance_status=AttendanceStatus.PRESENT,
                            punch_in_location="Office",
                            punch_out_location="Office",
                            is_late=(in_hour > 9 or (in_hour == 9 and in_minute > 15)),
                            is_early_out=(out_hour < 17 or (out_hour == 17 and out_minute < 45)),
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        db.add(attendance_record)
                        db.flush()  # Get the ID
                        
                        # Create punch records
                        punch_method = random.choice(punch_methods)
                        
                        # IN punch
                        in_punch = AttendancePunch(
                            employee_id=employee.id,
                            attendance_record_id=attendance_record.id,
                            punch_time=punch_in_time,
                            punch_type=PunchType.IN,
                            location="Office",
                            device_info=f"Device-{emp_idx + 1}",
                            ip_address="192.168.1.100",
                            is_biometric=(punch_method == 'biometric'),
                            is_manual=(punch_method == 'manual'),
                            created_at=datetime.now()
                        )
                        db.add(in_punch)
                        
                        # OUT punch (only if not today or if it's past out time)
                        if punch_date < base_date or datetime.now().time() > time(out_hour, out_minute):
                            out_punch = AttendancePunch(
                                employee_id=employee.id,
                                attendance_record_id=attendance_record.id,
                                punch_time=punch_out_time,
                                punch_type=PunchType.OUT,
                                location="Office",
                                device_info=f"Device-{emp_idx + 1}",
                                ip_address="192.168.1.100",
                                is_biometric=(punch_method == 'biometric'),
                                is_manual=(punch_method == 'manual'),
                                created_at=datetime.now()
                            )
                            db.add(out_punch)
                        
                        # Add some random additional punches (break in/out)
                        if random.choice([True, False]):
                            break_out_time = punch_in_time + timedelta(hours=4, minutes=random.randint(0, 30))
                            break_in_time = break_out_time + timedelta(minutes=random.randint(30, 60))
                            
                            break_out_punch = AttendancePunch(
                                employee_id=employee.id,
                                attendance_record_id=attendance_record.id,
                                punch_time=break_out_time,
                                punch_type=PunchType.OUT,
                                location="Office",
                                device_info=f"Device-{emp_idx + 1}",
                                ip_address="192.168.1.100",
                                is_biometric=(punch_method == 'biometric'),
                                is_manual=(punch_method == 'manual'),
                                created_at=datetime.now()
                            )
                            db.add(break_out_punch)
                            
                            break_in_punch = AttendancePunch(
                                employee_id=employee.id,
                                attendance_record_id=attendance_record.id,
                                punch_time=break_in_time,
                                punch_type=PunchType.IN,
                                location="Office",
                                device_info=f"Device-{emp_idx + 1}",
                                ip_address="192.168.1.100",
                                is_biometric=(punch_method == 'biometric'),
                                is_manual=(punch_method == 'manual'),
                                created_at=datetime.now()
                            )
                            db.add(break_in_punch)
            
            # Commit all changes
            db.commit()
            
            # Count records created
            total_punches = db.query(AttendancePunch).count()
            
            total_attendance = db.query(AttendanceRecord).filter(
                AttendanceRecord.business_id == business.id
            ).count()
            
            logger.info(f"[OK] Time punches sample data created successfully")
            logger.info(f"  - Punch records: {total_punches}")
            logger.info(f"  - Attendance records: {total_attendance}")
            logger.info(f"  - Employees covered: {len(employees)}")
            logger.info(f"  - Date range: Last 3 days")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create time punches sample data: {e}")
        return False


def create_sample_employee_documents():
    """Create sample employee documents data"""
    logger.info("\nStep 34.5: Creating sample employee documents data...")
    
    try:
        from app.models.employee import Employee, EmployeeDocument
        import os
        import shutil
        from datetime import datetime
        
        with get_db_context() as db:
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get employees
            employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                Employee.is_active == True
            ).limit(10).all()  # Create documents for first 10 employees
            
            if not employees:
                logger.error("No employees found")
                return False
            
            # Create uploads directory if it doesn't exist
            upload_dir = "uploads/employee_documents"
            os.makedirs(upload_dir, exist_ok=True)
            
            # Sample document types and names
            document_types = [
                {"type": "id_proof", "name": "Aadhaar Card", "filename": "sample_pan.jpg"},
                {"type": "address_proof", "name": "Address Proof", "filename": "sample_address.pdf"},
                {"type": "bank_proof", "name": "Bank Statement", "filename": "sample_bank.pdf"},
                {"type": "resume", "name": "Resume", "filename": "sample_pan.jpg"},
                {"type": "educational", "name": "Educational Certificate", "filename": "sample_address.pdf"}
            ]
            
            documents_created = 0
            
            for i, employee in enumerate(employees):
                # Each employee gets 2-4 documents
                num_docs = min(len(document_types), 3)  # Max 3 documents per employee
                selected_docs = document_types[:num_docs]
                
                for j, doc_info in enumerate(selected_docs):
                    # Create unique filename
                    unique_filename = f"{employee.id}_{doc_info['type']}_{doc_info['filename']}"
                    file_path = os.path.join(upload_dir, unique_filename)
                    
                    # Copy sample file if it exists
                    source_file = os.path.join(upload_dir, doc_info['filename'])
                    if os.path.exists(source_file):
                        try:
                            shutil.copy2(source_file, file_path)
                            file_size = os.path.getsize(file_path)
                        except Exception as e:
                            logger.warning(f"Could not copy sample file {source_file}: {e}")
                            # Create a dummy file
                            with open(file_path, 'w') as f:
                                f.write(f"Sample document for {employee.first_name} {employee.last_name}")
                            file_size = os.path.getsize(file_path)
                    else:
                        # Create a dummy file
                        with open(file_path, 'w') as f:
                            f.write(f"Sample {doc_info['name']} for {employee.first_name} {employee.last_name}")
                        file_size = os.path.getsize(file_path)
                    
                    # Determine MIME type
                    if doc_info['filename'].endswith('.pdf'):
                        mime_type = 'application/pdf'
                    elif doc_info['filename'].endswith(('.jpg', '.jpeg')):
                        mime_type = 'image/jpeg'
                    elif doc_info['filename'].endswith('.png'):
                        mime_type = 'image/png'
                    else:
                        mime_type = 'application/octet-stream'
                    
                    # Create database record
                    document = EmployeeDocument(
                        employee_id=employee.id,
                        document_type=doc_info['type'],
                        document_name=doc_info['name'],
                        file_path=file_path,
                        file_size=file_size,
                        mime_type=mime_type,
                        hidden=j == 0,  # First document is hidden for testing
                        uploaded_by=1,  # Superadmin user ID
                        uploaded_at=datetime.now(),
                        created_at=datetime.now()
                    )
                    
                    db.add(document)
                    documents_created += 1
            
            db.commit()
            logger.info(f"[OK] Created {documents_created} sample employee documents")
            logger.info(f"  - Documents created for {len(employees)} employees")
            logger.info(f"  - Files stored in: {upload_dir}")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample employee documents: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_sample_relatives():
    """Create sample employee relatives data"""
    logger.info("\nStep 35: Creating sample employee relatives data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee
            from app.models.employee_relative import EmployeeRelative
            from app.models.business import Business
            
            # Check if relatives data already exists
            existing_relatives = db.query(EmployeeRelative).first()
            if existing_relatives:
                logger.info("Employee relatives sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get employees
            employees = db.query(Employee).filter(
                Employee.business_id == business.id
            ).limit(10).all()
            
            if not employees:
                logger.info("No employees found for relatives assignment")
                return True
            
            # Sample relatives data
            relatives_data = [
                # Employee 1 - Abhilash Gurrampally
                {
                    'employee_code': 'LEV098',
                    'relatives': [
                        {
                            'relation': 'Father',
                            'relative_name': 'G.Ramakrishna Goud',
                            'date_of_birth': date(1971, 9, 8),
                            'dependent': 'No',
                            'phone': '+91-9876543210',
                            'email': 'ramakrishna.goud@example.com',
                            'notes': 'Retired government employee'
                        },
                        {
                            'relation': 'Mother',
                            'relative_name': 'E.Sunitha',
                            'date_of_birth': date(1975, 2, 28),
                            'dependent': 'No',
                            'phone': '+91-9876543211',
                            'email': 'sunitha.e@example.com',
                            'notes': 'Homemaker'
                        }
                    ]
                },
                # Employee 2 - Akirala Saikiran
                {
                    'employee_code': 'LEV068',
                    'relatives': [
                        {
                            'relation': 'Father',
                            'relative_name': 'Santosh',
                            'date_of_birth': date(1970, 5, 5),
                            'dependent': 'No',
                            'phone': '+91-9876543212',
                            'email': 'santosh.akirala@example.com',
                            'notes': 'Business owner'
                        }
                    ]
                },
                # Employee 3 - Anusha Enigalla (no relatives)
                {
                    'employee_code': 'LEV111',
                    'relatives': []
                }
            ]
            
            relatives_created = 0
            
            # Create relatives for existing employees
            for emp_data in relatives_data:
                # Find employee by code
                employee = db.query(Employee).filter(
                    Employee.employee_code == emp_data['employee_code']
                ).first()
                
                if not employee:
                    # Create a sample employee if not found
                    employee = Employee(
                        business_id=business.id,
                        employee_code=emp_data['employee_code'],
                        first_name=emp_data['employee_code'].replace('LEV', 'Employee'),
                        last_name='Sample',
                        email=f"{emp_data['employee_code'].lower()}@example.com",
                        mobile=f"+91-98765432{len(relatives_data)}",
                        date_of_joining=date.today() - timedelta(days=random.randint(30, 365)),
                        employee_status='active',
                        is_active=True
                    )
                    db.add(employee)
                    db.commit()
                    db.refresh(employee)
                
                # Create relatives for this employee
                for rel_data in emp_data['relatives']:
                    relative = EmployeeRelative(
                        employee_id=employee.id,
                        relation=rel_data['relation'],
                        relative_name=rel_data['relative_name'],
                        date_of_birth=rel_data['date_of_birth'],
                        dependent=rel_data['dependent'],
                        phone=rel_data.get('phone'),
                        email=rel_data.get('email'),
                        notes=rel_data.get('notes'),
                        is_active=True,
                        created_at=datetime.now()
                    )
                    db.add(relative)
                    relatives_created += 1
            
            # Add more sample relatives for other employees
            other_employees = db.query(Employee).filter(
                Employee.business_id == business.id,
                ~Employee.employee_code.in_(['LEV098', 'LEV068', 'LEV111'])
            ).limit(5).all()
            
            sample_relations = ['Father', 'Mother', 'Spouse', 'Child', 'Brother', 'Sister']
            sample_names = [
                'Rajesh Kumar', 'Priya Sharma', 'Amit Singh', 'Sunita Devi',
                'Vikash Gupta', 'Meera Patel', 'Ravi Reddy', 'Kavitha Nair',
                'Suresh Babu', 'Lakshmi Rao', 'Mahesh Varma', 'Deepika Joshi'
            ]
            
            for employee in other_employees:
                # Each employee gets 1-3 relatives
                num_relatives = random.randint(1, 3)
                used_relations = []
                
                for _ in range(num_relatives):
                    # Avoid duplicate relations for same employee
                    available_relations = [r for r in sample_relations if r not in used_relations]
                    if not available_relations:
                        break
                    
                    relation = random.choice(available_relations)
                    used_relations.append(relation)
                    
                    # Generate relative details
                    relative_name = random.choice(sample_names)
                    birth_year = random.randint(1950, 2000)
                    birth_month = random.randint(1, 12)
                    birth_day = random.randint(1, 28)
                    
                    relative = EmployeeRelative(
                        employee_id=employee.id,
                        relation=relation,
                        relative_name=relative_name,
                        date_of_birth=date(birth_year, birth_month, birth_day),
                        dependent=random.choice(['Yes', 'No']),
                        phone=f"+91-{random.randint(7000000000, 9999999999)}",
                        email=f"{relative_name.lower().replace(' ', '.')}@example.com",
                        notes=f"{relation} of {employee.first_name} {employee.last_name}",
                        is_active=True,
                        created_at=datetime.now()
                    )
                    db.add(relative)
                    relatives_created += 1
            
            db.commit()
            logger.info(f"[OK] Created {relatives_created} sample employee relatives")
            logger.info(f"  - Relatives assigned to employees")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample relatives: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_sample_additional_info():
    """Create sample employee additional info data"""
    logger.info("\nStep 35.5: Creating sample employee additional info data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee
            from app.models.employee_additional_info import EmployeeAdditionalInfo
            from app.models.business import Business
            
            # Check if additional info already exists
            existing_info = db.query(EmployeeAdditionalInfo).count()
            if existing_info > 0:
                logger.info("Sample additional info already exists, skipping...")
                return True
            
            # Get employees to add additional info for (including employee 12)
            employees = db.query(Employee).filter(Employee.id.in_([1, 2, 3, 12])).all()
            
            if not employees:
                logger.warning("No employees found, cannot create additional info")
                return True
            
            additional_info_data = [
                {
                    "employee_id": 1,
                    "other_info_1": "Excellent communication skills",
                    "other_info_2": "Proficient in multiple programming languages",
                    "other_info_3": "Team player with leadership qualities",
                    "other_info_4": "Certified in Agile methodologies",
                    "other_info_5": "Experience with cloud technologies",
                    "other_info_6": "Strong problem-solving abilities",
                    "other_info_7": "Mentoring junior developers",
                    "other_info_8": "Active in open source community",
                    "other_info_9": "Continuous learning mindset",
                    "other_info_10": "Cross-functional collaboration experience"
                },
                {
                    "employee_id": 2,
                    "other_info_1": "Strong analytical thinking",
                    "other_info_2": "Experience with project management",
                    "other_info_3": "Mentor to junior team members",
                    "other_info_4": "Passionate about continuous learning",
                    "other_info_5": "Certified in data analysis",
                    "other_info_6": "Process improvement initiatives",
                    "other_info_7": "Client relationship management",
                    "other_info_8": "Quality assurance expertise",
                    "other_info_9": "Risk assessment capabilities",
                    "other_info_10": "Strategic planning involvement"
                },
                {
                    "employee_id": 3,
                    "other_info_1": "Creative problem solver",
                    "other_info_2": "Strong attention to detail",
                    "other_info_3": "Experience with customer service",
                    "other_info_4": "Multilingual capabilities",
                    "other_info_5": "Volunteer work experience",
                    "other_info_6": "Design thinking approach",
                    "other_info_7": "User experience focus",
                    "other_info_8": "Innovation mindset",
                    "other_info_9": "Cultural sensitivity",
                    "other_info_10": "Community engagement activities"
                },
                {
                    "employee_id": 12,
                    "other_info_1": "Technical expertise in system architecture",
                    "other_info_2": "Database optimization specialist",
                    "other_info_3": "Security best practices advocate",
                    "other_info_4": "Performance tuning experience",
                    "other_info_5": "DevOps pipeline management",
                    "other_info_6": "Code review and quality standards",
                    "other_info_7": "Documentation and knowledge sharing",
                    "other_info_8": "Incident response and troubleshooting",
                    "other_info_9": "Scalability planning and implementation",
                    "other_info_10": "Technology evaluation and adoption"
                }
            ]
            
            # Create additional info records for available employees
            created_count = 0
            for info_data in additional_info_data:
                # Check if employee exists
                employee_exists = any(emp.id == info_data["employee_id"] for emp in employees)
                if employee_exists:
                    additional_info = EmployeeAdditionalInfo(**info_data)
                    db.add(additional_info)
                    created_count += 1
            
            db.commit()
            
            logger.info(f"[OK] Created {created_count} employee additional info records")
            
            return True
            
    except Exception as e:
        logger.error(f"[ERROR] Failed to create sample additional info: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to create sample additional info: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_sample_permissions():
    """Create sample employee permissions data"""
    logger.info("\nStep 35.6: Creating sample employee permissions data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee
            from app.models.employee_permissions import EmployeePermissions
            from app.models.business import Business
            
            # Check if permissions already exist
            existing_permissions = db.query(EmployeePermissions).count()
            
            if existing_permissions > 0:
                logger.info("Sample permissions already exist, skipping...")
                return True
            
            # Get employees to create permissions for
            employees = db.query(Employee).limit(15).all()
            
            if not employees:
                logger.warning("No employees found to create permissions for")
                return True
            
            # Create permissions only for unique employees
            permissions_templates = [
                {
                    "selfie_punch": True,
                    "selfie_face_recognition": False,
                    "selfie_all_locations": False,
                    "remote_punch": True,
                    "missed_punch": True,
                    "missed_punch_limit": 3,
                    "web_punch": False,
                    "time_relaxation": False,
                    "scan_all_locations": True,
                    "ignore_time_strikes": False,
                    "auto_punch": False,
                    "visit_punch": False,
                    "visit_punch_approval": False,
                    "visit_punch_attendance": False,
                    "live_travel": False,
                    "live_travel_attendance": False,
                    "give_badges": False,
                    "give_rewards": False
                },
                {
                    "selfie_punch": True,
                    "selfie_face_recognition": True,
                    "selfie_all_locations": True,
                    "remote_punch": True,
                    "missed_punch": True,
                    "missed_punch_limit": 5,
                    "web_punch": True,
                    "time_relaxation": True,
                    "scan_all_locations": True,
                    "ignore_time_strikes": False,
                    "auto_punch": False,
                    "visit_punch": True,
                    "visit_punch_approval": True,
                    "visit_punch_attendance": True,
                    "live_travel": True,
                    "live_travel_attendance": True,
                    "give_badges": True,
                    "give_rewards": True
                },
                {
                    "selfie_punch": True,
                    "selfie_face_recognition": False,
                    "selfie_all_locations": False,
                    "remote_punch": False,
                    "missed_punch": True,
                    "missed_punch_limit": 2,
                    "web_punch": False,
                    "time_relaxation": False,
                    "scan_all_locations": False,
                    "ignore_time_strikes": True,
                    "auto_punch": True,
                    "visit_punch": False,
                    "visit_punch_approval": False,
                    "visit_punch_attendance": False,
                    "live_travel": False,
                    "live_travel_attendance": False,
                    "give_badges": False,
                    "give_rewards": False
                },
                {
                    "selfie_punch": True,
                    "selfie_face_recognition": True,
                    "selfie_all_locations": True,
                    "remote_punch": True,
                    "missed_punch": True,
                    "missed_punch_limit": 10,
                    "web_punch": True,
                    "time_relaxation": True,
                    "scan_all_locations": True,
                    "ignore_time_strikes": False,
                    "auto_punch": True,
                    "visit_punch": True,
                    "visit_punch_approval": False,
                    "visit_punch_attendance": True,
                    "live_travel": True,
                    "live_travel_attendance": True,
                    "give_badges": True,
                    "give_rewards": True
                }
            ]
            
            # Create permissions records only for available employees (no duplicates)
            for idx, employee in enumerate(employees[:len(permissions_templates)]):
                perm_data = permissions_templates[idx].copy()
                perm_data["employee_id"] = employee.id
                permissions = EmployeePermissions(**perm_data)
                db.add(permissions)
            
            db.commit()
            
            created_count = db.query(EmployeePermissions).count()
            logger.info(f"[OK] Created {created_count} employee permissions records")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create sample permissions: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_sample_employee_access():
    """Create sample employee access data"""
    logger.info("\nStep 35.7: Creating sample employee access data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee
            from app.models.employee_access import EmployeeAccess, EmployeeLoginSession
            from datetime import datetime, timedelta
            import random
            
            # Check if access settings already exist
            existing_access = db.query(EmployeeAccess).count()
            
            if existing_access > 0:
                logger.info("Sample employee access already exists, skipping...")
                return True
            
            # Get employees to create access settings for
            employees = db.query(Employee).limit(15).all()
            
            if not employees:
                logger.warning("No employees found to create access settings for")
                return True
            
            # Create access templates
            access_templates = [
                {
                    "pin_never_expires": False,
                    "multi_device_logins": False,
                    "mobile_access_enabled": True,
                    "web_access_enabled": True,
                    "wall_admin": False,
                    "wall_posting": True,
                    "wall_commenting": True
                },
                {
                    "pin_never_expires": True,
                    "multi_device_logins": True,
                    "mobile_access_enabled": True,
                    "web_access_enabled": True,
                    "wall_admin": True,
                    "wall_posting": True,
                    "wall_commenting": True
                },
                {
                    "pin_never_expires": False,
                    "multi_device_logins": False,
                    "mobile_access_enabled": True,
                    "web_access_enabled": False,
                    "wall_admin": False,
                    "wall_posting": False,
                    "wall_commenting": True
                },
                {
                    "pin_never_expires": True,
                    "multi_device_logins": True,
                    "mobile_access_enabled": True,
                    "web_access_enabled": True,
                    "wall_admin": True,
                    "wall_posting": True,
                    "wall_commenting": True
                }
            ]
            
            # Create access records only for unique employees (no duplicates)
            for idx, employee in enumerate(employees[:len(access_templates)]):
                access_item = access_templates[idx].copy()
                access_item["employee_id"] = employee.id
                access_settings = EmployeeAccess(**access_item)
                db.add(access_settings)
            
            # Create sample login sessions
            device_names = [
                "Samsung Galaxy S23", "iPhone 15 Pro", "OnePlus 12", 
                "Xiaomi 13", "Google Pixel 8", "Motorola Edge 40"
            ]
            
            os_versions = [
                "Android 15", "iOS 17.1", "Android 14", 
                "Android 13", "iOS 16.6", "Android 12"
            ]
            
            app_versions = ["7.6.13", "7.6.12", "7.6.11", "7.5.9"]
            
            for i, employee in enumerate(employees[:4]):  # Include employee 12
                # Create 1-2 active sessions per employee
                num_sessions = random.randint(1, 2)
                for j in range(num_sessions):
                    session = EmployeeLoginSession(
                        employee_id=employee.id,
                        session_token=f"session_{employee.id}_{j}_{random.randint(1000, 9999)}",
                        device_name=device_names[i % len(device_names)],
                        device_type="mobile",
                        os_version=os_versions[i % len(os_versions)],
                        app_version=random.choice(app_versions),
                        ip_address=f"192.168.1.{random.randint(100, 200)}",
                        user_agent="Mobile App",
                        is_active=True,
                        last_activity=datetime.now() - timedelta(minutes=random.randint(5, 120)),
                        login_time=datetime.now() - timedelta(hours=random.randint(1, 24))
                    )
                    db.add(session)
            
            db.commit()
            
            created_access_count = db.query(EmployeeAccess).count()
            created_sessions_count = db.query(EmployeeLoginSession).count()
            logger.info(f"[OK] Created {created_access_count} employee access records")
            logger.info(f"[OK] Created {created_sessions_count} login session records")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create sample employee access: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_sample_activity_logs():
    """Create sample activity logs for Employee Activity module"""
    logger.info("\nStep 35.8: Creating sample activity logs...")
    
    try:
        with get_db_context() as db:
            from app.models.reports import ActivityLog
            from app.models.employee import Employee
            from app.models.user import User
            from datetime import datetime, timedelta
            import json
            
            # Get Super Administrator user
            admin_user = db.query(User).filter(User.email == "superadmin@levitica.com").first()
            if not admin_user:
                logger.warning("Super Administrator user not found, skipping activity logs creation")
                return True
            
            # Get employees for activity logs
            employees = db.query(Employee).filter(Employee.id.in_([1, 2, 3, 12])).all()
            if not employees:
                logger.warning("No employees found for activity logs creation")
                return True
            
            # Define activity templates
            activity_templates = [
                {"action": "Updated Basic Information for {name}", "module": "Employee Management"},
                {"action": "Policy Updated for {name}", "module": "HR Policies"},
                {"action": "Attendance Manually Updated for {name}", "module": "Attendance"},
                {"action": "Employee Profile Updated for {name}", "module": "Employee Management"},
                {"action": "Onboarding Form Completed for {name}", "module": "Onboarding"},
                {"action": "Onboarding Form Approved for {name}", "module": "Onboarding"},
                {"action": "Salary Processed for {name}", "module": "Payroll"},
                {"action": "User Access Granted for {name}", "module": "User Management"},
                {"action": "Reporting Period Allowed for {name}", "module": "Payroll"},
                {"action": "Payroll Period Modified for {name}", "module": "Payroll"},
                {"action": "Leave Request Approved for {name}", "module": "Leave Management"},
                {"action": "Document Uploaded for {name}", "module": "Document Management"},
                {"action": "Added Family Member for {name}", "module": "Employee Management"},
                {"action": "Updated Salary Details for {name}", "module": "Payroll"},
                {"action": "Added Document for {name}: PAN Card", "module": "Document Management"},
                {"action": "Updated Address Details for {name}", "module": "Employee Management"},
                {"action": "Updated Work Profile for {name}", "module": "Employee Management"},
                {"action": "Added Asset for {name}: Laptop", "module": "Asset Management"},
                {"action": "Updated Policies for {name}: Shift and Week Off", "module": "HR Policies"}
            ]
            
            created_count = 0
            
            # Create activity logs for each employee
            for employee in employees:
                employee_name = f"{employee.first_name or ''} {employee.last_name or ''}".strip()
                
                # Create 5-8 activity logs per employee
                num_logs = random.randint(5, 8)
                selected_templates = random.sample(activity_templates, min(num_logs, len(activity_templates)))
                
                for i, template in enumerate(selected_templates):
                    # Calculate timestamp (spread over last 30 days)
                    days_ago = random.randint(1, 30)
                    hours_ago = random.randint(1, 23)
                    activity_date = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
                    
                    # Format action with employee name
                    action = template["action"].format(name=employee_name)
                    
                    # Create details with employee_id
                    details = {
                        "employee_id": employee.id,
                        "employee_name": employee_name,
                        "action_type": "manual",
                        "source": "admin_panel"
                    }
                    
                    # Check if similar log already exists (avoid duplicates)
                    existing_log = db.query(ActivityLog).filter(
                        ActivityLog.action == action,
                        ActivityLog.module == template["module"],
                        ActivityLog.user_id == admin_user.id
                    ).first()
                    
                    if not existing_log:
                        # Create new activity log
                        activity_log = ActivityLog(
                            user_id=admin_user.id,
                            action=action,
                            module=template["module"],
                            details=details,
                            ip_address="192.168.1.100",
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            created_at=activity_date
                        )
                        
                        db.add(activity_log)
                        created_count += 1
            
            db.commit()
            
            # Verify creation
            total_employee_logs = db.query(ActivityLog).filter(
                ActivityLog.details.op('->>')('employee_id').in_([str(emp.id) for emp in employees])
            ).count()
            
            logger.info(f"[OK] Created {created_count} new activity logs")
            logger.info(f"[OK] Total employee-specific activity logs: {total_employee_logs}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create sample activity logs: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_sample_inactive_employees():
    """Create sample inactive employees data"""
    logger.info("\nStep 36: Creating sample inactive employees data...")
    
    try:
        with get_db_context() as db:
            from app.models.employee import Employee, EmployeeProfile
            from app.models.business import Business
            from app.models.department import Department
            from app.models.designations import Designation
            from app.models.location import Location
            from app.models.cost_center import CostCenter
            
            # Check if inactive employees already exist
            existing_inactive = db.query(Employee).filter(
                Employee.employee_status.in_(['inactive', 'terminated'])
            ).first()
            
            if existing_inactive:
                logger.info("Inactive employees sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found")
                return False
            
            # Get departments, designations, locations, cost centers
            departments = db.query(Department).filter(Department.business_id == business.id).all()
            designations = db.query(Designation).filter(Designation.business_id == business.id).all()
            locations = db.query(Location).filter(Location.business_id == business.id).all()
            cost_centers = db.query(CostCenter).filter(CostCenter.business_id == business.id).all()
            
            # Sample inactive employees data matching frontend
            inactive_employees_data = [
                {
                    'employee_code': 'LEV100',
                    'first_name': 'P',
                    'last_name': 'Krishnakumari',
                    'email': 'p.krishnakumari@example.com',
                    'mobile': '+91-9876543100',
                    'date_of_joining': date(2025, 7, 14),
                    'employee_status': 'inactive',
                    'gender': 'female'
                },
                {
                    'employee_code': 'LEV069',
                    'first_name': 'M',
                    'last_name': 'Durgaprasad',
                    'email': 'm.durgaprasad@example.com',
                    'mobile': '+91-9876543069',
                    'date_of_joining': date(2025, 5, 12),
                    'employee_status': 'terminated',
                    'gender': 'male'
                },
                {
                    'employee_code': 'LEV101',
                    'first_name': 'I',
                    'last_name': 'Phanindra',
                    'email': 'i.phanindra@example.com',
                    'mobile': '+91-9876543101',
                    'date_of_joining': date(2025, 7, 14),
                    'employee_status': 'inactive',
                    'gender': 'male'
                },
                {
                    'employee_code': 'LEV102',
                    'first_name': 'P',
                    'last_name': 'Saidurga',
                    'email': 'p.saidurga@example.com',
                    'mobile': '+91-9876543102',
                    'date_of_joining': date(2025, 7, 14),
                    'employee_status': 'inactive',
                    'gender': 'female'
                },
                {
                    'employee_code': 'LEV013',
                    'first_name': 'V',
                    'last_name': 'Sai Charan',
                    'email': 'v.saicharan@example.com',
                    'mobile': '+91-9876543013',
                    'date_of_joining': date(2024, 1, 25),
                    'employee_status': 'terminated',
                    'gender': 'male'
                }
            ]
            
            employees_created = 0
            
            # Get default values
            default_department = next((d for d in departments if 'Technical Support' in d.name), departments[0] if departments else None)
            default_designation = next((d for d in designations if 'Associate' in d.name), designations[0] if designations else None)
            default_location = next((l for l in locations if 'Hyderabad' in l.name), locations[0] if locations else None)
            default_cost_center = next((c for c in cost_centers if 'Associate' in c.name), cost_centers[0] if cost_centers else None)
            
            for emp_data in inactive_employees_data:
                # Check if employee already exists
                existing_emp = db.query(Employee).filter(
                    Employee.employee_code == emp_data['employee_code']
                ).first()
                
                if existing_emp:
                    # Update existing employee to inactive status
                    existing_emp.employee_status = emp_data['employee_status']
                    existing_emp.date_of_termination = date.today()
                    db.commit()
                    employees_created += 1
                else:
                    # Create new inactive employee
                    employee = Employee(
                        business_id=business.id,
                        employee_code=emp_data['employee_code'],
                        first_name=emp_data['first_name'],
                        last_name=emp_data['last_name'],
                        email=emp_data['email'],
                        mobile=emp_data['mobile'],
                        date_of_joining=emp_data['date_of_joining'],
                        date_of_termination=date.today(),
                        employee_status=emp_data['employee_status'],
                        gender=emp_data['gender'],
                        department_id=default_department.id if default_department else None,
                        designation_id=default_designation.id if default_designation else None,
                        location_id=default_location.id if default_location else None,
                        cost_center_id=default_cost_center.id if default_cost_center else None,
                        is_active=False,
                        created_at=datetime.now()
                    )
                    db.add(employee)
                    db.commit()
                    db.refresh(employee)
                    
                    # Create employee profile
                    profile = EmployeeProfile(
                        employee_id=employee.id,
                        profile_image_url=f"https://randomuser.me/api/portraits/{'women' if emp_data['gender'] == 'female' else 'men'}/{employee.id % 10 + 1}.jpg",
                        created_at=datetime.now()
                    )
                    db.add(profile)
                    employees_created += 1
            
            db.commit()
            logger.info(f"[OK] Created {employees_created} sample inactive employees")
            logger.info(f"  - Inactive employees with proper status and profiles")
            return True
    
    except Exception as e:
        logger.error(f"Failed to create sample inactive employees: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_form16_sample_data():
    """Create sample Form 16 data (employer info, person responsible, and CIT info)"""
    logger.info("\nStep 40: Creating sample Form 16 data...")
    
    try:
        with get_db_context() as db:
            from app.models.form16_models import EmployerInfo, PersonResponsible, CitInfo
            from app.models.business import Business
            
            # Check if Form 16 data already exists
            existing_employer = db.query(EmployerInfo).first()
            existing_person = db.query(PersonResponsible).first()
            existing_cit = db.query(CitInfo).first()
            
            if existing_employer and existing_person and existing_cit:
                logger.info("Form 16 sample data already exists, skipping...")
                return True
            
            # Get business
            business = db.query(Business).first()
            if not business:
                logger.error("No business found. Please create business data first.")
                return False
            
            # Create employer info if not exists
            if not existing_employer:
                employer_info = EmployerInfo(
                    name=business.business_name or "Levitica Technologies Pvt Ltd",
                    address1="123 Business Park, Tech City",
                    address2="Near IT Hub, Electronic City",
                    address3="Bangalore, Karnataka - 560100",
                    place_of_issue="Bangalore",
                    business_id=business.id
                )
                db.add(employer_info)
                logger.info("[OK] Created employer info")
            
            # Create person responsible if not exists
            if not existing_person:
                person_responsible = PersonResponsible(
                    full_name="Rajesh Kumar",
                    designation="HR Manager",
                    father_name="Suresh Kumar",
                    signature_path=None,  # Optional signature path
                    business_id=business.id
                )
                db.add(person_responsible)
                logger.info("[OK] Created person responsible")
            
            # Create CIT info if not exists
            if not existing_cit:
                cit_info = CitInfo(
                    name="Income Tax Officer",
                    address1="Central Processing Centre",
                    address2="Income Tax Department",
                    address3="Bangalore, Karnataka - 560001",
                    business_id=business.id
                )
                db.add(cit_info)
                logger.info("[OK] Created CIT info")
            
            db.commit()
            
            # Count created records
            total_employer = db.query(EmployerInfo).count()
            total_person = db.query(PersonResponsible).count()
            total_cit = db.query(CitInfo).count()
            logger.info(f"[OK] Form 16 setup complete - {total_employer} employer info, {total_person} person responsible, {total_cit} CIT info")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to create Form 16 sample data: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
