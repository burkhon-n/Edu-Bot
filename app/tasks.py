"""
Background task queue for handling async jobs like quiz generation.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from pathlib import Path
from app.database import SessionLocal
from app import crud
from app.utils import extract_text_from_file, truncate_text_smart
from app.ai_provider import get_ai_provider
from app.config import config


# Thread pool for background tasks
executor = ThreadPoolExecutor(max_workers=3)


def notify_quiz_ready(db, material, quiz, difficulty):
    """Notify students that a new quiz is ready."""
    try:
        from app.bot import bot
        
        # Get course info
        course = material.course
        if not course:
            return
        
        # Get all verified students for this course
        students = db.query(crud.models.Student).filter(
            crud.models.Student.db_university_id == course.university_id,
            crud.models.Student.db_major_id == course.major_id,
            crud.models.Student.year == course.year,
            crud.models.Student.verified == True,
            crud.models.Student.telegram_id.isnot(None)
        ).all()
        
        # Prepare notification message
        difficulty_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(difficulty.lower(), "🧠")
        message = (
            f"🎉 New Quiz Available!\n\n"
            f"📚 Course: {course.name}\n"
            f"📅 Week: {material.week}\n"
            f"{difficulty_emoji} Difficulty: {difficulty.title()}\n"
            f"📝 Material: {material.filename}\n\n"
            f"Ready to test your knowledge? Use /start to take the quiz!"
        )
        
        # Send to each student
        notified_count = 0
        for student in students:
            try:
                bot.send_message(student.telegram_id, message)
                notified_count += 1
            except Exception as e:
                print(f"Failed to notify student {student.id}: {e}")
        
        print(f"📢 Notified {notified_count} student(s) about new quiz for {course.name}")
        
    except Exception as e:
        print(f"Error in notify_quiz_ready: {e}")
        # Don't raise - notification failure shouldn't stop quiz generation


def notify_quiz_failed(db, material_id: int, error_msg: str):
    """Notify professor that quiz generation failed."""
    try:
        from app.bot import bot
        
        # Get material and professor
        material = crud.get_material_by_id(db, material_id)
        if not material:
            print(f"⚠️ Cannot notify - material {material_id} not found")
            return
        
        professor = db.query(crud.models.Professor).filter(
            crud.models.Professor.id == material.uploader_id
        ).first()
        
        if not professor:
            print(f"⚠️ Cannot notify - professor not found for material {material_id}")
            return
            
        if not professor.telegram_id:
            print(f"⚠️ Cannot notify - professor {professor.id} has no telegram_id")
            return
        
        # Prepare error message
        course = material.course
        message = (
            f"❌ Quiz Generation Failed\n\n"
            f"📚 Course: {course.name}\n"
            f"📅 Week: {material.week}\n"
            f"📝 Material: {material.filename}\n\n"
            f"Error: {error_msg[:200]}\n\n"
            f"Please try uploading the material again or contact support."
        )
        
        bot.send_message(professor.telegram_id, message)
        print(f"📧 Notified professor {professor.id} (telegram: {professor.telegram_id}) about quiz generation failure")
        
    except Exception as e:
        print(f"❌ Error in notify_quiz_failed: {e}")
        import traceback
        traceback.print_exc()


def process_quiz_generation(job_id: int, course_id: int, week: str, student_id: int, difficulty: str, n_questions: int):
    """
    Background task to generate personalized quiz for a student based on ALL materials in a week.
    
    Args:
        job_id: Background job ID
        course_id: Course ID
        week: Week number
        student_id: Student ID (for personalization)
        difficulty: Quiz difficulty level
        n_questions: Number of questions to generate
    """
    db = SessionLocal()
    
    try:
        # Update job status
        crud.update_job_status(db, job_id, 'running')
        
        # Get all materials for this course/week
        materials = crud.get_materials_by_course(db, course_id, week=week)
        if not materials:
            raise ValueError(f"No materials found for course {course_id}, week {week}")
        
        # Extract and combine text from ALL materials
        combined_text = ""
        material_count = 0
        
        for material in materials:
            try:
                filepath = Path(material.filepath)
                if not filepath.is_absolute():
                    filepath = config.STORAGE_ROOT / filepath
                
                text = extract_text_from_file(filepath)
                if text and len(text.strip()) >= 100:
                    combined_text += f"\n\n=== From {material.filename} ===\n\n{text}"
                    material_count += 1
            except Exception as e:
                print(f"⚠️ Failed to extract text from {material.filename}: {e}")
        
        if not combined_text or len(combined_text.strip()) < 100:
            raise ValueError("Could not extract sufficient text from materials")
        
        # Truncate text if too long
        combined_text = truncate_text_smart(combined_text, max_length=12000)
        
        # Generate quiz using AI with randomization seed based on student ID for uniqueness
        ai_provider = get_ai_provider()
        questions = ai_provider.generate_quiz(combined_text, n_questions, difficulty)
        
        if not questions:
            raise ValueError("AI provider returned no questions")
        
        # Save quiz to database (linked to student for personalization)
        quiz_data = json.dumps(questions)
        quiz = crud.create_quiz(
            db,
            course_id=course_id,
            difficulty=difficulty,
            data_json=quiz_data,
            material_id=None,  # Not linked to a single material
            student_id=student_id,  # Personal quiz for this student
            week=week
        )
        
        # Update job status
        result_data = json.dumps({
            "quiz_id": quiz.id, 
            "num_questions": len(questions),
            "material_count": material_count
        })
        crud.update_job_status(db, job_id, 'completed', result_data=result_data)
        
        print(f"✅ Quiz generated successfully for student {student_id}, course {course_id}, week {week} from {material_count} materials")
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Quiz generation failed: {error_msg}")
        crud.update_job_status(db, job_id, 'failed', error_message=error_msg)
    
    finally:
        db.close()


def submit_quiz_generation_task(course_id: int, week: str, student_id: int,
                                professor_id: Optional[int] = None,
                                difficulty: str = "medium", 
                                n_questions: Optional[int] = None) -> int:
    """
    Submit quiz generation task to background queue for a specific student.
    
    Args:
        course_id: Course ID
        week: Week number
        student_id: Student ID requesting the quiz
        professor_id: Professor ID (optional, for tracking)
        difficulty: Quiz difficulty
        n_questions: Number of questions (default from config)
        
    Returns:
        Job ID
    """
    db = SessionLocal()
    
    try:
        if n_questions is None:
            n_questions = config.QUIZ_QUESTIONS_DEFAULT
        
        # Create job record
        job = crud.create_background_job(
            db,
            job_type='quiz_generation',
            course_id=course_id,
            student_id=student_id,
            professor_id=professor_id
        )
        
        # Submit to executor
        executor.submit(process_quiz_generation, job.id, course_id, week, student_id, difficulty, n_questions)
        
        print(f"📝 Submitted quiz generation job {job.id} for student {student_id}, course {course_id}, week {week}")
        return job.id
        
    finally:
        db.close()


def get_job_status(job_id: int) -> Optional[dict]:
    """
    Get status of background job.
    
    Args:
        job_id: Job ID
        
    Returns:
        Job status dict or None
    """
    db = SessionLocal()
    
    try:
        job = crud.get_job_by_id(db, job_id)
        if not job:
            return None
        
        result = {
            "id": job.id,
            "type": job.job_type,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
        }
        
        if job.error_message:
            result["error"] = job.error_message
        
        if job.result_data:
            try:
                result["result"] = json.loads(job.result_data)
            except:
                result["result"] = job.result_data
        
        if job.completed_at:
            result["completed_at"] = job.completed_at.isoformat()
        
        return result
        
    finally:
        db.close()
