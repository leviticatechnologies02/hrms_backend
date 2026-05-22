"""
Data Capture Models
Employee data capture and management data models
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Date, ForeignKey, Text, Numeric, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
import enum
from datetime import datetime


class SalaryVariableType(str, enum.Enum):
    ALLOWANCE = "allowance"
    BONUS = "bonus"
    INCENTIVE = "incentive"
    COMMISSION = "commission"
    OVERTIME = "overtime"
    OTHER = "other"


class DeductionType(str, enum.Enum):
    TAX = "tax"
    INSURANCE = "insurance"
    LOAN = "loan"
    ADVANCE = "advance"
    FINE = "fine"
    OTHER = "other"


class LoanStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DEFAULTED = "defaulted"
    CANCELLED = "cancelled"


class ITDeclarationStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class SalaryVariable(Base):
    """Salary variable components for employees"""
    __tablename__ = "salary_variables"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Variable details
    variable_name = Column(String(255), nullable=False)
    variable_type = Column(Enum(SalaryVariableType), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    
    # Period details
    effective_date = Column(Date, nullable=False)
    end_date = Column(Date)
    is_recurring = Column(Boolean, default=False)
    frequency = Column(String(50))  # monthly, quarterly, yearly
    
    # Additional details
    description = Column(Text)
    is_taxable = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    employee = relationship("Employee")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])


class SalaryUnit(Base):
    """Salary unit configurations"""
    __tablename__ = "salary_units"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    
    # Unit details
    unit_name = Column(String(255), nullable=False)
    unit_code = Column(String(50), nullable=False)
    unit_type = Column(String(100), nullable=False)  # hourly, daily, monthly, piece_rate
    base_rate = Column(Numeric(10, 2), nullable=False)
    
    # Configuration
    description = Column(Text)
    is_overtime_applicable = Column(Boolean, default=False)
    overtime_multiplier = Column(Numeric(5, 2), default=1.5)
    is_active = Column(Boolean, default=True)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    creator = relationship("User")


class EmployeeSalaryUnit(Base):
    """Employee salary units - linking employees to salary units with amounts"""
    __tablename__ = "employee_salary_units"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Salary unit details
    unit_name = Column(String(255), nullable=False)
    unit_type = Column(String(100), nullable=False)  # travel, allowance, bonus, etc.
    amount = Column(Numeric(15, 2), nullable=False, default=0)
    
    # Period and configuration
    effective_date = Column(Date, nullable=False)
    end_date = Column(Date)
    comments = Column(Text)
    is_arrear = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    employee = relationship("Employee")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])


class EmployeeDeduction(Base):
    """Employee-specific deductions"""
    __tablename__ = "employee_deductions"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Deduction details
    deduction_name = Column(String(255), nullable=False)
    deduction_type = Column(Enum(DeductionType), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    
    # Period details
    effective_date = Column(Date, nullable=False)
    end_date = Column(Date)
    is_recurring = Column(Boolean, default=True)
    frequency = Column(String(50), default="monthly")
    
    # Additional details
    description = Column(Text)
    reference_number = Column(String(100))
    is_active = Column(Boolean, default=True)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    employee = relationship("Employee")
    creator = relationship("User")


class IncomeTaxTDS(Base):
    """Income tax TDS records"""
    __tablename__ = "income_tax_tds"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # TDS details
    financial_year = Column(String(10), nullable=False)  # 2023-24
    quarter = Column(String(10), nullable=False)  # Q1, Q2, Q3, Q4
    gross_salary = Column(Numeric(15, 2), nullable=False)
    taxable_income = Column(Numeric(15, 2), nullable=False)
    tds_amount = Column(Numeric(15, 2), nullable=False)
    
    # Tax computation
    tax_slab_rate = Column(Numeric(5, 2))
    exemptions = Column(Numeric(15, 2), default=0)
    deductions_80c = Column(Numeric(15, 2), default=0)
    other_deductions = Column(Numeric(15, 2), default=0)
    
    # Additional details
    challan_number = Column(String(100))
    deposit_date = Column(Date)
    remarks = Column(Text)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    employee = relationship("Employee")
    creator = relationship("User")


class ExtraDay(Base):
    """Extra working days records"""
    __tablename__ = "extra_days"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Extra day details
    work_date = Column(Date, nullable=False)
    hours_worked = Column(Numeric(5, 2), nullable=False)
    hourly_rate = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(15, 2), nullable=False)
    
    # Work details
    work_description = Column(Text)
    location = Column(String(255))
    approved_by = Column(Integer, ForeignKey("users.id"))
    approval_date = Column(Date)
    
    # Status
    is_approved = Column(Boolean, default=False)
    is_paid = Column(Boolean, default=False)
    payment_date = Column(Date)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    employee = relationship("Employee")
    approver = relationship("User", foreign_keys=[approved_by])
    creator = relationship("User", foreign_keys=[created_by])


class ExtraHour(Base):
    """Extra working hours records"""
    __tablename__ = "extra_hours"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Extra hour details
    work_date = Column(Date, nullable=False)
    regular_hours = Column(Numeric(5, 2), default=8.0)
    extra_hours = Column(Numeric(5, 2), nullable=False)
    overtime_rate = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(15, 2), nullable=False)
    
    # Work details
    start_time = Column(String(10))  # HH:MM
    end_time = Column(String(10))    # HH:MM
    work_description = Column(Text)
    approved_by = Column(Integer, ForeignKey("users.id"))
    approval_date = Column(Date)
    
    # Status
    is_approved = Column(Boolean, default=False)
    is_paid = Column(Boolean, default=False)
    payment_date = Column(Date)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    employee = relationship("Employee")
    approver = relationship("User", foreign_keys=[approved_by])
    creator = relationship("User", foreign_keys=[created_by])


class EmployeeLoan(Base):
    """Employee loan records"""
    __tablename__ = "employee_loans"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Loan details
    loan_type = Column(String(100), nullable=False)
    loan_amount = Column(Numeric(15, 2), nullable=False)
    interest_rate = Column(Numeric(5, 2), default=0)
    tenure_months = Column(Integer, nullable=False)
    emi_amount = Column(Numeric(15, 2), nullable=False)
    
    # Dates
    loan_date = Column(Date, nullable=False)
    first_emi_date = Column(Date, nullable=False)
    last_emi_date = Column(Date)
    
    # Status tracking
    status = Column(Enum(LoanStatus), default=LoanStatus.ACTIVE)
    outstanding_amount = Column(Numeric(15, 2), nullable=False)
    paid_amount = Column(Numeric(15, 2), default=0)
    paid_emis = Column(Integer, default=0)
    remaining_emis = Column(Integer, nullable=False)
    
    # Additional details
    purpose = Column(Text)
    guarantor_name = Column(String(255))
    guarantor_relation = Column(String(100))
    approved_by = Column(Integer, ForeignKey("users.id"))
    approval_date = Column(Date)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    employee = relationship("Employee")
    approver = relationship("User", foreign_keys=[approved_by])
    creator = relationship("User", foreign_keys=[created_by])
    
    # Related records
    emi_payments = relationship("LoanEMIPayment", back_populates="loan")


class LoanEMIPayment(Base):
    """Loan EMI payment records"""
    __tablename__ = "loan_emi_payments"

    id = Column(Integer, primary_key=True, index=True)
    loan_id = Column(Integer, ForeignKey("employee_loans.id"), nullable=False)
    
    # Payment details
    emi_number = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    paid_date = Column(Date)
    emi_amount = Column(Numeric(15, 2), nullable=False)
    principal_amount = Column(Numeric(15, 2), nullable=False)
    interest_amount = Column(Numeric(15, 2), nullable=False)
    
    # Status
    is_paid = Column(Boolean, default=False)
    payment_method = Column(String(50))  # salary_deduction, cash, bank_transfer
    remarks = Column(Text)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    loan = relationship("EmployeeLoan", back_populates="emi_payments")


class ITDeclaration(Base):
    """Income tax declarations by employees"""
    __tablename__ = "it_declarations"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Declaration details
    financial_year = Column(String(10), nullable=False)  # 2023-24
    status = Column(Enum(ITDeclarationStatus), default=ITDeclarationStatus.DRAFT)
    
    # Section 80C deductions
    pf_amount = Column(Numeric(15, 2), default=0)
    life_insurance = Column(Numeric(15, 2), default=0)
    elss_mutual_funds = Column(Numeric(15, 2), default=0)
    home_loan_principal = Column(Numeric(15, 2), default=0)
    tuition_fees = Column(Numeric(15, 2), default=0)
    other_80c = Column(Numeric(15, 2), default=0)
    total_80c = Column(Numeric(15, 2), default=0)
    
    # Other deductions
    section_80d_medical = Column(Numeric(15, 2), default=0)
    section_24_home_loan_interest = Column(Numeric(15, 2), default=0)
    section_80g_donations = Column(Numeric(15, 2), default=0)
    hra_exemption = Column(Numeric(15, 2), default=0)
    
    # House rent details
    rent_paid = Column(Numeric(15, 2), default=0)
    landlord_name = Column(String(255))
    landlord_pan = Column(String(20))
    
    # Submission details
    submitted_at = Column(DateTime)
    approved_at = Column(DateTime)
    approved_by = Column(Integer, ForeignKey("users.id"))
    rejection_reason = Column(Text)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    employee = relationship("Employee")
    approver = relationship("User", foreign_keys=[approved_by])
    creator = relationship("User", foreign_keys=[created_by])


class TDSChallan(Base):
    """TDS challan records"""
    __tablename__ = "tds_challans"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    
    # Challan details
    challan_number = Column(String(100), nullable=False, unique=True)
    financial_year = Column(String(10), nullable=False)
    quarter = Column(String(10), nullable=False)
    deposit_date = Column(Date, nullable=False)
    
    # Amount details
    tds_amount = Column(Numeric(15, 2), nullable=False)
    interest = Column(Numeric(15, 2), default=0)
    penalty = Column(Numeric(15, 2), default=0)
    total_amount = Column(Numeric(15, 2), nullable=False)
    
    # Bank details
    bank_name = Column(String(255))
    branch_code = Column(String(20))
    
    # Additional details
    remarks = Column(Text)
    uploaded_file_path = Column(String(500))
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    creator = relationship("User")


class TDSReturn(Base):
    """TDS return filing records"""
    __tablename__ = "tds_returns"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    
    # Return details
    return_type = Column(String(20), nullable=False)  # 24Q, 26Q, 27Q, etc.
    financial_year = Column(String(10), nullable=False)
    quarter = Column(String(10), nullable=False)
    filing_date = Column(Date, nullable=False)
    
    # Filing details
    acknowledgment_number = Column(String(100))
    total_deductees = Column(Integer, default=0)
    total_tds_amount = Column(Numeric(15, 2), default=0)
    total_deposited = Column(Numeric(15, 2), default=0)
    
    # Status
    is_filed = Column(Boolean, default=False)
    is_revised = Column(Boolean, default=False)
    revision_number = Column(Integer, default=0)
    
    # File details
    return_file_path = Column(String(500))
    acknowledgment_file_path = Column(String(500))
    
    # Additional details
    remarks = Column(Text)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    creator = relationship("User")


class TravelRequestStatus(str, enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class TravelRequest(Base):
    """Employee travel request records"""
    __tablename__ = "travel_requests"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Travel details
    travel_date = Column(Date, nullable=False)
    from_location = Column(String(200))
    to_location = Column(String(200))
    purpose = Column(String(500))
    
    # Distance and allowance
    calculated_distance = Column(Numeric(10, 2), default=0.0)
    approved_distance = Column(Numeric(10, 2), default=0.0)
    travel_allowance = Column(Numeric(10, 2), default=0.0)
    
    # Status and approval
    status = Column(Enum(TravelRequestStatus), default=TravelRequestStatus.PENDING)
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime(timezone=True))
    rejection_reason = Column(Text)
    
    # Additional details
    vehicle_type = Column(String(100))  # Car, Bike, Public Transport, etc.
    mode_of_transport = Column(String(100))
    remarks = Column(Text)
    
    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    business = relationship("Business")
    employee = relationship("Employee")
    approver = relationship("User", foreign_keys=[approved_by])
    creator = relationship("User", foreign_keys=[created_by])


# Indexes for tenant isolation
Index("idx_salary_variables_business_id", SalaryVariable.business_id)
Index("idx_salary_units_business_id", SalaryUnit.business_id)
Index("idx_employee_salary_units_business_id", EmployeeSalaryUnit.business_id)
Index("idx_employee_deductions_business_id", EmployeeDeduction.business_id)
Index("idx_income_tax_tds_business_id", IncomeTaxTDS.business_id)
Index("idx_extra_days_business_id", ExtraDay.business_id)
Index("idx_extra_hours_business_id", ExtraHour.business_id)
Index("idx_employee_loans_business_id", EmployeeLoan.business_id)
Index("idx_it_declarations_business_id", ITDeclaration.business_id)
Index("idx_tds_challans_business_id", TDSChallan.business_id)
Index("idx_tds_returns_business_id", TDSReturn.business_id)
Index("idx_travel_requests_business_id", TravelRequest.business_id)