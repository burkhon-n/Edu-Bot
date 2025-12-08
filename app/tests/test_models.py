"""Tests for database models."""

import pytest
from datetime import datetime
from app.database import Base, engine, SessionLocal
from app.models import Admin, Professor, Student, Course, Material, Quiz


@pytest.fixture
def db():
    """Create test database session."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_create_admin(db):
    """Test admin creation."""
    admin = Admin(telegram_id="123456789")
    db.add(admin)
    db.commit()
    
    assert admin.id is not None
    assert admin.telegram_id == "123456789"
    assert isinstance(admin.created_at, datetime)


def test_create_professor(db):
    """Test professor creation."""
    prof = Professor(name="Dr. Smith", code="PROF001", active=True)
    db.add(prof)
    db.commit()
    
    assert prof.id is not None
    assert prof.name == "Dr. Smith"
    assert prof.code == "PROF001"
    assert prof.active is True


def test_create_student(db):
    """Test student creation."""
    student = Student(
        university_id="U123456",
        major="Computer Science",
        year="1",
        verified=False
    )
    db.add(student)
    db.commit()
    
    assert student.id is not None
    assert student.university_id == "U123456"
    assert student.verified is False


def test_create_course(db):
    """Test course creation."""
    course = Course(
        university="Tech University",
        major="Computer Science",
        year="1",
        name="Introduction to Programming"
    )
    db.add(course)
    db.commit()
    
    assert course.id is not None
    assert course.name == "Introduction to Programming"


def test_create_material_with_relationships(db):
    """Test material creation with relationships."""
    # Create professor
    prof = Professor(name="Dr. Smith", code="PROF001", active=True)
    db.add(prof)
    db.commit()
    
    # Create course
    course = Course(
        university="Tech University",
        major="Computer Science",
        year="1",
        name="Intro to Programming"
    )
    db.add(course)
    db.commit()
    
    # Create material
    material = Material(
        course_id=course.id,
        uploader_id=prof.id,
        filename="lecture1.pdf",
        filepath="storage/cs/week1/lecture1.pdf",
        week="1",
        description="First lecture"
    )
    db.add(material)
    db.commit()
    
    assert material.id is not None
    assert material.course.name == "Intro to Programming"
    assert material.uploader.name == "Dr. Smith"


def test_course_unique_constraint(db):
    """Test course unique constraint."""
    course1 = Course(
        university="Tech U",
        major="CS",
        year="1",
        name="Intro"
    )
    db.add(course1)
    db.commit()
    
    # Try to create duplicate
    course2 = Course(
        university="Tech U",
        major="CS",
        year="1",
        name="Intro"
    )
    db.add(course2)
    
    with pytest.raises(Exception):
        db.commit()
