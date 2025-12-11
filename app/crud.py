"""
CRUD operations for database models.
"""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app import models


# Admin operations
def get_admin_by_telegram_id(db: Session, telegram_id: str) -> Optional[models.Admin]:
    """Get admin by Telegram ID."""
    return db.query(models.Admin).filter(models.Admin.telegram_id == telegram_id).first()


def create_admin(db: Session, telegram_id: str) -> models.Admin:
    """Create new admin."""
    admin = models.Admin(telegram_id=telegram_id)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


# University operations
def get_all_universities(db: Session) -> List[models.University]:
    """Get all universities."""
    return db.query(models.University).order_by(models.University.name).all()


def get_university_by_id(db: Session, university_id: int) -> Optional[models.University]:
    """Get university by ID."""
    return db.query(models.University).filter(models.University.id == university_id).first()


def get_university_by_name(db: Session, name: str) -> Optional[models.University]:
    """Get university by name."""
    return db.query(models.University).filter(models.University.name == name).first()


def create_university(db: Session, name: str) -> models.University:
    """Create new university."""
    university = models.University(name=name)
    db.add(university)
    db.commit()
    db.refresh(university)
    return university


def update_university(db: Session, university_id: int, name: str) -> models.University:
    """Update university name."""
    university = get_university_by_id(db, university_id)
    if university:
        university.name = name
        db.commit()
        db.refresh(university)
    return university


def delete_university(db: Session, university_id: int) -> bool:
    """Delete university and all related data."""
    university = get_university_by_id(db, university_id)
    if university:
        db.delete(university)
        db.commit()
        return True
    return False


# Major operations
def get_majors_by_university(db: Session, university_id: int) -> List[models.Major]:
    """Get all majors for a university."""
    return db.query(models.Major).filter(
        models.Major.university_id == university_id
    ).order_by(models.Major.name).all()


def get_major_by_id(db: Session, major_id: int) -> Optional[models.Major]:
    """Get major by ID."""
    return db.query(models.Major).filter(models.Major.id == major_id).first()


def get_major_by_name(db: Session, university_id: int, name: str) -> Optional[models.Major]:
    """Get major by name within a university."""
    return db.query(models.Major).filter(
        and_(
            models.Major.university_id == university_id,
            models.Major.name == name
        )
    ).first()


def create_major(db: Session, university_id: int, name: str) -> models.Major:
    """Create new major."""
    major = models.Major(university_id=university_id, name=name)
    db.add(major)
    db.commit()
    db.refresh(major)
    return major


def update_major(db: Session, major_id: int, name: str) -> models.Major:
    """Update major name."""
    major = get_major_by_id(db, major_id)
    if major:
        major.name = name
        db.commit()
        db.refresh(major)
    return major


def delete_major(db: Session, major_id: int) -> bool:
    """Delete major and all related data."""
    major = get_major_by_id(db, major_id)
    if major:
        db.delete(major)
        db.commit()
        return True
    return False


# Professor operations
def get_professor_by_code(db: Session, code: str) -> Optional[models.Professor]:
    """Get professor by authentication code."""
    return db.query(models.Professor).filter(models.Professor.code == code).first()


def get_professor_by_telegram_id(db: Session, telegram_id: str) -> Optional[models.Professor]:
    """Get professor by Telegram ID."""
    return db.query(models.Professor).filter(models.Professor.telegram_id == telegram_id).first()


def create_professor(db: Session, name: str, code: str, course_id: Optional[int] = None) -> models.Professor:
    """Create new professor."""
    professor = models.Professor(name=name, code=code, course_id=course_id, active=True)
    db.add(professor)
    db.commit()
    db.refresh(professor)
    return professor


def link_professor_telegram(db: Session, professor_id: int, telegram_id: str) -> models.Professor:
    """Link Telegram ID to professor."""
    professor = db.query(models.Professor).filter(models.Professor.id == professor_id).first()
    if professor:
        professor.telegram_id = telegram_id
        db.commit()
        db.refresh(professor)
    return professor


