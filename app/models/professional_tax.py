"""
Professional Tax Model
State-wise professional tax configuration
"""

from sqlalchemy import Column, Integer, String, Boolean, Float, Date, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ProfessionalTaxSettings(BaseModel):
    """Professional Tax Settings - Main configuration"""
    
    __tablename__ = "professional_tax_settings"
    
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    calculation_base = Column(String(50), default="Gross Salary")  # Gross Salary, Earned Salary
    
    # Relationships
    business = relationship("Business", back_populates="professional_tax_settings")
    component_mappings = relationship("PTComponentMapping", back_populates="pt_settings", cascade="all, delete-orphan")
    tax_rates = relationship("ProfessionalTaxRate", back_populates="pt_settings", cascade="all, delete-orphan")


class PTComponentMapping(BaseModel):
    """PT Component Mapping - Which salary components are included"""
    
    __tablename__ = "pt_component_mappings"
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)    
    pt_settings_id = Column(Integer, ForeignKey("professional_tax_settings.id"), nullable=False, index=True)
    component_name = Column(String(100), nullable=False)
    component_code = Column(String(50), nullable=False)
    component_type = Column(String(50), nullable=False)  # Payable Days, Variable
    is_selected = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    pt_settings = relationship("ProfessionalTaxSettings", back_populates="component_mappings")


class ProfessionalTaxRate(BaseModel):
    """Professional Tax Rates - State-wise tax slabs"""
    
    __tablename__ = "professional_tax_rates"
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    pt_settings_id = Column(Integer, ForeignKey("professional_tax_settings.id"), nullable=False, index=True)
    state = Column(String(100), nullable=False, index=True)
    effective_from = Column(Date, nullable=False)
    salary_above = Column(Float, nullable=False, default=0.0)
    month = Column(String(50), default="All Months", nullable=False)  # All Months, January, February, etc.
    gender = Column(String(50), default="All Genders", nullable=False)  # All Genders, Male, Female, Other
    tax_amount = Column(Float, nullable=False)
    
    # Relationships
    pt_settings = relationship("ProfessionalTaxSettings", back_populates="tax_rates")
