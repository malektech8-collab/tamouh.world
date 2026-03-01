from sqlalchemy import Column, String, JSON, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import datetime
import uuid

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True)
    stripe_customer_id = Column(String, nullable=True)
    plan = Column(String, default="free")
    credits = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    jobs = relationship("ResumeJob", back_populates="user")

class ResumeJob(Base):
    __tablename__ = "resume_jobs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    status = Column(String) # 'queued', 'processing', 'completed', 'failed'
    
    # AI Results
    input_text = Column(String, nullable=True)
    job_description = Column(String, nullable=True)
    resume_json = Column(JSON, nullable=True)
    audit_json = Column(JSON, nullable=True)
    
    # Generated Assets
    pdf_url = Column(String, nullable=True)
    docx_url = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="jobs")