def update_professor_course(db: Session, professor_id: int, course_id: int) -> models.Professor:
    """Update professor's assigned course."""
    professor = db.query(models.Professor).filter(models.Professor.id == professor_id).first()
    if professor:
        professor.course_id = course_id
        db.commit()
        db.refresh(professor)
    return professor


def get_all_professors(db: Session) -> List[models.Professor]:
    """Get all professors."""
    return db.query(models.Professor).all()


def get_professor_by_id(db: Session, professor_id: int) -> Optional[models.Professor]:
    """Get professor by ID."""
    return db.query(models.Professor).filter(models.Professor.id == professor_id).first()


def update_professor(db: Session, professor_id: int, name: str = None, code: str = None, active: bool = None) -> Optional[models.Professor]:
    """Update professor details."""
    professor = db.query(models.Professor).filter(models.Professor.id == professor_id).first()
    if not professor:
        return None
    
    if name is not None:
        professor.name = name
    if code is not None:
        professor.code = code
    if active is not None:
        professor.active = active
    
    db.commit()
    db.refresh(professor)
    return professor


def delete_professor(db: Session, professor_id: int) -> bool:
    """Delete professor."""
    professor = db.query(models.Professor).filter(models.Professor.id == professor_id).first()
    if not professor:
        return False
    
    db.delete(professor)
    db.commit()
    return True


# Student operations
def get_student_by_university_id(db: Session, university_id: str) -> Optional[models.Student]:
    """Get student by university ID."""
    return db.query(models.Student).filter(models.Student.university_id == university_id).first()


def get_student_by_telegram_id(db: Session, telegram_id: str) -> Optional[models.Student]:
    """Get student by Telegram ID."""
    return db.query(models.Student).filter(models.Student.telegram_id == telegram_id).first()


