from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    TIMESTAMP
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base
import enum



class UnitTypeEnum(enum.Enum):
    PAID_DAYS = "Paid Days"
    FIXED = "Fixed"
    MONTHLY = "Monthly"

class SalaryComponent(Base):
    __tablename__ = "salary_components"

    id = Column(Integer, primary_key=True, index=True)

    # -------------------------------
    # Multi-tenant (Business)
    # -------------------------------
    business_id = Column(
        Integer,
        ForeignKey("businesses.id"),
        nullable=False,
        index=True
    )

    # -------------------------------
    # Salary Component (UI fields)
    # -------------------------------
    name = Column(String(255), nullable=False)      # Basic Salary
    alias = Column(String(50), nullable=False)      # Basic / HRA
    component_type = Column(String(50), nullable=False)  
    # Fixed / Variable

    unit_type = Column(String(50), nullable=False)
    # Paid Days / Fixed / Monthly

    # -------------------------------
    # Salary Component Toggles
    # -------------------------------
    is_active = Column(Boolean, default=True)

    exclude_holidays = Column(Boolean, default=False)
    exclude_weekoffs = Column(Boolean, default=False)

    exclude_from_gross = Column(Boolean, default=False)
    hide_in_ctc = Column(Boolean, default=False)
    not_payable = Column(Boolean, default=False)

    # -------------------------------
    # 🔹 LWF Screen Checkbox
    # -------------------------------
    is_lwf_applicable = Column(Boolean, default=False)

    # -------------------------------
    # 🔹 Tax Category Fields (Income Tax)
    # -------------------------------
    basic = Column(Boolean, default=False)
    hra = Column(Boolean, default=False)
    profit = Column(Boolean, default=False)
    perk = Column(Boolean, default=False)
    ent_all = Column(Boolean, default=False)
    exempt = Column(Boolean, default=False)
    exempt_new = Column(Boolean, default=False)

    # -------------------------------
    # Audit
    # -------------------------------
    created_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    business = relationship(
        "Business",
        back_populates="salary_components"
    )

    # Properties for schema compatibility
    @property
    def active(self):
        """Alias for is_active to match schema"""
        return self.is_active
    
    @property
    def hide_in_ctc_reports(self):
        """Alias for hide_in_ctc to match schema"""
        return self.hide_in_ctc
