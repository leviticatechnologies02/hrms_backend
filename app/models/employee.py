"""
Employee Models
Core employee management data models
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Date, ForeignKey, Enum, JSON
from sqlalchemy.types import Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
import enum


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"
    ON_LEAVE = "on_leave"
    PROBATION = "probation"


class MaritalStatus(str, enum.Enum):
    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Employee(Base):
    """Main employee table"""
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(50), unique=True, index=True, nullable=False)
    
    # Basic Information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    middle_name = Column(String(100))
    email = Column(String(255), unique=True, index=True, nullable=False)
    mobile = Column(String(20), nullable=True)  # Made optional - not all employees may have mobile at creation
    alternate_mobile = Column(String(20))
    
    # Personal Details
    date_of_birth = Column(Date)
    gender = Column(Enum(Gender))
    marital_status = Column(Enum(MaritalStatus))
    blood_group = Column(String(10))
    nationality = Column(String(100))
    religion = Column(String(100))
    
    # Contact Information
    office_phone = Column(String(20))
    official_email = Column(String(255))
    
    # Address Information
    current_address = Column(Text)
    permanent_address = Column(Text)
    
    # Document Information
    aadhar_number = Column(String(12))
    passport_number = Column(String(20))
    passport_expiry = Column(Date)
    driving_license = Column(String(20))
    license_expiry = Column(Date)
    
    # Emergency Contact
    emergency_contact = Column(String(100))
    emergency_phone = Column(String(20))
    
    # Family Information
    father_name = Column(String(100))
    mother_name = Column(String(100))
    
    # Employment Details (additional)
    notice_period_days = Column(Integer)
    date_of_marriage = Column(Date)
    
    # Employment Details
    date_of_joining = Column(Date, nullable=True)  # Made optional - can be set later
    date_of_confirmation = Column(Date)
    date_of_termination = Column(Date)
    employee_status = Column(Enum(EmployeeStatus), default=EmployeeStatus.ACTIVE)
    employment_type = Column(String(50))  # permanent, contract, intern
    work_mode = Column(String(50))  # workfromhome, workfromoffice, hybrid
    
    # Organizational Details
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    business_unit_id = Column(Integer, ForeignKey("business_units.id"))
    department_id = Column(Integer, ForeignKey("departments.id"))
    designation_id = Column(Integer, ForeignKey("designations.id"))
    location_id = Column(Integer, ForeignKey("locations.id"))
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id"))
    grade_id = Column(Integer, ForeignKey("grades.id"))
    
    # Policy Assignments
    shift_policy_id = Column(Integer, ForeignKey("shift_policies.id"))
    weekoff_policy_id = Column(Integer, ForeignKey("weekoff_policies.id"))
    overtime_policy_id = Column(Integer, ForeignKey("overtime_policies.id"))
    auto_shift_enabled = Column(Boolean, default=False)
    # Note: Overtime policies are handled by the setup system
    
    # Biometric and Access Control
    biometric_code = Column(String(50))
    send_mobile_login = Column(Boolean, default=False)
    send_web_login = Column(Boolean, default=True)
    
    # Reporting Structure
    reporting_manager_id = Column(Integer, ForeignKey("employees.id"))
    hr_manager_id = Column(Integer, ForeignKey("employees.id"))
    indirect_manager_id = Column(Integer, ForeignKey("employees.id"))
    
    # System Fields
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business", back_populates="employees")
    business_unit = relationship("BusinessUnit")
    department = relationship("Department")
    designation = relationship("Designation")
    location = relationship("Location")
    cost_center = relationship("CostCenter")
    grade = relationship("Grade")
    shift_policy = relationship("ShiftPolicy")
    weekoff_policy = relationship("WeekOffPolicy")
    overtime_policy = relationship("OvertimePolicy", foreign_keys=[overtime_policy_id])
    # Note: Overtime policies are handled by the setup system
    reporting_manager = relationship("Employee", remote_side=[id], foreign_keys=[reporting_manager_id])
    hr_manager = relationship("Employee", remote_side=[id], foreign_keys=[hr_manager_id])
    indirect_manager = relationship("Employee", remote_side=[id], foreign_keys=[indirect_manager_id])
    
    # Reverse relationships
    subordinates = relationship("Employee", foreign_keys=[reporting_manager_id], remote_side=[id], overlaps="reporting_manager")
    attendance_records = relationship("AttendanceRecord", back_populates="employee")
    payroll_records = relationship("PayrollRecord", back_populates="employee")
    onboarding_forms = relationship("OnboardingForm", back_populates="employee")
    separation_requests = relationship("SeparationRequest", back_populates="employee")
    assets = relationship("Asset", back_populates="assigned_employee")
    profile = relationship("EmployeeProfile", back_populates="employee", uselist=False)
    documents = relationship("EmployeeDocument", back_populates="employee")
    salary_records = relationship("EmployeeSalary", back_populates="employee")
    relatives = relationship("EmployeeRelative", back_populates="employee")
    additional_info = relationship("EmployeeAdditionalInfo", back_populates="employee", uselist=False)
    permissions = relationship("EmployeePermissions", back_populates="employee", uselist=False)
    access_settings = relationship("EmployeeAccess", back_populates="employee", uselist=False)
    leave_policy_assignments = relationship("EmployeeLeavePolicy", back_populates="employee")

    @property
    def full_name(self):
        """Get employee full name"""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    @property
    def display_name(self):
        """Get display name for UI"""
        return f"{self.full_name} ({self.employee_code})"


class EmployeeProfile(Base):
    """Extended employee profile information"""
    __tablename__ = "employee_profiles"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), unique=True, nullable=False)
    
    # Address Information
    present_address_line1 = Column(String(255))
    present_address_line2 = Column(String(255))
    present_city = Column(String(100))
    present_state = Column(String(100))
    present_country = Column(String(100))
    present_pincode = Column(String(20))
    
    permanent_address_line1 = Column(String(255))
    permanent_address_line2 = Column(String(255))
    permanent_city = Column(String(100))
    permanent_state = Column(String(100))
    permanent_country = Column(String(100))
    permanent_pincode = Column(String(20))
    
    # Statutory Information
    pan_number = Column(String(20), unique=True)
    aadhaar_number = Column(String(20), unique=True)
    uan_number = Column(String(20))
    esi_number = Column(String(20))
    
    # Bank Information
    bank_name = Column(String(255))
    bank_account_number = Column(String(50))
    bank_ifsc_code = Column(String(20))
    bank_branch = Column(String(255))
    
    # Emergency Contact
    emergency_contact_name = Column(String(255))
    emergency_contact_relationship = Column(String(100))
    emergency_contact_mobile = Column(String(20))
    emergency_contact_address = Column(Text)
    
    # Additional Information
    profile_image_url = Column(String(500))
    bio = Column(Text)
    skills = Column(Text)  # JSON string
    certifications = Column(Text)  # JSON string
    wedding_date = Column(Date)  # Wedding anniversary date
    vaccination_status = Column(String(20), default="Not Vaccinated")  # Vaccinated or Not Vaccinated
    kyc_completed = Column(Boolean, default=False)  # KYC completion status
    
    # Workman Status Information
    workman_installed = Column(Boolean, default=False)  # Whether workman is installed
    workman_version = Column(String(50), default="Not Installed")  # Workman version
    workman_last_seen = Column(DateTime(timezone=True))  # Last seen timestamp
    
    # System Fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    employee = relationship("Employee", back_populates="profile")


class EmployeeDocument(Base):
    """Employee document storage"""
    __tablename__ = "employee_documents"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    document_type = Column(String(100), nullable=False)  # resume, id_proof, address_proof, etc.
    document_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255))  # Store original filename for proper downloads
    file_size = Column(Integer)
    mime_type = Column(String(100))
    
    # Visibility flag
    hidden = Column(Boolean, default=False)
    
    # System Fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    employee = relationship("Employee", back_populates="documents")


class EmployeeSalary(Base):
    """Employee salary information"""
    __tablename__ = "employee_salaries"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Salary Structure
    salary_structure_id = Column(Integer, ForeignKey("salary_structures.id"))
    basic_salary = Column(Numeric(15, 2), nullable=False)
    gross_salary = Column(Numeric(15, 2), nullable=False)
    ctc = Column(Numeric(15, 2), nullable=False)
    
    # Individual Allowance Components
    house_rent_allowance = Column(Numeric(15, 2), default=0)
    special_allowance = Column(Numeric(15, 2), default=0)
    medical_allowance = Column(Numeric(15, 2), default=0)
    conveyance_allowance = Column(Numeric(15, 2), default=0)
    telephone_allowance = Column(Numeric(15, 2), default=0)
    
    # Employer Benefits
    group_insurance = Column(Numeric(15, 2), default=0)
    gratuity = Column(Numeric(15, 2), default=0)
    
    # Salary Options (JSON storage for all toggle settings)
    salary_options = Column(JSON, default={})
    
    # Effective Period
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    
    # System Fields
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    employee = relationship("Employee", back_populates="salary_records")
    salary_structure = relationship("SalaryStructure")

