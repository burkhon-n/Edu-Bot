"""Tests for CRUD operations."""

import pytest
from app.database import Base, engine, SessionLocal
from app import crud, models


@pytest.fixture
def db():
    """Create test database session."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_create_and_get_professor(db):
    """Test professor creation and retrieval."""
    prof = crud.create_professor(db, "Dr. Smith", "PROF001")
    
    assert prof.id is not None
    assert prof.name == "Dr. Smith"
    
    # Retrieve by code
    retrieved = crud.get_professor_by_code(db, "PROF001")
    assert retrieved.id == prof.id


def test_create_and_verify_student(db):
    """Test student creation and verification."""
    student = crud.create_student(
        db,
        university_id="U123456",
        major="Computer Science",
        year="1",
        verified=False
    )
    
    assert student.verified is False
    
    # Verify student
    verified = crud.verify_student(db, student.id, "telegram123")
    
    assert verified.verified is True
    assert verified.telegram_id == "telegram123"
    assert verified.verified_at is not None


def test_get_or_create_course(db):
    """Test get or create course."""
    # Create first time
    course1 = crud.get_or_create_course(
        db, "Tech U", "CS", "1", "Intro to Programming"
    )
    
    assert course1.id is not None
    
    # Get existing
    course2 = crud.get_or_create_course(
        db, "Tech U", "CS", "1", "Intro to Programming"
    )
    
    assert course1.id == course2.id


def test_rate_limiting(db):
    """Test rate limiting functionality."""
    prof = crud.create_professor(db, "Dr. Smith", "PROF001")
    
    # Check initial limit
    assert crud.check_rate_limit(db, prof.id, "upload", 50) is True
    
    # Increment multiple times
    for _ in range(3):
        count = crud.increment_rate_limit(db, prof.id, "upload")
    
    assert count == 3
    
    # Check again
    assert crud.check_rate_limit(db, prof.id, "upload", 50) is True
    assert crud.check_rate_limit(db, prof.id, "upload", 3) is False


def test_get_materials_by_course(db):
    """Test getting materials by course."""
    prof = crud.create_professor(db, "Dr. Smith", "PROF001")
    course = crud.get_or_create_course(db, "Tech U", "CS", "1", "Intro")
    
    # Create materials
    for i in range(3):
        crud.create_material(
            db,
            course_id=course.id,
            uploader_id=prof.id,
            filename=f"lecture{i}.pdf",
            filepath=f"path/lecture{i}.pdf",
            week="1"
        )
    
    materials = crud.get_materials_by_course(db, course.id, week="1")
    assert len(materials) == 3


def test_pending_students(db):
    """Test pending students functionality."""
    # Create pending student
    student = crud.create_student(
        db,
        university_id="U123456",
        major="CS",
        year="1",
        verified=False
    )
    
    # Get pending students
    pending = crud.get_pending_students(db)
    assert len(pending) == 1
    assert pending[0].id == student.id
    
    # Verify student
    crud.verify_student(db, student.id, "telegram123")
    
    # Check pending again
    pending = crud.get_pending_students(db)
    assert len(pending) == 0


def test_upload_stats(db):
    """Test statistics retrieval."""
    # Create test data
    prof = crud.create_professor(db, "Dr. Smith", "PROF001")
    course = crud.get_or_create_course(db, "Tech U", "CS", "1", "Intro")
    crud.create_material(db, course.id, prof.id, "test.pdf", "path/test.pdf", "1")
    crud.create_student(db, "U123456", "CS", "1", verified=True)
    
    stats = crud.get_upload_stats(db)
    
    assert stats["total_uploads"] == 1
    assert stats["total_courses"] == 1
    assert stats["total_professors"] == 1
    assert stats["total_verified_students"] == 1
