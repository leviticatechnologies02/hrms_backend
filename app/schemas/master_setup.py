"""
Master Setup Schemas
Pydantic schemas for Master Setup API
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List, Any
from datetime import datetime


# ============================================================================
# Department Schemas
# ============================================================================

class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    head: Optional[str] = Field(None, max_length=255)
    deputy_head: Optional[str] = Field(None, max_length=255)
    is_default: bool = Field(default=False)
    
    @model_validator(mode='before')
    @classmethod
    def trim_strings(cls, data: Any) -> Any:
        """Trim whitespace from string fields and validate"""
        if isinstance(data, dict):
            # Trim and validate name
            if 'name' in data and isinstance(data['name'], str):
                trimmed = data['name'].strip()
                if not trimmed:
                    raise ValueError('name cannot be empty or whitespace only')
                data['name'] = trimmed
            
            # Trim and validate head (optional)
            if 'head' in data and data['head'] is not None and isinstance(data['head'], str):
                trimmed = data['head'].strip()
                if not trimmed:
                    data['head'] = None  # Convert empty to None
                else:
                    data['head'] = trimmed
            
            # Trim deputy_head (optional)
            if 'deputy_head' in data and data['deputy_head'] is not None and isinstance(data['deputy_head'], str):
                trimmed = data['deputy_head'].strip()
                data['deputy_head'] = trimmed if trimmed else None
        
        return data


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    head: Optional[str] = Field(None, min_length=1, max_length=255)
    deputy_head: Optional[str] = Field(None, max_length=255)
    is_default: Optional[bool] = None
    employees: Optional[int] = Field(None, ge=0)
    
    @model_validator(mode='before')
    @classmethod
    def trim_strings(cls, data: Any) -> Any:
        """Trim whitespace from string fields and validate"""
        if isinstance(data, dict):
            # Trim and validate name (if provided)
            if 'name' in data and data['name'] is not None and isinstance(data['name'], str):
                trimmed = data['name'].strip()
                if not trimmed:
                    raise ValueError('name cannot be empty or whitespace only')
                data['name'] = trimmed
            
            # Trim and validate head (if provided)
            if 'head' in data and data['head'] is not None and isinstance(data['head'], str):
                trimmed = data['head'].strip()
                if not trimmed:
                    raise ValueError('head cannot be empty or whitespace only')
                data['head'] = trimmed
            
            # Trim deputy_head (optional, if provided)
            if 'deputy_head' in data and data['deputy_head'] is not None and isinstance(data['deputy_head'], str):
                trimmed = data['deputy_head'].strip()
                data['deputy_head'] = trimmed if trimmed else None
        
        return data


class DepartmentResponse(DepartmentBase):
    id: int
    business_id: int
    employees: int = Field(default=0)
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Location Schemas
# ============================================================================

class LocationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    state: str = Field(..., min_length=1, max_length=100)
    location_head: Optional[str] = Field(None, max_length=255)
    deputy_head: Optional[str] = Field(None, max_length=255)
    is_default: bool = Field(default=False)
    map_url: Optional[str] = Field(None, max_length=500)
    
    @model_validator(mode='before')
    @classmethod
    def trim_strings(cls, data: Any) -> Any:
        """Trim whitespace from string fields and validate"""
        if isinstance(data, dict):
            # Trim and validate name
            if 'name' in data and isinstance(data['name'], str):
                trimmed = data['name'].strip()
                if not trimmed:
                    raise ValueError('name cannot be empty or whitespace only')
                data['name'] = trimmed
            
            # Trim and validate state
            if 'state' in data and isinstance(data['state'], str):
                trimmed = data['state'].strip()
                if not trimmed:
                    raise ValueError('state cannot be empty or whitespace only')
                data['state'] = trimmed
            
            # Trim optional fields
            for field in ['location_head', 'deputy_head', 'map_url']:
                if field in data and isinstance(data[field], str):
                    trimmed = data[field].strip()
                    data[field] = trimmed if trimmed else None
        
        return data


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    state: Optional[str] = Field(None, min_length=1, max_length=100)
    location_head: Optional[str] = Field(None, max_length=255)
    deputy_head: Optional[str] = Field(None, max_length=255)
    is_default: Optional[bool] = None
    map_url: Optional[str] = Field(None, max_length=500)
    employees: Optional[int] = Field(None, ge=0)
    
    @model_validator(mode='before')
    @classmethod
    def trim_strings(cls, data: Any) -> Any:
        """Trim whitespace from string fields and validate"""
        if isinstance(data, dict):
            # Trim and validate name (if provided)
            if 'name' in data and data['name'] is not None and isinstance(data['name'], str):
                trimmed = data['name'].strip()
                if not trimmed:
                    raise ValueError('name cannot be empty or whitespace only')
                data['name'] = trimmed
            
            # Trim and validate state (if provided)
            if 'state' in data and data['state'] is not None and isinstance(data['state'], str):
                trimmed = data['state'].strip()
                if not trimmed:
                    raise ValueError('state cannot be empty or whitespace only')
                data['state'] = trimmed
            
            # Trim optional fields
            for field in ['location_head', 'deputy_head', 'map_url']:
                if field in data and data[field] is not None and isinstance(data[field], str):
                    trimmed = data[field].strip()
                    data[field] = trimmed if trimmed else None
        
        return data


class LocationResponse(LocationBase):
    id: int
    business_id: int
    employees: int = Field(default=0)
    qr_code_url: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Grade Schemas
# ============================================================================

class GradeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    
    @model_validator(mode='before')
    @classmethod
    def trim_strings(cls, data: Any) -> Any:
        """Trim whitespace from string fields and validate"""
        if isinstance(data, dict):
            if 'name' in data and isinstance(data['name'], str):
                trimmed = data['name'].strip()
                if not trimmed:
                    raise ValueError('name cannot be empty or whitespace only')
                data['name'] = trimmed
        return data


class GradeCreate(GradeBase):
    pass


class GradeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    employees: Optional[int] = Field(None, ge=0)
    
    @model_validator(mode='before')
    @classmethod
    def trim_strings(cls, data: Any) -> Any:
        """Trim whitespace from string fields and validate"""
        if isinstance(data, dict):
            if 'name' in data and data['name'] is not None and isinstance(data['name'], str):
                trimmed = data['name'].strip()
                if not trimmed:
                    raise ValueError('name cannot be empty or whitespace only')
                data['name'] = trimmed
        return data


class GradeResponse(GradeBase):
    id: int
    business_id: int
    employees: int = Field(default=0)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Designation Schemas
# ============================================================================

class DesignationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    default: bool = Field(default=False)
    
    @model_validator(mode='before')
    @classmethod
    def trim_strings(cls, data: Any) -> Any:
        """Trim whitespace from string fields and validate"""
        if isinstance(data, dict):
            if 'name' in data and isinstance(data['name'], str):
                trimmed = data['name'].strip()
                if not trimmed:
                    raise ValueError('name cannot be empty or whitespace only')
                data['name'] = trimmed
        return data


class DesignationCreate(DesignationBase):
    pass


class DesignationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    default: Optional[bool] = None
    employees: Optional[int] = Field(None, ge=0)
    
    @model_validator(mode='before')
    @classmethod
    def trim_strings(cls, data: Any) -> Any:
        """Trim whitespace from string fields and validate"""
        if isinstance(data, dict):
            if 'name' in data and data['name'] is not None and isinstance(data['name'], str):
                trimmed = data['name'].strip()
                if not trimmed:
                    raise ValueError('name cannot be empty or whitespace only')
                data['name'] = trimmed
        return data


class DesignationResponse(DesignationBase):
    id: int
    business_id: int
    employees: int = Field(default=0)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Cost Center Schemas
# ============================================================================

class CostCenterBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Cost center name")
    is_default: bool = Field(default=False, description="Whether this is the default cost center")
    
    @model_validator(mode='before')
    @classmethod
    def trim_strings(cls, data: Any) -> Any:
        """Trim whitespace from string fields and validate"""
        if isinstance(data, dict):
            if 'name' in data and isinstance(data['name'], str):
                trimmed = data['name'].strip()
                if not trimmed:
                    raise ValueError('name cannot be empty or whitespace only')
                data['name'] = trimmed
        return data


class CostCenterCreate(CostCenterBase):
    pass


class CostCenterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Cost center name")
    is_default: Optional[bool] = Field(None, description="Whether this is the default cost center")
    # Note: employees count is auto-calculated, not manually updatable
    # Note: business_id cannot be changed after creation
    
    @model_validator(mode='before')
    @classmethod
    def trim_strings(cls, data: Any) -> Any:
        """Trim whitespace from string fields and validate"""
        if isinstance(data, dict):
            if 'name' in data and data['name'] is not None and isinstance(data['name'], str):
                trimmed = data['name'].strip()
                if not trimmed:
                    raise ValueError('name cannot be empty or whitespace only')
                data['name'] = trimmed
        return data


class CostCenterResponse(CostCenterBase):
    id: int
    business_id: int
    employees: int = Field(default=0, ge=0, description="Number of employees assigned to this cost center")
    is_active: bool = Field(default=True)
    created_at: Optional[str] = Field(None, description="Creation timestamp in ISO format")
    updated_at: Optional[str] = Field(None, description="Last update timestamp in ISO format")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Work Shift Schemas
# ============================================================================

class WorkShiftBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    payable_hours: str = Field(..., min_length=1, max_length=50)
    rules: int = Field(default=0)
    is_default: bool = Field(default=False)
    timing: Optional[str] = Field(None, max_length=100)
    start_buffer: int = Field(default=0, ge=0, le=5)
    end_buffer: int = Field(default=0, ge=0, le=5)


class WorkShiftCreate(WorkShiftBase):
    pass


class WorkShiftUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    payable_hours: Optional[str] = Field(None, min_length=1, max_length=50)
    rules: Optional[int] = None
    is_default: Optional[bool] = None
    timing: Optional[str] = Field(None, max_length=100)
    start_buffer: Optional[int] = Field(None, ge=0, le=5)
    end_buffer: Optional[int] = Field(None, ge=0, le=5)


class WorkShiftResponse(WorkShiftBase):
    id: int
    business_id: int
    start_buffer: int = Field(default=0)
    end_buffer: int = Field(default=0)
    is_active: bool = Field(default=True)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Visit Type Schemas
# ============================================================================

class VisitTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class VisitTypeCreate(VisitTypeBase):
    pass


# ============================================================================
# Master Policy Schemas
# ============================================================================


class MasterPolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    type: Optional[str] = None
    is_mandatory: Optional[bool] = False
    requires_acknowledgment: Optional[bool] = False
    file_path: Optional[str] = None


class MasterPolicyResponse(BaseModel):
    id: int
    business_id: int
    name: str
    description: Optional[str] = None
    type: Optional[str] = None
    is_mandatory: bool = False
    requires_acknowledgment: bool = False
    file_path: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MasterPolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    is_mandatory: Optional[bool] = None
    requires_acknowledgment: Optional[bool] = None
    file_path: Optional[str] = None


class VisitTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)


class VisitTypeResponse(VisitTypeBase):
    id: int
    business_id: int
    is_active: bool = Field(default=True)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Helpdesk Category Schemas
# ============================================================================

class HelpdeskCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    primary_approver: Optional[str] = Field(None, max_length=255)
    backup_approver: Optional[str] = Field(None, max_length=255)
    is_active: bool = Field(default=True)


class HelpdeskCategoryCreate(HelpdeskCategoryBase):
    pass


class HelpdeskCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    primary_approver: Optional[str] = Field(None, max_length=255)
    backup_approver: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class HelpdeskCategoryResponse(HelpdeskCategoryBase):
    id: int
    business_id: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Employee Code Config Schemas
# ============================================================================

class EmployeeCodeConfigBase(BaseModel):
    auto_code: bool = Field(default=True)
    prefix: str = Field(..., min_length=1, max_length=10)
    length: int = Field(..., ge=1, le=20)
    suffix: Optional[str] = Field(None, max_length=10)


class EmployeeCodeConfigCreate(EmployeeCodeConfigBase):
    pass


class EmployeeCodeConfigUpdate(BaseModel):
    auto_code: Optional[bool] = None
    prefix: Optional[str] = Field(None, min_length=1, max_length=10)
    length: Optional[int] = Field(None, ge=1, le=20)
    suffix: Optional[str] = Field(None, max_length=10)


class EmployeeCodeConfigResponse(EmployeeCodeConfigBase):
    id: int
    business_id: int
    preview_codes: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Exit Reason Schemas
# ============================================================================

class ExitReasonBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    esi_mapping: Optional[str] = Field(None, max_length=255)


class ExitReasonCreate(ExitReasonBase):
    pass


class ExitReasonUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    esi_mapping: Optional[str] = Field(None, max_length=255)


class ExitReasonResponse(ExitReasonBase):
    id: int
    business_id: int
    is_active: bool = Field(default=True)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Business Unit Schemas
# ============================================================================

class BusinessUnitBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    is_default: bool = Field(default=False)
    report_title: str = Field(..., min_length=1, max_length=255)
    
    @model_validator(mode='before')
    @classmethod
    def trim_strings(cls, data: Any) -> Any:
        """Trim whitespace from string fields and validate"""
        if isinstance(data, dict):
            if 'name' in data and isinstance(data['name'], str):
                trimmed = data['name'].strip()
                if not trimmed:
                    raise ValueError('name cannot be empty or whitespace only')
                data['name'] = trimmed
            
            if 'report_title' in data and isinstance(data['report_title'], str):
                trimmed = data['report_title'].strip()
                if not trimmed:
                    raise ValueError('report_title cannot be empty or whitespace only')
                data['report_title'] = trimmed
        return data


class BusinessUnitCreate(BusinessUnitBase):
    pass


class BusinessUnitUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_default: Optional[bool] = None
    report_title: Optional[str] = Field(None, min_length=1, max_length=255)
    
    @model_validator(mode='before')
    @classmethod
    def trim_strings(cls, data: Any) -> Any:
        """Trim whitespace from string fields and validate"""
        if isinstance(data, dict):
            if 'name' in data and data['name'] is not None and isinstance(data['name'], str):
                trimmed = data['name'].strip()
                if not trimmed:
                    raise ValueError('name cannot be empty or whitespace only')
                data['name'] = trimmed
            
            if 'report_title' in data and data['report_title'] is not None and isinstance(data['report_title'], str):
                trimmed = data['report_title'].strip()
                if not trimmed:
                    raise ValueError('report_title cannot be empty or whitespace only')
                data['report_title'] = trimmed
        return data
    report_title: Optional[str] = Field(None, min_length=1, max_length=255)
    employees: Optional[int] = Field(None, ge=0)
    header_image_url: Optional[str] = None  # Removed max_length to support base64
    footer_image_url: Optional[str] = None  # Removed max_length to support base64


class BusinessUnitResponse(BusinessUnitBase):
    id: int
    business_id: int
    company: Optional[str] = Field(None, description="Business/Company name")
    employees: int = Field(default=0)
    header_image: Optional[str] = None
    footer_image: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)