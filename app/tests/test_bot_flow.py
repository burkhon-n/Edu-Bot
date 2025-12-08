"""Tests for bot flow logic (mocked, non-network)."""

import pytest
from unittest.mock import Mock, patch
from app import crud
from app.database import Base, engine, SessionLocal


@pytest.fixture
def db():
    """Create test database session."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_student_verification_flow(db):
    """Test student verification state transitions."""
    # Create unverified student
    student = crud.create_student(
        db,
        university_id="U123456",
        major="Computer Science",
        year="1",
        name="John Doe",
        verified=False
    )
    
    assert student.verified is False
    assert student.telegram_id is None
    
    # Simulate approval
    verified_student = crud.verify_student(db, student.id, "telegram123")
    
    assert verified_student.verified is True
    assert verified_student.telegram_id == "telegram123"
    assert verified_student.verified_at is not None


def test_professor_authentication_flow(db):
    """Test professor authentication logic."""
    # Create professor
    prof = crud.create_professor(db, "Dr. Smith", "PROF_CODE_123")
    
    # Simulate code validation
    retrieved = crud.get_professor_by_code(db, "PROF_CODE_123")
    assert retrieved is not None
    assert retrieved.id == prof.id
    
    # Invalid code
    invalid = crud.get_professor_by_code(db, "INVALID_CODE")
    assert invalid is None
    
    # Link telegram ID
    linked = crud.link_professor_telegram(db, prof.id, "telegram456")
    assert linked.telegram_id == "telegram456"


def test_course_material_access_logic(db):
    """Test material access authorization logic."""
    # Setup
    prof = crud.create_professor(db, "Dr. Smith", "PROF001")
    student = crud.create_student(
        db, "U123456", "Computer Science", "1",
        telegram_id="student_tg", verified=True
    )
    course = crud.get_or_create_course(
        db, "Tech U", "Computer Science", "1", "Intro to CS"
    )
    material = crud.create_material(
        db, course.id, prof.id, "lecture.pdf", "path/lecture.pdf", "1"
    )
    
    # Test authorization logic
    # Student with matching major/year should have access
    retrieved_student = crud.get_student_by_telegram_id(db, "student_tg")
    assert retrieved_student.verified is True
    assert retrieved_student.major == course.major
    assert retrieved_student.year == course.year
    
    # Different major/year should not have access
    other_student = crud.create_student(
        db, "U789012", "Mathematics", "2",
        telegram_id="other_tg", verified=True
    )
    assert other_student.major != course.major


def test_rate_limit_logic(db):
    """Test rate limiting logic."""
    prof = crud.create_professor(db, "Dr. Smith", "PROF001")
    
    # Should allow initially
    assert crud.check_rate_limit(db, prof.id, "quiz_generation", 5) is True
    
    # Increment to limit
    for i in range(5):
        count = crud.increment_rate_limit(db, prof.id, "quiz_generation")
        assert count == i + 1
    
    # Should deny now
    assert crud.check_rate_limit(db, prof.id, "quiz_generation", 5) is False
    
    # Should still allow different action type
    assert crud.check_rate_limit(db, prof.id, "upload", 5) is True


@patch('app.ai_provider.OpenAI')
def test_quiz_generation_mock(mock_openai, db):
    """Test quiz generation with mocked AI provider."""
    from app.ai_provider import OpenAIProvider
    
    # Mock response
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '''[
        {
            "type": "mcq",
            "question": "What is 2+2?",
            "choices": ["3", "4", "5", "6"],
            "answer": 1,
            "explanation": "2+2 equals 4"
        }
    ]'''
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client
    
    provider = OpenAIProvider(api_key="test_key")
    questions = provider.generate_quiz("Sample text", 1, "easy")
    
    assert len(questions) == 1
    assert questions[0]["type"] == "mcq"
    assert questions[0]["question"] == "What is 2+2?"
    assert len(questions[0]["choices"]) == 4
    assert questions[0]["answer"] == 1


def test_background_job_status_tracking(db):
    """Test background job status tracking."""
    prof = crud.create_professor(db, "Dr. Smith", "PROF001")
    
    # Create job
    job = crud.create_background_job(
        db, job_type="quiz_generation", professor_id=prof.id
    )
    
    assert job.status == "pending"
    
    # Update to running
    crud.update_job_status(db, job.id, "running")
    updated = crud.get_job_by_id(db, job.id)
    assert updated.status == "running"
    
    # Update to completed
    crud.update_job_status(db, job.id, "completed", result_data='{"quiz_id": 1}')
    completed = crud.get_job_by_id(db, job.id)
    assert completed.status == "completed"
    assert completed.result_data == '{"quiz_id": 1}'
    assert completed.completed_at is not None