def create_student(db: Session, university_id: str, db_university_id: int, db_major_id: int, 
                   year: str, name: Optional[str] = None, telegram_id: Optional[str] = None,
                   verified: bool = False) -> models.Student:
    """Create new student."""
    student = models.Student(
        university_id=university_id,
        db_university_id=db_university_id,
        db_major_id=db_major_id,
        year=year,
        name=name,
        telegram_id=telegram_id,
        verified=verified
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def verify_student(db: Session, student_id: int, telegram_id: str) -> models.Student:
    """Verify student and link Telegram ID."""
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if student:
        student.verified = True
        student.telegram_id = telegram_id
        student.verified_at = datetime.utcnow()
        db.commit()
        db.refresh(student)
    return student


def get_pending_students(db: Session) -> List[models.Student]:
    """Get all pending (unverified) students."""
    return db.query(models.Student).filter(models.Student.verified == False).all()


def reject_student(db: Session, student_id: int):
    """Delete/reject pending student."""
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if student:
        db.delete(student)
        db.commit()


# Course operations
def create_course(db: Session, university_id: int, major_id: int, year: str, name: str) -> models.Course:
    """Create new course."""
    course = models.Course(
        university_id=university_id,
        major_id=major_id,
        year=year,
        name=name
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def get_or_create_course(db: Session, university_id: int, major_id: int, year: str, name: str) -> models.Course:
    """Get existing course or create new one."""
    course = db.query(models.Course).filter(
        and_(
            models.Course.university_id == university_id,
            models.Course.major_id == major_id,
            models.Course.year == year,
            models.Course.name == name
        )
    ).first()
    
    if not course:
        course = create_course(db, university_id, major_id, year, name)
    
    return course


def update_course(db: Session, course_id: int, name: str = None, year: str = None) -> models.Course:
    """Update course details."""
    course = get_course_by_id(db, course_id)
    if course:
        if name:
            course.name = name
        if year:
            course.year = year
        db.commit()
        db.refresh(course)
    return course


def delete_course(db: Session, course_id: int) -> bool:
    """Delete course and related data safely.
    - Null out professor.course_id references
    - Delete quizzes for the course
    - Delete materials (and their files)
    - Finally delete the course
    """
    course = get_course_by_id(db, course_id)
    if not course:
        return False
    
    # Unassign professors
    professors = db.query(models.Professor).filter(models.Professor.course_id == course_id).all()
    for prof in professors:
        prof.course_id = None
    
    # Delete quizzes for this course
    db.query(models.Quiz).filter(models.Quiz.course_id == course_id).delete()
    
    # Delete materials (also removes files)
    materials = get_materials_by_course(db, course_id)
    for mat in materials:
        delete_material(db, mat.id)
    
    # Delete course
    db.delete(course)
    db.commit()
    return True


def get_courses_by_filters(db: Session, university_id: Optional[int] = None, 
                           major_id: Optional[int] = None, year: Optional[str] = None) -> List[models.Course]:
    """Get courses with optional filters."""
    query = db.query(models.Course)
    if university_id:
        query = query.filter(models.Course.university_id == university_id)
    if major_id:
        query = query.filter(models.Course.major_id == major_id)
    if year:
        query = query.filter(models.Course.year == year)
    return query.all()


def get_all_courses(db: Session) -> List[models.Course]:
    """Get all courses."""
    return db.query(models.Course).all()


def get_course_by_id(db: Session, course_id: int) -> Optional[models.Course]:
    """Get course by ID."""
    return db.query(models.Course).filter(models.Course.id == course_id).first()


# Material operations
def create_material(db: Session, course_id: int, uploader_id: int, filename: str,
                   filepath: str, week: str, description: Optional[str] = None) -> models.Material:
    """Create new material."""
    material = models.Material(
        course_id=course_id,
        uploader_id=uploader_id,
        filename=filename,
        filepath=filepath,
        week=week,
        description=description
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def get_materials_by_course(db: Session, course_id: int, week: Optional[str] = None) -> List[models.Material]:
    """Get materials for a course, optionally filtered by week."""
    query = db.query(models.Material).filter(models.Material.course_id == course_id)
    if week:
        query = query.filter(models.Material.week == week)
    return query.order_by(models.Material.uploaded_at.desc()).all()


def get_material_by_id(db: Session, material_id: int) -> Optional[models.Material]:
    """Get material by ID."""
    return db.query(models.Material).filter(models.Material.id == material_id).first()


def get_materials_by_professor(db: Session, professor_id: int, week: Optional[str] = None) -> List[models.Material]:
    """Get materials uploaded by a professor, optionally filtered by week."""
    query = db.query(models.Material).filter(models.Material.uploader_id == professor_id)
    if week:
        query = query.filter(models.Material.week == week)
    return query.order_by(models.Material.week, models.Material.uploaded_at.desc()).all()


def delete_material(db: Session, material_id: int) -> bool:
    """Delete material and associated file."""
    material = get_material_by_id(db, material_id)
    if material:
        # Delete associated quizzes and background jobs (cascade)
        db.delete(material)
        db.commit()
        
        # Delete physical file
        try:
            from app.storage import get_file_path
            filepath = get_file_path(material.filepath)
            if filepath.exists():
                filepath.unlink()
        except Exception as e:
            print(f"Failed to delete file: {e}")
        
        return True
    return False


# Quiz operations
def create_quiz(db: Session, course_id: int, difficulty: str, data_json: str,
               material_id: Optional[int] = None, student_id: Optional[int] = None, 
               week: Optional[str] = None) -> models.Quiz:
    """Create new personalized quiz for a student."""
    quiz = models.Quiz(
        course_id=course_id,
        material_id=material_id,
        student_id=student_id,
        week=week,
        difficulty=difficulty,
        data_json=data_json
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz


def get_quiz_by_material(db: Session, material_id: int, difficulty: str) -> Optional[models.Quiz]:
    """Get quiz for material with specific difficulty."""
    return db.query(models.Quiz).filter(
        and_(
            models.Quiz.material_id == material_id,
            models.Quiz.difficulty == difficulty
        )
    ).first()


def get_quiz_by_id(db: Session, quiz_id: int) -> Optional[models.Quiz]:
    """Get quiz by ID."""
    return db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()


# Rate limiting operations
def get_rate_limit(db: Session, professor_id: int, action_type: str, date_str: str) -> Optional[models.RateLimit]:
    """Get rate limit record for professor, action, and date."""
    return db.query(models.RateLimit).filter(
        and_(
            models.RateLimit.professor_id == professor_id,
            models.RateLimit.action_type == action_type,
            models.RateLimit.date == date_str
        )
    ).first()


def increment_rate_limit(db: Session, professor_id: int, action_type: str) -> int:
    """Increment rate limit counter and return new count."""
    today = date.today().isoformat()
    rate_limit = get_rate_limit(db, professor_id, action_type, today)
    
    if not rate_limit:
        rate_limit = models.RateLimit(
            professor_id=professor_id,
            action_type=action_type,
            date=today,
            count=1
        )
        db.add(rate_limit)
    else:
        rate_limit.count += 1
    
    db.commit()
    return rate_limit.count


def check_rate_limit(db: Session, professor_id: int, action_type: str, limit: int) -> bool:
    """Check if professor has exceeded rate limit for today."""
    today = date.today().isoformat()
    rate_limit = get_rate_limit(db, professor_id, action_type, today)
    
    if not rate_limit:
        return True  # No limit used, OK to proceed
    
    return rate_limit.count < limit


# Background job operations
def create_background_job(db: Session, job_type: str, material_id: Optional[int] = None,
                         course_id: Optional[int] = None, student_id: Optional[int] = None,
                         professor_id: Optional[int] = None) -> models.BackgroundJob:
    """Create new background job."""
    job = models.BackgroundJob(
        job_type=job_type,
        material_id=material_id,
        course_id=course_id,
        student_id=student_id,
        professor_id=professor_id,
        status='pending'
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job_status(db: Session, job_id: int, status: str, 
                     error_message: Optional[str] = None,
                     result_data: Optional[str] = None):
    """Update background job status."""
    job = db.query(models.BackgroundJob).filter(models.BackgroundJob.id == job_id).first()
    if job:
        job.status = status
        if error_message:
            job.error_message = error_message
        if result_data:
            job.result_data = result_data
        if status in ['completed', 'failed']:
            job.completed_at = datetime.utcnow()
        db.commit()


def get_job_by_id(db: Session, job_id: int) -> Optional[models.BackgroundJob]:
    """Get background job by ID."""
    return db.query(models.BackgroundJob).filter(models.BackgroundJob.id == job_id).first()


# Statistics operations
def get_upload_stats(db: Session) -> dict:
    """Get upload statistics."""
    total_uploads = db.query(models.Material).count()
    total_courses = db.query(models.Course).count()
    total_professors = db.query(models.Professor).count()
    total_students = db.query(models.Student).filter(models.Student.verified == True).count()
    total_quizzes = db.query(models.Quiz).count()
    total_universities = db.query(models.University).count()
    total_majors = db.query(models.Major).count()
    
    return {
        "total_uploads": total_uploads,
        "total_courses": total_courses,
        "total_professors": total_professors,
        "total_verified_students": total_students,
        "total_quizzes": total_quizzes,
        "total_universities": total_universities,
        "total_majors": total_majors
    }


def get_professor_stats(db: Session, professor_id: int) -> dict:
    """Get statistics for specific professor."""
    uploads = db.query(models.Material).filter(models.Material.uploader_id == professor_id).count()
    return {
        "total_uploads": uploads
    }


def get_distinct_universities(db: Session) -> List[str]:
    """Get list of distinct universities (deprecated - use get_all_universities)."""
    results = db.query(models.University.name).all()
    return [r[0] for r in results if r[0]]


def get_distinct_majors(db: Session, university_id: Optional[int] = None) -> List[str]:
    """Get list of distinct majors (deprecated - use get_majors_by_university)."""
    query = db.query(models.Major.name)
    if university_id:
        query = query.filter(models.Major.university_id == university_id)
    results = query.distinct().all()
    return [r[0] for r in results if r[0]]
