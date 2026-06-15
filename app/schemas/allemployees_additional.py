"""
Additional All Employees Schemas
Pydantic models for employee API endpoints that were missing proper schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, date


# ============================================================================
# Salary Revision Delete Schema
# ============================================================================

class SalaryRevisionDeleteRequest(BaseModel):
    """Salary revision delete request"""
    effectiveDate: str = Field(..., description="Effective date of the revision to delete in YYYY-MM-DD or ISO format", example="2026-02-19")
    
    @field_validator('effectiveDate')
    @classmethod
    def validate_effective_date(cls, v):
        """Validate effective date format"""
        if not v:
            raise ValueError("effectiveDate is required")
        
        # Try ISO format first
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except:
            pass
        
        # Try YYYY-MM-DD format
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except:
            raise ValueError("Invalid date format. Use YYYY-MM-DD or ISO format")
    
    class Config:
        json_schema_extra = {
            "example": {
                "effectiveDate": "2026-02-19"
            }
        }


# ============================================================================
# Work Profile Revision Schema
# ============================================================================

class WorkProfileRevisionRequest(BaseModel):
    """Work profile revision request"""
    month: Optional[int] = Field(None, description="Month (1-12)", ge=1, le=12, example=2)
    year: Optional[int] = Field(None, description="Year", ge=2020, le=2030, example=2026)
    businessId: Optional[int] = Field(None, description="Business ID", gt=0, example=1)
    locationId: Optional[int] = Field(None, description="Location ID", gt=0, example=1)
    costCenterId: Optional[int] = Field(None, description="Cost center ID", gt=0, example=1)
    departmentId: Optional[int] = Field(None, description="Department ID", gt=0, example=1)
    designationId: Optional[int] = Field(None, description="Designation ID", gt=0, example=1)
    gradeId: Optional[int] = Field(None, description="Grade ID", gt=0, example=1)
    reportingManagerId: Optional[int] = Field(None, description="Reporting Manager ID", example=10)
    hrManagerId: Optional[int] = Field(None, description="HR Manager ID", example=11)
    indirectManagerId: Optional[int] = Field(None, description="Indirect Manager ID", example=12)
    isPromotion: Optional[bool] = Field(False, description="Is this a promotion?", example=False)
    promotion: Optional[bool] = Field(None, description="Is this a promotion?", example=False)
    promation: Optional[bool] = Field(None, description="Is this a promotion?", example=False)
    effectiveFrom: Optional[str] = Field(None, description="Effective from date (format month and year)", example="2026-02")
    effective_from: Optional[str] = Field(None, description="Effective from date (format month and year)", example="2026-02")
    employmentType: Optional[str] = Field(None, description="Employment type", max_length=50, example="Full-time")
    notes: Optional[str] = Field(None, description="Revision notes", max_length=500, example="Promoted to Senior Developer")
    
    @field_validator('month')
    @classmethod
    def validate_month(cls, v):
        """Validate month"""
        if v is not None and (v < 1 or v > 12):
            raise ValueError("Month must be between 1 and 12")
        return v
    
    @field_validator('year')
    @classmethod
    def validate_year(cls, v):
        """Validate year"""
        if v is not None and (v < 2020 or v > 2030):
            raise ValueError("Year must be between 2020 and 2030")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "month": 2,
                "year": 2026,
                "businessId": 1,
                "locationId": 1,
                "costCenterId": 1,
                "departmentId": 1,
                "designationId": 1,
                "gradeId": 1,
                "employmentType": "Full-time",
                "notes": "Promoted to Senior Developer",
                "promotion": True,
                "effective_from": "2026-02"
            }
        }


# ============================================================================
# Manager Update Schema
# ============================================================================

class ManagerUpdateRequest(BaseModel):
    """Manager update request"""
    managerId: int = Field(..., description="Manager ID (use 0 or null to remove manager)", example=456)
    
    @field_validator('managerId')
    @classmethod
    def validate_manager_id(cls, v):
        """Validate manager ID"""
        if v is not None and v < 0:
            raise ValueError("Manager ID must be 0 or positive")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "managerId": 456
            }
        }
