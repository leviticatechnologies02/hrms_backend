"""
TDS Return Service
Business logic for TDS return management
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, date
from decimal import Decimal

from app.repositories.tds_return_repository import TDSReturnRepository
from app.repositories.employee_repository import EmployeeRepository


class TDSReturnService:
    """Service for TDS return business logic"""
    
    def __init__(self, db: Session):
        self.db = db
        self.tds_return_repo = TDSReturnRepository(db)
        self.employee_repo = EmployeeRepository(db)
    
    def get_returns_by_financial_year(
        self,
        financial_year: str,
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get all TDS returns for a financial year
        
        Args:
            financial_year: Financial year in format "2024-25"
            business_id: Business ID filter
            
        Returns:
            Dictionary with financial year and quarterly return data
        """
        try:
            # Generate all 4 quarters for the financial year
            quarters = ["Q1", "Q2", "Q3", "Q4"]
            
            # Get existing return data from database
            existing_returns = self.tds_return_repo.get_returns_by_financial_year(
                financial_year, business_id
            )
            
            # Create a lookup dictionary for existing data
            return_lookup = {ret["quarter"]: ret for ret in existing_returns}
            
            # Build response with all 4 quarters
            return_data = []
            for quarter in quarters:
                if quarter in return_lookup:
                    # Use existing data
                    return_data.append(return_lookup[quarter])
                else:
                    # Create empty entry for missing quarters
                    return_data.append({
                        "quarter": quarter,
                        "receipt_number": ""
                    })
            
            return {
                "financial_year": financial_year,
                "total_quarters": 4,
                "returns": return_data
            }
            
        except Exception as e:
            raise Exception(f"Failed to get returns for financial year: {str(e)}")
    
    def save_return_quarter(
        self,
        financial_year: str,
        quarter: str,
        receipt_number: str,
        return_type: str = "24Q",
        filing_date: Optional[str] = None,
        business_id: Optional[int] = None,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Save TDS return data for a specific quarter
        
        Args:
            financial_year: Financial year in format "2024-25"
            quarter: Quarter (Q1, Q2, Q3, Q4)
            receipt_number: Acknowledgment/receipt number
            return_type: Type of return (24Q, 26Q, etc.)
            filing_date: Date of filing in YYYY-MM-DD format
            business_id: Business ID
            created_by: User ID who created
            
        Returns:
            Save result
        """
        try:
            # Validate inputs
            if not receipt_number.strip():
                raise ValueError("Receipt number is required")
            
            if quarter not in ["Q1", "Q2", "Q3", "Q4"]:
                raise ValueError("Invalid quarter. Must be Q1, Q2, Q3, or Q4")
            
            # Parse filing date if provided
            parsed_date = None
            if filing_date and filing_date.strip():
                try:
                    parsed_date = datetime.strptime(filing_date, "%Y-%m-%d").date()
                except ValueError:
                    raise ValueError("Invalid date format. Use YYYY-MM-DD")
            
            # Save or update return data
            result = self.tds_return_repo.save_return_quarter(
                financial_year=financial_year,
                quarter=quarter,
                receipt_number=receipt_number.strip(),
                return_type=return_type,
                filing_date=parsed_date,
                business_id=business_id,
                created_by=created_by
            )
            
            return {
                "message": "TDS return saved successfully",
                "quarter": quarter,
                "financial_year": financial_year,
                "receipt_number": receipt_number.strip(),
                "saved_at": datetime.now().isoformat(),
                "return_id": result["return_id"]
            }
            
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to save return for quarter {quarter}: {str(e)}")
    
    def get_return_by_quarter(
        self,
        financial_year: str,
        quarter: str,
        business_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get TDS return data for a specific quarter
        
        Args:
            financial_year: Financial year in format "2024-25"
            quarter: Quarter (Q1, Q2, Q3, Q4)
            business_id: Business ID
            
        Returns:
            Return data for the quarter or None if not found
        """
        try:
            return self.tds_return_repo.get_return_by_quarter(
                financial_year, quarter, business_id
            )
            
        except Exception as e:
            raise Exception(f"Failed to get return for quarter {quarter}: {str(e)}")
    
    def delete_return_quarter(
        self,
        financial_year: str,
        quarter: str,
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Delete TDS return data for a specific quarter
        
        Args:
            financial_year: Financial year in format "2024-25"
            quarter: Quarter (Q1, Q2, Q3, Q4)
            business_id: Business ID
            
        Returns:
            Delete result
        """
        try:
            success = self.tds_return_repo.delete_return_quarter(
                financial_year, quarter, business_id
            )
            
            if success:
                return {
                    "message": f"TDS return for {quarter} deleted successfully",
                    "quarter": quarter,
                    "financial_year": financial_year,
                    "deleted_at": datetime.now().isoformat()
                }
            else:
                raise ValueError(f"No TDS return found for {quarter} in {financial_year}")
            
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Failed to delete return for quarter {quarter}: {str(e)}")
    
    def get_returns_summary(
        self,
        financial_year: str,
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get summary of TDS returns for a financial year
        
        Args:
            financial_year: Financial year in format "2024-25"
            business_id: Business ID
            
        Returns:
            Summary statistics
        """
        try:
            summary = self.tds_return_repo.get_returns_summary(
                financial_year, business_id
            )
            
            return summary
            
        except Exception as e:
            raise Exception(f"Failed to get returns summary: {str(e)}")
    
    def download_return_receipt(
        self,
        financial_year: str,
        quarter: str,
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate download content for TDS return receipt
        
        Args:
            financial_year: Financial year in format "2024-25"
            quarter: Quarter (Q1, Q2, Q3, Q4)
            business_id: Business ID
            
        Returns:
            Download content and metadata
        """
        try:
            # Get return data
            return_data = self.tds_return_repo.get_return_by_quarter(
                financial_year, quarter, business_id
            )
            
            if not return_data:
                raise ValueError(f"No TDS return found for {quarter} in {financial_year}")
            
            # Generate receipt content
            content = f"""TDS RETURN RECEIPT
===================

Quarter: {quarter}
Financial Year: {financial_year}
Receipt Number: {return_data['receipt_number'] or 'N/A'}
Return Type: {return_data['return_type']}
Filing Date: {return_data['filing_date'] or 'N/A'}
Total TDS Amount: ₹{return_data['total_tds_amount']:,.2f}
Total Deductees: {return_data['total_deductees']}
Status: {'Filed' if return_data['is_filed'] else 'Not Filed'}

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            return {
                "content": content,
                "filename": f"TDS_{quarter}_{financial_year}.txt",
                "quarter": quarter,
                "financial_year": financial_year,
                "receipt_number": return_data['receipt_number']
            }
            
        except Exception as e:
            raise Exception(f"Failed to generate download for quarter {quarter}: {str(e)}")