"""
TDS Challan Service
Business logic for TDS challan management
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, date
from decimal import Decimal

from app.repositories.tds_challan_repository import TDSChallanRepository
from app.repositories.employee_repository import EmployeeRepository


class TDSChallanService:
    """Service for TDS challan business logic"""
    
    def __init__(self, db: Session):
        self.db = db
        self.tds_challan_repo = TDSChallanRepository(db)
        self.employee_repo = EmployeeRepository(db)
    
    def get_challans_by_financial_year(
        self,
        financial_year: str,
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get all TDS challans for a financial year
        
        Args:
            financial_year: Financial year in format "2024-25"
            business_id: Business ID filter
            
        Returns:
            Dictionary with financial year and monthly challan data
        """
        try:
            # Generate all 12 months for the financial year
            months = self._generate_financial_year_months(financial_year)
            
            # Get existing challan data from database
            existing_challans = self.tds_challan_repo.get_challans_by_financial_year(
                financial_year, business_id
            )
            
            # Create a lookup dictionary for existing data
            challan_lookup = {challan["month"]: challan for challan in existing_challans}
            
            # Build response with all 12 months
            challan_data = []
            for month in months:
                if month in challan_lookup:
                    # Use existing data
                    challan_data.append(challan_lookup[month])
                else:
                    # Create empty entry for missing months
                    challan_data.append({
                        "month": month,
                        "bsrcode": "",
                        "date": "",
                        "challan": ""
                    })
            
            return {
                "financial_year": financial_year,
                "total_months": 12,
                "challans": challan_data
            }
            
        except Exception as e:
            raise Exception(f"Failed to get challans for financial year: {str(e)}")
    
    def save_challan_month(
        self,
        financial_year: str,
        month: str,
        bsrcode: str,
        deposit_date: str,
        challan_number: str,
        business_id: Optional[int] = None,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Save TDS challan data for a specific month
        
        Args:
            financial_year: Financial year in format "2024-25"
            month: Month in format "APR-2024"
            bsrcode: BSR code
            deposit_date: Date of deposit in YYYY-MM-DD format
            challan_number: Challan serial number
            business_id: Business ID
            created_by: User ID who created
            
        Returns:
            Save result
        """
        try:
            # Validate inputs
            if not bsrcode.strip() and not deposit_date.strip() and not challan_number.strip():
                raise ValueError("At least one field (BSR code, date, or challan number) must be provided")
            
            # Parse deposit date if provided
            parsed_date = None
            if deposit_date.strip():
                try:
                    parsed_date = datetime.strptime(deposit_date, "%Y-%m-%d").date()
                except ValueError:
                    raise ValueError("Invalid date format. Use YYYY-MM-DD")
            
            # Save or update challan data
            result = self.tds_challan_repo.save_challan_month(
                financial_year=financial_year,
                month=month,
                bsrcode=bsrcode.strip(),
                deposit_date=parsed_date,
                challan_number=challan_number.strip(),
                business_id=business_id,
                created_by=created_by
            )
            
            return {
                "message": "Challan saved successfully",
                "month": month,
                "financial_year": financial_year,
                "saved_at": datetime.now().isoformat(),
                "challan_id": result["challan_id"]
            }
            
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to save challan for month {month}: {str(e)}")
    
    def get_challan_by_month(
        self,
        financial_year: str,
        month: str,
        business_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get TDS challan data for a specific month
        
        Args:
            financial_year: Financial year in format "2024-25"
            month: Month in format "APR-2024"
            business_id: Business ID
            
        Returns:
            Challan data for the month or None if not found
        """
        try:
            return self.tds_challan_repo.get_challan_by_month(
                financial_year, month, business_id
            )
            
        except Exception as e:
            raise Exception(f"Failed to get challan for month {month}: {str(e)}")
    
    def delete_challan_month(
        self,
        financial_year: str,
        month: str,
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Delete TDS challan data for a specific month
        
        Args:
            financial_year: Financial year in format "2024-25"
            month: Month in format "APR-2024"
            business_id: Business ID
            
        Returns:
            Delete result
        """
        try:
            success = self.tds_challan_repo.delete_challan_month(
                financial_year, month, business_id
            )
            
            if success:
                return {
                    "message": f"Challan for {month} deleted successfully",
                    "month": month,
                    "financial_year": financial_year,
                    "deleted_at": datetime.now().isoformat()
                }
            else:
                raise ValueError(f"No challan found for {month} in {financial_year}")
            
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to delete challan for month {month}: {str(e)}")
    
    def get_challan_summary(
        self,
        financial_year: str,
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get summary of TDS challans for a financial year
        
        Args:
            financial_year: Financial year in format "2024-25"
            business_id: Business ID
            
        Returns:
            Summary statistics
        """
        try:
            # Get all challans for the financial year
            challans = self.tds_challan_repo.get_challans_by_financial_year(
                financial_year, business_id
            )
            
            # Generate all expected months for the financial year
            expected_months = self._generate_financial_year_months(financial_year)
            
            # Create a set of months that have challan data (with challan number)
            completed_months_set = set()
            for challan in challans:
                if challan.get("challan") and challan.get("challan").strip():
                    # Extract month from the challan data
                    month = challan.get("month")
                    if month:
                        completed_months_set.add(month)
            
            total_months = len(expected_months)  # Always 12
            completed_months = len(completed_months_set)  # Unique months with data
            pending_months = total_months - completed_months
            
            # Calculate completion percentage (max 100%)
            completion_percentage = min(100.0, round((completed_months / total_months) * 100, 2))
            
            # Calculate total amount from all challans
            total_amount = 0.0
            for challan in challans:
                # Add total_amount from dictionary
                if isinstance(challan, dict) and 'total_amount' in challan:
                    total_amount += float(challan['total_amount'])
                elif hasattr(challan, 'total_amount') and challan.total_amount:
                    total_amount += float(challan.total_amount)
            
            return {
                "financial_year": financial_year,
                "total_months": total_months,
                "completed_months": completed_months,
                "pending_months": max(0, pending_months),  # Ensure non-negative
                "completion_percentage": completion_percentage,
                "total_amount": total_amount,
                "expected_months": expected_months,
                "completed_months_list": list(completed_months_set)
            }
            
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to get challan summary: {str(e)}")
    
    def _generate_financial_year_months(self, financial_year: str) -> List[str]:
        """
        Generate list of months for a financial year
        
        Args:
            financial_year: Financial year in format "2024-25"
            
        Returns:
            List of months in format ["APR-2024", "MAY-2024", ...]
        """
        try:
            # Parse financial year
            start_year, end_year_suffix = financial_year.split('-')
            start_year = int(start_year)
            end_year = int(f"20{end_year_suffix}")
            
            # Generate months from April to March
            months = []
            month_names = ["APR", "MAY", "JUN", "JUL", "AUG", "SEP", 
                          "OCT", "NOV", "DEC", "JAN", "FEB", "MAR"]
            
            for i, month_name in enumerate(month_names):
                if i < 9:  # APR to DEC (first year)
                    year = start_year
                else:  # JAN to MAR (second year)
                    year = end_year
                
                months.append(f"{month_name}-{year}")
            
            return months
            
        except Exception as e:
            raise ValueError(f"Invalid financial year format: {financial_year}")