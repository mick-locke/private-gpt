from private_gpt.users.db.base_class import Base
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime


class Document(Base):
    """Models a document table"""
    __tablename__ = "document"  
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(225), nullable=False, unique=True)
    uploaded_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    uploaded_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    uploaded_by_user = relationship(
        "User", back_populates="uploaded_documents")
    
    department_id = Column(Integer, ForeignKey(
        "departments.id"), nullable=False)
    uploaded_by_user = relationship(
        "User", back_populates="uploaded_documents")
    department = relationship("Department", back_populates="documents")