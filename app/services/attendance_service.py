"""
Attendance Service
Business logic for attendance management
"""

from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, time, timedelta
from decimal import Decimal
import logging

from app.repositories.attendance_repository import (
    AttendanceRepository, AttendancePunchRepository, 
    AttendanceCorrectionRepository, ShiftRosterRepository
)
from app.repositories.employee_repository import EmployeeRepository
from app.models.attendance import (
    AttendanceRecord, AttendancePunch, AttendanceCorrection,
    ShiftRoster, AttendanceStatus, PunchType
)
from app.models.employee import Employee
from app.models.work_shifts import WorkShift
from app.schemas.attendance import (
    AttendanceRecordCreate, AttendanceRecordUpdate,
    PunchCreate, ManualAttendanceRequest, ManualAttendanceUpdate,
    LeaveCorrectionSaveRequest, ShiftRosterCreate
)
from app.core.exceptions import ValidationError, NotFoundError

logger = logging.getLogger(__name__)


class AttendanceService:
    """Service class for attendance operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.attendance_repo = AttendanceRepository(db)
        self.punch_repo = AttendancePunchRepository(db)
        self.correction_repo = AttendanceCorrectionRepository(db)
        self.roster_repo = ShiftRosterRepository(db)
        self.employee_repo = EmployeeRepository(db)
    
    def get_attendance_dashboard(self, business_id: Optional[int]) -> Dict[str, Any]:
        """Get attendance dashboard data"""
        try:
            today = date.today()
            
            # Get today's attendance summary
            daily_summary = self.attendance_repo.get_attendance_summary_by_date(business_id, today)
            
            # Get weekly trends (last 7 days)
            weekly_trends = []
            for i in range(7):
                trend_date = today - timedelta(days=i)
                day_summary = self.attendance_repo.get_attendance_summary_by_date(business_id, trend_date)
                weekly_trends.append({
                    "day": trend_date.strftime("%A"),
                    "date": trend_date.strftime("%Y-%m-%d"),
                    "present": day_summary.get('present', 0),
                    "absent": day_summary.get('absent', 0),
                    "late": day_summary.get('late', 0)
                })
            
            # Get recent activities (last 10 punches)
            punch_query = self.db.query(AttendancePunch).join(Employee)
            
            # Apply business filter only if business_id is provided (not superadmin)
            if business_id is not None:
                punch_query = punch_query.filter(Employee.business_id == business_id)
            
            recent_punches = punch_query.order_by(AttendancePunch.punch_time.desc()).limit(10).all()
            
            recent_activities = []
            for punch in recent_punches:
                employee_name = f"{punch.employee.first_name} {punch.employee.last_name}"
                action = "Check In" if punch.punch_type == PunchType.IN else "Check Out"
                punch_time = punch.punch_time.strftime("%I:%M %p")
                
                # Determine status based on time (simple logic)
                status = "On Time"
                if punch.punch_type == PunchType.IN:
                    punch_hour = punch.punch_time.hour
                    if punch_hour > 9:  # After 9 AM is late
                        status = "Late"
                
                recent_activities.append({
                    "employee_name": employee_name,
                    "action": action,
                    "time": punch_time,
                    "status": status
                })
            
            return {
                "daily_summary": daily_summary,
                "weekly_trends": weekly_trends,
                "recent_activities": recent_activities
            }
            
        except Exception as e:
            logger.error(f"Error getting attendance dashboard: {str(e)}")
            raise
    
    def add_punch(self, punch_data: PunchCreate, created_by: int) -> AttendancePunch:
        """Add a new punch record"""
        try:
            # Validate employee exists
            employee = self.employee_repo.get(punch_data.employee_id)
            if not employee:
                raise NotFoundError("Employee not found")
            
            # Get current date
            punch_time = datetime.now()
            punch_date = punch_time.date()
            
            # Check for existing attendance record
            attendance_record = self.attendance_repo.get_by_employee_and_date(
                punch_data.employee_id, punch_date
            )
            
            # Create punch record
            punch = AttendancePunch(
                employee_id=punch_data.employee_id,
                punch_time=punch_time,
                punch_type=punch_data.punch_type,
                location=punch_data.location,
                latitude=punch_data.latitude,
                longitude=punch_data.longitude,
                is_remote=punch_data.is_remote,
                device_info=punch_data.device_info,
                created_by=created_by
            )
            
            # If attendance record exists, link the punch
            if attendance_record:
                punch.attendance_record_id = attendance_record.id
                
                # Update attendance record with punch times
                if punch_data.punch_type == PunchType.IN and not attendance_record.punch_in_time:
                    attendance_record.punch_in_time = punch_time
                elif punch_data.punch_type == PunchType.OUT:
                    attendance_record.punch_out_time = punch_time
                    
                    # Calculate total hours if both punch in and out exist
                    if attendance_record.punch_in_time:
                        time_diff = punch_time - attendance_record.punch_in_time
                        attendance_record.total_hours = Decimal(time_diff.total_seconds() / 3600)
            else:
                # Create new attendance record
                attendance_record = AttendanceRecord(
                    employee_id=punch_data.employee_id,
                    business_id=employee.business_id,
                    attendance_date=punch_date,
                    attendance_status=AttendanceStatus.PRESENT,
                    created_by=created_by
                )
                
                if punch_data.punch_type == PunchType.IN:
                    attendance_record.punch_in_time = punch_time
                    
                    # Check if late (assuming 9:00 AM is standard time)
                    if punch_time.time() > time(9, 0):
                        attendance_record.is_late = True
                        attendance_record.attendance_status = AttendanceStatus.LATE
                
                self.db.add(attendance_record)
                self.db.flush()  # Get the ID
                punch.attendance_record_id = attendance_record.id
            
            self.db.add(punch)
            self.db.commit()
            self.db.refresh(punch)
            
            return punch
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding punch: {str(e)}")
            raise
    
    def get_daily_punches(
        self, 
        business_id: int, 
        punch_date: date,
        page: int = 1,
        size: int = 50
    ) -> Tuple[List[Dict[str, Any]], int, Dict[str, int]]:
        """Get daily punch records for all employees"""
        try:
            # Get employee punches
            employee_punches, total = self.punch_repo.get_daily_punches(
                business_id, punch_date, page, size
            )
            
            # Get summary
            summary = self.attendance_repo.get_attendance_summary_by_date(business_id, punch_date)
            
            return employee_punches, total, summary
            
        except Exception as e:
            logger.error(f"Error getting daily punches: {str(e)}")
            raise
    
    def get_daily_attendance_cards(
        self, 
        business_id: int, 
        attendance_date: date,
        department_id: Optional[int] = None,
        location_id: Optional[int] = None,
        search: Optional[str] = None,
        page: int = 1,
        size: int = 50
    ) -> Tuple[List[Dict[str, Any]], int, Dict[str, int]]:
        """Get daily attendance in card format"""
        try:
            # Get attendance records
            records, total = self.attendance_repo.get_daily_attendance(
                business_id, attendance_date, department_id, location_id, search, page, size
            )
            
            # Convert to card format
            cards = []
            for record in records:
                employee = record.employee
                
                # Build timeline
                timeline = {}
                if record.punch_in_time:
                    timeline["punchIn"] = record.punch_in_time.strftime("%H:%M")
                if record.punch_out_time:
                    timeline["punchOut"] = record.punch_out_time.strftime("%H:%M")
                
                # Calculate total hours
                total_hours = "0:00"
                if record.total_hours:
                    hours = int(record.total_hours)
                    minutes = int((record.total_hours - hours) * 60)
                    total_hours = f"{hours}:{minutes:02d}"
                
                # Build punches list
                punches = []
                for punch in record.punches:
                    punches.append({
                        "time": punch.punch_time.strftime("%H:%M"),
                        "type": punch.punch_type.value,
                        "location": punch.location or "N/A"
                    })
                
                card = {
                    "id": record.id,
                    "name": f"{employee.first_name} {employee.last_name}",
                    "code": employee.employee_code,
                    "date": attendance_date.strftime("%Y-%m-%d"),
                    "status": record.attendance_status.value,
                    "note": record.manual_entry_reason or "",
                    "location": employee.location.name if employee.location else "N/A",
                    "designation": employee.designation.name if employee.designation else "N/A",
                    "department": employee.department.name if employee.department else "N/A",
                    "punchIn": record.punch_in_time.strftime("%H:%M") if record.punch_in_time else None,
                    "punchOut": record.punch_out_time.strftime("%H:%M") if record.punch_out_time else None,
                    "punchType": "biometric" if not record.is_manual_entry else "manual",
                    "timeline": timeline,
                    "totalHours": total_hours,
                    "punches": punches
                }
                cards.append(card)
            
            # Get summary
            summary = self.attendance_repo.get_attendance_summary_by_date(business_id, attendance_date)
            
            return cards, total, summary
            
        except Exception as e:
            logger.error(f"Error getting daily attendance cards: {str(e)}")
            raise
    
    def create_manual_attendance(
        self, 
        manual_data: ManualAttendanceRequest, 
        created_by: int
    ) -> AttendanceRecord:
        """Create manual attendance entry"""
        try:
            # Validate employee exists
            employee = self.employee_repo.get(manual_data.employee_id)
            if not employee:
                raise NotFoundError("Employee not found")
            
            # Check if attendance already exists for this date
            existing_record = self.attendance_repo.get_by_employee_and_date(
                manual_data.employee_id, manual_data.attendance_date
            )
            
            if existing_record:
                raise ValidationError("Attendance record already exists for this date")
            
            # Parse check in/out times
            punch_in_time = None
            punch_out_time = None
            
            def parse_time_str(time_str: str) -> datetime.time:
                for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"):
                    try:
                        return datetime.strptime(time_str, fmt).time()
                    except ValueError:
                        continue
                raise ValueError(f"Invalid time format: {time_str}")

            if manual_data.check_in_time:
                punch_in_time = datetime.combine(
                    manual_data.attendance_date,
                    parse_time_str(manual_data.check_in_time)
                )
            
            if manual_data.check_out_time:
                punch_out_time = datetime.combine(
                    manual_data.attendance_date,
                    parse_time_str(manual_data.check_out_time)
                )
            
            # Calculate total hours
            total_hours = None
            if punch_in_time and punch_out_time:
                time_diff = punch_out_time - punch_in_time
                total_hours = Decimal(time_diff.total_seconds() / 3600)
            
            # Create attendance record
            attendance_record = AttendanceRecord(
                employee_id=manual_data.employee_id,
                business_id=employee.business_id,
                attendance_date=manual_data.attendance_date,
                punch_in_time=punch_in_time,
                punch_out_time=punch_out_time,
                total_hours=total_hours,
                attendance_status=manual_data.attendance_status,
                is_manual_entry=True,
                manual_entry_reason=manual_data.reason,
                created_by=created_by
            )
            
            self.db.add(attendance_record)
            self.db.commit()
            self.db.refresh(attendance_record)
            
            return attendance_record
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating manual attendance: {str(e)}")
            raise
    
    def get_employee_punches(
        self, 
        employee_id: int, 
        punch_date: date
    ) -> List[AttendancePunch]:
        """Get employee punches for a specific date"""
        try:
            return self.punch_repo.get_employee_punches_by_date(employee_id, punch_date)
        except Exception as e:
            logger.error(f"Error getting employee punches: {str(e)}")
            raise
    
    def create_leave_correction(
        self, 
        correction_data: LeaveCorrectionSaveRequest, 
        requested_by: int
    ) -> AttendanceCorrection:
        """Create leave correction request"""
        try:
            # Validate employee exists
            employee = self.employee_repo.get(correction_data.employee_id)
            if not employee:
                raise NotFoundError("Employee not found")
            
            # Get attendance record for the correction date
            attendance_record = self.attendance_repo.get_by_employee_and_date(
                correction_data.employee_id, correction_data.correction_date
            )
            
            if not attendance_record:
                raise NotFoundError("Attendance record not found for the specified date")
            
            # Create correction record
            correction = AttendanceCorrection(
                attendance_record_id=attendance_record.id,
                employee_id=correction_data.employee_id,
                correction_type="leave_correction",
                reason=correction_data.reason,
                supporting_documents=str(correction_data.supporting_documents) if correction_data.supporting_documents else None,
                status="pending"
            )
            
            self.db.add(correction)
            self.db.commit()
            self.db.refresh(correction)
            
            return correction
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating leave correction: {str(e)}")
            raise
    
    def get_monthly_attendance_summary(
        self, 
        business_id: int, 
        year: int, 
        month: int,
        department_id: Optional[int] = None,
        location_id: Optional[int] = None,
        search: Optional[str] = None,
        page: int = 1,
        size: int = 50
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get monthly attendance summary with filters and pagination"""
        try:
            return self.attendance_repo.get_monthly_attendance_summary(
                business_id, year, month, department_id, location_id, search, page, size
            )
        except Exception as e:
            logger.error(f"Error getting monthly attendance summary: {str(e)}")
            raise
    
    def save_manual_attendance_bulk(
        self,
        attendance_updates: List[ManualAttendanceUpdate],
        created_by: int
    ) -> Dict[str, Any]:
        """Save bulk manual attendance updates"""
        try:
            processed_records = 0
            errors = []
            
            for update in attendance_updates:
                try:
                    # Validate employee exists
                    employee = self.employee_repo.get(update.employee_id)
                    if not employee:
                        errors.append(f"Employee {update.employee_id} not found")
                        continue
                    
                    # Parse month
                    month_str, year_str = update.month.split('-')
                    year = int(year_str)
                    month_names = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                                  'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
                    month_num = month_names.index(month_str) + 1
                    
                    # Calculate date range
                    start_date = date(year, month_num, 1)
                    if month_num == 12:
                        end_date = date(year + 1, 1, 1) - timedelta(days=1)
                    else:
                        end_date = date(year, month_num + 1, 1) - timedelta(days=1)
                    
                    # Delete existing records for this month to avoid duplicates
                    self.db.query(AttendanceRecord).filter(
                        AttendanceRecord.employee_id == update.employee_id,
                        AttendanceRecord.attendance_date >= start_date,
                        AttendanceRecord.attendance_date <= end_date
                    ).delete()
                    
                    # Create new records based on the counts
                    current_date = start_date
                    present_count = 0
                    absent_count = 0
                    holiday_count = 0
                    weekend_count = 0
                    comp_off_count = 0
                    casual_leave_count = 0
                    lwp_count = 0
                    
                    while current_date <= end_date:
                        # Determine what type of day this should be
                        day_of_week = current_date.weekday()
                        
                        # Priority order: Weekend -> Holiday -> Absent -> Leave -> Present
                        if day_of_week in [5, 6] and weekend_count < update.weekend_days:
                            status = AttendanceStatus.WEEKEND
                            weekend_count += 1
                        elif holiday_count < update.holiday_days:
                            status = AttendanceStatus.HOLIDAY
                            holiday_count += 1
                        elif absent_count < update.absent_days:
                            status = AttendanceStatus.ABSENT
                            absent_count += 1
                        elif comp_off_count < update.comp_off_days:
                            status = AttendanceStatus.ON_LEAVE
                            comp_off_count += 1
                        elif casual_leave_count < update.casual_leave_days:
                            status = AttendanceStatus.ON_LEAVE
                            casual_leave_count += 1
                        elif lwp_count < update.leave_without_pay_days:
                            status = AttendanceStatus.ON_LEAVE
                            lwp_count += 1
                        elif present_count < update.present_days:
                            status = AttendanceStatus.PRESENT
                            present_count += 1
                        else:
                            # Default to present for remaining days
                            status = AttendanceStatus.PRESENT
                        
                        # Create attendance record
                        attendance_record = AttendanceRecord(
                            employee_id=update.employee_id,
                            business_id=employee.business_id,
                            attendance_date=current_date,
                            attendance_status=status,
                            is_manual_entry=True,
                            manual_entry_reason=f"Manual attendance entry for {update.month}",
                            created_by=created_by
                        )
                        
                        self.db.add(attendance_record)
                        current_date += timedelta(days=1)
                    
                    processed_records += 1
                    
                except Exception as e:
                    errors.append(f"Error processing employee {update.employee_id}: {str(e)}")
            
            self.db.commit()
            
            return {
                "success": True,
                "processed_records": processed_records,
                "errors": errors,
                "message": f"Processed {processed_records} employee records"
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving bulk manual attendance: {str(e)}")
            raise
    
    def calculate_leave_balance(
        self, 
        employee_id: int, 
        year: int, 
        month: Optional[int] = None
    ) -> Dict[str, float]:
        """Calculate employee leave balance"""
        try:
            # This is a simplified calculation
            # In a real system, this would consider leave policies, accruals, etc.
            
            # Get attendance records for the period
            if month:
                start_date = date(year, month, 1)
                if month == 12:
                    end_date = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = date(year, month + 1, 1) - timedelta(days=1)
            else:
                start_date = date(year, 1, 1)
                end_date = date(year, 12, 31)
            
            records = self.attendance_repo.get_employee_attendance_range(
                employee_id, start_date, end_date
            )
            
            # Count leave days
            leave_days = len([r for r in records if r.attendance_status == AttendanceStatus.ON_LEAVE])
            
            # Get corrections
            corrections = self.correction_repo.get_employee_corrections(
                employee_id, start_date, end_date
            )
            
            correction_count = len(corrections)
            
            # Simple calculation (in real system, this would be more complex)
            opening_balance = 24.0  # Annual leave entitlement
            activity = -leave_days  # Leaves taken
            correction = correction_count * 0.5  # Correction adjustments
            closing_balance = opening_balance + activity + correction
            
            return {
                "opening_balance": opening_balance,
                "activity": activity,
                "correction": correction,
                "closing_balance": max(0, closing_balance)  # Cannot be negative
            }
            
        except Exception as e:
            logger.error(f"Error calculating leave balance: {str(e)}")
            raise


class ShiftRosterService:
    """Service class for shift roster operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.roster_repo = ShiftRosterRepository(db)
        self.employee_repo = EmployeeRepository(db)
    
    def create_shift_roster(
        self, 
        roster_data: ShiftRosterCreate, 
        created_by: int
    ) -> ShiftRoster:
        """Create shift roster entry"""
        try:
            # Validate employee exists
            employee = self.employee_repo.get(roster_data.employee_id)
            if not employee:
                raise NotFoundError("Employee not found")
            
            # Validate shift exists
            shift = self.db.query(WorkShift).filter(WorkShift.id == roster_data.shift_id).first()
            if not shift:
                raise NotFoundError("Work shift not found")
            
            # Check if roster already exists for this date
            existing_roster = self.db.query(ShiftRoster).filter(
                ShiftRoster.employee_id == roster_data.employee_id,
                ShiftRoster.roster_date == roster_data.roster_date
            ).first()
            
            if existing_roster:
                raise ValidationError("Shift roster already exists for this date")
            
            # Create roster
            roster = ShiftRoster(
                employee_id=roster_data.employee_id,
                business_id=employee.business_id,
                roster_date=roster_data.roster_date,
                shift_id=roster_data.shift_id,
                custom_start_time=roster_data.custom_start_time,
                custom_end_time=roster_data.custom_end_time,
                notes=roster_data.notes,
                created_by=created_by
            )
            
            self.db.add(roster)
            self.db.commit()
            self.db.refresh(roster)
            
            return roster
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating shift roster: {str(e)}")
            raise
    
    def get_employee_roster(
        self, 
        employee_id: int, 
        start_date: date, 
        end_date: date
    ) -> List[ShiftRoster]:
        """Get employee shift roster for date range"""
        try:
            return self.roster_repo.get_employee_roster(employee_id, start_date, end_date)
        except Exception as e:
            logger.error(f"Error getting employee roster: {str(e)}")
            raise
    
    def bulk_create_roster(
        self, 
        business_id: int, 
        roster_data: List[Dict[str, Any]], 
        created_by: int
    ) -> List[ShiftRoster]:
        """Bulk create shift rosters"""
        try:
            # Add business_id and created_by to each roster entry
            for data in roster_data:
                data['business_id'] = business_id
                data['created_by'] = created_by
            
            return self.roster_repo.bulk_create_roster(roster_data)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error bulk creating roster: {str(e)}")
            raise