from datetime import datetime
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database.connection import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    role = Column(String(50), default="STUDENT", nullable=False)  # STUDENT, CHIEF
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username='{self.username}', role='{self.role}')>"


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    semester = Column(String(50), nullable=False)  # e.g., 'CSE 2-2', 'CSE 3-1'

    resources = relationship("Resource", back_populates="subject", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Subject(id={self.id}, name='{self.name}', semester='{self.semester}')>"


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    semester = Column(String(50), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    resource_type = Column(String(50), nullable=False)  # NOTES, PYQ, ASSIGNMENT
    file_id = Column(String(512), nullable=False)
    file_name = Column(String(255), nullable=True)
    uploaded_by = Column(BigInteger, nullable=False)  # Telegram user ID
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING, APPROVED, REJECTED
    download_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject", back_populates="resources")

    def __repr__(self):
        return f"<Resource(id={self.id}, title='{self.title}', semester='{self.semester}', status='{self.status}')>"
