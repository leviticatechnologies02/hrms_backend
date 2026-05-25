from .base import Base, BaseModel
from .user import User
from .user import User
from .employee import Employee
from .business import Business
from .user_preferences import UserPreferences
from .setup.Integrations.emailsettings import (
    EmailMailbox,
    EmailSmtpConfig,
    EmailOAuthConfig,
    EmailTestLog,
)
from .setup.Integrations.biometricsync import (
    BiometricDevice,
    BiometricSyncLog,
)
from .setup.Integrations.gatekeeper import GatekeeperDevice
from .setup.Integrations.sqlserver import SqlServerSource, SqlServerSyncLog
from .setup.Integrations.sap_mapping import SAPMapping
from .setup.Integrations.api_access import APIAccess
from .attendance_settings import AttendanceSettings
from .esi_settings import ESISettings, ESIComponentMapping, ESIRateChange
from .epf_settings import EPFSettings, EPFComponentMapping, EPFRateChange
from .professional_tax import ProfessionalTaxSettings, PTComponentMapping, ProfessionalTaxRate
from .holiday import Holiday, Setting
from .compoff_rule import CompOffRule
from .business import Business
from .leave_type import LeaveType
from .leave_policy import LeavePolicy
from .strike_adjustment import StrikeAdjustment
from .strike_rule import StrikeRule
from .tds24q_models import TDS24Q
from .form16_models import  EmployerInfo, PersonResponsible, CitInfo
from .lwf_models import LWFRate, LWFSettings
from .tax_models import TDSSetting, FinancialYear, TaxRate 
from .setup.salary_and_deductions.salary_deduction import SalaryDeduction
from .business import Business
from .business_unit import BusinessUnit
from .location import Location
from .cost_center import CostCenter
from .department import Department
from .approval_settings import ApprovalSettings
from .employee_code_config import EmployeeCodeSetting
from .exit_reason import ExitReason
from .helpdesk_category import HelpdeskCategory
from .workflow import Workflow
from .weekoff_policy import WeekOffPolicy
from .visit_type import VisitType
from .shift_policy import ShiftPolicy
from .business_info import BusinessInformation
from .grades import Grade
from .designations import Designation
from .work_shifts import WorkShift
from .datacapture import SalaryVariable, SalaryUnit, ExtraDay, EmployeeDeduction, IncomeTaxTDS, ExtraHour, EmployeeLoan, LoanEMIPayment, ITDeclaration, TDSChallan, TDSReturn
from .asset import Asset, AssetHistory
from .hrmanagement import (
    Notification, Letter, Alert, Greeting, HRPolicy,
    PolicyAcknowledgment, NotificationRead, AlertAcknowledgment,
    NotificationStatus, NotificationPriority, LetterType,
    AlertType, GreetingType, PolicyStatus
)
from .reports import (
    AIReportQuery, ReportTemplate, GeneratedReport, SalaryReport,
    AttendanceReport, EmployeeReport, StatutoryReport, AnnualReport,
    ActivityLog, UserFeedback, SystemAlert
)
from .crm import (
    CRMCompany, CRMContact, CRMDeal, CRMActivity, CRMPipeline,
    ContactType, LeadStatus, DealStage, ActivityType, Priority
)
from .calendar import (
    CalendarEvent, CalendarEventAttendee, CalendarView,
    EventType, EventPriority, EventStatus
)
from .project_management import (
    Project, Task, TimeEntry, ProjectMember, ProjectActivityLog,
    ProjectStatus, TaskStatus, MemberRole
)
from .notes import (
    Note, NoteShare, NoteAttachment,
    NoteCategory, NotePriority
)
from .subscription import (
    Subscription, SubscriptionPayment, SubscriptionPlan
)
from .domain import (
    DomainRequest, DomainConfiguration, DomainUsageLog
)
from .purchase_transaction import (
    PurchaseTransaction, TransactionLineItem, PaymentLog
)
from .remote_session import (
    RemoteSession, RemoteSessionStatus, RemoteSessionType
)
from .help_article import (
    HelpArticle, ArticleCategory, ArticleType
)
from .contact_inquiry import (
    ContactInquiry, InquiryStatus, InquirySource
)

# Import model modules so SQLAlchemy can locate related class names when configuring mappers.
# Order matters: import dependent models first so names like EmployerInfo, PersonResponsible, CitInfo, TDS24Q
# are defined before Business is mapped.


