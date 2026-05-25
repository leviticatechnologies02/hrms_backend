"""
API Router - Aggregates all v1 routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.core.database import get_db
from app.api.v1.deps import get_current_admin, get_current_superadmin, get_current_user
from app.models.user import User

from .endpoints import auth, superadmin, health, files, registration, dev, business, employees, allemployees, dashboard, onboarding, separation, attendance, datacapture, bulkupdate, requests, hrmanagement, payroll, reports, setup_dashboard, crm, profile, master_setup, master_policies, salary_setup, calendar, project_management, notes, subscriptions, packages, domain, purchase_transaction, documents, help, support, system_stats, preferences, todo, contact_inquiry, public_location, password_reset
from .endpoints import otp

from app.api.v1.setup.mastersetup.workflows import router as workflows_router
from app.api.v1.setup.mastersetup.business_unit_files import router as business_unit_files_router
from app.api.v1.setup.salary_and_deductions.salary_components import router as salary_component_router
from app.api.v1.setup.salary_and_deductions.salary_deductions import router as salary_deduction_router
from app.api.v1.setup.salary_and_deductions.salary_structures import router as salary_structure_router
from app.api.v1.setup.salary_and_deductions.salary_structure_rules import router as salary_structure_rule_router
from app.api.v1.setup.salary_and_deductions.time_salary import router as time_salary_router
from app.api.v1.setup.salary_and_deductions.overtime import router as overtime_router
from .setup.Integrations import emailsettings, gatekeeper, sqlserver, api_access, sap_mapping
from app.api.v1.setup.Integrations import biometricsync
from app.api.v1.setup.employeeselfservice import approvals, user_management
from app.api.v1.setup import maintenance
from app.api.v1.setup.leaves_statutory import (
    attendance_settings,leave_types,
    holidays,
    compoff_rules,
    strike_rules,
    strike_adjustments,
    leave_policies,
    esi_settings,
    epf_settings,
    professional_tax,
    form16,
    tds24q,lwf,tax
)




#=======================================================================
api_router = APIRouter()

# ============================================================================
# 1. User Registration
# ============================================================================

api_router.include_router(
    registration.router,
    tags=["User Registration"]
)

# ============================================================================
# 1.1. Password Reset (Forgot Password)
# ============================================================================

api_router.include_router(
    password_reset.router,
    tags=["Password Reset"]
)

# ============================================================================
# 1.2. Contact Inquiry (PUBLIC - No Auth Required)
# ============================================================================

api_router.include_router(
    contact_inquiry.router,
    prefix="/contact-inquiry",
    tags=["Contact Inquiry"]
)

# ============================================================================
# 1.2. Public Location Info (PUBLIC - No Auth Required)
# ============================================================================

api_router.include_router(
    public_location.router,
    prefix="/public",
    tags=["Public"]
)

# ============================================================================
# 2. Authentication
# ============================================================================

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)
# ============================================================================
# 16. Master Setup (Direct endpoints used by frontend)
# ============================================================================

api_router.include_router(
    master_setup.router,
    tags=["Master Setup"]
)

api_router.include_router(
    master_policies.router,
    tags=["Master Setup"]
)

# ============================================================================
# 16.1. Workflows (Under Master Setup)
# ============================================================================

api_router.include_router(
    workflows_router,
    prefix="/{business_id}/workflows",
    tags=["Master Setup"],
    dependencies=[Depends(get_current_admin)],
)
 
# ============================================================================
# 15. Setup
# ============================================================================


# ============================================================================
# Business-specific Setup routes (allow paths like /api/v1/{business_id}/setup/...)
# ============================================================================
api_router.include_router(
    setup_dashboard.router,
    prefix="/{business_id}/setup",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    salary_setup.router,
    prefix="/{business_id}/setup/salarysetup",
    tags=["Setup"]
)

# Business Unit Files (Image Upload)
api_router.include_router(
    business_unit_files_router,
    prefix="/{business_id}/setup/business-unit-files",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

# Salary Components (Under Setup)
api_router.include_router(
    salary_component_router,
    prefix="/{business_id}/setup/salarysetup/salary-components",
    tags=["Setup"]
)

api_router.include_router(
    salary_deduction_router,
    prefix="/{business_id}/setup/salarysetup/salary-deductions",
    tags=["Setup"]
)

api_router.include_router(
    salary_structure_router,
    prefix="/{business_id}/setup/salarysetup/salary-structures",
    tags=["Setup"]
)

api_router.include_router(
    salary_structure_rule_router,
    prefix="/{business_id}/setup/salarysetup",
    tags=["Setup"]
)

api_router.include_router(
    time_salary_router,
    prefix="/{business_id}/setup/salarysetup/time-salary",
    tags=["Setup"]
)

api_router.include_router(
    overtime_router,
    prefix="/{business_id}/setup/salarysetup/overtime",
    tags=["Setup"]
)

# ============================================================================
# Setup - Leaves & Attendance (Under Setup)
# ============================================================================

api_router.include_router(
    attendance_settings.router,
    prefix="/{business_id}/setup/leaves-attendance-setup/attendance-settings",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    leave_types.router,
    prefix="/{business_id}/setup/leaves-attendance-setup/leave-type",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    leave_policies.router,
    prefix="/{business_id}/setup/leaves-attendance-setup/leave-policies",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    holidays.router,
    prefix="/{business_id}/setup/holidays",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    compoff_rules.router,
    prefix="/{business_id}/setup/compoff-rules",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    strike_rules.router,
    prefix="/{business_id}/setup/strike-rules",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    strike_adjustments.router,
    prefix="/{business_id}/setup/strike-adjustments",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

# ============================================================================
# Setup - Statutory Settings (Under Setup)
# ============================================================================

api_router.include_router(
    esi_settings.router,
    prefix="/{business_id}/setup/esi-settings",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    epf_settings.router,
    prefix="/{business_id}/setup/epf-settings",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    professional_tax.router,
    prefix="/{business_id}/setup/professional-tax",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    form16.router,
    prefix="/{business_id}/setup/form16",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    tds24q.router,
    prefix="/{business_id}/setup/tds24q",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    lwf.router,
    prefix="/{business_id}/setup/lwf",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)   

api_router.include_router(
    tax.router,
    prefix="/{business_id}/setup/tax",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

# ============================================================================
# Setup - ESS (Employee Self Service) (Under Setup)
# ============================================================================

api_router.include_router(
    approvals.router,
    prefix="/{business_id}/setup/ess",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    user_management.router,
    prefix="/{business_id}/setup/ess",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

# ============================================================================
# Setup - Integrations (Under Setup)
# ============================================================================

api_router.include_router(
    emailsettings.router,
    prefix="/{business_id}/setup",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    biometricsync.router,
    prefix="/{business_id}/setup",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    gatekeeper.router,
    prefix="/{business_id}/setup",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    sqlserver.router,
    prefix="/{business_id}/setup",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    api_access.router,
    prefix="/{business_id}/setup",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

api_router.include_router(
    sap_mapping.router,
    prefix="/{business_id}/setup",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)

# ============================================================================
# Setup - Maintenance (Under Setup)
# ============================================================================

api_router.include_router(
    maintenance.router,
    prefix="/{business_id}/setup",
    tags=["Setup"],
    dependencies=[Depends(get_current_admin)],
)
# ============================================================================
# 3. Dashboard
# ============================================================================

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard"]
)

# ============================================================================
# 4. All Employees (Consolidated - Single Source of Truth)
# ============================================================================

api_router.include_router(
    allemployees.router,
    prefix="/{business_id}/allemployees",
    tags=["All Employees"]
)

# ============================================================================
# 5. Onboarding
# ============================================================================

api_router.include_router(
    onboarding.router,
    prefix="/{business_id}/onboarding",
    tags=["Onboarding"]
)

# OTP verification endpoints (public - multi-tenant)
api_router.include_router(
    otp.router,
    prefix="/{business_id}",
    tags=["OTP"],
)

# ============================================================================
# 6. Separation
# ============================================================================

api_router.include_router(
    separation.router,
    prefix="/{business_id}/separation",
    tags=["Separation"]
)

# ============================================================================
# 7. Attendance
# ============================================================================

api_router.include_router(
    attendance.router,
    prefix="/{business_id}/attendance",
    tags=["Attendance"]
)

# ============================================================================
# 8. Data Capture
# ============================================================================

api_router.include_router(
    datacapture.router,
    prefix="/{business_id}/datacapture",
    tags=["Data Capture"]
)

# ============================================================================
# 9. Bulk Update
# ============================================================================

api_router.include_router(
    bulkupdate.router,
    prefix="/{business_id}/bulkupdate",
    tags=["Bulk Update"]
)

# ============================================================================
# 10. HR Management
# ============================================================================

api_router.include_router(
    hrmanagement.router,
    prefix="/{business_id}/hrmanagement",
    tags=["HR Management"]
)

# ============================================================================
# 11. Request
# ============================================================================

api_router.include_router(
    requests.router,
    prefix="/{business_id}/requests",
    tags=["Request"]
)

# ============================================================================
# 12. Support (Remote Sessions, Help)
# ============================================================================

api_router.include_router(
    support.router,
    prefix="/{business_id}/support",
    tags=["Support"]
)

api_router.include_router(
    help.router,
    prefix="/{business_id}/help",
    tags=["Help & Documentation"]
)

# ============================================================================
# 13. Payroll
# ============================================================================

api_router.include_router(
    payroll.router,
    prefix="/{business_id}/payroll",
    tags=["Payroll"]
)

# ============================================================================
# 14. Reports
# ============================================================================

api_router.include_router(
    reports.router,
    prefix="/{business_id}/reports",
    tags=["Reports"]
)


# ============================================================================
# 16. CRM
# ============================================================================

api_router.include_router(
    crm.router,
    prefix="/{business_id}/crm",
    tags=["CRM"]
)

# ============================================================================
# Business Management (Admin & Superadmin)
# ============================================================================

api_router.include_router(
    business.router,
    prefix="/businesses",
    tags=["Business Management"]
)

# ============================================================================
# Project Management
# ============================================================================

api_router.include_router(
    project_management.router,
    prefix="/project-management",
    tags=["Project Management"]
)

# ============================================================================
# Calendar Management
# ============================================================================

api_router.include_router(
    calendar.router,
    prefix="/calendar",
    tags=["Calendar Management"]
)

# ============================================================================
# Notes Management
# ============================================================================

api_router.include_router(
    notes.router,
    prefix="/notes",
    tags=["Notes Management"]
)

# ============================================================================
# Profile Management
# ============================================================================

api_router.include_router(
    profile.router,
    prefix="/profile",
    tags=["Profile Management"]
)

# ============================================================================
# User Preferences
# ============================================================================

api_router.include_router(
    preferences.router,
    tags=["User Preferences"]
)

# ============================================================================
# TODO/Tasks Management
# ============================================================================

api_router.include_router(
    todo.router,
    prefix="/todo",
    tags=["TODO/Tasks"]
)

# ============================================================================
# Superadmin Endpoints
# ============================================================================

api_router.include_router(
    superadmin.router,
    prefix="/superadmin",
    tags=["Superadmin"]
)

api_router.include_router(
    subscriptions.router,
    prefix="/subscriptions",
    tags=["Subscriptions"]
)

api_router.include_router(
    packages.router,
    prefix="/superadmin/packages",
    tags=["Packages"]
)

api_router.include_router(
    domain.router,
    prefix="/superadmin/domain",
    tags=["Domain Management"]
)

api_router.include_router(
    purchase_transaction.router,
    prefix="/superadmin/purchase-transactions",
    tags=["Purchase Transaction Management"]
)

# ============================================================================
# File Upload & Document Management
# ============================================================================

api_router.include_router(
    files.router,
    prefix="/upload",
    tags=["File Upload"]
)

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["System"]
)

api_router.include_router(
    dev.router,
    prefix="/dev",
    tags=["Developer"]
)



# ============================================================================
# System Statistics (Real-time Backend Analysis)
# ============================================================================

api_router.include_router(
    system_stats.router,
    prefix="/system",
    tags=["System Statistics"]
)
