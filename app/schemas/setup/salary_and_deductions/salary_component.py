from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum


class UnitTypeEnum(str, Enum):
    PAID_DAYS = "Paid Days"
    FIXED = "Fixed"
    MONTHLY = "Monthly"


class SalaryComponentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Component name")
    alias: str = Field(..., min_length=1, max_length=50, description="Short name/alias")
    component_type: str = Field(..., min_length=1, max_length=50, description="Component type (Fixed/Variable/Deduction)")
    unit_type: UnitTypeEnum = Field(..., description="Unit type for calculation")
    is_lwf_applicable: bool = Field(default=False, description="LWF applicable flag")

    exclude_holidays: bool = Field(default=False, description="Exclude holidays from calculation")
    exclude_weekoffs: bool = Field(default=False, description="Exclude weekoffs from calculation")
    active: bool = Field(default=True, description="Active status")
    exclude_from_gross: bool = Field(default=False, description="Exclude from gross salary")
    hide_in_ctc_reports: bool = Field(default=False, description="Hide in CTC reports")
    not_payable: bool = Field(default=False, description="Not payable flag")

    @field_validator('name', 'alias', 'component_type')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure string fields are not empty or whitespace only"""
        if not v or not v.strip():
            raise ValueError('Field cannot be empty or whitespace only')
        return v.strip()


# ---------- CREATE ----------
class SalaryComponentCreate(SalaryComponentBase):
    pass


# ---------- UPDATE ----------
class SalaryComponentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    alias: Optional[str] = Field(None, min_length=1, max_length=50)
    unit_type: Optional[UnitTypeEnum] = None
    is_lwf_applicable: Optional[bool] = None

    exclude_holidays: Optional[bool] = None
    exclude_weekoffs: Optional[bool] = None
    active: Optional[bool] = None
    exclude_from_gross: Optional[bool] = None
    hide_in_ctc_reports: Optional[bool] = None
    not_payable: Optional[bool] = None

    @field_validator('name', 'alias')
    @classmethod
    def validate_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure string fields are not empty or whitespace only if provided"""
        if v is not None and (not v or not v.strip()):
            raise ValueError('Field cannot be empty or whitespace only')
        return v.strip() if v else v

    # business_id should never be editable → NOT included


# ---------- RESPONSE ----------
class SalaryComponentOut(SalaryComponentBase):
    id: int
    business_id: int

    class Config:
        from_attributes = True