__all__ = [
    "Base",
    "BaseModel",
    "User",
    "UserPreferences",
    "Employee",
    "EmployeeAdditionalInfo",
    "EmployeePermissions",
    "EmployeeAccess",
    "EmployeeLoginSession",
    "AttendanceRecord",
    "PayrollRecord",
    "SeparationRequest",
    "OnboardingForm",
    "AttendanceSettings",
    "ESISettings",
    "ESIComponentMapping",
    "ESIRateChange",
    "EPFSettings",
    "EPFComponentMapping",
    "EPFRateChange",
    "ProfessionalTaxSettings",
    "PTComponentMapping",
    "ProfessionalTaxRate",
    "Business",
    "LeaveType",
    "LeavePolicy",
    "CompOffRule",
    "Holiday",
    "Location",
    "Setting",
    "StrikeAdjustment",
    "StrikeRule",
    "CompOffRule",
    "TDS24Q",
    "EmployerInfo",
    "PersonResponsible",
    "CitInfo",
    "SalaryComponent",
    "SalaryDeduction",
    "LWFRate",
    "LWFSettings",
    "TDSSetting",
    "FinancialYear",
    "TaxRate",
    "Business",
	"BusinessUnit",
	"Location",
	"CostCenter",
	"Department",
	"ApprovalSettings",
	"EmployeeCodeSetting",
	"ExitReason",
	"HelpdeskCategory",
	"Workflow",
    "WeekOffPolicy",
    "VisitType",
    "ShiftPolicy",
    "BusinessInformation",
    "Grade",
    "Designation",
	"WorkShift",
    "EmailMailbox",
    "EmailSmtpConfig",
    "EmailOAuthConfig",
    "EmailTestLog",
    "BiometricDevice",
    "BiometricSyncLog",
    "GatekeeperDevice",
    "SqlServerSource",
    "SqlServerSyncLog",
    "SAPMapping",
    "APIAccess",
    "SalaryVariable",
    "SalaryUnit",
    "ExtraDay",
    "EmployeeDeduction",
    "IncomeTaxTDS",
    "ExtraHour",
    "Notification",
    "Letter",
    "Alert",
    "Greeting",
    "HRPolicy",
    "PolicyAcknowledgment",
    "NotificationRead",
    "AlertAcknowledgment",
    "NotificationStatus",
    "NotificationPriority",
    "LetterType",
    "AlertType",
    "GreetingType",
    "PolicyStatus",
    "AIReportQuery",
    "ReportTemplate",
    "GeneratedReport",
    "SalaryReport",
    "AttendanceReport",
    "EmployeeReport",
    "StatutoryReport",
    "AnnualReport",
    "ActivityLog",
    "UserFeedback",
    "SystemAlert",
    "CRMCompany",
    "CRMContact",
    "CRMDeal",
    "CRMActivity",
    "CRMPipeline",
    "ContactType",
    "LeadStatus",
    "DealStage",
    "ActivityType",
    "Priority",
    "CalendarEvent",
    "CalendarEventAttendee",
    "CalendarView",
    "EventType",
    "EventPriority",
    "EventStatus",
    "Project",
    "Task",
    "TimeEntry",
    "ProjectMember",
    "ProjectActivityLog",
    "ProjectStatus",
    "TaskStatus",
    "MemberRole",
    "TodoTask",
    "Note",
    "NoteShare",
    "NoteAttachment",
    "NoteCategory",
    "NotePriority",
    "Subscription",
    "SubscriptionPayment",
    "SubscriptionPlan",
    "DomainRequest",
    "DomainConfiguration",
    "DomainUsageLog",
    "PurchaseTransaction",
    "TransactionLineItem",
    "PaymentLog",
    "RemoteSession",
    "RemoteSessionStatus",
    "RemoteSessionType",
    "LeaveBalance",
    "LeaveCorrection",
    "ContactInquiry",
    "InquiryStatus",
    "InquirySource"
]
from .base import Base, BaseModel
from .user import User
from .employee import Employee
from .employee_relative import EmployeeRelative
from .employee_additional_info import EmployeeAdditionalInfo
from .employee_permissions import EmployeePermissions
from .employee_access import EmployeeAccess, EmployeeLoginSession
from .attendance import AttendanceRecord
from .payroll import PayrollRecord, PayrollPeriod, PayrollRecalculation
from .separation import SeparationRequest
from .master_policy import MasterPolicy, FormPolicyMapping
from .onboarding import OnboardingForm
from .business import Business
from .business_unit import BusinessUnit
from .location import Location
from .cost_center import CostCenter
from .department import Department
from .approval_settings import ApprovalSettings
from .employee_code_config import EmployeeCodeSetting
from .exit_reason import ExitReason
from .helpdesk_category import HelpdeskCategory
from .workflow import Workflow
from .weekoff_policy import WeekOffPolicy
from .visit_type import VisitType
from .shift_policy import ShiftPolicy
from .business_info import BusinessInformation
from .grades import Grade
from .designations import Designation
from .work_shifts import WorkShift

# Additional policy models
from .employee_leave_policy import EmployeeLeavePolicy
from .setup.salary_and_deductions.overtime import OvertimePolicy
from .leave_balance import LeaveBalance, LeaveCorrection
from .remote_session import RemoteSession, RemoteSessionStatus, RemoteSessionType
from .todo import TodoTask
from .calendar import CalendarEvent, CalendarEventAttendee, CalendarView
from .otp_verification import OTPVerification

__all__.append("OTPVerification")
