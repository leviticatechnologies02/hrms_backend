"""
Master Policy model (global master setup policies)
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base


class MasterPolicy(Base):
    __tablename__ = "master_policies"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    type = Column(String(100))
    is_mandatory = Column(Boolean, default=False)
    requires_acknowledgment = Column(Boolean, default=False)
    file_path = Column(String(500))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationship to form-policy mappings
    # Use simple class name string so SQLAlchemy resolves it after all models are imported.
    form_policy_mappings = relationship("FormPolicyMapping", back_populates="policy", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "is_mandatory": self.is_mandatory,
            "requires_acknowledgment": self.requires_acknowledgment,
            "file_path": self.file_path,
            "created_at": self.created_at
        }


class FormPolicyMapping(Base):
    __tablename__ = "form_policy_mapping"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("onboarding_forms.id"), nullable=False, index=True)
    policy_id = Column(Integer, ForeignKey("master_policies.id"), nullable=False, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    # Refer to related models by class name strings to avoid import-order issues.
    form = relationship("OnboardingForm", back_populates="form_policy_mappings")
    policy = relationship("MasterPolicy", back_populates="form_policy_mappings")

