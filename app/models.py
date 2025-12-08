"""
SQLAlchemy database models for CourseMateBot.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, 
    Text, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from app.database import Base


class Admin(Base):
    """Admin user model."""
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class University(Base):
    """University model - only created by admins."""
    __tablename__ = "universities"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    majors = relationship("Major", back_populates="university")
    courses = relationship("Course", back_populates="university")


class Major(Base):
    """Major/Department model - only created by admins."""
    __tablename__ = "majors"
    
    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    university = relationship("University", back_populates="majors")
    courses = relationship("Course", back_populates="major")
    
    __table_args__ = (
        UniqueConstraint('university_id', 'name', name='uq_major_per_university'),
    )


class Professor(Base):
    """Professor model with authentication code."""
    __tablename__ = "professors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    telegram_id = Column(String, unique=True, nullable=True, index=True)
    code = Column(String, unique=True, nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    course = relationship("Course", back_populates="professors")
    materials = relationship("Material", back_populates="uploader")
    rate_limits = relationship("RateLimit", back_populates="professor")


class Student(Base):
    """Student model with verification status."""
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, nullable=True, index=True)
    university_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    db_university_id = Column(Integer, ForeignKey("universities.id"), nullable=False, index=True)
    db_major_id = Column(Integer, ForeignKey("majors.id"), nullable=False, index=True)
    year = Column(String, nullable=False)
    verified = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)
    
    # Relationships
    university = relationship("University")
    major = relationship("Major")
    quizzes = relationship("Quiz", back_populates="student", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_student_verification', 'university_id', 'verified'),
    )


class Course(Base):
    """Course model."""
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False, index=True)
    major_id = Column(Integer, ForeignKey("majors.id"), nullable=False, index=True)
    year = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    
    # Relationships
    university = relationship("University", back_populates="courses")
    major = relationship("Major", back_populates="courses")
    professors = relationship("Professor", back_populates="course")
    materials = relationship("Material", back_populates="course")
    quizzes = relationship("Quiz", back_populates="course")
    
    __table_args__ = (
        UniqueConstraint('university_id', 'major_id', 'year', 'name', name='uq_course'),
    )


class Material(Base):
    """Course material model."""
    __tablename__ = "materials"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    uploader_id = Column(Integer, ForeignKey("professors.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    week = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    course = relationship("Course", back_populates="materials")
    uploader = relationship("Professor", back_populates="materials")
    quizzes = relationship("Quiz", back_populates="material")


class Quiz(Base):
    """Quiz model with JSON data storage - personalized per student."""
    __tablename__ = "quizzes"
    
    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=True, index=True)  # Legacy, now optional
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True, index=True)  # New: quiz is for specific student
    week = Column(String, nullable=True, index=True)  # New: week number
    difficulty = Column(String, nullable=False)
    data_json = Column(Text, nullable=False)  # JSON string of quiz questions
    generated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    material = relationship("Material", back_populates="quizzes")
    course = relationship("Course", back_populates="quizzes")
    student = relationship("Student", back_populates="quizzes")


class RateLimit(Base):
    """Rate limiting tracker for professors."""
    __tablename__ = "rate_limits"
    
    id = Column(Integer, primary_key=True, index=True)
    professor_id = Column(Integer, ForeignKey("professors.id"), nullable=False, index=True)
    action_type = Column(String, nullable=False)  # 'upload' or 'quiz_generation'
    count = Column(Integer, default=0)
    date = Column(String, nullable=False)  # YYYY-MM-DD format
    
    # Relationships
    professor = relationship("Professor", back_populates="rate_limits")
    
    __table_args__ = (
        UniqueConstraint('professor_id', 'action_type', 'date', name='uq_rate_limit'),
    )


class BackgroundJob(Base):
    """Background job tracking."""
    __tablename__ = "background_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String, nullable=False)  # 'quiz_generation', 'text_extraction'
    status = Column(String, default='pending')  # pending, running, completed, failed
    material_id = Column(Integer, nullable=True)  # Legacy
    course_id = Column(Integer, nullable=True, index=True)  # New: for quiz generation
    student_id = Column(Integer, nullable=True, index=True)  # New: for quiz generation
    professor_id = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    result_data = Column(Text, nullable=True)  # JSON result
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
