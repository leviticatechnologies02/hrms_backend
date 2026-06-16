"""
Reports Repository
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc, case, extract
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from app.models.reports import (
    AIReportQuery, ReportTemplate, GeneratedReport, SalaryReport,
    AttendanceReport, EmployeeReport, StatutoryReport, AnnualReport,
    ActivityLog, UserFeedback, SystemAlert
)
from app.schemas.reports import (
    AIReportQueryCreate, ReportTemplateCreate, GeneratedReportCreate,
    SalaryReportCreate, AttendanceReportCreate, EmployeeReportCreate,
    StatutoryReportCreate, AnnualReportCreate, ActivityLogCreate,
    UserFeedbackCreate, SystemAlertCreate, ReportFilters
)

logger = logging.getLogger(__name__)


class ReportsRepository:
    """Repository for all report-related database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # AI Reporting Methods
    def create_ai_query(self, user_id: int, query_data: AIReportQueryCreate) -> AIReportQuery:
        """Create a new AI report query"""
        db_query = AIReportQuery(
            user_id=user_id,
            **query_data.dict()
        )
        self.db.add(db_query)
        self.db.commit()
        self.db.refresh(db_query)
        return db_query
    
    def get_ai_query(self, query_id: int) -> Optional[AIReportQuery]:
        """Get AI query by ID"""
        return self.db.query(AIReportQuery).filter(AIReportQuery.id == query_id).first()
    
    def get_user_ai_queries(self, user_id: int, limit: int = 50) -> List[AIReportQuery]:
        """Get user's AI queries"""
        return self.db.query(AIReportQuery).filter(
            AIReportQuery.user_id == user_id
        ).order_by(desc(AIReportQuery.created_at)).limit(limit).all()
    
    def update_ai_query_status(self, query_id: int, status: str, response_data: Optional[Dict] = None) -> Optional[AIReportQuery]:
        """Update AI query status and response"""
        db_query = self.get_ai_query(query_id)
        if db_query:
            db_query.status = status
            if response_data:
                db_query.response_data = response_data
            if status == "completed":
                db_query.processed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(db_query)
        return db_query
    
    # Report Template Methods
    def create_report_template(self, template_data: ReportTemplateCreate) -> ReportTemplate:
        """Create a new report template"""
        db_template = ReportTemplate(**template_data.dict())
        self.db.add(db_template)
        self.db.commit()
        self.db.refresh(db_template)
        return db_template
    
    def get_report_templates(self, category: Optional[str] = None) -> List[ReportTemplate]:
        """Get report templates by category"""
        query = self.db.query(ReportTemplate).filter(ReportTemplate.is_active == True)
        if category:
            query = query.filter(ReportTemplate.category == category)
        return query.order_by(ReportTemplate.name).all()
    
    def get_report_template(self, template_id: int) -> Optional[ReportTemplate]:
        """Get report template by ID"""
        return self.db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    
    # Generated Report Methods
    def create_generated_report(self, user_id: int, report_data: GeneratedReportCreate) -> GeneratedReport:
        """Create a new generated report"""
        db_report = GeneratedReport(
            user_id=user_id,
            **report_data.dict()
        )
        self.db.add(db_report)
        self.db.commit()
        self.db.refresh(db_report)
        return db_report
    
    def get_generated_reports(self, user_id: int, limit: int = 100) -> List[GeneratedReport]:
        """Get user's generated reports"""
        return self.db.query(GeneratedReport).filter(
            GeneratedReport.user_id == user_id
        ).order_by(desc(GeneratedReport.created_at)).limit(limit).all()
    
    def update_generated_report_status(self, report_id: int, status: str, file_path: Optional[str] = None) -> Optional[GeneratedReport]:
        """Update generated report status"""
        db_report = self.db.query(GeneratedReport).filter(GeneratedReport.id == report_id).first()
        if db_report:
            db_report.status = status
            if file_path:
                db_report.file_path = file_path
            if status == "completed":
                db_report.completed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(db_report)
        return db_report
    
    # Salary Report Methods
    def create_salary_report(self, report_data: SalaryReportCreate) -> SalaryReport:
        """Create a new salary report"""
        db_report = SalaryReport(**report_data.dict())
        self.db.add(db_report)
        self.db.commit()
        self.db.refresh(db_report)
        return db_report
    
    def get_salary_reports(self, filters: ReportFilters) -> List[SalaryReport]:
        """Get salary reports with filters"""
        query = self.db.query(SalaryReport)
        
        if filters.employee_ids:
            query = query.filter(SalaryReport.employee_id.in_(filters.employee_ids))
        
        if filters.start_date and filters.end_date:
            start_period = filters.start_date.strftime('%Y-%m')
            end_period = filters.end_date.strftime('%Y-%m')
            query = query.filter(
                and_(
                    SalaryReport.report_period >= start_period,
                    SalaryReport.report_period <= end_period
                )
            )
        
        return query.order_by(desc(SalaryReport.created_at)).all()
    
    def get_salary_reports_for_summary(self, period: str, business_id: int) -> List[SalaryReport]:
        """Get salary reports with employee relationships for summary"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.grades import Grade
        
        return self.db.query(SalaryReport).join(
            Employee, SalaryReport.employee_id == Employee.id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            Grade, Employee.grade_id == Grade.id
        ).filter(
            SalaryReport.report_period == period,
            Employee.business_id == business_id  # CRITICAL: Business isolation
        ).add_columns(
            Employee.first_name,
            Employee.last_name,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            Grade.name.label('grade_name')
        ).all()

    def get_bank_transfer_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get bank transfer letter data with employee bank details"""
        from app.models.employee import Employee, EmployeeProfile
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from sqlalchemy import func
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[BANK TRANSFER] Querying for period={period}, business_id={business_id}")
        
        # Base query with all joins including employee_profiles for bank details
        query = self.db.query(
            SalaryReport,
            Employee,
            EmployeeProfile,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).join(
            Employee, SalaryReport.employee_id == Employee.id
        ).join(
            EmployeeProfile, Employee.id == EmployeeProfile.employee_id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            SalaryReport.report_period == period,
            Employee.employee_status == 'ACTIVE',  # Only active employees for bank transfers
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Debug: Check if any salary reports exist for this period
        total_reports_for_period = self.db.query(func.count(SalaryReport.id)).filter(
            SalaryReport.report_period == period
        ).scalar()
        logger.info(f"[BANK TRANSFER] Total salary reports for period {period}: {total_reports_for_period}")
        
        # Debug: Check if any salary reports exist for this business
        total_reports_for_business = self.db.query(func.count(SalaryReport.id)).join(
            Employee, SalaryReport.employee_id == Employee.id
        ).filter(
            Employee.business_id == business_id
        ).scalar()
        logger.info(f"[BANK TRANSFER] Total salary reports for business_id {business_id}: {total_reports_for_business}")
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            query = query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            query = query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        # Only include employees with bank details
        query = query.filter(
            EmployeeProfile.bank_account_number.isnot(None),
            EmployeeProfile.bank_ifsc_code.isnot(None)
        )
        
        results = query.order_by(Employee.employee_code).all()
        logger.info(f"[BANK TRANSFER] Query returned {len(results)} records")
        
        return results

    def get_salary_slip_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get comprehensive salary slip data with all employee details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.grades import Grade
        from app.models.cost_center import CostCenter
        from app.models.attendance import AttendanceRecord
        from sqlalchemy import func, case
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[SALARY SLIPS] Querying for period={period}, business_id={business_id}")
        
        # Base query with all joins
        query = self.db.query(
            SalaryReport,
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            Grade.name.label('grade_name'),
            CostCenter.name.label('cost_center_name')
        ).join(
            Employee, SalaryReport.employee_id == Employee.id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            Grade, Employee.grade_id == Grade.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            SalaryReport.report_period == period,
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Debug: Check if any salary reports exist for this period
        total_reports_for_period = self.db.query(func.count(SalaryReport.id)).filter(
            SalaryReport.report_period == period
        ).scalar()
        logger.info(f"[SALARY SLIPS] Total salary reports for period {period}: {total_reports_for_period}")
        
        # Debug: Check if any salary reports exist for this business
        total_reports_for_business = self.db.query(func.count(SalaryReport.id)).join(
            Employee, SalaryReport.employee_id == Employee.id
        ).filter(
            Employee.business_id == business_id
        ).scalar()
        logger.info(f"[SALARY SLIPS] Total salary reports for business_id {business_id}: {total_reports_for_business}")
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            query = query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            query = query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee'):
            search_term = f"%{filters['employee']}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        # Apply record type filters
        if filters.get('records') == 'Active':
            query = query.filter(Employee.employee_status == 'ACTIVE')
        elif filters.get('records') == 'Inactive':
            query = query.filter(Employee.employee_status != 'ACTIVE')
        # 'All' records - no filter needed
        
        # Exclude hold salary if requested
        if filters.get('exclude_hold'):
            # Add logic to exclude employees with hold salary status
            pass
        
        results = query.all()
        logger.info(f"[SALARY SLIPS] Query returned {len(results)} records")
        
        return results

    def get_salary_register_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get comprehensive salary register data with all employee details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.grades import Grade
        from app.models.cost_center import CostCenter
        from app.models.attendance import AttendanceRecord
        from sqlalchemy import func, case
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[SALARY REGISTER] Querying for period={period}, business_id={business_id}")
        
        # Base query with all joins
        query = self.db.query(
            SalaryReport,
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            Grade.name.label('grade_name'),
            CostCenter.name.label('cost_center_name')
        ).join(
            Employee, SalaryReport.employee_id == Employee.id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            Grade, Employee.grade_id == Grade.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            SalaryReport.report_period == period,
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Debug: Check if any salary reports exist for this period
        total_reports_for_period = self.db.query(func.count(SalaryReport.id)).filter(
            SalaryReport.report_period == period
        ).scalar()
        logger.info(f"[SALARY REGISTER] Total salary reports for period {period}: {total_reports_for_period}")
        
        # Debug: Check if any salary reports exist for this business
        total_reports_for_business = self.db.query(func.count(SalaryReport.id)).join(
            Employee, SalaryReport.employee_id == Employee.id
        ).filter(
            Employee.business_id == business_id
        ).scalar()
        logger.info(f"[SALARY REGISTER] Total salary reports for business_id {business_id}: {total_reports_for_business}")
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            query = query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            query = query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee'):
            search_term = f"%{filters['employee']}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        # Apply record type filters
        if filters.get('active_records') and not filters.get('all_records'):
            query = query.filter(Employee.employee_status == 'ACTIVE')
        elif filters.get('inactive_records') and not filters.get('all_records'):
            query = query.filter(Employee.employee_status != 'ACTIVE')
        
        # Exclude hold salary if requested
        if filters.get('exclude_hold'):
            # Add logic to exclude employees with hold salary status
            pass
        
        results = query.all()
        logger.info(f"[SALARY REGISTER] Query returned {len(results)} records")
        
        return results

    def get_attendance_summary_for_register(self, employee_ids: List[int], period: str) -> Dict[int, Dict[str, int]]:
        """Get attendance summary for salary register"""
        from app.models.attendance import AttendanceRecord, AttendanceStatus
        from datetime import datetime
        
        # Parse period to get start and end dates
        year, month = period.split('-')
        start_date = datetime(int(year), int(month), 1).date()
        
        # Calculate end date (last day of month)
        if int(month) == 12:
            end_date = datetime(int(year) + 1, 1, 1).date()
        else:
            end_date = datetime(int(year), int(month) + 1, 1).date()
        
        # Get attendance data
        attendance_data = self.db.query(
            AttendanceRecord.employee_id,
            AttendanceRecord.attendance_status,
            func.count(AttendanceRecord.id).label('count')
        ).filter(
            AttendanceRecord.employee_id.in_(employee_ids),
            AttendanceRecord.attendance_date >= start_date,
            AttendanceRecord.attendance_date < end_date
        ).group_by(
            AttendanceRecord.employee_id,
            AttendanceRecord.attendance_status
        ).all()
        
        # Process attendance data
        result = {}
        for employee_id in employee_ids:
            result[employee_id] = {
                'total_days': 30,  # Default month days
                'presents': 0,
                'absents': 0,
                'week_offs': 8,  # Default weekends
                'holidays': 2,   # Default holidays
                'paid_leaves': 0,
                'unpaid_leaves': 0,
                'payable_days': 0,
                'unpaid_days': 0,
                'extra_days': 0,
                'arrear_days': 0,
                'overtime_days': 0
            }
        
        # Update with actual data
        for record in attendance_data:
            employee_id = record.employee_id
            status = record.attendance_status
            count = record.count
            
            if employee_id in result:
                if status == AttendanceStatus.PRESENT:
                    result[employee_id]['presents'] = count
                elif status == AttendanceStatus.ABSENT:
                    result[employee_id]['absents'] = count
                elif status == AttendanceStatus.ON_LEAVE:
                    result[employee_id]['paid_leaves'] = count
        
        # Calculate derived values
        for employee_id in result:
            data = result[employee_id]
            data['payable_days'] = data['presents'] + data['paid_leaves']
            data['unpaid_days'] = data['absents'] + data['unpaid_leaves']
        
        return result

    def get_cost_to_company_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get cost to company data with employee salary details"""
        from app.models.employee import Employee, EmployeeSalary
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.setup.salary_and_deductions.salary_structure import SalaryStructure
        from app.models.setup.salary_and_deductions.salary_component import SalaryComponent
        from sqlalchemy import func, and_, or_
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[COST TO COMPANY] Querying for business_id={business_id}")
        
        # Base query with all joins
        query = self.db.query(
            EmployeeSalary,
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name'),
            SalaryStructure.name.label('salary_structure_name')
        ).join(
            Employee, EmployeeSalary.employee_id == Employee.id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).outerjoin(
            SalaryStructure, EmployeeSalary.salary_structure_id == SalaryStructure.id
        ).filter(
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Debug: Check if any salary records exist for this business
        total_salaries_for_business = self.db.query(func.count(EmployeeSalary.id)).join(
            Employee, EmployeeSalary.employee_id == Employee.id
        ).filter(
            Employee.business_id == business_id,
            EmployeeSalary.is_active == True
        ).scalar()
        logger.info(f"[COST TO COMPANY] Total active salary records for business_id {business_id}: {total_salaries_for_business}")
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            query = query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            query = query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        # Apply active records filter
        if filters.get('active_only', True):
            # Check for both string and enum values for employee status
            query = query.filter(
                or_(
                    Employee.employee_status == 'ACTIVE',
                    Employee.employee_status == 'active'
                )
            )
        
        # Apply revision filters
        revision = filters.get('revision', 'latest')
        if revision == 'latest':
            # Get only the latest salary record for each employee
            subquery = self.db.query(
                EmployeeSalary.employee_id,
                func.max(EmployeeSalary.effective_from).label('max_effective_from')
            ).filter(
                EmployeeSalary.is_active == True
            ).group_by(EmployeeSalary.employee_id).subquery()
            
            query = query.join(
                subquery,
                and_(
                    EmployeeSalary.employee_id == subquery.c.employee_id,
                    EmployeeSalary.effective_from == subquery.c.max_effective_from
                )
            )
        elif revision == 'dateSpecific' and filters.get('date_specific'):
            # Get salary records effective as on specific date
            specific_date = datetime.strptime(filters['date_specific'], '%Y-%m-%d').date()
            query = query.filter(
                and_(
                    EmployeeSalary.effective_from <= specific_date,
                    or_(
                        EmployeeSalary.effective_to.is_(None),
                        EmployeeSalary.effective_to >= specific_date
                    )
                )
            )
        # For 'all' revisions, no additional filter needed
        
        results = query.filter(EmployeeSalary.is_active == True).order_by(Employee.employee_code).all()
        logger.info(f"[COST TO COMPANY] Query returned {len(results)} records")
        
        return results

    def get_salary_components_for_business(self, business_id: int) -> List[Any]:
        """Get salary components for a business"""
        from app.models.setup.salary_and_deductions.salary_component import SalaryComponent
        
        return self.db.query(SalaryComponent).filter(
            SalaryComponent.business_id == business_id,
            SalaryComponent.is_active == True
        ).order_by(SalaryComponent.name).all()

    def get_overtime_register_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get overtime register data with employee details"""
        from app.models.employee import Employee, EmployeeProfile
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.datacapture import ExtraHour
        from sqlalchemy import func, extract
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[OVERTIME REGISTER] Querying for period={period}, business_id={business_id}")
        
        # Parse period from frontend format (e.g., "JUN-2025" to "2025-06")
        from datetime import datetime
        if '-' in period and len(period.split('-')[0]) == 3:
            # Frontend format: "JUN-2025"
            month_obj = datetime.strptime(period, "%b-%Y")
            year = month_obj.year
            month = month_obj.month
        else:
            # Backend format: "2025-06"
            year, month = map(int, period.split('-'))
        
        # Debug: Check if any overtime records exist for this period
        total_overtime_for_period = self.db.query(func.count(ExtraHour.id)).filter(
            extract('year', ExtraHour.work_date) == year,
            extract('month', ExtraHour.work_date) == month
        ).scalar()
        logger.info(f"[OVERTIME REGISTER] Total overtime records for period {period}: {total_overtime_for_period}")
        
        # Debug: Check if any overtime records exist for this business
        total_overtime_for_business = self.db.query(func.count(ExtraHour.id)).join(
            Employee, ExtraHour.employee_id == Employee.id
        ).filter(
            Employee.business_id == business_id
        ).scalar()
        logger.info(f"[OVERTIME REGISTER] Total overtime records for business_id {business_id}: {total_overtime_for_business}")
        
        # Base query with all joins
        query = self.db.query(
            ExtraHour,
            Employee,
            EmployeeProfile,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).join(
            Employee, ExtraHour.employee_id == Employee.id
        ).outerjoin(
            EmployeeProfile, Employee.id == EmployeeProfile.employee_id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            extract('year', ExtraHour.work_date) == year,
            extract('month', ExtraHour.work_date) == month,
            ExtraHour.is_approved == True,  # Only approved overtime
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply include_inactive_employees filter
        if not filters.get('include_inactive_employees', False):
            query = query.filter(Employee.employee_status == 'ACTIVE')
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            query = query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            query = query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        # Apply include_zero_records filter
        if not filters.get('include_zero_records', False):
            query = query.filter(ExtraHour.extra_hours > 0)
        
        results = query.order_by(Employee.employee_code, ExtraHour.work_date).all()
        logger.info(f"[OVERTIME REGISTER] Query returned {len(results)} records")
        
        return results

    def get_time_salary_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get time salary data with employee time-based calculations"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.attendance import AttendanceRecord, AttendanceStatus
        from app.models.datacapture import ExtraHour
        from app.models.setup.salary_and_deductions.time_salary import TimeSalaryRule
        from app.models.setup.salary_and_deductions.salary_component import SalaryComponent
        from sqlalchemy import func, extract, case, or_
        from datetime import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[TIME SALARY] Querying for period={period}, business_id={business_id}")
        
        # Parse period from frontend format (e.g., "MAR-2025" to "2025-03")
        if '-' in period and len(period.split('-')[0]) == 3:
            # Frontend format: "MAR-2025"
            month_obj = datetime.strptime(period, "%b-%Y")
            year = month_obj.year
            month = month_obj.month
        else:
            # Backend format: "2025-03"
            year, month = map(int, period.split('-'))
        
        # Base query for employees with time salary rules
        query = self.db.query(
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            TimeSalaryRule,
            SalaryComponent.name.label('component_name')
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            TimeSalaryRule, TimeSalaryRule.business_id == Employee.business_id
        ).outerjoin(
            SalaryComponent, TimeSalaryRule.component_id == SalaryComponent.id
        ).filter(
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            query = query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            query = query.filter(Department.name == filters['department'])
        
        if filters.get('salary_component'):
            query = query.filter(SalaryComponent.name.ilike(f"%{filters['salary_component']}%"))
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        employees_data = query.all()
        logger.info(f"[TIME SALARY] Found {len(employees_data)} employees for business_id={business_id}")
        
        # Get attendance data for the period
        attendance_data = {}
        if employees_data:
            employee_ids = [emp[0].id for emp in employees_data]
            
            # Calculate start and end dates for the month
            from calendar import monthrange
            days_in_month = monthrange(year, month)[1]
            start_date = datetime(year, month, 1).date()
            end_date = datetime(year, month, days_in_month).date()
            
            # Get attendance records for the period
            attendance_records = self.db.query(
                AttendanceRecord.employee_id,
                func.count(AttendanceRecord.id).label('total_days'),
                func.sum(
                    case(
                        (AttendanceRecord.attendance_status == AttendanceStatus.PRESENT, 1),
                        else_=0
                    )
                ).label('present_days'),
                func.sum(
                    case(
                        (AttendanceRecord.total_hours.isnot(None), AttendanceRecord.total_hours),
                        else_=8.0
                    )
                ).label('total_hours')
            ).filter(
                AttendanceRecord.employee_id.in_(employee_ids),
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date
            ).group_by(AttendanceRecord.employee_id).all()
            
            for record in attendance_records:
                attendance_data[record.employee_id] = {
                    'total_days': record.total_days or 0,
                    'present_days': record.present_days or 0,
                    'total_hours': float(record.total_hours or 0)
                }
            
            # Get overtime data for the period
            overtime_records = self.db.query(
                ExtraHour.employee_id,
                func.sum(ExtraHour.extra_hours).label('overtime_hours'),
                func.sum(ExtraHour.total_amount).label('overtime_amount')
            ).filter(
                ExtraHour.employee_id.in_(employee_ids),
                extract('year', ExtraHour.work_date) == year,
                extract('month', ExtraHour.work_date) == month,
                ExtraHour.is_approved == True
            ).group_by(ExtraHour.employee_id).all()
            
            for record in overtime_records:
                if record.employee_id in attendance_data:
                    attendance_data[record.employee_id]['overtime_hours'] = float(record.overtime_hours or 0)
                    attendance_data[record.employee_id]['overtime_amount'] = float(record.overtime_amount or 0)
                else:
                    attendance_data[record.employee_id] = {
                        'total_days': 0,
                        'present_days': 0,
                        'total_hours': 0,
                        'overtime_hours': float(record.overtime_hours or 0),
                        'overtime_amount': float(record.overtime_amount or 0)
                    }
        
        # Combine employee data with attendance data
        result = []
        for emp_data in employees_data:
            employee = emp_data[0]
            attendance = attendance_data.get(employee.id, {
                'total_days': 0,
                'present_days': 0,
                'total_hours': 0,
                'overtime_hours': 0,
                'overtime_amount': 0
            })
            
            result.append((emp_data, attendance))
        
        return result

    def get_variable_salary_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get variable salary data with employee details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.datacapture import SalaryVariable, SalaryVariableType
        from sqlalchemy import func, extract, or_
        from datetime import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[VARIABLE SALARY] Querying for period={period}, business_id={business_id}")
        
        # Parse period from frontend format (e.g., "JUN-2025" to "2025-06")
        if '-' in period and len(period.split('-')[0]) == 3:
            # Frontend format: "JUN-2025"
            month_obj = datetime.strptime(period, "%b-%Y")
            year = month_obj.year
            month = month_obj.month
        else:
            # Backend format: "2025-06"
            year, month = map(int, period.split('-'))
        
        # Base query with all joins
        query = self.db.query(
            SalaryVariable,
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name')
        ).join(
            Employee, SalaryVariable.employee_id == Employee.id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).filter(
            extract('year', SalaryVariable.effective_date) == year,
            extract('month', SalaryVariable.effective_date) == month,
            SalaryVariable.is_active == True,
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply salary component filter
        salary_component = filters.get('salary_component')
        if salary_component and salary_component not in ["-Select-", "All Components", None]:
            # Try exact match first
            query = query.filter(SalaryVariable.variable_name == salary_component)
        
        # Apply other filters
        if filters.get('location') and filters['location'] != "All Locations":
            query = query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            query = query.filter(Department.name == filters['department'])
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        results = query.order_by(Employee.employee_code).all()
        logger.info(f"[VARIABLE SALARY] Query returned {len(results)} records")
        
        return results

    def get_statutory_bonus_report_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get statutory bonus report data with employee details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.payroll import StatutoryBonus, PayrollPeriod
        from app.models.datacapture import SalaryVariable, SalaryVariableType
        from sqlalchemy import func, extract, case, or_
        from datetime import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[STATUTORY BONUS] Querying for period={period}, business_id={business_id}")
        
        # Parse period from frontend format (e.g., "JUL-2025" to "2025-07")
        if '-' in period and len(period.split('-')[0]) == 3:
            # Frontend format: "JUL-2025"
            month_obj = datetime.strptime(period, "%b-%Y")
            year = month_obj.year
            month = month_obj.month
        else:
            # Backend format: "2025-07"
            year, month = map(int, period.split('-'))
        
        # First, try to get data from StatutoryBonus table (if exists)
        try:
            statutory_bonus_query = self.db.query(
                StatutoryBonus,
                Employee,
                Department.name.label('department_name'),
                Designation.name.label('designation_name'),
                Location.name.label('location_name'),
                CostCenter.name.label('cost_center_name')
            ).join(
                Employee, StatutoryBonus.employee_id == Employee.id
            ).join(
                PayrollPeriod, StatutoryBonus.period_id == PayrollPeriod.id
            ).outerjoin(
                Department, Employee.department_id == Department.id
            ).outerjoin(
                Designation, Employee.designation_id == Designation.id
            ).outerjoin(
                Location, Employee.location_id == Location.id
            ).outerjoin(
                CostCenter, Employee.cost_center_id == CostCenter.id
            ).filter(
                extract('year', PayrollPeriod.start_date) == year,
                extract('month', PayrollPeriod.start_date) == month,
                Employee.employee_status == 'ACTIVE',
                Employee.business_id == business_id  # CRITICAL: Business isolation
            )
            
            # Apply filters
            if filters.get('location') and filters['location'] != "All Locations":
                statutory_bonus_query = statutory_bonus_query.filter(Location.name == filters['location'])
            
            if filters.get('department') and filters['department'] != "All Departments":
                statutory_bonus_query = statutory_bonus_query.filter(Department.name == filters['department'])
            
            if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
                statutory_bonus_query = statutory_bonus_query.filter(CostCenter.name == filters['cost_center'])
            
            if filters.get('employee_search'):
                search_term = f"%{filters['employee_search']}%"
                statutory_bonus_query = statutory_bonus_query.filter(
                    or_(
                        Employee.first_name.ilike(search_term),
                        Employee.last_name.ilike(search_term),
                        Employee.employee_code.ilike(search_term)
                    )
                )
            
            statutory_bonus_data = statutory_bonus_query.all()
            
            logger.info(f"[STATUTORY BONUS] Found {len(statutory_bonus_data)} records from StatutoryBonus table")
            
            if statutory_bonus_data:
                return statutory_bonus_data
        except Exception as e:
            # StatutoryBonus table might not exist, continue to fallback
            logger.info(f"[STATUTORY BONUS] StatutoryBonus table query failed, using fallback: {str(e)}")
            pass
        
        # Fallback: Get from SalaryVariable table (Bonus entries)
        logger.info(f"[STATUTORY BONUS] Querying SalaryVariable table for business_id={business_id}")
        salary_variable_query = self.db.query(
            SalaryVariable,
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).join(
            Employee, SalaryVariable.employee_id == Employee.id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            extract('year', SalaryVariable.effective_date) == year,
            extract('month', SalaryVariable.effective_date) == month,
            or_(
                SalaryVariable.variable_type == SalaryVariableType.BONUS,
                SalaryVariable.variable_name.ilike('%bonus%')
            ),
            SalaryVariable.is_active == True,
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply same filters
        if filters.get('location') and filters['location'] != "All Locations":
            salary_variable_query = salary_variable_query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            salary_variable_query = salary_variable_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            salary_variable_query = salary_variable_query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            salary_variable_query = salary_variable_query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        results = salary_variable_query.order_by(Employee.employee_code).all()
        logger.info(f"[STATUTORY BONUS] Query returned {len(results)} records from SalaryVariable table")
        
        return results

    def get_employee_loans_report_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get employee loans report data with employee details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.datacapture import EmployeeLoan, LoanStatus
        from sqlalchemy import or_
        from datetime import datetime, timedelta
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[EMPLOYEE LOANS] Querying for business_id={business_id}")
        
        try:
            # Base query for loans with employee details
            query = self.db.query(
                EmployeeLoan,
                Employee,
                Department.name.label('department_name'),
                Designation.name.label('designation_name'),
                Location.name.label('location_name'),
                CostCenter.name.label('cost_center_name')
            ).join(
                Employee, EmployeeLoan.employee_id == Employee.id
            ).outerjoin(
                Department, Employee.department_id == Department.id
            ).outerjoin(
                Designation, Employee.designation_id == Designation.id
            ).outerjoin(
                Location, Employee.location_id == Location.id
            ).outerjoin(
                CostCenter, Employee.cost_center_id == CostCenter.id
            ).filter(
                Employee.employee_status == 'ACTIVE',
                Employee.business_id == business_id  # CRITICAL: Business isolation
            )
            
            # Apply filters
            if filters.get('location') and filters['location'] != "All Locations":
                query = query.filter(Location.name == filters['location'])
            
            if filters.get('department') and filters['department'] != "All Departments":
                query = query.filter(Department.name == filters['department'])
            
            if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
                query = query.filter(CostCenter.name == filters['cost_center'])
            
            if filters.get('employee_search'):
                search_term = f"%{filters['employee_search']}%"
                query = query.filter(
                    or_(
                        Employee.first_name.ilike(search_term),
                        Employee.last_name.ilike(search_term),
                        Employee.employee_code.ilike(search_term)
                    )
                )
            
            # Apply date range filter based on "issued_during"
            if filters.get('issued_during'):
                issued_during = filters['issued_during']
                today = datetime.now().date()
                
                if issued_during == "Last 30 days":
                    start_date = today - timedelta(days=30)
                elif issued_during == "Last 3 months":
                    start_date = today - timedelta(days=90)
                elif issued_during == "Last 6 months":
                    start_date = today - timedelta(days=180)
                elif issued_during == "Last 1 year":
                    start_date = today - timedelta(days=365)
                else:
                    start_date = None
                
                if start_date:
                    query = query.filter(EmployeeLoan.loan_date >= start_date)
            
            results = query.order_by(Employee.employee_code).all()
            logger.info(f"[EMPLOYEE LOANS] Query returned {len(results)} records")
            
            return results
            
        except Exception as e:
            logger.error(f"[EMPLOYEE LOANS] Error: {str(e)}")
            raise Exception(f"Failed to get employee loans report data: {str(e)}")

    def get_sap_export_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get SAP export data with employee salary details"""
        from app.models.employee import Employee, EmployeeProfile
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.reports import SalaryReport
        from app.models.attendance import AttendanceRecord, AttendanceStatus
        from sqlalchemy import or_
        from datetime import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[SAP EXPORT] Querying for period={period}, business_id={business_id}")
        
        try:
            # Parse period from frontend format (e.g., "SEP-2025" to "2025-09")
            if '-' in period and len(period.split('-')[0]) == 3:
                # Frontend format: "SEP-2025"
                month_obj = datetime.strptime(period, "%b-%Y")
                year = month_obj.year
                month_num = month_obj.month
                period_db = month_obj.strftime('%Y-%m')
            else:
                # Backend format: "2025-09"
                year, month_num = map(int, period.split('-'))
                period_db = period
            
            # Base query for employees with salary data
            query = self.db.query(
                SalaryReport,
                Employee,
                EmployeeProfile,
                Department.name.label('department_name'),
                Designation.name.label('designation_name'),
                Location.name.label('location_name'),
                CostCenter.name.label('cost_center_name')
            ).join(
                Employee, SalaryReport.employee_id == Employee.id
            ).outerjoin(
                EmployeeProfile, Employee.id == EmployeeProfile.employee_id
            ).outerjoin(
                Department, Employee.department_id == Department.id
            ).outerjoin(
                Designation, Employee.designation_id == Designation.id
            ).outerjoin(
                Location, Employee.location_id == Location.id
            ).outerjoin(
                CostCenter, Employee.cost_center_id == CostCenter.id
            ).filter(
                SalaryReport.report_period == period_db,
                Employee.employee_status == 'ACTIVE',
                Employee.business_id == business_id  # CRITICAL: Business isolation
            )
            
            # Apply filters
            if filters.get('location') and filters['location'] != "All Locations":
                query = query.filter(Location.name == filters['location'])
            
            if filters.get('department') and filters['department'] != "All Departments":
                query = query.filter(Department.name == filters['department'])
            
            if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
                query = query.filter(CostCenter.name == filters['cost_center'])
            
            if filters.get('employee_search'):
                search_term = f"%{filters['employee_search']}%"
                query = query.filter(
                    or_(
                        Employee.first_name.ilike(search_term),
                        Employee.last_name.ilike(search_term),
                        Employee.employee_code.ilike(search_term)
                    )
                )
            
            results = query.order_by(Employee.employee_code).all()
            logger.info(f"[SAP EXPORT] Query returned {len(results)} records for business_id={business_id}")
            return results
            
        except Exception as e:
            raise Exception(f"Failed to get SAP export data: {str(e)}")

    def get_attendance_register_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get attendance register data with employee attendance details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.attendance import AttendanceRecord, AttendanceStatus
        from datetime import datetime, timedelta
        from sqlalchemy import func, extract, case, or_
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[ATTENDANCE REGISTER] Querying for business_id={business_id}")
        
        try:
            # Parse date range
            from_date = None
            to_date = None
            
            if filters.get('from_date'):
                from_date = datetime.strptime(filters['from_date'], '%Y-%m-%d').date()
            if filters.get('to_date'):
                to_date = datetime.strptime(filters['to_date'], '%Y-%m-%d').date()
            
            # If no date range provided, use current month
            if not from_date or not to_date:
                today = datetime.now().date()
                from_date = today.replace(day=1)
                # Get last day of current month
                if today.month == 12:
                    to_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    to_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            
            logger.info(f"[ATTENDANCE REGISTER] Date range: {from_date} to {to_date}")
            
            # Base query for employees
            query = self.db.query(
                Employee,
                Department.name.label('department_name'),
                Designation.name.label('designation_name'),
                Location.name.label('location_name'),
                CostCenter.name.label('cost_center_name')
            ).outerjoin(
                Department, Employee.department_id == Department.id
            ).outerjoin(
                Designation, Employee.designation_id == Designation.id
            ).outerjoin(
                Location, Employee.location_id == Location.id
            ).outerjoin(
                CostCenter, Employee.cost_center_id == CostCenter.id
            ).filter(
                Employee.business_id == business_id  # CRITICAL: Business isolation
            )
            
            # Apply filters
            if filters.get('location') and filters['location'] != "All Locations":
                query = query.filter(Location.name == filters['location'])
            
            if filters.get('department') and filters['department'] != "All Departments":
                query = query.filter(Department.name == filters['department'])
            
            if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
                query = query.filter(CostCenter.name == filters['cost_center'])
            
            if filters.get('employee'):
                search_term = f"%{filters['employee']}%"
                query = query.filter(
                    or_(
                        Employee.first_name.ilike(search_term),
                        Employee.last_name.ilike(search_term),
                        Employee.employee_code.ilike(search_term)
                    )
                )
            
            # Apply record type filter
            record_type = filters.get('record_type', 'All Records')
            if record_type == 'Active Records':
                query = query.filter(Employee.employee_status == 'ACTIVE')
            elif record_type == 'Inactive Records':
                query = query.filter(Employee.employee_status != 'ACTIVE')
            
            employees_data = query.all()
            logger.info(f"[ATTENDANCE REGISTER] Found {len(employees_data)} employees")
            
            # Get attendance data for the date range
            attendance_by_employee = {}
            if employees_data:
                employee_ids = [emp[0].id for emp in employees_data]
                
                attendance_query = self.db.query(AttendanceRecord).filter(
                    AttendanceRecord.employee_id.in_(employee_ids),
                    AttendanceRecord.attendance_date >= from_date,
                    AttendanceRecord.attendance_date <= to_date
                ).order_by(AttendanceRecord.employee_id, AttendanceRecord.attendance_date)
                
                attendance_records = attendance_query.all()
                logger.info(f"[ATTENDANCE REGISTER] Found {len(attendance_records)} attendance records")
                
                # Group attendance by employee
                for record in attendance_records:
                    if record.employee_id not in attendance_by_employee:
                        attendance_by_employee[record.employee_id] = []
                    attendance_by_employee[record.employee_id].append(record)
            
            return {
                'employees': employees_data,
                'attendance': attendance_by_employee,
                'date_range': {'from_date': from_date, 'to_date': to_date}
            }
            
        except Exception as e:
            logger.error(f"[ATTENDANCE REGISTER] Error: {str(e)}")
            raise Exception(f"Failed to get attendance register data: {str(e)}")

    def get_sap_mapping(self, business_id: Optional[int] = None) -> Optional[Any]:
        """Get SAP mapping configuration"""
        from app.models.setup.Integrations.sap_mapping import SAPMapping
        
        try:
            query = self.db.query(SAPMapping)
            if business_id:
                query = query.filter(SAPMapping.business_id == business_id)
            
            return query.first()
            
        except Exception as e:
            raise Exception(f"Failed to get SAP mapping: {str(e)}")

    def get_leave_encashment_report_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get leave encashment report data with employee details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.payroll import LeaveEncashment, PayrollPeriod
        from app.models.datacapture import SalaryVariable, SalaryVariableType
        from sqlalchemy import func, extract, case, or_
        from datetime import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[LEAVE ENCASHMENT] Querying for period={period}, business_id={business_id}")
        
        # Parse period from frontend format (e.g., "OCT-2025" to "2025-10")
        if '-' in period and len(period.split('-')[0]) == 3:
            # Frontend format: "OCT-2025"
            month_obj = datetime.strptime(period, "%b-%Y")
            year = month_obj.year
            month = month_obj.month
        else:
            # Backend format: "2025-10"
            year, month = map(int, period.split('-'))
        
        # First, try to get data from LeaveEncashment table (if exists)
        leave_encashment_query = self.db.query(
            LeaveEncashment,
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).join(
            Employee, LeaveEncashment.employee_id == Employee.id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            extract('year', LeaveEncashment.payment_period) == year,
            extract('month', LeaveEncashment.payment_period) == month,
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            leave_encashment_query = leave_encashment_query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            leave_encashment_query = leave_encashment_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            leave_encashment_query = leave_encashment_query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            leave_encashment_query = leave_encashment_query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        leave_encashment_data = leave_encashment_query.all()
        
        logger.info(f"[LEAVE ENCASHMENT] Found {len(leave_encashment_data)} records from LeaveEncashment table")
        
        # If no data in LeaveEncashment table, get from SalaryVariable table (Leave Encashment entries)
        if not leave_encashment_data:
            logger.info(f"[LEAVE ENCASHMENT] Checking SalaryVariable table for business_id={business_id}")
            salary_variable_query = self.db.query(
                SalaryVariable,
                Employee,
                Department.name.label('department_name'),
                Designation.name.label('designation_name'),
                Location.name.label('location_name'),
                CostCenter.name.label('cost_center_name')
            ).join(
                Employee, SalaryVariable.employee_id == Employee.id
            ).outerjoin(
                Department, Employee.department_id == Department.id
            ).outerjoin(
                Designation, Employee.designation_id == Designation.id
            ).outerjoin(
                Location, Employee.location_id == Location.id
            ).outerjoin(
                CostCenter, Employee.cost_center_id == CostCenter.id
            ).filter(
                extract('year', SalaryVariable.effective_date) == year,
                extract('month', SalaryVariable.effective_date) == month,
                SalaryVariable.variable_name.ilike('%leave%encashment%'),
                SalaryVariable.is_active == True,
                Employee.employee_status == 'ACTIVE',
                Employee.business_id == business_id  # CRITICAL: Business isolation
            )
            
            # Apply same filters
            if filters.get('location') and filters['location'] != "All Locations":
                salary_variable_query = salary_variable_query.filter(Location.name == filters['location'])
            
            if filters.get('department') and filters['department'] != "All Departments":
                salary_variable_query = salary_variable_query.filter(Department.name == filters['department'])
            
            if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
                salary_variable_query = salary_variable_query.filter(CostCenter.name == filters['cost_center'])
            
            if filters.get('employee_search'):
                search_term = f"%{filters['employee_search']}%"
                salary_variable_query = salary_variable_query.filter(
                    or_(
                        Employee.first_name.ilike(search_term),
                        Employee.last_name.ilike(search_term),
                        Employee.employee_code.ilike(search_term)
                    )
                )
            
            return salary_variable_query.order_by(Employee.employee_code).all()
        
        return leave_encashment_data

    def get_rate_salary_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get rate salary data with employee rate-based calculations"""
        from app.models.employee import Employee, EmployeeSalary
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.setup.salary_and_deductions.salary_component import SalaryComponent
        from app.models.setup.salary_and_deductions.salary_structure import SalaryStructure
        from app.models.attendance import AttendanceRecord, AttendanceStatus
        from sqlalchemy import func, extract, case, or_, and_
        from datetime import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[RATE SALARY] Querying for period={period}, business_id={business_id}")
        
        # Parse period from frontend format (e.g., "JUN-2025" to "2025-06")
        if '-' in period and len(period.split('-')[0]) == 3:
            # Frontend format: "JUN-2025"
            month_obj = datetime.strptime(period, "%b-%Y")
            year = month_obj.year
            month = month_obj.month
        else:
            # Backend format: "2025-06"
            year, month = map(int, period.split('-'))
        
        # Base query for employees with salary structures
        query = self.db.query(
            EmployeeSalary,
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            SalaryStructure.name.label('salary_structure_name')
        ).join(
            Employee, EmployeeSalary.employee_id == Employee.id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            SalaryStructure, EmployeeSalary.salary_structure_id == SalaryStructure.id
        ).filter(
            Employee.employee_status == 'ACTIVE',
            EmployeeSalary.is_active == True,
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            query = query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            query = query.filter(Department.name == filters['department'])
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        # Get latest salary record for each employee
        subquery = self.db.query(
            EmployeeSalary.employee_id,
            func.max(EmployeeSalary.effective_from).label('max_effective_from')
        ).filter(
            EmployeeSalary.is_active == True
        ).group_by(EmployeeSalary.employee_id).subquery()
        
        query = query.join(
            subquery,
            and_(
                EmployeeSalary.employee_id == subquery.c.employee_id,
                EmployeeSalary.effective_from == subquery.c.max_effective_from
            )
        )
        
        employees_data = query.all()
        
        # Get attendance data for the period to calculate working days
        if employees_data:
            employee_ids = [emp[1].id for emp in employees_data]
            
            # Calculate start and end dates for the month
            from calendar import monthrange
            days_in_month = monthrange(year, month)[1]
            start_date = datetime(year, month, 1).date()
            end_date = datetime(year, month, days_in_month).date()
            
            # Get attendance records for the period
            attendance_data = {}
            attendance_records = self.db.query(
                AttendanceRecord.employee_id,
                func.count(
                    case(
                        (AttendanceRecord.attendance_status == AttendanceStatus.PRESENT, 1),
                        else_=None
                    )
                ).label('working_days')
            ).filter(
                AttendanceRecord.employee_id.in_(employee_ids),
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date
            ).group_by(AttendanceRecord.employee_id).all()
            
            for record in attendance_records:
                attendance_data[record.employee_id] = record.working_days or 22  # Default 22 working days
        
        # Combine employee data with attendance data
        result = []
        for emp_data in employees_data:
            salary_record = emp_data[0]
            employee = emp_data[1]
            working_days = attendance_data.get(employee.id, 22) if employees_data else 22
            
            result.append((emp_data, working_days))
        
        return result

    def get_leave_register_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get leave register data with employee leave details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.attendance import AttendanceRecord, AttendanceStatus
        from app.models.leave_balance import LeaveBalance
        from app.models.reports import SalaryReport
        from datetime import datetime, date
        from calendar import monthrange
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[LEAVE REGISTER] Querying for business_id={business_id}")
        
        try:
            # Parse year and month
            year = int(filters.get('year', 2025))
            month_name = filters.get('month', 'December')
            
            logger.info(f"[LEAVE REGISTER] Year={year}, Month={month_name}")
            
            # Convert month name to number
            month_mapping = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4,
                'May': 5, 'June': 6, 'July': 7, 'August': 8,
                'September': 9, 'October': 10, 'November': 11, 'December': 12
            }
            
            # Get data for all months from January to the selected month
            end_month = month_mapping.get(month_name, 12)
            
            # Base query for employees
            query = self.db.query(
                Employee,
                Department.name.label('department_name'),
                Designation.name.label('designation_name'),
                Location.name.label('location_name'),
                CostCenter.name.label('cost_center_name')
            ).outerjoin(
                Department, Employee.department_id == Department.id
            ).outerjoin(
                Designation, Employee.designation_id == Designation.id
            ).outerjoin(
                Location, Employee.location_id == Location.id
            ).outerjoin(
                CostCenter, Employee.cost_center_id == CostCenter.id
            ).filter(
                Employee.employee_status == 'ACTIVE',
                Employee.business_id == business_id  # CRITICAL: Business isolation
            )
            
            # Apply filters
            if filters.get('location') and filters['location'] != "All Locations":
                query = query.filter(Location.name == filters['location'])
            
            if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
                query = query.filter(CostCenter.name == filters['cost_center'])
            
            if filters.get('department') and filters['department'] != "All Departments":
                query = query.filter(Department.name == filters['department'])
            
            employees_data = query.all()
            logger.info(f"[LEAVE REGISTER] Found {len(employees_data)} employees")
            
            if not employees_data:
                return []
            
            # Get employee IDs
            employee_ids = [emp[0].id for emp in employees_data]
            
            # Get attendance and salary data for each month
            result = []
            
            for month_num in range(1, end_month + 1):
                # Get month name
                month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                month_str = f"{month_names[month_num]}-{year}"
                
                # Calculate days in month
                days_in_month = monthrange(year, month_num)[1]
                start_date = date(year, month_num, 1)
                end_date = date(year, month_num, days_in_month)
                
                # Get attendance data for this month
                attendance_data = self.db.query(
                    AttendanceRecord.employee_id,
                    func.count(
                        case(
                            (AttendanceRecord.attendance_status == AttendanceStatus.PRESENT, 1),
                            else_=None
                        )
                    ).label('present_days'),
                    func.count(
                        case(
                            (AttendanceRecord.attendance_status == AttendanceStatus.ABSENT, 1),
                            else_=None
                        )
                    ).label('absent_days'),
                    func.count(
                        case(
                            (AttendanceRecord.attendance_status == AttendanceStatus.ON_LEAVE, 1),
                            else_=None
                        )
                    ).label('leave_days'),
                    func.count(
                        case(
                            (AttendanceRecord.attendance_status == AttendanceStatus.WEEKEND, 1),
                            else_=None
                        )
                    ).label('week_off_days')
                ).filter(
                    AttendanceRecord.employee_id.in_(employee_ids),
                    AttendanceRecord.attendance_date >= start_date,
                    AttendanceRecord.attendance_date <= end_date
                ).group_by(AttendanceRecord.employee_id).all()
                
                # Create attendance lookup
                attendance_lookup = {}
                for att in attendance_data:
                    attendance_lookup[att.employee_id] = {
                        'present_days': att.present_days or 0,
                        'absent_days': att.absent_days or 0,
                        'leave_days': att.leave_days or 0,
                        'week_off_days': att.week_off_days or 0
                    }
                
                # Get salary data for this month
                salary_period = f"{year}-{month_num:02d}"
                salary_data = self.db.query(SalaryReport).filter(
                    SalaryReport.employee_id.in_(employee_ids),
                    SalaryReport.report_period == salary_period
                ).all()
                
                # Create salary lookup
                salary_lookup = {}
                for sal in salary_data:
                    salary_lookup[sal.employee_id] = sal.net_salary
                
                # Process each employee for this month
                for emp_data in employees_data:
                    employee = emp_data[0]
                    dept_name = emp_data[1]
                    desig_name = emp_data[2]
                    loc_name = emp_data[3]
                    cc_name = emp_data[4]
                    
                    # Get attendance for this employee and month
                    att_data = attendance_lookup.get(employee.id, {
                        'present_days': 0,
                        'absent_days': 0,
                        'leave_days': 0,
                        'week_off_days': 0
                    })
                    
                    # Calculate days worked (present + paid leaves)
                    days_worked = att_data['present_days'] + att_data['leave_days']
                    
                    # Calculate unpaid leaves (absents)
                    unpaid_leaves = att_data['absent_days']
                    
                    # Calculate paid leaves
                    paid_leaves = att_data['leave_days']
                    
                    # Get wages (salary) for this month
                    wages = salary_lookup.get(employee.id, 0)
                    
                    # Add employee record for this month
                    result.append((
                        employee,
                        dept_name,
                        desig_name,
                        loc_name,
                        cc_name,
                        month_str,
                        days_worked,
                        unpaid_leaves,
                        paid_leaves,
                        wages
                    ))
            
            logger.info(f"[LEAVE REGISTER] Query returned {len(result)} records for business_id={business_id}")
            return result
            
        except Exception as e:
            logger.error(f"[LEAVE REGISTER] Error: {str(e)}")
            raise Exception(f"Failed to get leave register data: {str(e)}")

    def get_salary_summary(self, period: str) -> Dict[str, Any]:
        """Get salary summary for a period"""
        result = self.db.query(
            func.count(SalaryReport.id).label('total_employees'),
            func.sum(SalaryReport.gross_salary).label('total_gross'),
            func.sum(SalaryReport.net_salary).label('total_net'),
            func.sum(SalaryReport.total_deductions).label('total_deductions'),
            func.avg(SalaryReport.gross_salary).label('avg_salary')
        ).filter(SalaryReport.report_period == period).first()
        
        return {
            'total_employees': result.total_employees or 0,
            'total_gross_salary': float(result.total_gross or 0),
            'total_net_salary': float(result.total_net or 0),
            'total_deductions': float(result.total_deductions or 0),
            'average_salary': float(result.avg_salary or 0)
        }
    
    # Attendance Report Methods
    def create_attendance_report(self, report_data: AttendanceReportCreate) -> AttendanceReport:
        """Create a new attendance report"""
        db_report = AttendanceReport(**report_data.dict())
        self.db.add(db_report)
        self.db.commit()
        self.db.refresh(db_report)
        return db_report
    
    def get_attendance_reports(self, filters: ReportFilters) -> List[AttendanceReport]:
        """Get attendance reports with filters"""
        query = self.db.query(AttendanceReport)
        
        if filters.employee_ids:
            query = query.filter(AttendanceReport.employee_id.in_(filters.employee_ids))
        
        if filters.start_date:
            query = query.filter(AttendanceReport.report_date >= filters.start_date)
        
        if filters.end_date:
            query = query.filter(AttendanceReport.report_date <= filters.end_date)
        
        if filters.status:
            query = query.filter(AttendanceReport.status == filters.status)
        
        return query.order_by(desc(AttendanceReport.report_date)).all()
    
    def get_attendance_summary(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get attendance summary for a date range"""
        from sqlalchemy import case
        
        result = self.db.query(
            func.count(func.distinct(AttendanceReport.employee_id)).label('total_employees'),
            func.count(case((AttendanceReport.status == 'present', 1))).label('present_count'),
            func.count(case((AttendanceReport.status == 'absent', 1))).label('absent_count'),
            func.count(case((AttendanceReport.status == 'leave', 1))).label('leave_count')
        ).filter(
            and_(
                AttendanceReport.report_date >= start_date,
                AttendanceReport.report_date <= end_date
            )
        ).first()
        
        total_records = (result.present_count or 0) + (result.absent_count or 0) + (result.leave_count or 0)
        attendance_percentage = ((result.present_count or 0) / total_records * 100) if total_records > 0 else 0
        
        return {
            'total_employees': result.total_employees or 0,
            'present_count': result.present_count or 0,
            'absent_count': result.absent_count or 0,
            'leave_count': result.leave_count or 0,
            'attendance_percentage': round(attendance_percentage, 2)
        }
    
    # Employee Report Methods
    def create_employee_report(self, report_data: EmployeeReportCreate) -> EmployeeReport:
        """Create a new employee report"""
        db_report = EmployeeReport(**report_data.dict())
        self.db.add(db_report)
        self.db.commit()
        self.db.refresh(db_report)
        return db_report
    
    def get_employee_reports(self, filters: ReportFilters) -> List[EmployeeReport]:
        """Get employee reports with filters"""
        query = self.db.query(EmployeeReport)
        
        if filters.employee_ids:
            query = query.filter(EmployeeReport.employee_id.in_(filters.employee_ids))
        
        if filters.report_type:
            query = query.filter(EmployeeReport.report_type == filters.report_type)
        
        if filters.status:
            query = query.filter(EmployeeReport.status == filters.status)
        
        return query.order_by(desc(EmployeeReport.created_at)).all()
    
    # Statutory Report Methods
    def create_statutory_report(self, report_data: StatutoryReportCreate) -> StatutoryReport:
        """Create a new statutory report"""
        db_report = StatutoryReport(**report_data.dict())
        self.db.add(db_report)
        self.db.commit()
        self.db.refresh(db_report)
        return db_report
    
    def get_statutory_reports(self, filters: ReportFilters) -> List[StatutoryReport]:
        """Get statutory reports with filters"""
        query = self.db.query(StatutoryReport)
        
        if filters.employee_ids:
            query = query.filter(StatutoryReport.employee_id.in_(filters.employee_ids))
        
        if filters.report_type:
            query = query.filter(StatutoryReport.report_type == filters.report_type)
        
        if filters.start_date and filters.end_date:
            start_period = filters.start_date.strftime('%Y-%m')
            end_period = filters.end_date.strftime('%Y-%m')
            query = query.filter(
                and_(
                    StatutoryReport.report_period >= start_period,
                    StatutoryReport.report_period <= end_period
                )
            )
        
        return query.order_by(desc(StatutoryReport.created_at)).all()
    
    # Annual Report Methods
    def create_annual_report(self, report_data: AnnualReportCreate) -> AnnualReport:
        """Create a new annual report"""
        db_report = AnnualReport(**report_data.dict())
        self.db.add(db_report)
        self.db.commit()
        self.db.refresh(db_report)
        return db_report
    
    def get_annual_reports(self, filters: ReportFilters) -> List[AnnualReport]:
        """Get annual reports with filters"""
        query = self.db.query(AnnualReport)
        
        if filters.employee_ids:
            query = query.filter(AnnualReport.employee_id.in_(filters.employee_ids))
        
        if filters.report_type:
            query = query.filter(AnnualReport.report_type == filters.report_type)
        
        return query.order_by(desc(AnnualReport.report_year)).all()
    
    # Activity Log Methods
    def create_activity_log(self, user_id: int, log_data: ActivityLogCreate) -> ActivityLog:
        """Create a new activity log"""
        db_log = ActivityLog(
            user_id=user_id,
            **log_data.dict()
        )
        self.db.add(db_log)
        self.db.commit()
        self.db.refresh(db_log)
        return db_log
    
    def get_activity_logs(self, user_id: Optional[int] = None, limit: int = 100) -> List[ActivityLog]:
        """Get activity logs"""
        query = self.db.query(ActivityLog)
        if user_id:
            query = query.filter(ActivityLog.user_id == user_id)
        return query.order_by(desc(ActivityLog.created_at)).limit(limit).all()

    def get_activity_logs_with_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get activity logs with date range and other filters"""
        from app.models.user import User
        from app.models.business import Business
        from datetime import datetime, date
        
        logger.info(f"Getting activity logs with filters: {filters}")
        
        try:
            # CRITICAL: Get business_id from filters for security
            business_id = filters.get('business_id')
            if not business_id:
                raise ValueError("business_id is required for security")
            
            logger.info(f"[ACTIVITY LOGS] Filtering for business_id={business_id}")
            
            # Base query with user relationship
            # Filter to only show logs from the business owner (current user)
            query = self.db.query(ActivityLog, User.name.label('user_name')).join(
                User, ActivityLog.user_id == User.id
            ).join(
                Business, Business.owner_id == User.id
            ).filter(
                Business.id == business_id  # SECURITY: Filter by business_id
            )
            
            # Apply date range filters
            if filters.get('from_date'):
                try:
                    from_date = datetime.strptime(filters['from_date'], '%Y-%m-%d').date()
                    query = query.filter(func.date(ActivityLog.created_at) >= from_date)
                except ValueError:
                    pass
            
            if filters.get('to_date'):
                try:
                    to_date = datetime.strptime(filters['to_date'], '%Y-%m-%d').date()
                    query = query.filter(func.date(ActivityLog.created_at) <= to_date)
                except ValueError:
                    pass
            
            # Apply other filters
            if filters.get('user_id'):
                query = query.filter(ActivityLog.user_id == filters['user_id'])
            
            if filters.get('module'):
                query = query.filter(ActivityLog.module.ilike(f"%{filters['module']}%"))
            
            if filters.get('action'):
                query = query.filter(ActivityLog.action.ilike(f"%{filters['action']}%"))
            
            # Get total count before applying limit
            total_count = query.count()
            
            logger.info(f"[ACTIVITY LOGS] Found {total_count} logs for business_id={business_id}")
            
            # Apply limit and order
            limit = filters.get('limit', 100)
            results = query.order_by(desc(ActivityLog.created_at)).limit(limit).all()
            
            logger.info(f"[ACTIVITY LOGS] Returning {len(results)} logs (limited to {limit})")
            
            return {
                "logs": results,
                "total_count": total_count,
                "message": "Activity logs retrieved successfully"
            }
            
        except Exception as e:
            logger.error(f"Error in get_activity_logs_with_filters: {e}")
            import traceback
            traceback.print_exc()
            return {
                "logs": [],
                "total_count": 0,
                "message": f"Error retrieving activity logs: {str(e)}"
            }
    
    # User Feedback Methods
    def create_user_feedback(self, user_id: int, feedback_data: UserFeedbackCreate) -> UserFeedback:
        """Create a new user feedback"""
        db_feedback = UserFeedback(
            user_id=user_id,
            **feedback_data.dict()
        )
        self.db.add(db_feedback)
        self.db.commit()
        self.db.refresh(db_feedback)
        return db_feedback
    
    def get_user_feedback(self, limit: int = 100) -> List[UserFeedback]:
        """Get user feedback"""
        return self.db.query(UserFeedback).order_by(desc(UserFeedback.created_at)).limit(limit).all()
    
    def update_feedback_status(self, feedback_id: int, status: str, resolved_by: Optional[int] = None) -> Optional[UserFeedback]:
        """Update feedback status"""
        db_feedback = self.db.query(UserFeedback).filter(UserFeedback.id == feedback_id).first()
        if db_feedback:
            db_feedback.status = status
            if status == "resolved" and resolved_by:
                db_feedback.resolved_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(db_feedback)
        return db_feedback

    def get_user_feedback_with_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get user feedback with date range and other filters"""
        from app.models.user import User
        from app.models.business import Business
        from datetime import datetime, date
        
        logger.info(f"Getting user feedback with filters: {filters}")
        
        try:
            # CRITICAL: Get business_id from filters for security
            business_id = filters.get('business_id')
            if not business_id:
                raise ValueError("business_id is required for security")
            
            logger.info(f"[USER FEEDBACK] Filtering for business_id={business_id}")
            
            # Base query with user relationship
            # Filter to only show feedback from the business owner (current user)
            query = self.db.query(UserFeedback, User.name.label('user_name')).join(
                User, UserFeedback.user_id == User.id
            ).join(
                Business, Business.owner_id == User.id
            ).filter(
                Business.id == business_id  # SECURITY: Filter by business_id
            )
            
            # Apply date range filters
            if filters.get('from_date'):
                try:
                    from_date = datetime.strptime(filters['from_date'], '%Y-%m-%d').date()
                    query = query.filter(func.date(UserFeedback.created_at) >= from_date)
                except ValueError:
                    pass
            
            if filters.get('to_date'):
                try:
                    to_date = datetime.strptime(filters['to_date'], '%Y-%m-%d').date()
                    query = query.filter(func.date(UserFeedback.created_at) <= to_date)
                except ValueError:
                    pass
            
            # Apply other filters
            if filters.get('feedback_type'):
                query = query.filter(UserFeedback.feedback_type == filters['feedback_type'])
            
            if filters.get('status'):
                query = query.filter(UserFeedback.status == filters['status'])
            
            if filters.get('rating'):
                query = query.filter(UserFeedback.rating == filters['rating'])
            
            # Get total count before applying limit
            total_count = query.count()
            
            logger.info(f"[USER FEEDBACK] Found {total_count} feedback for business_id={business_id}")
            
            # Apply limit and order
            limit = filters.get('limit', 100)
            results = query.order_by(desc(UserFeedback.created_at)).limit(limit).all()
            
            logger.info(f"[USER FEEDBACK] Returning {len(results)} feedback (limited to {limit})")
            
            return {
                "feedback": results,
                "total_count": total_count,
                "message": "User feedback retrieved successfully"
            }
            
        except Exception as e:
            logger.error(f"Error in get_user_feedback_with_filters: {e}")
            import traceback
            traceback.print_exc()
            return {
                "feedback": [],
                "total_count": 0,
                "message": f"Error retrieving user feedback: {str(e)}"
            }
    
    # System Alert Methods
    def create_system_alert(self, alert_data: SystemAlertCreate) -> SystemAlert:
        """Create a new system alert"""
        db_alert = SystemAlert(**alert_data.dict())
        self.db.add(db_alert)
        self.db.commit()
        self.db.refresh(db_alert)
        return db_alert
    
    def get_system_alerts(self, is_resolved: Optional[bool] = None, limit: int = 100) -> List[SystemAlert]:
        """Get system alerts"""
        query = self.db.query(SystemAlert)
        if is_resolved is not None:
            query = query.filter(SystemAlert.is_resolved == is_resolved)
        return query.order_by(desc(SystemAlert.created_at)).limit(limit).all()
    
    def resolve_system_alert(self, alert_id: int, resolved_by: int) -> Optional[SystemAlert]:
        """Resolve system alert"""
        db_alert = self.db.query(SystemAlert).filter(SystemAlert.id == alert_id).first()
        if db_alert:
            db_alert.is_resolved = True
            db_alert.resolved_at = datetime.utcnow()
            db_alert.resolved_by = resolved_by
            self.db.commit()
            self.db.refresh(db_alert)
        return db_alert

    def get_system_alerts_with_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get system alerts with date range and other filters"""
        from app.models.user import User
        from app.models.business import Business
        from datetime import datetime, date
        
        logger.info(f"Getting system alerts with filters: {filters}")
        
        try:
            # CRITICAL: Get business_id from filters for security
            business_id = filters.get('business_id')
            if not business_id:
                raise ValueError("business_id is required for security")
            
            logger.info(f"[SYSTEM ALERTS] Filtering for business_id={business_id}")
            
            # Base query with user relationship for resolver
            # SECURITY: Show all unresolved alerts (system-wide) OR resolved alerts by users from this business
            query = self.db.query(SystemAlert, User.name.label('resolver_name')).outerjoin(
                User, SystemAlert.resolved_by == User.id
            ).outerjoin(
                Business, Business.owner_id == User.id
            ).filter(
                or_(
                    SystemAlert.is_resolved == False,  # Show all unresolved alerts
                    and_(
                        SystemAlert.is_resolved == True,
                        Business.id == business_id  # Show resolved alerts only if resolved by business owner
                    )
                )
            )
            
            # Apply date range filters
            if filters.get('from_date'):
                try:
                    from_date = datetime.strptime(filters['from_date'], '%Y-%m-%d').date()
                    query = query.filter(func.date(SystemAlert.created_at) >= from_date)
                except ValueError:
                    pass
            
            if filters.get('to_date'):
                try:
                    to_date = datetime.strptime(filters['to_date'], '%Y-%m-%d').date()
                    query = query.filter(func.date(SystemAlert.created_at) <= to_date)
                except ValueError:
                    pass
            
            # Apply other filters
            if filters.get('alert_type'):
                query = query.filter(SystemAlert.alert_type == filters['alert_type'])
            
            if filters.get('is_resolved') is not None:
                query = query.filter(SystemAlert.is_resolved == filters['is_resolved'])
            
            if filters.get('module'):
                query = query.filter(SystemAlert.module.ilike(f"%{filters['module']}%"))
            
            # Get total count before applying limit
            total_count = query.count()
            
            logger.info(f"[SYSTEM ALERTS] Found {total_count} alerts for business_id={business_id}")
            
            # Apply limit and order
            limit = filters.get('limit', 100)
            results = query.order_by(desc(SystemAlert.created_at)).limit(limit).all()
            
            logger.info(f"[SYSTEM ALERTS] Returning {len(results)} alerts (limited to {limit})")
            
            return {
                "alerts": results,
                "total_count": total_count,
                "message": "System alerts retrieved successfully"
            }
            
        except Exception as e:
            logger.error(f"Error in get_system_alerts_with_filters: {e}")
            import traceback
            traceback.print_exc()
            return {
                "alerts": [],
                "total_count": 0,
                "message": f"Error retrieving system alerts: {str(e)}"
            }
    
    def get_time_register_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get time register data with employee time breakdown details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.attendance import AttendanceRecord, AttendanceStatus
        from app.models.datacapture import ExtraHour
        from sqlalchemy import func, extract, case, or_
        from datetime import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[TIME REGISTER] Querying for period={period}, business_id={business_id}")
        
        # Parse period from frontend format (e.g., "NOV-2025" to "2025-11")
        if '-' in period and len(period.split('-')[0]) == 3:
            # Frontend format: "NOV-2025"
            month_obj = datetime.strptime(period, "%b-%Y")
            year = month_obj.year
            month = month_obj.month
        else:
            # Backend format: "2025-11"
            year, month = map(int, period.split('-'))
        
        # Base query for employees
        query = self.db.query(
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('business_unit') and filters['business_unit'] != "All Units":
            # Filter by business name
            from app.models.business import Business
            business = self.db.query(Business).filter(Business.business_name == filters['business_unit']).first()
            if business:
                query = query.filter(Employee.business_id == business.id)
        
        if filters.get('location') and filters['location'] != "All Locations":
            query = query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            query = query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('salary_component') and filters['salary_component']:
            # Filter by salary component (salary unit)
            from app.models.datacapture import EmployeeSalaryUnit, SalaryUnit
            # Get employees who have this salary component assigned
            salary_unit_subquery = self.db.query(EmployeeSalaryUnit.employee_id).join(
                SalaryUnit, EmployeeSalaryUnit.salary_unit_id == SalaryUnit.id
            ).filter(
                SalaryUnit.unit_name == filters['salary_component']
            ).subquery()
            query = query.filter(Employee.id.in_(salary_unit_subquery))
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        employees_data = query.all()
        logger.info(f"[TIME REGISTER] Found {len(employees_data)} employees")
        
        # Get attendance data for the period
        if employees_data:
            employee_ids = [emp[0].id for emp in employees_data]
            
            # Calculate start and end dates for the month
            from calendar import monthrange
            days_in_month = monthrange(year, month)[1]
            start_date = datetime(year, month, 1).date()
            end_date = datetime(year, month, days_in_month).date()
            
            # Get attendance records for the period
            attendance_records = self.db.query(
                AttendanceRecord.employee_id,
                func.count(AttendanceRecord.id).label('total_records'),
                func.sum(
                    case(
                        (AttendanceRecord.attendance_status == AttendanceStatus.PRESENT, 1),
                        else_=0
                    )
                ).label('present_days'),
                func.sum(
                    case(
                        (AttendanceRecord.punch_in_time.isnot(None), 
                         func.extract('epoch', AttendanceRecord.punch_out_time - AttendanceRecord.punch_in_time) / 3600),
                        else_=0
                    )
                ).label('total_hours'),
                func.avg(
                    case(
                        (AttendanceRecord.punch_in_time.isnot(None), 
                         func.extract('epoch', AttendanceRecord.punch_out_time - AttendanceRecord.punch_in_time) / 3600),
                        else_=0
                    )
                ).label('avg_hours_per_day')
            ).filter(
                AttendanceRecord.employee_id.in_(employee_ids),
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date
            ).group_by(AttendanceRecord.employee_id).all()
            
            # Get overtime data for the period
            overtime_records = self.db.query(
                ExtraHour.employee_id,
                func.sum(ExtraHour.extra_hours).label('total_overtime_hours')
            ).filter(
                ExtraHour.employee_id.in_(employee_ids),
                extract('year', ExtraHour.work_date) == year,
                extract('month', ExtraHour.work_date) == month,
                ExtraHour.is_approved == True
            ).group_by(ExtraHour.employee_id).all()
            
            # Create lookup dictionaries
            attendance_lookup = {record.employee_id: record for record in attendance_records}
            overtime_lookup = {record.employee_id: record for record in overtime_records}
            
            # Combine data
            result = []
            for employee_data in employees_data:
                employee = employee_data[0]
                attendance = attendance_lookup.get(employee.id)
                overtime = overtime_lookup.get(employee.id)
                
                result.append((
                    employee_data,  # Employee with related data
                    attendance,     # Attendance summary
                    overtime        # Overtime summary
                ))
            
            logger.info(f"[TIME REGISTER] Query returned {len(result)} records for business_id={business_id}")
            return result
        
        return []
    def get_strike_register_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get strike register data with employee strike details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.strike_adjustment import StrikeAdjustment
        from app.models.strike_rule import StrikeRule
        from app.models.attendance import AttendanceRecord, AttendanceStatus
        from sqlalchemy import func, extract, case, or_
        from datetime import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[STRIKE REGISTER] Querying for period={period}, business_id={business_id}")
        
        # Parse period from frontend format (e.g., "JUL-2025" to "2025-07")
        if '-' in period and len(period.split('-')[0]) == 3:
            # Frontend format: "JUL-2025"
            month_obj = datetime.strptime(period, "%b-%Y")
            year = month_obj.year
            month = month_obj.month
        else:
            # Backend format: "2025-07"
            year, month = map(int, period.split('-'))
        
        # Base query for employees
        query = self.db.query(
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            query = query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            query = query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        employees_data = query.all()
        logger.info(f"[STRIKE REGISTER] Found {len(employees_data)} employees")
        
        # Get strike adjustments and rules for the business
        if employees_data:
            # Get strike rules for the business
            strike_rules = self.db.query(StrikeRule).filter(
                StrikeRule.business_id == business_id
            ).all()
            
            # Get strike adjustments for the business
            strike_adjustments = self.db.query(StrikeAdjustment).filter(
                StrikeAdjustment.business_id == business_id
            ).all()
            
            # Get attendance records for the period to identify strikes
            employee_ids = [emp[0].id for emp in employees_data]
            
            # Calculate start and end dates for the month
            from calendar import monthrange
            days_in_month = monthrange(year, month)[1]
            start_date = datetime(year, month, 1).date()
            end_date = datetime(year, month, days_in_month).date()
            
            # Get attendance records that could indicate strikes - fetch full objects
            attendance_records = self.db.query(AttendanceRecord).filter(
                AttendanceRecord.employee_id.in_(employee_ids),
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date
            ).all()
            
            # Group attendance by employee
            attendance_by_employee = {}
            for record in attendance_records:
                if record.employee_id not in attendance_by_employee:
                    attendance_by_employee[record.employee_id] = []
                attendance_by_employee[record.employee_id].append(record)
            
            # Combine data
            result = []
            for employee_data in employees_data:
                employee = employee_data[0]
                attendance_records = attendance_by_employee.get(employee.id, [])
                
                result.append((
                    employee_data,      # Employee with related data
                    attendance_records, # Attendance records for strike analysis
                    strike_rules,       # Strike rules for the business
                    strike_adjustments  # Strike adjustments for the business
                ))
            
            logger.info(f"[STRIKE REGISTER] Query returned {len(result)} records for business_id={business_id}")
            return result
        
        return []

    def get_travel_register_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get travel register data with employee travel details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.datacapture import TravelRequest
        from sqlalchemy import func, or_, and_
        from datetime import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[TRAVEL REGISTER] Querying for business_id={business_id}")
        
        # Base query with all joins
        query = self.db.query(
            TravelRequest,
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).join(
            Employee, TravelRequest.employee_id == Employee.id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            query = query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            query = query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee_id'):
            search_term = f"%{filters['employee_id']}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        # Apply date filters
        if filters.get('date_from'):
            try:
                from_date = datetime.strptime(filters['date_from'], '%Y-%m-%d').date()
                query = query.filter(TravelRequest.travel_date >= from_date)
            except ValueError:
                pass
        
        if filters.get('date_to'):
            try:
                to_date = datetime.strptime(filters['date_to'], '%Y-%m-%d').date()
                query = query.filter(TravelRequest.travel_date <= to_date)
            except ValueError:
                pass
        
        # Exclude zero distance if requested
        if filters.get('exclude_zero_distance'):
            query = query.filter(TravelRequest.calculated_distance > 0)
        
        results = query.order_by(Employee.employee_code, TravelRequest.travel_date).all()
        logger.info(f"[TRAVEL REGISTER] Query returned {len(results)} records for business_id={business_id}")
        return results

    def get_time_punches_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get time punches data with employee punch details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.attendance import AttendancePunch, AttendanceRecord
        from sqlalchemy import func, or_, and_
        from datetime import datetime, date
        import logging
        
        logger = logging.getLogger(__name__)
        
        # CRITICAL: Get business_id from filters for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[TIME PUNCHES] Querying for business_id={business_id}")
        
        # Parse date filters
        date_from = None
        date_to = None
        
        if filters.get('date_from'):
            try:
                date_from = datetime.strptime(filters['date_from'], '%Y-%m-%d').date()
            except ValueError:
                pass
        
        if filters.get('date_to'):
            try:
                date_to = datetime.strptime(filters['date_to'], '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # If no dates provided, use today
        if not date_from and not date_to:
            date_from = date_to = date.today()
        elif not date_to:
            date_to = date_from
        elif not date_from:
            date_from = date_to
        
        logger.info(f"[TIME PUNCHES] Date range: {date_from} to {date_to}")
        
        # Base query for employees with their details
        employee_query = self.db.query(
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply business unit filter (HYBRID logic)
        if filters.get('business_unit') and filters['business_unit'] != "All Business Units":
            from app.models.business import Business
            from app.models.business_unit import BusinessUnit
            
            # Check if it's a business name or business unit name
            business = self.db.query(Business).filter(Business.business_name == filters['business_unit']).first()
            if business:
                # Filter by business
                employee_query = employee_query.filter(Employee.business_id == business.id)
            else:
                # Try as business unit
                business_unit = self.db.query(BusinessUnit).filter(BusinessUnit.name == filters['business_unit']).first()
                if business_unit:
                    employee_query = employee_query.filter(Employee.business_unit_id == business_unit.id)
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            employee_query = employee_query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            employee_query = employee_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            employee_query = employee_query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee'):
            search_term = f"%{filters['employee']}%"
            employee_query = employee_query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        employees_data = employee_query.all()
        logger.info(f"[TIME PUNCHES] Found {len(employees_data)} employees")
        
        if not employees_data:
            return []
        
        # Get employee IDs
        employee_ids = [emp[0].id for emp in employees_data]
        
        # Get punch records for the date range
        punch_query = self.db.query(AttendancePunch).filter(
            AttendancePunch.employee_id.in_(employee_ids),
            func.date(AttendancePunch.punch_time) >= date_from,
            func.date(AttendancePunch.punch_time) <= date_to
        ).order_by(AttendancePunch.employee_id, AttendancePunch.punch_time)
        
        punch_records = punch_query.all()
        
        # Get attendance records for the date range
        attendance_query = self.db.query(AttendanceRecord).filter(
            AttendanceRecord.employee_id.in_(employee_ids),
            AttendanceRecord.attendance_date >= date_from,
            AttendanceRecord.attendance_date <= date_to
        )
        
        attendance_records = attendance_query.all()
        
        # Group data by employee and date
        result = []
        for employee_data in employees_data:
            employee = employee_data[0]
            
            # Get punches for this employee
            emp_punches = [p for p in punch_records if p.employee_id == employee.id]
            
            # Get attendance records for this employee
            emp_attendance = [a for a in attendance_records if a.employee_id == employee.id]
            
            result.append((
                employee_data,    # Employee with related data
                emp_punches,      # Punch records
                emp_attendance    # Attendance records
            ))
        
        logger.info(f"[TIME PUNCHES] Query returned {len(result)} employee records with punch data")
        return result

    def get_remote_punch_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get remote punch data with employee punch details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.attendance import AttendancePunch
        from sqlalchemy import func, or_, and_
        from datetime import datetime, date
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[REMOTE PUNCH] Querying for business_id={business_id}")
        
        # Parse date filters
        date_from = None
        date_to = None
        
        if filters.get('date_from'):
            try:
                date_from = datetime.strptime(filters['date_from'], '%Y-%m-%d').date()
            except ValueError:
                pass
        
        if filters.get('date_to'):
            try:
                date_to = datetime.strptime(filters['date_to'], '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # If no dates provided, use today
        if not date_from and not date_to:
            date_from = date_to = date.today()
        elif not date_to:
            date_to = date_from
        elif not date_from:
            date_from = date_to
        
        # Base query for employees with their details
        employee_query = self.db.query(
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            employee_query = employee_query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            employee_query = employee_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            employee_query = employee_query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            employee_query = employee_query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        employees_data = employee_query.all()
        
        if not employees_data:
            return []
        
        # Get employee IDs
        employee_ids = [emp[0].id for emp in employees_data]
        
        # Get remote punch records for the date range
        # Remote punches are identified by having location coordinates or being marked as remote
        punch_query = self.db.query(AttendancePunch).filter(
            AttendancePunch.employee_id.in_(employee_ids),
            func.date(AttendancePunch.punch_time) >= date_from,
            func.date(AttendancePunch.punch_time) <= date_to,
            or_(
                and_(AttendancePunch.latitude.isnot(None), AttendancePunch.longitude.isnot(None)),
                AttendancePunch.location.ilike('%remote%'),
                AttendancePunch.device_info.ilike('%remote%'),
                AttendancePunch.is_remote == True
            )
        ).order_by(AttendancePunch.employee_id, AttendancePunch.punch_time)
        
        punch_records = punch_query.all()
        
        # Group data by employee
        result = []
        for employee_data in employees_data:
            employee = employee_data[0]
            
            # Get remote punches for this employee
            emp_punches = [p for p in punch_records if p.employee_id == employee.id]
            
            result.append((
                employee_data,    # Employee with related data
                emp_punches       # Remote punch records
            ))
        
        logger.info(f"[REMOTE PUNCH] Query returned {len(result)} employee records with remote punch data")
        return result
    
    def get_manual_updates_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get manual updates data with attendance corrections and manual entries"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.attendance import AttendanceRecord, AttendanceCorrection
        from app.models.user import User
        from sqlalchemy import func, or_, and_
        from datetime import datetime, date
        import calendar
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[MANUAL UPDATES] Querying for business_id={business_id}")
        
        # Parse month filter
        month_start = None
        month_end = None
        
        if filters.get('month'):
            try:
                # Handle different month formats: "August 2025" or "AUG-2025"
                month_str = filters['month']
                if '-' in month_str:
                    # Format: "AUG-2025"
                    month_parts = month_str.split('-')
                    month_name = month_parts[0]
                    year = int(month_parts[1])
                    
                    # Convert month abbreviation to number
                    month_abbr_to_num = {
                        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
                    }
                    month_num = month_abbr_to_num.get(month_name.upper(), 8)  # Default to August
                else:
                    # Format: "August 2025"
                    month_parts = month_str.split(' ')
                    month_name = month_parts[0]
                    year = int(month_parts[1]) if len(month_parts) > 1 else datetime.now().year
                    
                    # Convert month name to number
                    month_name_to_num = {
                        'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
                        'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
                    }
                    month_num = month_name_to_num.get(month_name, 8)  # Default to August
                
                # Get first and last day of month
                month_start = date(year, month_num, 1)
                last_day = calendar.monthrange(year, month_num)[1]
                month_end = date(year, month_num, last_day)
                
            except (ValueError, IndexError):
                # Default to current month if parsing fails
                today = date.today()
                month_start = date(today.year, today.month, 1)
                last_day = calendar.monthrange(today.year, today.month)[1]
                month_end = date(today.year, today.month, last_day)
        else:
            # Default to current month
            today = date.today()
            month_start = date(today.year, today.month, 1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            month_end = date(today.year, today.month, last_day)
        
        # Base query for manual attendance records
        manual_records_query = self.db.query(
            AttendanceRecord,
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name'),
            User.name.label('updated_by_name')
        ).join(
            Employee, AttendanceRecord.employee_id == Employee.id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).outerjoin(
            User, AttendanceRecord.created_by == User.id
        ).filter(
            AttendanceRecord.is_manual_entry == True,
            AttendanceRecord.attendance_date >= month_start,
            AttendanceRecord.attendance_date <= month_end,
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            manual_records_query = manual_records_query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            manual_records_query = manual_records_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            manual_records_query = manual_records_query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            manual_records_query = manual_records_query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        manual_records = manual_records_query.order_by(
            AttendanceRecord.attendance_date.desc(),
            Employee.employee_code
        ).all()
        
        # Query for attendance corrections
        corrections_query = self.db.query(
            AttendanceCorrection,
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name'),
            User.name.label('updated_by_name'),
            AttendanceRecord.attendance_date
        ).join(
            Employee, AttendanceCorrection.employee_id == Employee.id
        ).join(
            AttendanceRecord, AttendanceCorrection.attendance_record_id == AttendanceRecord.id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).outerjoin(
            User, AttendanceCorrection.approved_by == User.id
        ).filter(
            AttendanceRecord.attendance_date >= month_start,
            AttendanceRecord.attendance_date <= month_end,
            AttendanceCorrection.status == 'approved',
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply same filters to corrections
        if filters.get('location') and filters['location'] != "All Locations":
            corrections_query = corrections_query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            corrections_query = corrections_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            corrections_query = corrections_query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            corrections_query = corrections_query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        corrections = corrections_query.order_by(
            AttendanceRecord.attendance_date.desc(),
            Employee.employee_code
        ).all()
        
        # Combine results
        result = []
        
        # Process manual records
        for record_data in manual_records:
            result.append(('manual_entry', record_data))
        
        # Process corrections
        for correction_data in corrections:
            result.append(('correction', correction_data))
        
        # Sort combined results by date (descending)
        result.sort(key=lambda x: x[1][0].attendance_date if x[0] == 'manual_entry' else x[1][-1], reverse=True)
        
        logger.info(f"[MANUAL UPDATES] Query returned {len(result)} records ({len(manual_records)} manual entries, {len(corrections)} corrections)")
        return result
    
    def get_employee_register_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get employee register data with all employee details"""
        from app.models.employee import Employee, EmployeeProfile
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.grades import Grade
        from sqlalchemy import func, or_, and_
        from datetime import datetime, date
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[EMPLOYEE REGISTER] Querying for business_id={business_id}")
        
        # Base query for employees with their details
        employee_query = self.db.query(
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name'),
            Grade.name.label('grade_name'),
            EmployeeProfile.bank_name.label('bank_name'),
            EmployeeProfile.bank_ifsc_code.label('bank_ifsc'),
            EmployeeProfile.bank_account_number.label('bank_account'),
            EmployeeProfile.pan_number.label('pan_number'),
            EmployeeProfile.esi_number.label('esi_number'),
            EmployeeProfile.uan_number.label('pf_uan_number'),
            EmployeeProfile.aadhaar_number.label('aadhaar_number'),
            EmployeeProfile.emergency_contact_mobile.label('home_phone'),
            Employee.email.label('personal_email'),  # Using employee email as personal email
            EmployeeProfile.bio.label('other_info1'),
            EmployeeProfile.skills.label('other_info2'),
            EmployeeProfile.certifications.label('other_info3'),
            EmployeeProfile.present_city.label('other_info4'),
            EmployeeProfile.permanent_city.label('other_info5')
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).outerjoin(
            Grade, Employee.grade_id == Grade.id
        ).outerjoin(
            EmployeeProfile, Employee.id == EmployeeProfile.employee_id
        ).filter(
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location'):
            employee_query = employee_query.filter(Location.name == filters['location'])
        
        if filters.get('department'):
            employee_query = employee_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center'):
            employee_query = employee_query.filter(CostCenter.name == filters['cost_center'])
        
        # Apply ordering first
        employee_query = employee_query.order_by(Employee.employee_code)
        
        # Apply pagination if specified
        if filters.get('records_per_page'):
            try:
                limit = int(filters['records_per_page'])
                if 1 <= limit <= 1000:
                    employee_query = employee_query.limit(limit)
            except (ValueError, TypeError):
                pass  # Ignore invalid pagination values
        
        employees_data = employee_query.all()
        
        logger.info(f"[EMPLOYEE REGISTER] Query returned {len(employees_data)} employee records")
        return employees_data

    def get_employee_addresses_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get employee addresses data with both present and permanent addresses"""
        from app.models.employee import Employee, EmployeeProfile
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from sqlalchemy import func, or_, and_
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[EMPLOYEE ADDRESSES] Querying for business_id={business_id}")
        
        # Base query for employees with their profile data
        employee_query = self.db.query(
            Employee,
            EmployeeProfile,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).join(
            EmployeeProfile, Employee.id == EmployeeProfile.employee_id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            employee_query = employee_query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            employee_query = employee_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            employee_query = employee_query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            employee_query = employee_query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        # Apply ordering
        employee_query = employee_query.order_by(Employee.employee_code)
        
        employees_data = employee_query.all()
        
        logger.info(f"[EMPLOYEE ADDRESSES] Query returned {len(employees_data)} employee records")
        return employees_data

    def get_employee_events_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get employee events data with birthdays, work anniversaries, and wedding anniversaries"""
        from app.models.employee import Employee, EmployeeProfile
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from sqlalchemy import func, or_, and_, extract
        from datetime import datetime, date
        import calendar
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[EMPLOYEE EVENTS] Querying for business_id={business_id}")
        
        # Base query for employees with their details
        employee_query = self.db.query(
            Employee,
            EmployeeProfile,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).outerjoin(
            EmployeeProfile, Employee.id == EmployeeProfile.employee_id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            employee_query = employee_query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            employee_query = employee_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            employee_query = employee_query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('employee_search'):
            search_term = f"%{filters['employee_search']}%"
            employee_query = employee_query.filter(
                or_(
                    Employee.first_name.ilike(search_term),
                    Employee.last_name.ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        # Get month range for filtering
        from_month = filters.get('from_month', 'January')
        to_month = filters.get('to_month', 'December')
        
        # Convert month names to numbers
        month_name_to_num = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
            'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
        }
        
        from_month_num = month_name_to_num.get(from_month, 1)
        to_month_num = month_name_to_num.get(to_month, 12)
        
        # Build date filter conditions based on event types requested
        date_conditions = []
        
        # Add birthday filter if requested
        if filters.get('show_birthdays', True):
            if from_month_num <= to_month_num:
                date_conditions.append(
                    and_(
                        Employee.date_of_birth.isnot(None),
                        extract('month', Employee.date_of_birth) >= from_month_num,
                        extract('month', Employee.date_of_birth) <= to_month_num
                    )
                )
            else:
                date_conditions.append(
                    and_(
                        Employee.date_of_birth.isnot(None),
                        or_(
                            extract('month', Employee.date_of_birth) >= from_month_num,
                            extract('month', Employee.date_of_birth) <= to_month_num
                        )
                    )
                )
        
        # Add work anniversary filter if requested
        if filters.get('show_work_anniversaries', True):
            if from_month_num <= to_month_num:
                date_conditions.append(
                    and_(
                        Employee.date_of_joining.isnot(None),
                        extract('month', Employee.date_of_joining) >= from_month_num,
                        extract('month', Employee.date_of_joining) <= to_month_num
                    )
                )
            else:
                date_conditions.append(
                    and_(
                        Employee.date_of_joining.isnot(None),
                        or_(
                            extract('month', Employee.date_of_joining) >= from_month_num,
                            extract('month', Employee.date_of_joining) <= to_month_num
                        )
                    )
                )
        
        # Add wedding anniversary filter if requested
        if filters.get('show_wedding_anniversaries', True):
            if from_month_num <= to_month_num:
                date_conditions.append(
                    and_(
                        EmployeeProfile.wedding_date.isnot(None),
                        extract('month', EmployeeProfile.wedding_date) >= from_month_num,
                        extract('month', EmployeeProfile.wedding_date) <= to_month_num
                    )
                )
            else:
                date_conditions.append(
                    and_(
                        EmployeeProfile.wedding_date.isnot(None),
                        or_(
                            extract('month', EmployeeProfile.wedding_date) >= from_month_num,
                            extract('month', EmployeeProfile.wedding_date) <= to_month_num
                        )
                    )
                )
        
        # Apply date filters if any conditions exist
        if date_conditions:
            employee_query = employee_query.filter(or_(*date_conditions))
        else:
            # If no event types are selected, return empty result
            return []
        
        employees_data = employee_query.order_by(Employee.employee_code).all()
        
        logger.info(f"[EMPLOYEE EVENTS] Query returned {len(employees_data)} employee records")
        return employees_data

    def get_promotion_age_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get promotion age data for employees with their last promotion dates"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.grades import Grade
        from app.models.reports import EmployeeReport
        from sqlalchemy import func, desc, and_
        from datetime import datetime, date
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[PROMOTION AGE] Querying for business_id={business_id}")
        
        # Subquery to get the latest promotion date for each employee
        latest_promotion_subquery = self.db.query(
            EmployeeReport.employee_id,
            func.max(EmployeeReport.effective_date).label('last_promotion_date')
        ).filter(
            EmployeeReport.report_type == 'promotion'
        ).group_by(EmployeeReport.employee_id).subquery()
        
        # Main query for employees with their details and last promotion date
        employee_query = self.db.query(
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name'),
            Grade.name.label('grade_name'),
            latest_promotion_subquery.c.last_promotion_date
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).outerjoin(
            Grade, Employee.grade_id == Grade.id
        ).outerjoin(
            latest_promotion_subquery, Employee.id == latest_promotion_subquery.c.employee_id
        ).filter(
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            employee_query = employee_query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            employee_query = employee_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            employee_query = employee_query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('grade') and filters['grade'] != "All Grades":
            employee_query = employee_query.filter(Grade.name == filters['grade'])
        
        employees_data = employee_query.order_by(Employee.employee_code).all()
        
        logger.info(f"[PROMOTION AGE] Query returned {len(employees_data)} employee records")
        return employees_data

    def get_increment_ageing_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get increment ageing data for employees with their last increment dates"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.grades import Grade
        from app.models.reports import EmployeeReport
        from sqlalchemy import func, desc, and_
        from datetime import datetime, date
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[INCREMENT AGEING] Querying for business_id={business_id}")
        
        # Subquery to get the latest increment date for each employee
        latest_increment_subquery = self.db.query(
            EmployeeReport.employee_id,
            func.max(EmployeeReport.effective_date).label('last_increment_date')
        ).filter(
            EmployeeReport.report_type == 'increment'
        ).group_by(EmployeeReport.employee_id).subquery()
        
        # Main query for employees with their details and last increment date
        employee_query = self.db.query(
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name'),
            Grade.name.label('grade_name'),
            latest_increment_subquery.c.last_increment_date
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).outerjoin(
            Grade, Employee.grade_id == Grade.id
        ).outerjoin(
            latest_increment_subquery, Employee.id == latest_increment_subquery.c.employee_id
        ).filter(
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            employee_query = employee_query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            employee_query = employee_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            employee_query = employee_query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('grade') and filters['grade'] != "All Grades":
            employee_query = employee_query.filter(Grade.name == filters['grade'])
        
        employees_data = employee_query.order_by(Employee.employee_code).all()
        
        logger.info(f"[INCREMENT AGEING] Query returned {len(employees_data)} employee records")
        return employees_data
    def get_employee_joinings_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get employee joinings data with their joining and confirmation dates"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.grades import Grade
        from sqlalchemy import and_
        from datetime import datetime, date
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[EMPLOYEE JOININGS] Querying for business_id={business_id}")
        
        # Main query for employees with their details
        employee_query = self.db.query(
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name'),
            Grade.name.label('grade_name')
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).outerjoin(
            Grade, Employee.grade_id == Grade.id
        ).filter(
            Employee.employee_status == 'ACTIVE',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            employee_query = employee_query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            employee_query = employee_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            employee_query = employee_query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('grade') and filters['grade'] != "All Grades":
            employee_query = employee_query.filter(Grade.name == filters['grade'])
        
        # Apply date range filters
        if filters.get('from_date'):
            try:
                from_date = datetime.strptime(filters['from_date'], '%Y-%m-%d').date()
                employee_query = employee_query.filter(Employee.date_of_joining >= from_date)
            except (ValueError, TypeError):
                pass
        
        if filters.get('to_date'):
            try:
                to_date = datetime.strptime(filters['to_date'], '%Y-%m-%d').date()
                employee_query = employee_query.filter(Employee.date_of_joining <= to_date)
            except (ValueError, TypeError):
                pass
        
        # Only include employees with joining dates
        employee_query = employee_query.filter(Employee.date_of_joining.isnot(None))
        
        employees_data = employee_query.order_by(Employee.date_of_joining.desc()).all()
        
        logger.info(f"[EMPLOYEE JOININGS] Query returned {len(employees_data)} employee records")
        return employees_data
    def get_employee_exits_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get employee exits data with their exit and separation details"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.grades import Grade
        from app.models.separation import SeparationRequest
        from sqlalchemy import and_, or_
        from datetime import datetime, date
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[EMPLOYEE EXITS] Querying for business_id={business_id}")
        
        # Main query for employees with their details and separation info
        employee_query = self.db.query(
            Employee,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name'),
            Grade.name.label('grade_name'),
            SeparationRequest.separation_type.label('separation_type'),
            SeparationRequest.last_working_date.label('exit_date'),
            SeparationRequest.reason.label('exit_reason_text')
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).outerjoin(
            Grade, Employee.grade_id == Grade.id
        ).outerjoin(
            SeparationRequest, Employee.id == SeparationRequest.employee_id
        ).filter(
            Employee.business_id == business_id,  # CRITICAL: Business isolation
            or_(
                Employee.employee_status == 'TERMINATED',
                Employee.date_of_termination.isnot(None),
                SeparationRequest.id.isnot(None)
            )
        )
        
        # Apply filters
        if filters.get('location') and filters['location'] != "All Locations":
            employee_query = employee_query.filter(Location.name == filters['location'])
        
        if filters.get('department') and filters['department'] != "All Departments":
            employee_query = employee_query.filter(Department.name == filters['department'])
        
        if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
            employee_query = employee_query.filter(CostCenter.name == filters['cost_center'])
        
        if filters.get('exit_reason') and filters['exit_reason'] != "All Reasons":
            employee_query = employee_query.filter(
                or_(
                    SeparationRequest.reason.ilike(f"%{filters['exit_reason']}%"),
                    SeparationRequest.separation_type == filters['exit_reason'].lower()
                )
            )
        
        # Apply date range filters on exit date
        if filters.get('from_date'):
            try:
                from_date = datetime.strptime(filters['from_date'], '%Y-%m-%d').date()
                employee_query = employee_query.filter(
                    or_(
                        Employee.date_of_termination >= from_date,
                        SeparationRequest.last_working_date >= from_date
                    )
                )
            except (ValueError, TypeError):
                pass
        
        if filters.get('to_date'):
            try:
                to_date = datetime.strptime(filters['to_date'], '%Y-%m-%d').date()
                employee_query = employee_query.filter(
                    or_(
                        Employee.date_of_termination <= to_date,
                        SeparationRequest.last_working_date <= to_date
                    )
                )
            except (ValueError, TypeError):
                pass
        
        employees_data = employee_query.order_by(
            Employee.date_of_termination.desc().nullslast(),
            SeparationRequest.last_working_date.desc().nullslast()
        ).all()
        
        logger.info(f"[EMPLOYEE EXITS] Query returned {len(employees_data)} employee records")
        return employees_data

    def get_vaccination_status_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get vaccination status data with employee vaccination details"""
        from app.models.employee import Employee, EmployeeProfile
        from app.models.department import Department
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[VACCINATION STATUS] Querying for business_id={business_id}")
        
        # Base query with joins
        employee_query = self.db.query(
            Employee.id,
            Employee.employee_code,
            func.concat(Employee.first_name, ' ', Employee.last_name).label('name'),
            Location.name.label('location'),
            Department.name.label('department'),
            func.coalesce(EmployeeProfile.vaccination_status, 'Not Vaccinated').label('vaccination_status')
        ).join(
            EmployeeProfile, Employee.id == EmployeeProfile.employee_id, isouter=True
        ).join(
            Location, Employee.location_id == Location.id, isouter=True
        ).join(
            Department, Employee.department_id == Department.id, isouter=True
        ).filter(
            Employee.employee_status == 'active',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply location filter
        if filters.get('location') and filters['location'] != 'All Locations':
            employee_query = employee_query.filter(Location.name == filters['location'])
        
        # Apply cost center filter
        if filters.get('cost_center') and filters['cost_center'] != 'All Cost Centers':
            employee_query = employee_query.join(
                CostCenter, Employee.cost_center_id == CostCenter.id, isouter=True
            ).filter(CostCenter.name == filters['cost_center'])
        
        # Apply department filter
        if filters.get('department') and filters['department'] != 'All Departments':
            employee_query = employee_query.filter(Department.name == filters['department'])
        
        # Apply vaccination status filter
        if filters.get('status'):
            if filters['status'] == 'Vaccinated':
                employee_query = employee_query.filter(
                    EmployeeProfile.vaccination_status == 'Vaccinated'
                )
            elif filters['status'] == 'Not Vaccinated':
                employee_query = employee_query.filter(
                    or_(
                        EmployeeProfile.vaccination_status == 'Not Vaccinated',
                        EmployeeProfile.vaccination_status.is_(None)
                    )
                )
        
        employees_data = employee_query.order_by(Employee.employee_code).all()
        
        logger.info(f"[VACCINATION STATUS] Query returned {len(employees_data)} employee records")
        return employees_data

    def get_workman_status_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get workman status data with employee workman installation details"""
        from app.models.employee import Employee, EmployeeProfile
        from app.models.department import Department
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[WORKMAN STATUS] Querying for business_id={business_id}")
        
        # Base query with joins
        employee_query = self.db.query(
            Employee.id,
            Employee.employee_code,
            func.concat(Employee.first_name, ' ', Employee.last_name).label('name'),
            Location.name.label('location'),
            Department.name.label('department'),
            func.coalesce(EmployeeProfile.workman_installed, False).label('workman_installed'),
            func.coalesce(EmployeeProfile.workman_version, 'Not Installed').label('workman_version'),
            EmployeeProfile.workman_last_seen.label('workman_last_seen')
        ).join(
            EmployeeProfile, Employee.id == EmployeeProfile.employee_id, isouter=True
        ).join(
            Location, Employee.location_id == Location.id, isouter=True
        ).join(
            Department, Employee.department_id == Department.id, isouter=True
        ).filter(
            Employee.employee_status == 'active',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply location filter
        if filters.get('location') and filters['location'] != 'All Locations':
            employee_query = employee_query.filter(Location.name == filters['location'])
        
        # Apply cost center filter
        if filters.get('cost_center') and filters['cost_center'] != 'All Cost Centers':
            employee_query = employee_query.join(
                CostCenter, Employee.cost_center_id == CostCenter.id, isouter=True
            ).filter(CostCenter.name == filters['cost_center'])
        
        # Apply department filter
        if filters.get('department') and filters['department'] != 'All Departments':
            employee_query = employee_query.filter(Department.name == filters['department'])
        
        # Apply inactive only filter (show only employees without workman installed)
        if filters.get('inactive_only'):
            employee_query = employee_query.filter(
                or_(
                    EmployeeProfile.workman_installed == False,
                    EmployeeProfile.workman_installed.is_(None)
                )
            )
        
        employees_data = employee_query.order_by(Employee.employee_code).all()
        
        logger.info(f"[WORKMAN STATUS] Query returned {len(employees_data)} employee records")
        return employees_data

    def get_employee_assets_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get employee assets data with their assigned assets"""
        from app.models.employee import Employee
        from app.models.asset import Asset
        from app.models.department import Department
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[EMPLOYEE ASSETS] Querying for business_id={business_id}")
        
        # Base query with joins
        employee_query = self.db.query(
            Employee.id,
            Employee.employee_code,
            func.concat(Employee.first_name, ' ', Employee.last_name).label('employee_name'),
            Location.name.label('location'),
            Department.name.label('department')
        ).join(
            Location, Employee.location_id == Location.id, isouter=True
        ).join(
            Department, Employee.department_id == Department.id, isouter=True
        ).filter(
            Employee.employee_status == 'active',
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply location filter
        if filters.get('location') and filters['location'] != 'All Locations':
            employee_query = employee_query.filter(Location.name == filters['location'])
        
        # Apply cost center filter
        if filters.get('cost_center') and filters['cost_center'] != 'All Cost Centers':
            employee_query = employee_query.join(
                CostCenter, Employee.cost_center_id == CostCenter.id, isouter=True
            ).filter(CostCenter.name == filters['cost_center'])
        
        # Apply department filter
        if filters.get('department') and filters['department'] != 'All Departments':
            employee_query = employee_query.filter(Department.name == filters['department'])
        
        # Apply search filter
        if filters.get('search'):
            search_term = f"%{filters['search']}%"
            employee_query = employee_query.filter(
                or_(
                    func.concat(Employee.first_name, ' ', Employee.last_name).ilike(search_term),
                    Employee.employee_code.ilike(search_term)
                )
            )
        
        # Get employees
        employees = employee_query.order_by(Employee.employee_code).all()
        
        # Get assets for these employees
        employee_ids = [emp.id for emp in employees]
        
        assets_query = self.db.query(Asset).filter(
            Asset.assigned_employee_id.in_(employee_ids),
            Asset.status == 'active'
        )
        
        # Apply warranty filter
        if filters.get('warranty_only'):
            from datetime import date
            assets_query = assets_query.filter(
                Asset.warranty_end_date < date.today()
            )
        
        assets = assets_query.all()
        
        # Group assets by employee
        employee_assets = {}
        for asset in assets:
            if asset.assigned_employee_id not in employee_assets:
                employee_assets[asset.assigned_employee_id] = []
            employee_assets[asset.assigned_employee_id].append(asset)
        
        # Combine employee and asset data
        result = []
        for emp in employees:
            emp_assets = employee_assets.get(emp.id, [])
            # Only include employees with assets (or all if not filtering by warranty)
            if emp_assets or not filters.get('warranty_only'):
                result.append({
                    'employee': emp,
                    'assets': emp_assets
                })
        
        logger.info(f"[EMPLOYEE ASSETS] Query returned {len(result)} employee records with assets")
        return result

    def get_employee_relatives_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get employee relatives data with their family members"""
        from app.models.employee import Employee, EmployeeStatus
        from app.models.employee_relative import EmployeeRelative
        from app.models.department import Department
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[EMPLOYEE RELATIVES] Querying for business_id={business_id}")
        
        # Base query with joins
        query = self.db.query(
            Employee,
            Department.name.label('department_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply active only filter
        if filters.get('active_only'):
            query = query.filter(Employee.employee_status == EmployeeStatus.ACTIVE)
        
        # Apply location filter
        if filters.get('location') and filters['location'] != 'All Locations':
            query = query.filter(Location.name == filters['location'])
        
        # Apply cost center filter
        if filters.get('cost_center') and filters['cost_center'] != 'All Cost Centers':
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        # Apply department filter
        if filters.get('department') and filters['department'] != 'All Departments':
            query = query.filter(Department.name == filters['department'])
        
        employees_data = query.order_by(Employee.employee_code).all()
        
        # Get employee IDs
        employee_ids = [emp[0].id for emp in employees_data]
        
        # Get relatives for these employees
        from sqlalchemy import or_
        relatives_query = self.db.query(EmployeeRelative).filter(
            EmployeeRelative.employee_id.in_(employee_ids),
            or_(EmployeeRelative.is_active == True, EmployeeRelative.is_active.is_(None))
        ).order_by(EmployeeRelative.employee_id, EmployeeRelative.relation)
        
        relatives = relatives_query.all()
        
        # Group relatives by employee
        employee_relatives = {}
        for relative in relatives:
            if relative.employee_id not in employee_relatives:
                employee_relatives[relative.employee_id] = []
            employee_relatives[relative.employee_id].append(relative)
        
        # Combine employee and relatives data
        result = []
        for emp_data in employees_data:
            employee = emp_data[0]
            emp_relatives = employee_relatives.get(employee.id, [])
            result.append({
                'employee': employee,
                'department_name': emp_data.department_name or 'General',
                'location_name': emp_data.location_name or 'Hyderabad',
                'cost_center_name': emp_data.cost_center_name or 'Default',
                'relatives': emp_relatives
            })
        
        logger.info(f"[EMPLOYEE RELATIVES] Query returned {len(result)} employee records with relatives")
        return result

    def get_inactive_employees_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get inactive employees data with their details"""
        from app.models.employee import Employee, EmployeeProfile, EmployeeStatus
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[INACTIVE EMPLOYEES] Querying for business_id={business_id}")
        
        # Base query with joins for inactive employees
        query = self.db.query(
            Employee,
            EmployeeProfile,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).outerjoin(
            EmployeeProfile, Employee.id == EmployeeProfile.employee_id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.business_id == business_id,  # CRITICAL: Business isolation
            # Filter for inactive employees
            Employee.employee_status.in_([EmployeeStatus.INACTIVE, EmployeeStatus.TERMINATED])
        )
        
        # Apply location filter
        if filters.get('location') and filters['location'] != 'All Locations':
            query = query.filter(Location.name == filters['location'])
        
        # Apply cost center filter
        if filters.get('cost_center') and filters['cost_center'] != 'All Cost Centers':
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        # Apply department filter
        if filters.get('department') and filters['department'] != 'All Departments':
            query = query.filter(Department.name == filters['department'])
        
        employees_data = query.order_by(Employee.employee_code).all()
        
        logger.info(f"[INACTIVE EMPLOYEES] Query returned {len(employees_data)} employee records")
        return employees_data

    def get_export_records_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get export records data with employee details for CSV download"""
        from app.models.employee import Employee, EmployeeProfile, EmployeeStatus
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[EXPORT RECORDS] Querying for business_id={business_id}")
        
        # Base query with joins for all employee data
        query = self.db.query(
            Employee,
            EmployeeProfile,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).outerjoin(
            EmployeeProfile, Employee.id == EmployeeProfile.employee_id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.business_id == business_id  # CRITICAL: Business isolation
        )
        
        # Apply record type filter
        record_type = filters.get('record_type', 'all')
        if record_type == 'active':
            query = query.filter(Employee.employee_status == EmployeeStatus.ACTIVE)
        elif record_type == 'inactive':
            query = query.filter(Employee.employee_status.in_([EmployeeStatus.INACTIVE, EmployeeStatus.TERMINATED]))
        # For 'all', no status filter needed
        
        # Apply location filter
        if filters.get('location') and filters['location'] != 'All Locations':
            query = query.filter(Location.name == filters['location'])
        
        # Apply cost center filter
        if filters.get('cost_center') and filters['cost_center'] != 'All Cost Centers':
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        # Apply department filter
        if filters.get('department') and filters['department'] != 'All Departments':
            query = query.filter(Department.name == filters['department'])
        
        employees_data = query.order_by(Employee.employee_code).all()
        
        logger.info(f"[EXPORT RECORDS] Query returned {len(employees_data)} employee records")
        return employees_data
    def get_esi_deduction_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get ESI deduction data with employee details"""
        from app.models.employee import Employee, EmployeeProfile, EmployeeStatus
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.reports import SalaryReport
        from datetime import datetime
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[ESI DEDUCTION] Querying for business_id={business_id}")
        
        # Parse month from frontend format (e.g., "NOV-2025" to "2025-11")
        month_str = filters.get('month', '')
        if '-' in month_str and len(month_str.split('-')[0]) == 3:
            # Frontend format: "NOV-2025"
            month_obj = datetime.strptime(month_str, "%b-%Y")
            period = month_obj.strftime('%Y-%m')
        else:
            # Backend format: "2025-11"
            period = month_str
        
        # Base query with joins for ESI eligible employees
        query = self.db.query(
            Employee,
            EmployeeProfile,
            SalaryReport,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).outerjoin(
            EmployeeProfile, Employee.id == EmployeeProfile.employee_id
        ).outerjoin(
            SalaryReport, and_(
                SalaryReport.employee_id == Employee.id,
                SalaryReport.report_period == period
            )
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.business_id == business_id,  # CRITICAL: Business isolation
            # Filter for active employees only (ESI applicable)
            Employee.employee_status == EmployeeStatus.ACTIVE
        )
        
        # Apply location filter
        if filters.get('location') and filters['location'] != 'All Locations':
            query = query.filter(Location.name == filters['location'])
        
        # Apply cost center filter
        if filters.get('cost_center') and filters['cost_center'] != 'All Cost Centers':
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        # Apply department filter
        if filters.get('department') and filters['department'] != 'All Departments':
            query = query.filter(Department.name == filters['department'])
        
        employees_data = query.order_by(Employee.employee_code).all()
        
        logger.info(f"[ESI DEDUCTION] Query returned {len(employees_data)} employee records")
        return employees_data
    def get_esi_coverage_data(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get ESI coverage statistics with employee counts and deduction amounts"""
        from app.models.employee import Employee, EmployeeProfile, EmployeeStatus
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.reports import SalaryReport
        from datetime import datetime
        from sqlalchemy import func, case
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[ESI COVERAGE] Querying for business_id={business_id}")
        
        # Parse month from frontend format (e.g., "NOV-2025" to "2025-11")
        month_str = filters.get('month', '')
        if '-' in month_str and len(month_str.split('-')[0]) == 3:
            # Frontend format: "NOV-2025"
            month_obj = datetime.strptime(month_str, "%b-%Y")
            period = month_obj.strftime('%Y-%m')
        else:
            # Backend format: "2025-11"
            period = month_str
        
        # Base query for all employees with salary data
        query = self.db.query(
            Employee,
            SalaryReport,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).outerjoin(
            SalaryReport, and_(
                SalaryReport.employee_id == Employee.id,
                SalaryReport.report_period == period
            )
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.business_id == business_id,  # CRITICAL: Business isolation
            # Filter for active employees only
            Employee.employee_status == EmployeeStatus.ACTIVE
        )
        
        # Apply location filter
        if filters.get('location') and filters['location'] != 'All Locations':
            query = query.filter(Location.name == filters['location'])
        
        # Apply cost center filter
        if filters.get('cost_center') and filters['cost_center'] != 'All Cost Centers':
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        # Apply department filter
        if filters.get('department') and filters['department'] != 'All Departments':
            query = query.filter(Department.name == filters['department'])
        
        employees_data = query.all()
        
        # Calculate ESI coverage statistics
        total_employees = len(employees_data)
        esi_deducted_count = 0
        esi_eligible_count = 0
        total_esi_amount = 0
        
        for emp_data in employees_data:
            employee = emp_data[0]
            salary_report = emp_data[1]
            
            if salary_report:
                # Check if ESI is deducted (gross salary <= 25000)
                if salary_report.gross_salary <= 25000:
                    esi_eligible_count += 1
                    # Check if ESI deduction exists in salary report
                    deductions = salary_report.deductions or {}
                    if 'ESI' in deductions and deductions['ESI'] > 0:
                        esi_deducted_count += 1
                        total_esi_amount += float(deductions['ESI'])
        
        esi_not_eligible = total_employees - esi_eligible_count
        average_esi = total_esi_amount / esi_deducted_count if esi_deducted_count > 0 else 0
        
        logger.info(f"[ESI COVERAGE] Query returned {total_employees} employees, {esi_deducted_count} with ESI deducted")
        
        return {
            'total_employees': total_employees,
            'esi_deducted': esi_deducted_count,
            'esi_eligible': esi_eligible_count,
            'esi_not_eligible': esi_not_eligible,
            'total_esi_amount': total_esi_amount,
            'average_esi_per_employee': average_esi,
            'period': period
        }
    def get_pf_deduction_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get PF deduction data with employee details"""
        from app.models.employee import Employee, EmployeeProfile, EmployeeStatus
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.reports import SalaryReport
        from datetime import datetime
        from sqlalchemy import func
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[PF DEDUCTION] Querying for business_id={business_id}")
        
        # Parse month from frontend format (e.g., "AUG-2025" to "2025-08")
        month_str = filters.get('month', '')
        if '-' in month_str and len(month_str.split('-')[0]) == 3:
            # Frontend format: "AUG-2025"
            month_obj = datetime.strptime(month_str, "%b-%Y")
            period = month_obj.strftime('%Y-%m')
        else:
            # Backend format: "2025-08"
            period = month_str
        
        # Subquery to get the latest salary report ID for each employee in the period
        # This prevents duplicates if there are multiple salary reports for same employee/period
        latest_salary_subquery = self.db.query(
            SalaryReport.employee_id,
            func.max(SalaryReport.id).label('max_id')
        ).filter(
            SalaryReport.report_period == period
        ).group_by(
            SalaryReport.employee_id
        ).subquery()
        
        # Base query with joins for PF eligible employees
        query = self.db.query(
            Employee,
            EmployeeProfile,
            SalaryReport,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).outerjoin(
            EmployeeProfile, Employee.id == EmployeeProfile.employee_id
        ).outerjoin(
            latest_salary_subquery,
            Employee.id == latest_salary_subquery.c.employee_id
        ).outerjoin(
            SalaryReport,
            SalaryReport.id == latest_salary_subquery.c.max_id
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.business_id == business_id,  # CRITICAL: Business isolation
            # Filter for active employees only (PF applicable)
            Employee.employee_status == EmployeeStatus.ACTIVE
        )
        
        # Apply location filter
        if filters.get('location') and filters['location'] != 'All Locations':
            query = query.filter(Location.name == filters['location'])
        
        # Apply cost center filter
        if filters.get('cost_center') and filters['cost_center'] != 'All Cost Centers':
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        # Apply department filter
        if filters.get('department') and filters['department'] != 'All Departments':
            query = query.filter(Department.name == filters['department'])
        
        employees_data = query.order_by(Employee.employee_code).all()
        
        logger.info(f"[PF DEDUCTION] Query returned {len(employees_data)} employee records")
        return employees_data
    def get_pf_coverage_data(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get PF coverage statistics with employee counts and deduction amounts"""
        from app.models.employee import Employee, EmployeeProfile, EmployeeStatus
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.reports import SalaryReport
        from datetime import datetime
        from sqlalchemy import func, case
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[PF COVERAGE] Querying for business_id={business_id}")
        
        # Parse month from frontend format (e.g., "NOV-2025" to "2025-11")
        month_str = filters.get('month', '')
        if '-' in month_str and len(month_str.split('-')[0]) == 3:
            # Frontend format: "NOV-2025"
            month_obj = datetime.strptime(month_str, "%b-%Y")
            period = month_obj.strftime('%Y-%m')
        else:
            # Backend format: "2025-11"
            period = month_str
        
        # Base query for all employees with salary data
        query = self.db.query(
            Employee,
            SalaryReport,
            Department.name.label('department_name'),
            Designation.name.label('designation_name'),
            Location.name.label('location_name'),
            CostCenter.name.label('cost_center_name')
        ).outerjoin(
            SalaryReport, and_(
                SalaryReport.employee_id == Employee.id,
                SalaryReport.report_period == period
            )
        ).outerjoin(
            Department, Employee.department_id == Department.id
        ).outerjoin(
            Designation, Employee.designation_id == Designation.id
        ).outerjoin(
            Location, Employee.location_id == Location.id
        ).outerjoin(
            CostCenter, Employee.cost_center_id == CostCenter.id
        ).filter(
            Employee.business_id == business_id,  # CRITICAL: Business isolation
            # Filter for active employees only
            Employee.employee_status == EmployeeStatus.ACTIVE
        )
        
        # Apply location filter
        if filters.get('location') and filters['location'] != 'All Locations':
            query = query.filter(Location.name == filters['location'])
        
        # Apply cost center filter
        if filters.get('cost_center') and filters['cost_center'] != 'All Cost Centers':
            query = query.filter(CostCenter.name == filters['cost_center'])
        
        # Apply department filter
        if filters.get('department') and filters['department'] != 'All Departments':
            query = query.filter(Department.name == filters['department'])
        
        employees_data = query.all()
        
        # Calculate PF coverage statistics
        total_employees = len(employees_data)
        pf_deducted_count = 0
        pf_eligible_count = 0
        total_pf_amount = 0
        
        for emp_data in employees_data:
            employee = emp_data[0]
            salary_report = emp_data[1]
            
            if salary_report:
                # All employees with salary are PF eligible (no wage ceiling for eligibility)
                pf_eligible_count += 1
                
                # Check if PF deduction exists in salary report (handle both 'PF' and 'pf' keys)
                deductions = salary_report.deductions or {}
                pf_amount = deductions.get('PF', 0) or deductions.get('pf', 0)
                
                if pf_amount > 0:
                    pf_deducted_count += 1
                    total_pf_amount += float(pf_amount)
        
        pf_not_eligible = total_employees - pf_eligible_count
        average_pf = total_pf_amount / pf_deducted_count if pf_deducted_count > 0 else 0
        
        logger.info(f"[PF COVERAGE] Query returned {total_employees} employees, {pf_deducted_count} with PF deducted")
        
        return {
            'total_employees': total_employees,
            'pf_deducted': pf_deducted_count,
            'pf_eligible': pf_eligible_count,
            'pf_not_eligible': pf_not_eligible,
            'total_pf_amount': total_pf_amount,
            'average_pf_per_employee': average_pf,
            'period': period
        }

    def get_income_tax_declaration_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get income tax declaration data for reports"""
        from app.models.datacapture import ITDeclaration, ITDeclarationStatus
        from app.models.employee import Employee, EmployeeStatus
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from sqlalchemy import func, or_
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[INCOME TAX DECLARATION] Querying for business_id={business_id}")
        
        try:
            # Base query for IT declarations with employee details
            query = self.db.query(
                ITDeclaration,
                Employee,
                Department.name.label('department_name'),
                Designation.name.label('designation_name'),
                Location.name.label('location_name'),
                CostCenter.name.label('cost_center_name')
            ).join(
                Employee, ITDeclaration.employee_id == Employee.id
            ).outerjoin(
                Department, Employee.department_id == Department.id
            ).outerjoin(
                Designation, Employee.designation_id == Designation.id
            ).outerjoin(
                Location, Employee.location_id == Location.id
            ).outerjoin(
                CostCenter, Employee.cost_center_id == CostCenter.id
            ).filter(
                Employee.business_id == business_id  # CRITICAL: Business isolation
            )
            
            # Apply filters
            if filters.get('location') and filters['location'] != "All Locations":
                query = query.filter(Location.name == filters['location'])
            
            if filters.get('financial_year'):
                query = query.filter(ITDeclaration.financial_year == filters['financial_year'])
            
            if filters.get('active_employees_only'):
                query = query.filter(Employee.employee_status == EmployeeStatus.ACTIVE)
            
            if filters.get('exclude_no_declarations'):
                # Exclude declarations with no deductions
                query = query.filter(
                    or_(
                        ITDeclaration.total_80c > 0,
                        ITDeclaration.section_80d_medical > 0,
                        ITDeclaration.section_24_home_loan_interest > 0,
                        ITDeclaration.section_80g_donations > 0,
                        ITDeclaration.hra_exemption > 0,
                        ITDeclaration.rent_paid > 0
                    )
                )
            
            if filters.get('employee_search'):
                search_term = f"%{filters['employee_search']}%"
                query = query.filter(
                    or_(
                        Employee.first_name.ilike(search_term),
                        Employee.last_name.ilike(search_term),
                        Employee.employee_code.ilike(search_term),
                        Employee.pan_number.ilike(search_term)
                    )
                )
            
            # Order by employee name
            query = query.order_by(Employee.first_name, Employee.last_name)
            
            result = query.all()
            
            logger.info(f"[INCOME TAX DECLARATION] Query returned {len(result)} records")
            return result
            
        except Exception as e:
            logger.error(f"[INCOME TAX DECLARATION] Error: {str(e)}")
            raise Exception(f"Failed to get income tax declaration data: {str(e)}")
    def get_income_tax_computation_data(self, filters: Dict[str, Any]) -> List[Any]:
        """Get income tax computation data for reports"""
        from app.models.datacapture import IncomeTaxTDS, ITDeclaration
        from app.models.employee import Employee, EmployeeStatus
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.reports import SalaryReport
        from sqlalchemy import func, or_, extract
        from datetime import datetime
        
        # CRITICAL: Validate business_id is present for security
        business_id = filters.get('business_id')
        if not business_id:
            raise ValueError("business_id is required for security")
        
        logger.info(f"[INCOME TAX COMPUTATION] Querying for business_id={business_id}")
        
        try:
            # Parse month from frontend format (e.g., "AUG-2025" to "2025-08")
            month_str = filters.get('month', 'AUG-2025')
            if '-' in month_str and len(month_str.split('-')[0]) == 3:
                # Frontend format: "AUG-2025"
                month_obj = datetime.strptime(month_str, "%b-%Y")
                year = month_obj.year
                month = month_obj.month
                period = f"{year}-{month:02d}"
                financial_year = f"{year}-{str(year+1)[2:]}" if month >= 4 else f"{year-1}-{str(year)[2:]}"
            else:
                # Fallback
                year = 2025
                month = 8
                period = "2025-08"
                financial_year = "2025-26"
            
            # Base query for employees with salary and TDS data
            query = self.db.query(
                Employee,
                Department.name.label('department_name'),
                Designation.name.label('designation_name'),
                Location.name.label('location_name'),
                CostCenter.name.label('cost_center_name'),
                SalaryReport.gross_salary,
                SalaryReport.basic_salary,
                SalaryReport.net_salary,
                SalaryReport.total_deductions,
                IncomeTaxTDS.tds_amount,
                IncomeTaxTDS.taxable_income,
                IncomeTaxTDS.tax_slab_rate,
                IncomeTaxTDS.exemptions,
                IncomeTaxTDS.deductions_80c,
                IncomeTaxTDS.other_deductions,
                ITDeclaration.total_80c,
                ITDeclaration.section_80d_medical,
                ITDeclaration.hra_exemption
            ).outerjoin(
                Department, Employee.department_id == Department.id
            ).outerjoin(
                Designation, Employee.designation_id == Designation.id
            ).outerjoin(
                Location, Employee.location_id == Location.id
            ).outerjoin(
                CostCenter, Employee.cost_center_id == CostCenter.id
            ).outerjoin(
                SalaryReport, and_(
                    SalaryReport.employee_id == Employee.id,
                    SalaryReport.report_period == period
                )
            ).outerjoin(
                IncomeTaxTDS, and_(
                    IncomeTaxTDS.employee_id == Employee.id,
                    IncomeTaxTDS.financial_year == financial_year
                )
            ).outerjoin(
                ITDeclaration, and_(
                    ITDeclaration.employee_id == Employee.id,
                    ITDeclaration.financial_year == financial_year
                )
            ).filter(
                Employee.business_id == business_id,  # CRITICAL: Business isolation
                Employee.employee_status == EmployeeStatus.ACTIVE
            )
            
            # Apply filters
            if filters.get('location') and filters['location'] != "All Locations":
                query = query.filter(Location.name == filters['location'])
            
            if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
                query = query.filter(CostCenter.name == filters['cost_center'])
            
            if filters.get('department') and filters['department'] != "All Departments":
                query = query.filter(Department.name == filters['department'])
            
            if filters.get('employee_search'):
                search_term = f"%{filters['employee_search']}%"
                query = query.filter(
                    or_(
                        Employee.first_name.ilike(search_term),
                        Employee.last_name.ilike(search_term),
                        Employee.employee_code.ilike(search_term)
                    )
                )
            
            # Order by employee name
            query = query.order_by(Employee.first_name, Employee.last_name)
            
            result = query.all()
            
            logger.info(f"[INCOME TAX COMPUTATION] Query returned {len(result)} records")
            return result
            
        except Exception as e:
            logger.error(f"[INCOME TAX COMPUTATION] Error: {str(e)}")
            raise Exception(f"Failed to get income tax computation data: {str(e)}")
    
    def get_income_tax_computation_reports(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get income tax computation report history"""
        try:
            # For now, return mock data as the frontend expects
            # In a real implementation, this would query a reports table
            month = filters.get('month', 'AUG-2025')
            
            # Get employee count for the month
            computation_data = self.get_income_tax_computation_data(filters)
            employee_count = len(computation_data)
            
            # Generate mock report history
            reports = [
                {
                    "id": 1,
                    "description": f"Income Tax Computation for {month} for {employee_count} employee(s)",
                    "requested_on": "02-Aug-2025 10:33:22",
                    "status": "ready",
                    "download_url": f"/api/v1/reports/incometaxcom/download/{month}",
                    "employee_count": employee_count,
                    "month": month
                }
            ]
            
            return reports
            
        except Exception as e:
            raise Exception(f"Failed to get income tax computation reports: {str(e)}")

    def get_labour_welfare_fund_data(self, period: str, filters: Dict[str, Any]) -> List[Any]:
        """Get Labour Welfare Fund data with employee details"""
        from app.models.employee import Employee, EmployeeProfile
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.lwf_models import LWFRate
        from app.models.setup.salary_and_deductions.salary_component import SalaryComponent
        from sqlalchemy import func, extract
        
        logger.info(f"Getting Labour Welfare Fund data for period: {period}, filters: {filters}")
        
        try:
            # Validate business_id is provided
            business_id = filters.get('business_id')
            if not business_id:
                raise ValueError("business_id is required for Labour Welfare Fund data")
            
            # Parse period from frontend format (e.g., "JAN-2025" to "2025-01")
            from datetime import datetime
            if '-' in period and len(period.split('-')[0]) == 3:
                # Frontend format: "JAN-2025"
                month_obj = datetime.strptime(period, "%b-%Y")
                year = month_obj.year
                month = month_obj.month
                db_period = month_obj.strftime('%Y-%m')
            else:
                # Backend format: "2025-01"
                year, month = map(int, period.split('-'))
                db_period = period
            
            # Base query with all joins - FILTER BY BUSINESS_ID
            query = self.db.query(
                SalaryReport,
                Employee,
                EmployeeProfile,
                Department.name.label('department_name'),
                Designation.name.label('designation_name'),
                Location.name.label('location_name'),
                CostCenter.name.label('cost_center_name')
            ).join(
                Employee, SalaryReport.employee_id == Employee.id
            ).outerjoin(
                EmployeeProfile, Employee.id == EmployeeProfile.employee_id
            ).outerjoin(
                Department, Employee.department_id == Department.id
            ).outerjoin(
                Designation, Employee.designation_id == Designation.id
            ).outerjoin(
                Location, Employee.location_id == Location.id
            ).outerjoin(
                CostCenter, Employee.cost_center_id == CostCenter.id
            ).filter(
                SalaryReport.report_period == db_period,
                Employee.employee_status == 'ACTIVE',
                Employee.business_id == business_id  # SECURITY: Filter by business_id
            )
            
            # Apply filters
            if filters.get('location') and filters['location'] != "All Locations":
                query = query.filter(Location.name == filters['location'])
            
            if filters.get('department') and filters['department'] != "All Departments":
                query = query.filter(Department.name == filters['department'])
            
            if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
                query = query.filter(CostCenter.name == filters['cost_center'])
            
            if filters.get('employee_search'):
                search_term = f"%{filters['employee_search']}%"
                query = query.filter(
                    or_(
                        Employee.first_name.ilike(search_term),
                        Employee.last_name.ilike(search_term),
                        Employee.employee_code.ilike(search_term)
                    )
                )
            
            return query.order_by(Employee.employee_code).all()
            
        except Exception as e:
            logger.error(f"Failed to get Labour Welfare Fund data: {str(e)}")
            raise Exception(f"Failed to get Labour Welfare Fund data: {str(e)}")

    def get_lwf_rates_for_period(self, business_id: int, period_date: date) -> List[Any]:
        """Get LWF rates applicable for the given period"""
        from app.models.lwf_models import LWFRate
        from datetime import date
        
        try:
            return self.db.query(LWFRate).filter(
                LWFRate.business_id == business_id,
                LWFRate.effective_from <= period_date
            ).order_by(LWFRate.state, LWFRate.effective_from.desc()).all()
            
        except Exception as e:
            raise Exception(f"Failed to get LWF rates: {str(e)}")

    def get_lwf_applicable_components(self, business_id: int) -> List[Any]:
        """Get salary components that are LWF applicable"""
        from app.models.setup.salary_and_deductions.salary_component import SalaryComponent
        
        try:
            return self.db.query(SalaryComponent).filter(
                SalaryComponent.business_id == business_id,
                SalaryComponent.is_lwf_applicable == True,
                SalaryComponent.is_active == True
            ).all()
            
        except Exception as e:
            raise Exception(f"Failed to get LWF applicable components: {str(e)}")

    def get_income_tax_form16_data(self, financial_year: str, employee_id: Optional[int] = None, 
                                  employee_code: Optional[str] = None, location: Optional[str] = None,
                                  department: Optional[str] = None, cost_center: Optional[str] = None,
                                  business_id: Optional[int] = None) -> Dict[str, Any]:
        """Get Income Tax Form 16 data for employees"""
        from app.models.employee import Employee
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.department import Department
        from app.models.datacapture import IncomeTaxTDS, ITDeclaration
        from app.models.form16_models import EmployerInfo, PersonResponsible
        from app.models.business import Business
        from app.models.business_info import BusinessInformation
        from sqlalchemy import func, extract, case
        from datetime import datetime
        from decimal import Decimal
        
        logger.info(f"Getting Income Tax Form 16 data for FY: {financial_year}, business_id: {business_id}")
        
        try:
            # Validate business_id is provided
            if not business_id:
                raise ValueError("business_id is required for Income Tax Form 16 data")
            
            # Base query for employees - FILTER BY BUSINESS_ID
            query = self.db.query(Employee).join(Location).join(Department).filter(
                Employee.business_id == business_id  # SECURITY: Filter by business_id
            ).distinct()
            
            # Apply filters
            if employee_id:
                query = query.filter(Employee.id == employee_id)
            if employee_code:
                query = query.filter(Employee.employee_code == employee_code)
            if location and location != "All Locations":
                query = query.filter(Location.name == location)
            if department and department != "All Departments":
                query = query.filter(Department.name == department)
            if cost_center and cost_center != "All Cost Centers":
                # Use exists subquery to avoid duplicate rows from cost_center join
                from sqlalchemy import exists
                cost_center_subquery = exists().where(
                    CostCenter.id == Employee.cost_center_id,
                    CostCenter.name == cost_center
                )
                query = query.filter(cost_center_subquery)
            
            employees = query.all()
            
            form16_data = []
            for employee in employees:
                # Get salary and TDS data
                tds_records = self.db.query(IncomeTaxTDS).filter(
                    IncomeTaxTDS.employee_id == employee.id,
                    IncomeTaxTDS.financial_year == financial_year
                ).all()
                
                # Get IT declarations
                it_declarations = self.db.query(ITDeclaration).filter(
                    ITDeclaration.employee_id == employee.id,
                    ITDeclaration.financial_year == financial_year
                ).all()
                
                # Calculate totals
                total_tds = sum(record.tds_amount for record in tds_records)
                total_gross_salary = sum(record.gross_salary for record in tds_records)
                total_taxable_income = sum(record.taxable_income for record in tds_records)
                
                # Calculate deductions (use correct attribute names from ITDeclaration model)
                total_80c = sum(decl.total_80c for decl in it_declarations)
                total_80d = sum(decl.section_80d_medical for decl in it_declarations)
                
                employee_data = {
                    "employee_id": employee.id,
                    "employee_code": employee.employee_code,
                    "employee_name": f"{employee.first_name} {employee.last_name}",
                    "designation": employee.designation.name if employee.designation else "",
                    "department": employee.department.name if employee.department else "",
                    "location": employee.location.name if employee.location else "",
                    "pan_number": getattr(employee, 'pan_number', None),
                    "aadhaar_number": getattr(employee, 'aadhaar_number', None),
                    "date_of_joining": employee.date_of_joining,
                    "address_line1": getattr(employee, 'address_line1', None),
                    "address_line2": getattr(employee, 'address_line2', None),
                    "city": getattr(employee, 'city', None),
                    "state": getattr(employee, 'state', None),
                    "pincode": getattr(employee, 'pincode', None),
                    "gross_salary": Decimal(str(total_gross_salary)) if total_gross_salary else Decimal('0'),
                    "taxable_income": Decimal(str(total_taxable_income)) if total_taxable_income else Decimal('0'),
                    "tds_deducted": Decimal(str(total_tds)) if total_tds else Decimal('0'),
                    "section_80c": Decimal(str(total_80c)) if total_80c else Decimal('0'),
                    "section_80d": Decimal(str(total_80d)) if total_80d else Decimal('0'),
                    "tds_records": tds_records,
                    "it_declarations": it_declarations
                }
                
                form16_data.append(employee_data)
            
            # Get employer info for this business
            employer_info = self.db.query(EmployerInfo).filter(
                EmployerInfo.business_id == business_id
            ).first()
            person_responsible = self.db.query(PersonResponsible).filter(
                PersonResponsible.business_id == business_id
            ).first()
            business = self.db.query(Business).filter(
                Business.id == business_id
            ).first()
            business_info = self.db.query(BusinessInformation).filter(
                BusinessInformation.business_id == business_id
            ).first()
            
            return {
                "employees": form16_data,
                "employer_info": employer_info,
                "person_responsible": person_responsible,
                "business": business,
                "business_info": business_info,
                "financial_year": financial_year
            }
            
        except Exception as e:
            logger.error(f"Error in get_income_tax_form16_data: {e}")
            import traceback
            traceback.print_exc()
            return {"employees": [], "employer_info": None, "person_responsible": None, "business": None, "business_info": None}

    def get_annual_salary_summary_data(self, financial_year: str, location: Optional[str] = None,
                                      department: Optional[str] = None, cost_center: Optional[str] = None,
                                      employee_grade: Optional[str] = None, business_id: Optional[int] = None) -> Dict[str, Any]:
        """Get Annual Salary Summary data for employees"""
        from app.models.employee import Employee
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.department import Department
        from app.models.payroll import PayrollPeriod
        from app.models.datacapture import SalaryVariable, SalaryVariableType
        from sqlalchemy import func, extract, case
        from datetime import datetime
        
        logger.info(f"Getting Annual Salary Summary data for FY: {financial_year}, business_id: {business_id}")
        
        try:
            # Validate business_id is provided
            if not business_id:
                raise ValueError("business_id is required for Annual Salary Summary data")
            
            # Parse financial year (e.g., "2024-25" to get start and end years)
            start_year, end_year = financial_year.split('-')
            start_year = int(start_year)
            end_year = int(f"20{end_year}")
            
            # Base query for employees - FILTER BY BUSINESS_ID
            query = self.db.query(Employee).join(Location).join(Department).filter(
                Employee.business_id == business_id  # SECURITY: Filter by business_id
            )
            
            # Apply filters
            if location and location != "All Locations":
                query = query.filter(Location.name == location)
            if department and department != "All Departments":
                query = query.filter(Department.name == department)
            if cost_center and cost_center != "All Cost Centers":
                query = query.join(CostCenter).filter(CostCenter.name == cost_center)
            if employee_grade and employee_grade != "All Grades":
                query = query.filter(Employee.grade == employee_grade)
            
            employees = query.all()
            
            annual_data = []
            for employee in employees:
                # Get salary data for the financial year
                from app.models.reports import SalaryReport
                
                salary_query = self.db.query(SalaryReport).filter(
                    SalaryReport.employee_id == employee.id,
                    SalaryReport.report_period >= f"{start_year}-04",  # April of start year
                    SalaryReport.report_period <= f"{end_year}-03"     # March of end year
                )
                
                salary_records = salary_query.all()
                
                # If no salary reports exist, use employee's current salary data from EmployeeSalary
                if not salary_records:
                    # Get employee's current/latest salary record
                    from app.models.employee import EmployeeSalary
                    
                    current_salary = self.db.query(EmployeeSalary).filter(
                        EmployeeSalary.employee_id == employee.id
                    ).order_by(EmployeeSalary.effective_from.desc()).first()
                    
                    if current_salary:
                        # Calculate annual salary based on employee's current salary
                        monthly_basic = Decimal(str(current_salary.basic_salary or 0))
                        monthly_gross = Decimal(str(current_salary.gross_salary or 0))
                        
                        # Assume 12 months for annual calculation
                        annual_basic = monthly_basic * 12
                        annual_gross = monthly_gross * 12
                        
                        # Estimate HRA as 40% of basic (standard calculation)
                        annual_hra = monthly_basic * Decimal('0.4') * 12
                        
                        # Estimate deductions
                        annual_pf = monthly_basic * Decimal('0.12') * 12  # 12% PF
                        annual_esi = Decimal('0')  # ESI only if gross < 21000
                        if monthly_gross < 21000:
                            annual_esi = monthly_gross * Decimal('0.0075') * 12  # 0.75% ESI
                        
                        annual_tds = Decimal('0')  # TDS calculated separately
                    else:
                        # No salary data at all, skip this employee
                        continue
                    annual_net = annual_gross - annual_pf - annual_esi - annual_tds
                    annual_deductions = annual_pf + annual_esi + annual_tds
                    months_worked = 12
                else:
                    # Calculate annual totals from salary reports
                    annual_basic = sum(Decimal(str(record.basic_salary or 0)) for record in salary_records)
                    annual_gross = sum(Decimal(str(record.gross_salary or 0)) for record in salary_records)
                    annual_net = sum(Decimal(str(record.net_salary or 0)) for record in salary_records)
                    annual_deductions = sum(Decimal(str(record.total_deductions or 0)) for record in salary_records)
                    
                    # Calculate allowances and deductions from JSON fields
                    annual_hra = Decimal('0')
                    annual_pf = Decimal('0')
                    annual_esi = Decimal('0')
                    annual_tds = Decimal('0')
                    
                    for record in salary_records:
                        # Extract HRA from allowances JSON
                        if record.allowances and isinstance(record.allowances, dict):
                            annual_hra += Decimal(str(record.allowances.get('hra', 0) or 0))
                        
                        # Extract deductions from deductions JSON
                        if record.deductions and isinstance(record.deductions, dict):
                            annual_pf += Decimal(str(record.deductions.get('pf_employee', 0) or 0))
                            annual_esi += Decimal(str(record.deductions.get('esi_employee', 0) or 0))
                            annual_tds += Decimal(str(record.deductions.get('tds', 0) or 0))
                    
                    # Calculate months worked
                    months_worked = len(salary_records) if salary_records else 0
                
                # Only include employees with salary data (either from reports or current salary)
                if annual_gross > 0:
                    employee_data = {
                        "employee_id": employee.id,
                        "employee_code": employee.employee_code,
                        "employee_name": f"{employee.first_name} {employee.last_name}",
                        "designation": employee.designation.name if employee.designation else "",
                        "department": employee.department.name if employee.department else "",
                        "location": employee.location.name if employee.location else "",
                        "cost_center": employee.cost_center.name if employee.cost_center else "",
                        "grade": employee.grade.name if hasattr(employee, 'grade') and employee.grade else "",
                        "date_of_joining": employee.date_of_joining,
                        "annual_basic": float(annual_basic),
                        "annual_hra": float(annual_hra),
                        "annual_gross_salary": float(annual_gross),
                        "annual_net_salary": float(annual_net),
                        "annual_pf": float(annual_pf),
                        "annual_esi": float(annual_esi),
                        "annual_tds": float(annual_tds),
                        "annual_deductions": float(annual_deductions),
                        "months_worked": months_worked,
                        "data_source": "salary_reports" if salary_records else "current_salary"
                    }
                    
                    annual_data.append(employee_data)
            
            return {
                "employees": annual_data,
                "financial_year": financial_year,
                "start_year": start_year,
                "end_year": end_year
            }
            
        except Exception as e:
            logger.error(f"Error in get_annual_salary_summary_data: {e}")
            import traceback
            traceback.print_exc()
            return {"employees": [], "financial_year": financial_year}

    def get_tds_return_data(self, financial_year: str, filters: Dict[str, Any]) -> List[Any]:
        """Get TDS Return data with quarterly details"""
        from app.models.datacapture import TDSReturn, TDSChallan, IncomeTaxTDS
        from app.models.employee import Employee
        from app.models.business import Business
        from sqlalchemy import func, extract
        
        logger.info(f"Getting TDS Return data for financial_year: {financial_year}, filters: {filters}")
        
        try:
            # Validate business_id is provided
            business_id = filters.get('business_id')
            if not business_id:
                raise ValueError("business_id is required for TDS Return data")
            
            # Base query for TDS returns - FILTER BY BUSINESS_ID
            query = self.db.query(TDSReturn).filter(
                TDSReturn.financial_year == financial_year,
                TDSReturn.business_id == business_id  # SECURITY: Filter by business_id
            )
            
            # Apply filters
            if filters.get('quarter'):
                query = query.filter(TDSReturn.quarter == filters['quarter'])
            
            if filters.get('return_type'):
                query = query.filter(TDSReturn.return_type == filters['return_type'])
            
            return query.order_by(TDSReturn.quarter).all()
            
        except Exception as e:
            logger.error(f"Failed to get TDS Return data: {str(e)}")
            raise Exception(f"Failed to get TDS Return data: {str(e)}")

    def get_tds_challan_data_for_period(self, financial_year: str, quarter: str, business_id: int) -> List[Any]:
        """Get TDS challan data for a specific quarter"""
        from app.models.datacapture import TDSChallan
        from datetime import datetime
        from sqlalchemy import extract
        
        logger.info(f"Getting TDS challan data for FY: {financial_year}, Q: {quarter}, business_id: {business_id}")
        
        try:
            # Map quarter to months
            quarter_months = {
                "Q1": ["04", "05", "06"],  # Apr-Jun
                "Q2": ["07", "08", "09"],  # Jul-Sep
                "Q3": ["10", "11", "12"],  # Oct-Dec
                "Q4": ["01", "02", "03"]   # Jan-Mar (next year)
            }
            
            if quarter not in quarter_months:
                return []
            
            months = quarter_months[quarter]
            
            # Parse financial year (e.g., "2024-25" -> start_year=2024, end_year=2025)
            start_year, end_year = map(int, financial_year.split('-'))
            
            # Build date filters for the quarter
            challan_data = []
            for month in months:
                # Determine the year for this month
                if month in ["01", "02", "03"]:  # Q4 months are in the next year
                    year = end_year
                else:
                    year = start_year
                
                # Query challans for this month - FILTER BY BUSINESS_ID
                month_challans = self.db.query(TDSChallan).filter(
                    TDSChallan.business_id == business_id,  # SECURITY: Filter by business_id
                    extract('year', TDSChallan.deposit_date) == year,
                    extract('month', TDSChallan.deposit_date) == int(month)
                ).all()
                
                challan_data.extend(month_challans)
            
            return challan_data
            
        except Exception as e:
            logger.error(f"Failed to get TDS challan data: {str(e)}")
            raise Exception(f"Failed to get TDS challan data: {str(e)}")

    def get_payroll_tds_data_for_period(self, financial_year: str, quarter: str, business_id: int) -> Dict[str, Any]:
        """Get payroll TDS data for comparison"""
        from app.models.datacapture import IncomeTaxTDS
        from app.models.employee import Employee
        from datetime import datetime
        from decimal import Decimal
        from sqlalchemy import func
        
        logger.info(f"Getting payroll TDS data for FY: {financial_year}, Q: {quarter}, business_id: {business_id}")
        
        try:
            # Map quarter to months
            quarter_months = {
                "Q1": ["04", "05", "06"],  # Apr-Jun
                "Q2": ["07", "08", "09"],  # Jul-Sep
                "Q3": ["10", "11", "12"],  # Oct-Dec
                "Q4": ["01", "02", "03"]   # Jan-Mar (next year)
            }
            
            if quarter not in quarter_months:
                return {"total_tds": 0, "total_employees": 0, "monthly_breakdown": {}}
            
            months = quarter_months[quarter]
            
            # Parse financial year
            start_year, end_year = map(int, financial_year.split('-'))
            
            # Get TDS data for each month in the quarter
            monthly_breakdown = {}
            total_tds = Decimal('0')
            employee_ids = set()
            
            for month in months:
                # Determine the year for this month
                if month in ["01", "02", "03"]:  # Q4 months are in the next year
                    year = end_year
                else:
                    year = start_year
                
                # Create period string for database query
                period = f"{year}-{month}"
                
                # Query TDS data for this period - FILTER BY BUSINESS_ID
                tds_records = self.db.query(IncomeTaxTDS).filter(
                    IncomeTaxTDS.business_id == business_id,  # SECURITY: Filter by business_id
                    IncomeTaxTDS.financial_year == financial_year,
                    func.to_char(IncomeTaxTDS.deposit_date, 'YYYY-MM') == period
                ).all()
                
                month_total = Decimal('0')
                month_employees = set()
                
                for tds in tds_records:
                    month_total += tds.tds_amount
                    month_employees.add(tds.employee_id)
                    employee_ids.add(tds.employee_id)
                
                monthly_breakdown[month] = {
                    "total_tds": float(month_total),
                    "employee_count": len(month_employees),
                    "period": period
                }
                
                total_tds += month_total
            
            return {
                "total_tds": float(total_tds),
                "total_employees": len(employee_ids),
                "monthly_breakdown": monthly_breakdown,
                "quarter": quarter,
                "financial_year": financial_year
            }
            
        except Exception as e:
            logger.error(f"Failed to get payroll TDS data: {str(e)}")
            raise Exception(f"Failed to get payroll TDS data: {str(e)}")

    def save_tds_return_data(self, return_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save TDS Return data to database"""
        from app.models.datacapture import TDSReturn
        from datetime import datetime, date
        
        try:
            financial_year = return_data.get('financial_year')
            quarter = return_data.get('quarter')
            business_id = return_data.get('business_id', 1)
            
            # Check if return already exists
            existing_return = self.db.query(TDSReturn).filter(
                TDSReturn.financial_year == financial_year,
                TDSReturn.quarter == quarter,
                TDSReturn.business_id == business_id
            ).first()
            
            if existing_return:
                # Update existing return
                existing_return.acknowledgment_number = return_data.get('acknowledgment_number')
                existing_return.total_deductees = return_data.get('total_deductees', 0)
                existing_return.total_tds_amount = return_data.get('total_tds_amount', 0)
                existing_return.total_deposited = return_data.get('total_deposited', 0)
                existing_return.is_filed = return_data.get('is_filed', False)
                existing_return.remarks = return_data.get('remarks', '')
                existing_return.updated_at = datetime.now()
                
                self.db.commit()
                self.db.refresh(existing_return)
                
                return {"return_id": existing_return.id, "action": "updated"}
            
            else:
                # Create new return
                new_return = TDSReturn(
                    business_id=business_id,
                    return_type=return_data.get('return_type', '24Q'),
                    financial_year=financial_year,
                    quarter=quarter,
                    filing_date=return_data.get('filing_date') or date.today(),
                    acknowledgment_number=return_data.get('acknowledgment_number', ''),
                    total_deductees=return_data.get('total_deductees', 0),
                    total_tds_amount=return_data.get('total_tds_amount', 0),
                    total_deposited=return_data.get('total_deposited', 0),
                    is_filed=return_data.get('is_filed', False),
                    is_revised=False,
                    revision_number=0,
                    remarks=return_data.get('remarks', f'TDS return for {quarter} {financial_year}'),
                    created_by=return_data.get('created_by', 1)
                )
                
                self.db.add(new_return)
                self.db.commit()
                self.db.refresh(new_return)
                
                return {"return_id": new_return.id, "action": "created"}
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to save TDS Return data: {str(e)}")

    def get_annual_salary_statement_data(self, periods: List[str], filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get Annual Salary Statement data for a specific employee across multiple periods"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from datetime import datetime
        
        logger.info(f"Getting Annual Salary Statement data for periods: {periods}, filters: {filters}")
        
        try:
            # Validate business_id is provided
            business_id = filters.get('business_id')
            if not business_id:
                raise ValueError("business_id is required for Annual Salary Statement data")
            
            # Convert periods from frontend format (e.g., "JUL-2025") to backend format (e.g., "2025-07")
            backend_periods = []
            for period in periods:
                try:
                    month_obj = datetime.strptime(period, "%b-%Y")
                    backend_period = month_obj.strftime('%Y-%m')
                    backend_periods.append(backend_period)
                except ValueError:
                    # If already in backend format, use as is
                    backend_periods.append(period)
            
            # Base query for employees - FILTER BY BUSINESS_ID
            query = self.db.query(
                Employee,
                Department.name.label('department_name'),
                Designation.name.label('designation_name'),
                Location.name.label('location_name'),
                CostCenter.name.label('cost_center_name')
            ).outerjoin(
                Department, Employee.department_id == Department.id
            ).outerjoin(
                Designation, Employee.designation_id == Designation.id
            ).outerjoin(
                Location, Employee.location_id == Location.id
            ).outerjoin(
                CostCenter, Employee.cost_center_id == CostCenter.id
            ).filter(
                Employee.employee_status == 'ACTIVE',
                Employee.business_id == business_id  # SECURITY: Filter by business_id
            )
            
            # Apply filters
            if filters.get('location') and filters['location'] != "All Locations":
                query = query.filter(Location.name == filters['location'])
            
            if filters.get('department') and filters['department'] != "All Departments":
                query = query.filter(Department.name == filters['department'])
            
            if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
                query = query.filter(CostCenter.name == filters['cost_center'])
            
            # Employee search filter
            if filters.get('employee_search'):
                search_term = f"%{filters['employee_search']}%"
                query = query.filter(
                    or_(
                        Employee.first_name.ilike(search_term),
                        Employee.last_name.ilike(search_term),
                        Employee.employee_code.ilike(search_term),
                        func.concat(Employee.first_name, ' ', Employee.last_name).ilike(search_term)
                    )
                )
            
            # Get the first matching employee (since this is employee-specific report)
            employee_result = query.first()
            
            if not employee_result:
                return {
                    "employee": None,
                    "periods": periods,
                    "backend_periods": backend_periods,
                    "message": "No matching employee found"
                }
            
            employee = employee_result[0]
            department_name = employee_result[1] or "General"
            designation_name = employee_result[2] or "Employee"
            location_name = employee_result[3] or "Main Office"
            cost_center_name = employee_result[4] or "Default"
            
            # Get salary reports for this employee across all periods
            salary_reports = self.db.query(SalaryReport).filter(
                SalaryReport.employee_id == employee.id,
                SalaryReport.report_period.in_(backend_periods)
            ).all()
            
            # Organize salary data by period
            salary_by_period = {}
            for report in salary_reports:
                # Convert backend period to frontend format for display
                try:
                    period_obj = datetime.strptime(report.report_period, '%Y-%m')
                    frontend_period = period_obj.strftime('%b-%Y').upper()
                except ValueError:
                    frontend_period = report.report_period
                
                salary_by_period[frontend_period] = {
                    'basic_salary': report.basic_salary,
                    'gross_salary': report.gross_salary,
                    'net_salary': report.net_salary,
                    'total_deductions': report.total_deductions,
                    'allowances': report.allowances or {},
                    'deductions': report.deductions or {}
                }
            
            return {
                "employee": {
                    "id": employee.id,
                    "name": f"{employee.first_name} {employee.last_name}".strip(),
                    "code": employee.employee_code,
                    "date_of_joining": employee.date_of_joining,
                    "designation": designation_name,
                    "department": department_name,
                    "location": location_name,
                    "cost_center": cost_center_name
                },
                "salary_by_period": salary_by_period,
                "periods": periods,
                "backend_periods": backend_periods,
                "message": "Employee data found"
            }
            
        except Exception as e:
            print(f"Error in get_annual_salary_statement_data: {e}")
            import traceback
            traceback.print_exc()
            return {
                "employee": None,
                "periods": periods,
                "backend_periods": [],
                "message": f"Error retrieving data: {str(e)}"
            }

    def get_annual_attendance_data(self, periods: List[str], filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get Annual Attendance data for employees across multiple periods"""
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.designations import Designation
        from app.models.location import Location
        from app.models.cost_center import CostCenter
        from app.models.attendance import AttendanceRecord, AttendanceStatus
        from app.models.datacapture import ExtraHour
        from datetime import datetime, date
        from calendar import monthrange
        from sqlalchemy import func, extract, and_, or_
        
        logger.info(f"Getting Annual Attendance data for periods: {periods}, filters: {filters}")
        
        try:
            # Validate business_id is provided
            business_id = filters.get('business_id')
            if not business_id:
                raise ValueError("business_id is required for Annual Attendance data")
            
            # Convert periods from frontend format (e.g., "JAN-2025") to date ranges
            date_ranges = []
            for period in periods:
                try:
                    month_obj = datetime.strptime(period, "%b-%Y")
                    year = month_obj.year
                    month = month_obj.month
                    
                    # Get first and last day of the month
                    first_day = date(year, month, 1)
                    last_day = date(year, month, monthrange(year, month)[1])
                    
                    date_ranges.append({
                        'period': period,
                        'start_date': first_day,
                        'end_date': last_day,
                        'year': year,
                        'month': month
                    })
                except ValueError:
                    continue
            
            if not date_ranges:
                return {
                    "employees": [],
                    "periods": periods,
                    "message": "Invalid period format"
                }
            
            # Calculate overall date range
            overall_start = min(dr['start_date'] for dr in date_ranges)
            overall_end = max(dr['end_date'] for dr in date_ranges)
            
            # Base query for employees - FILTER BY BUSINESS_ID
            query = self.db.query(
                Employee,
                Department.name.label('department_name'),
                Designation.name.label('designation_name'),
                Location.name.label('location_name'),
                CostCenter.name.label('cost_center_name')
            ).outerjoin(
                Department, Employee.department_id == Department.id
            ).outerjoin(
                Designation, Employee.designation_id == Designation.id
            ).outerjoin(
                Location, Employee.location_id == Location.id
            ).outerjoin(
                CostCenter, Employee.cost_center_id == CostCenter.id
            ).filter(
                Employee.business_id == business_id  # SECURITY: Filter by business_id
            )
            
            # Apply filters
            if filters.get('location') and filters['location'] != "All Locations":
                query = query.filter(Location.name == filters['location'])
            
            if filters.get('department') and filters['department'] != "All Departments":
                query = query.filter(Department.name == filters['department'])
            
            if filters.get('cost_center') and filters['cost_center'] != "All Cost Centers":
                query = query.filter(CostCenter.name == filters['cost_center'])
            
            # Employee search filter
            if filters.get('employee_search'):
                search_term = f"%{filters['employee_search']}%"
                query = query.filter(
                    or_(
                        Employee.first_name.ilike(search_term),
                        Employee.last_name.ilike(search_term),
                        Employee.employee_code.ilike(search_term),
                        func.concat(Employee.first_name, ' ', Employee.last_name).ilike(search_term)
                    )
                )
            
            # Record type filter
            if filters.get('record_type') == "Active Records":
                query = query.filter(Employee.employee_status == 'ACTIVE')
            elif filters.get('record_type') == "Inactive Records":
                query = query.filter(Employee.employee_status != 'ACTIVE')
            
            employees_data = query.all()
            
            if not employees_data:
                return {
                    "employees": [],
                    "periods": periods,
                    "message": "No employees found matching the criteria"
                }
            
            # Get attendance data for all employees across all periods
            employee_ids = [emp[0].id for emp in employees_data]
            
            attendance_records = self.db.query(AttendanceRecord).filter(
                AttendanceRecord.employee_id.in_(employee_ids),
                AttendanceRecord.attendance_date >= overall_start,
                AttendanceRecord.attendance_date <= overall_end
            ).all()
            
            # Get overtime data
            overtime_records = self.db.query(ExtraHour).filter(
                ExtraHour.employee_id.in_(employee_ids),
                ExtraHour.work_date >= overall_start,
                ExtraHour.work_date <= overall_end,
                ExtraHour.is_approved == True
            ).all()
            
            # Process attendance data by employee
            employees_attendance = {}
            for emp_data in employees_data:
                employee = emp_data[0]
                department_name = emp_data[1] or "General"
                designation_name = emp_data[2] or "Employee"
                location_name = emp_data[3] or "Main Office"
                cost_center_name = emp_data[4] or "Default"
                
                # Initialize attendance metrics
                attendance_metrics = {
                    'presents': 0,
                    'absents': 0,
                    'week_offs': 0,
                    'holidays': 0,
                    'paid_leaves': 0,
                    'unpaid_leaves': 0,
                    'paid_days': 0,
                    'total_days': 0,
                    'extra_days': 0,
                    'ot_days': 0,
                    'total_hours': 0.0,
                    'overtime_hours': 0.0
                }
                
                # Get employee's attendance records
                emp_attendance = [att for att in attendance_records if att.employee_id == employee.id]
                emp_overtime = [ot for ot in overtime_records if ot.employee_id == employee.id]
                
                # Process attendance for each period
                for date_range in date_ranges:
                    period_start = date_range['start_date']
                    period_end = date_range['end_date']
                    
                    # Get attendance records for this period
                    period_attendance = [
                        att for att in emp_attendance 
                        if period_start <= att.attendance_date <= period_end
                    ]
                    
                    # Get overtime records for this period
                    period_overtime = [
                        ot for ot in emp_overtime 
                        if period_start <= ot.work_date <= period_end
                    ]
                    
                    # Calculate total days in period
                    total_days_in_period = (period_end - period_start).days + 1
                    attendance_metrics['total_days'] += total_days_in_period
                    
                    # Count attendance statuses
                    for att_record in period_attendance:
                        if att_record.attendance_status == AttendanceStatus.PRESENT:
                            attendance_metrics['presents'] += 1
                            attendance_metrics['paid_days'] += 1
                            if att_record.total_hours:
                                attendance_metrics['total_hours'] += float(att_record.total_hours)
                        elif att_record.attendance_status == AttendanceStatus.ABSENT:
                            attendance_metrics['absents'] += 1
                        elif att_record.attendance_status == AttendanceStatus.ON_LEAVE:
                            attendance_metrics['paid_leaves'] += 1
                            attendance_metrics['paid_days'] += 1
                        elif att_record.attendance_status == AttendanceStatus.WEEKEND:
                            attendance_metrics['week_offs'] += 1
                        elif att_record.attendance_status == AttendanceStatus.HOLIDAY:
                            attendance_metrics['holidays'] += 1
                    
                    # Count overtime days and hours
                    ot_days_in_period = len(set(ot.work_date for ot in period_overtime))
                    attendance_metrics['ot_days'] += ot_days_in_period
                    
                    for ot_record in period_overtime:
                        if ot_record.extra_hours:
                            attendance_metrics['overtime_hours'] += float(ot_record.extra_hours)
                
                # Calculate derived metrics
                # Assume standard working days (excluding weekends and holidays)
                # This is a simplified calculation - you may need to adjust based on business rules
                expected_working_days = attendance_metrics['total_days'] - attendance_metrics['week_offs'] - attendance_metrics['holidays']
                actual_working_days = attendance_metrics['presents'] + attendance_metrics['paid_leaves']
                
                if actual_working_days > expected_working_days:
                    attendance_metrics['extra_days'] = actual_working_days - expected_working_days
                
                # Store employee data
                employees_attendance[employee.id] = {
                    'employee': employee,
                    'department': department_name,
                    'designation': designation_name,
                    'location': location_name,
                    'cost_center': cost_center_name,
                    'metrics': attendance_metrics
                }
            
            return {
                "employees": employees_attendance,
                "periods": periods,
                "date_range": {
                    "from_date": overall_start.strftime('%Y-%m-%d'),
                    "to_date": overall_end.strftime('%Y-%m-%d')
                },
                "message": "Annual attendance data retrieved successfully"
            }
            
        except Exception as e:
            print(f"Error in get_annual_attendance_data: {e}")
            import traceback
            traceback.print_exc()
            return {
                "employees": {},
                "periods": periods,
                "date_range": {"from_date": "", "to_date": ""},
                "message": f"Error retrieving attendance data: {str(e)}"
            }