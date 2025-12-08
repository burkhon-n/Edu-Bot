"""
FastAPI application with REST endpoints for CourseMateBot.
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional, List
import os
import telebot

from app.database import get_db, init_db
from app import crud
from app.storage import get_storage_path, save_uploaded_file, get_file_path, file_exists
from app.tasks import submit_quiz_generation_task, get_job_status
from app.config import config

app = FastAPI(title="CourseMateBot API", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
    config.STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    
    # Setup webhook if configured
    if config.WEBHOOK_URL:
        from app.bot import bot
        webhook_path = f"/webhook/{config.TELEGRAM_TOKEN}"
        webhook_url = f"{config.WEBHOOK_URL}{webhook_path}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook set: {webhook_url}")
    
    print("✅ FastAPI started")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "CourseMateBot API", "version": "1.0.0"}


@app.post("/upload-material/")
async def upload_material(
    university: str = Form(...),
    major: str = Form(...),
    course: str = Form(...),
    year: str = Form(...),
    week: str = Form(...),
    professor_code: str = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload course material.
    
    Professor authentication via professor_code.
    Creates course if doesn't exist.
    Triggers background quiz generation.
    """
    # Validate professor
    professor = crud.get_professor_by_code(db, professor_code)
    if not professor or not professor.active:
        raise HTTPException(status_code=401, detail="Invalid professor code")
    
    # Check rate limit
    if not crud.check_rate_limit(db, professor.id, 'upload', config.PROF_RATE_LIMIT_PER_DAY):
        raise HTTPException(
            status_code=429,
            detail=f"Upload limit reached ({config.PROF_RATE_LIMIT_PER_DAY} per day)"
        )
    
    # Get or create course
    course_obj = crud.get_or_create_course(db, university, major, year, course)
    
    # Read file content
    file_content = await file.read()
    
    # Generate storage path
    full_path, relative_path = get_storage_path(university, major, course, week, file.filename)
    
    # Save file
    if not save_uploaded_file(file_content, full_path):
        raise HTTPException(status_code=500, detail="Failed to save file")
    
    # Create material record
    material = crud.create_material(
        db,
        course_id=course_obj.id,
        uploader_id=professor.id,
        filename=file.filename,
        filepath=str(relative_path),
        week=week,
        description=description
    )
    
    # Increment rate limit
    crud.increment_rate_limit(db, professor.id, 'upload')
    
    # Submit quiz generation task
    job_id = submit_quiz_generation_task(material.id, professor.id, difficulty='medium')
    
    return {
        "material_id": material.id,
        "filename": material.filename,
        "course": course_obj.name,
        "week": week,
        "job_id": job_id,
        "message": "Material uploaded successfully. Quiz generation started."
    }


@app.get("/materials/{material_id}/download")
async def download_material(
    material_id: int,
    telegram_id: Optional[str] = None,
    professor_code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Download material file.
    
    Authorization: Student (verified) or Professor or Admin.
    """
    # Get material
    material = crud.get_material_by_id(db, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    # Check authorization
    authorized = False
    
    if professor_code:
        professor = crud.get_professor_by_code(db, professor_code)
        if professor:
            authorized = True
    
    elif telegram_id:
        # Check if student
        student = crud.get_student_by_telegram_id(db, telegram_id)
        if student and student.verified:
            # Check if student's major/year matches course
            course = crud.get_course_by_id(db, material.course_id)
            if course and course.major == student.major and course.year == student.year:
                authorized = True
        
        # Check if admin
        if not authorized:
            admin = crud.get_admin_by_telegram_id(db, telegram_id)
            if admin:
                authorized = True
    
    if not authorized:
        raise HTTPException(status_code=403, detail="Not authorized to download this material")
    
    # Get file path
    filepath = get_file_path(material.filepath)
    
    if not file_exists(material.filepath):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Stream file
    def iterfile():
        with open(filepath, "rb") as f:
            yield from f
    
    return StreamingResponse(
        iterfile(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={material.filename}"}
    )


@app.get("/courses/")
async def list_courses(
    university: Optional[str] = None,
    major: Optional[str] = None,
    year: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List courses with optional filters."""
    courses = crud.get_courses_by_filters(db, university, major, year)
    
    return {
        "count": len(courses),
        "courses": [
            {
                "id": c.id,
                "university": c.university,
                "major": c.major,
                "year": c.year,
                "name": c.name
            }
            for c in courses
        ]
    }


@app.post("/admin/create-professor")
async def create_professor(
    admin_code: str = Form(...),
    name: str = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Create new professor (admin only).
    
    Requires admin_code for authentication.
    """
    if admin_code != config.ADMIN_CODE:
        raise HTTPException(status_code=401, detail="Invalid admin code")
    
    # Check if code already exists
    existing = crud.get_professor_by_code(db, code)
    if existing:
        raise HTTPException(status_code=400, detail="Professor code already exists")
    
    professor = crud.create_professor(db, name, code)
    
    return {
        "id": professor.id,
        "name": professor.name,
        "code": professor.code,
        "message": "Professor created successfully"
    }


@app.get("/admin/stats")
async def get_stats(
    admin_code: str,
    db: Session = Depends(get_db)
):
    """Get system statistics (admin only)."""
    if admin_code != config.ADMIN_CODE:
        raise HTTPException(status_code=401, detail="Invalid admin code")
    
    stats = crud.get_upload_stats(db)
    
    # Get professor details
    professors = crud.get_all_professors(db)
    prof_stats = []
    for prof in professors:
        p_stats = crud.get_professor_stats(db, prof.id)
        prof_stats.append({
            "id": prof.id,
            "name": prof.name,
            "uploads": p_stats["total_uploads"],
            "linked": prof.telegram_id is not None
        })
    
    stats["professors"] = prof_stats
    
    return stats


@app.get("/jobs/{job_id}")
async def get_job_status_endpoint(job_id: int):
    """Get background job status."""
    status = get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/webhook/{token}")
async def webhook(token: str, request: Request):
    """Handle Telegram webhook updates."""
    if token != config.TELEGRAM_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    from app.bot import bot
    import traceback
    
    try:
        json_data = await request.json()
        
        # Debug: Log callback queries
        if 'callback_query' in json_data:
            callback_data = json_data['callback_query'].get('data', '')
            print(f"📞 Callback received: {callback_data}")
        
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
    except Exception as e:
        print(f"❌ Error processing update: {e}")
        traceback.print_exc()
        # Still return OK to Telegram so it doesn't retry
    
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
