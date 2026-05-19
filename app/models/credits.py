"""
Credit Service
Business logic for credit management
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Numeric,
    Text,
    ForeignKey,
    Index,
    text,
)
from sqlalchemy.orm import relationship
from .base import Base


class UserCredits(Base):
    __tablename__ = "user_credits"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    business_id = Column(Integer, nullable=False, index=True)
    credits = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    created_by = Column(Integer, nullable=True)

    transactions = relationship("CreditTransaction", back_populates="user_credits")

    __table_args__ = (
        Index("ix_user_credits_user_business", "user_id", "business_id"),
    )


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_credits_id = Column(Integer, ForeignKey("user_credits.id"), nullable=False, index=True)
    transaction_type = Column(String(50), nullable=False)
    amount = Column(Numeric, nullable=False)
    balance_before = Column(Numeric, nullable=False)
    balance_after = Column(Numeric, nullable=False)
    description = Column(Text, nullable=True)
    reference_id = Column(String(255), nullable=True)
    reference_type = Column(String(100), nullable=True)
    payment_method = Column(String(100), nullable=True)
    payment_reference = Column(String(255), nullable=True)
    payment_amount = Column(Numeric, nullable=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    user_credits = relationship("UserCredits", back_populates="transactions")


class CreditPricing(Base):
    __tablename__ = "credit_pricing"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    business_id = Column(Integer, nullable=False, index=True)
    service_name = Column(String(100), nullable=False)
    service_display_name = Column(String(255), nullable=True)
    credits_required = Column(Integer, nullable=False, default=0)
    is_free = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("ix_credit_pricing_business_service", "business_id", "service_name"),
    )