"""
Telegram bot logic using pyTelegramBotAPI for CourseMateBot.
"""

import json
import telebot
from telebot import types
from app.config import config
from app.database import SessionLocal
from app import crud, models
from app.tasks import submit_quiz_generation_task, get_job_status
from app.storage import get_file_path

# Initialize bot
bot = telebot.TeleBot(config.TELEGRAM_TOKEN)

# User session storage (in-memory for MVP)
user_sessions = {}


def get_session(user_id: int) -> dict:
    """Get or create user session."""
    if user_id not in user_sessions:
        user_sessions[user_id] = {"state": "start", "data": {}}
    return user_sessions[user_id]


def clear_session(user_id: int):
    """Clear user session."""
    if user_id in user_sessions:
        user_sessions[user_id] = {"state": "start", "data": {}}


# Start and role selection
@bot.message_handler(commands=['start', 'menu'])
def handle_start(message):
    """Handle /start and /menu commands."""
    clear_session(message.from_user.id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('👨‍🎓 Student', '👨‍🏫 Professor')
    
    bot.send_message(
        message.chat.id,
        "🎓 Welcome to CourseMateBot!\n\nSelect your role:",
        reply_markup=markup
    )


@bot.message_handler(func=lambda m: m.text in ['👨‍🎓 Student', '👨‍🏫 Professor'])
def handle_role_selection(message):
    """Handle role selection."""
    session = get_session(message.from_user.id)
    telegram_id = str(message.from_user.id)
    
    if message.text == '👨‍🎓 Student':
        db = SessionLocal()
        try:
            # Check if student already exists and is verified
            student = crud.get_student_by_telegram_id(db, telegram_id)
            
            if student and student.verified:
                # Show student home menu directly
                session["data"]["student_id"] = student.id
                session["state"] = "student_verified"
                show_student_home(message.chat.id, student)
                return
            elif student and not student.verified:
                bot.send_message(
                    message.chat.id,
                    "⏳ Your verification is still pending. You'll be notified once approved.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
                return
        finally:
            db.close()
        
        # New student - start registration
        session["state"] = "student_university"
        
        db = SessionLocal()
        try:
            universities = crud.get_all_universities(db)
            
            if not universities:
                bot.send_message(
                    message.chat.id,
                    "❌ Sorry, no universities are available yet. Please contact the admin.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
                return
            
            markup = types.InlineKeyboardMarkup()
            for uni in universities:
                markup.row(types.InlineKeyboardButton(uni.name, callback_data=f"stu_uni_{uni.id}"))
            
            bot.send_message(
                message.chat.id,
                "🏛 Select your University:",
                reply_markup=markup
            )
        finally:
            db.close()
    
    elif message.text == '👨‍🏫 Professor':
        session["state"] = "professor_code"
        markup = types.ReplyKeyboardRemove()
        bot.send_message(
            message.chat.id,
            "🔑 Please enter your Professor Code:",
            reply_markup=markup
        )


def show_student_home(chat_id: int, student):
    """Show student home menu."""
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("📚 Browse Courses", callback_data="student_browse"))
    markup.row(types.InlineKeyboardButton("👤 My Profile", callback_data="student_profile"))
    markup.row(types.InlineKeyboardButton("🏠 Main Menu", callback_data="home"))
    
    bot.send_message(
        chat_id,
        f"👋 Welcome, {student.name}!\n\n"
        f"🏛 University: {student.university.name}\n"
        f"📖 Major: {student.major.name}\n"
        f"📅 Year: {student.year}\n\n"
        f"What would you like to do?",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == 'student_browse')
def handle_student_browse(call):
    """Handle student browse courses."""
    telegram_id = str(call.from_user.id)
    db = SessionLocal()
    
    try:
        student = crud.get_student_by_telegram_id(db, telegram_id)
        if student:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            show_year_selection(call.message.chat.id, student.major.name, student.db_university_id, student.db_major_id)
        bot.answer_callback_query(call.id)
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'student_profile')
def handle_student_profile(call):
    """Show student profile."""
    telegram_id = str(call.from_user.id)
    db = SessionLocal()
    
    try:
        student = crud.get_student_by_telegram_id(db, telegram_id)
        if student:
            text = f"👤 Your Profile\n\n"
            text += f"Name: {student.name}\n"
            text += f"🆔 ID: {student.university_id}\n"
            text += f"🏛 University: {student.university.name}\n"
            text += f"📖 Major: {student.major.name}\n"
            text += f"📅 Year: {student.year}\n"
            text += f"✅ Status: {'Verified' if student.verified else 'Pending'}\n"
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("✏️ Edit Name", callback_data="student_edit_name"))
            markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="student_back_home"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'student_back_home')
def handle_student_back_home(call):
    """Return to student home."""
    telegram_id = str(call.from_user.id)
    db = SessionLocal()
    
    try:
        student = crud.get_student_by_telegram_id(db, telegram_id)
        if student:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            show_student_home(call.message.chat.id, student)
        bot.answer_callback_query(call.id)
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'student_edit_name')
def handle_student_edit_name(call):
    """Handle edit name request."""
    session = get_session(call.from_user.id)
    session["state"] = "student_editing_name"
    
    bot.edit_message_text(
        "✏️ Enter your new name (First and Last name):",
        call.message.chat.id,
        call.message.message_id
    )
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "student_editing_name")
def handle_student_name_update(message):
    """Handle student name update."""
    telegram_id = str(message.from_user.id)
    name = message.text.strip()
    
    if len(name) < 3:
        bot.send_message(
            message.chat.id,
            "❌ Name too short. Please enter your full name (First and Last name):"
        )
        return
    
    db = SessionLocal()
    
    try:
        student = crud.get_student_by_telegram_id(db, telegram_id)
        if student:
            student.name = name
            db.commit()
            db.refresh(student)
            
            clear_session(message.from_user.id)
            
            bot.send_message(
                message.chat.id,
                f"✅ Your name has been updated to: {name}"
            )
            
            show_student_home(message.chat.id, student)
        else:
            bot.send_message(message.chat.id, "❌ Student not found. Please use /start")
    
    finally:
        db.close()


# Student registration flow
@bot.callback_query_handler(func=lambda call: call.data.startswith('stu_uni_'))
def handle_student_university(call):
    """Handle student university selection."""
    university_id = int(call.data.split('_')[2])
    db = SessionLocal()
    
    try:
        majors = crud.get_majors_by_university(db, university_id)
        
        if not majors:
            bot.answer_callback_query(call.id, "❌ No majors available for this university!")
            return
        
        session = get_session(call.from_user.id)
        session["data"]["university_id"] = university_id
        session["state"] = "student_major"
        
        markup = types.InlineKeyboardMarkup()
        for major in majors:
            markup.row(types.InlineKeyboardButton(major.name, callback_data=f"stu_maj_{major.id}"))
        
        bot.edit_message_text(
            "📚 Select your Major:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


# Student major handler
@bot.callback_query_handler(func=lambda call: call.data.startswith('stu_maj_'))
def handle_student_major(call):
    """Handle student major selection."""
    major_id = int(call.data.split('_')[2])
    
    session = get_session(call.from_user.id)
    session["data"]["major_id"] = major_id
    session["state"] = "student_year"
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("1", callback_data="stu_year_1"),
        types.InlineKeyboardButton("2", callback_data="stu_year_2"),
        types.InlineKeyboardButton("3", callback_data="stu_year_3"),
        types.InlineKeyboardButton("4", callback_data="stu_year_4")
    )
    
    bot.edit_message_text(
        "📅 Select your Year:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('stu_year_'))
def handle_student_year(call):
    """Handle student year selection."""
    year = call.data.split('_')[2]
    
    session = get_session(call.from_user.id)
    session["data"]["year"] = year
    session["state"] = "student_name"
    
    bot.edit_message_text(
        "👤 Please enter your full name (First and Last name):",
        call.message.chat.id,
        call.message.message_id
    )
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "student_name")
def handle_student_name(message):
    """Handle student name input."""
    session = get_session(message.from_user.id)
    name = message.text.strip()
    
    if len(name) < 3:
        bot.send_message(
            message.chat.id,
            "❌ Name too short. Please enter your full name (First and Last name):"
        )
        return
    
    session["data"]["student_name"] = name
    session["state"] = "student_university_id"
    
    bot.send_message(
        message.chat.id,
        "🆔 Please enter your University ID (e.g., U123456):"
    )


@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "student_university_id")
def handle_student_university_id(message):
    """Handle student university ID and verification."""
    session = get_session(message.from_user.id)
    university_id_str = message.text.strip().upper()
    db_university_id = session["data"].get("university_id")
    db_major_id = session["data"].get("major_id")
    year = session["data"].get("year", "1")
    telegram_id = str(message.from_user.id)
    
    if not db_university_id or not db_major_id:
        bot.send_message(
            message.chat.id,
            "❌ Session expired. Please start over by selecting /start",
            reply_markup=types.ReplyKeyboardRemove()
        )
        clear_session(message.from_user.id)
        return
    
    db = SessionLocal()
    
    try:
        # Check if student exists
        student = crud.get_student_by_university_id(db, university_id_str)
        
        if student and student.verified:
            # Link telegram ID if not already linked
            if not student.telegram_id:
                student = crud.verify_student(db, student.id, telegram_id)
            
            session["data"]["student_id"] = student.id
            session["state"] = "student_verified"
            
            show_student_home(message.chat.id, student)
        
        elif student and not student.verified:
            bot.send_message(
                message.chat.id,
                "⏳ Your verification is pending. You will be notified once approved.",
                reply_markup=types.ReplyKeyboardRemove()
            )
        
        else:
            # Create pending student
            name = session["data"].get("student_name") or message.from_user.first_name or "Student"
            
            student = crud.create_student(
                db,
                university_id=university_id_str,
                db_university_id=db_university_id,
                db_major_id=db_major_id,
                year=year,
                name=name,
                telegram_id=telegram_id,  # Store telegram_id so we can notify them
                verified=False
            )
            db.refresh(student)
            
            session["data"]["student_id"] = student.id
            
            # Get university and major names for display
            university = crud.get_university_by_id(db, db_university_id)
            major = crud.get_major_by_id(db, db_major_id)
            
            bot.send_message(
                message.chat.id,
                f"📝 Your registration has been submitted for approval.\n\n"
                f"🏛 University: {university.name}\n"
                f"📖 Major: {major.name}\n"
                f"📅 Year: {year}\n\n"
                "An admin or professor will review it shortly. You'll be notified once approved.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            
            # Notify admin/professors
            notify_pending_student(student, message.from_user)
    
    finally:
        db.close()


def notify_pending_student(student, user):
    """Notify only admin about pending student."""
    db = SessionLocal()
    
    try:
        message_text = (
            f"🔔 New student approval request:\n\n"
            f"Name: {student.name}\n"
            f"University ID: {student.university_id}\n"
            f"🏛 University: {student.university.name}\n"
            f"📖 Major: {student.major.name}\n"
            f"📅 Year: {student.year}\n"
            f"Telegram: @{user.username or 'N/A'}\n"
        )
        
        # Create inline keyboard for approval
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_student_{student.id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_student_{student.id}")
        )
        
        # Send ONLY to bot owner (admin)
        if config.BOT_OWNER_TELEGRAM_ID:
            try:
                bot.send_message(config.BOT_OWNER_TELEGRAM_ID, message_text, reply_markup=markup)
            except Exception as e:
                print(f"Failed to notify admin: {e}")
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_student_'))
def handle_approve_student(call):
    """Handle student approval."""
    student_id = int(call.data.split('_')[2])
    db = SessionLocal()
    
    try:
        student = crud.get_student_by_university_id(db, None)
        student = db.query(crud.models.Student).filter(crud.models.Student.id == student_id).first()
        
        if not student:
            bot.answer_callback_query(call.id, "Student not found")
            return
        
        if student.verified:
            bot.answer_callback_query(call.id, "Already verified")
            return
        
        # For now, just mark as verified without telegram_id
        # They'll link when they enter their university ID again
        student.verified = True
        db.commit()
        
        bot.answer_callback_query(call.id, "✅ Student approved")
        bot.edit_message_text(
            f"✅ Approved: {student.name} ({student.university_id})",
            call.message.chat.id,
            call.message.message_id
        )
        
        # Notify student if they have telegram_id
        if student.telegram_id:
            try:
                bot.send_message(
                    student.telegram_id,
                    "✅ Your account has been verified! Please use /start to continue."
                )
            except:
                pass
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_student_'))
def handle_reject_student(call):
    """Handle student rejection."""
    student_id = int(call.data.split('_')[2])
    db = SessionLocal()
    
    try:
        crud.reject_student(db, student_id)
        
        bot.answer_callback_query(call.id, "❌ Student rejected")
        bot.edit_message_text(
            "❌ Request rejected",
            call.message.chat.id,
            call.message.message_id
        )
    
    finally:
        db.close()


def show_year_selection(chat_id: int, major_name: str, university_id: int, major_id: int):
    """Show year selection keyboard."""
    session = get_session(chat_id)
    session["data"]["browse_university_id"] = university_id
    session["data"]["browse_major_id"] = major_id
    
    markup = types.InlineKeyboardMarkup()
    for year in ['1', '2', '3', '4']:
        markup.row(types.InlineKeyboardButton(f"Year {year}", callback_data=f"year_{year}"))
    
    bot.send_message(
        chat_id,
        f"📚 {major_name}\n\nSelect your year:",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('year_'))
def handle_year_selection(call):
    """Handle year selection."""
    year = call.data.split('_')[1]
    session = get_session(call.from_user.id)
    session["data"]["year"] = year
    
    university_id = session["data"].get("browse_university_id")
    major_id = session["data"].get("browse_major_id")
    
    db = SessionLocal()
    
    try:
        if not university_id or not major_id:
            bot.answer_callback_query(call.id, "Session expired. Please start over.")
            return
        
        # Get courses for this university, major and year
        courses = crud.get_courses_by_filters(db, university_id=university_id, major_id=major_id, year=year)
        
        if not courses:
            major = crud.get_major_by_id(db, major_id)
            bot.edit_message_text(
                f"📭 No courses found for {major.name} Year {year}",
                call.message.chat.id,
                call.message.message_id
            )
            return
        
        # Show course list
        markup = types.InlineKeyboardMarkup()
        for course in courses:
            markup.row(types.InlineKeyboardButton(
                f"{course.name}",
                callback_data=f"course_{course.id}"
            ))
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_to_year"))
        
        major = crud.get_major_by_id(db, major_id)
        bot.edit_message_text(
            f"📚 {major.name} - Year {year}\n\nSelect a course:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('course_') and not call.data.startswith('course_year_') and not call.data.startswith('course_uni_') and not call.data.startswith('course_maj_'))
def handle_course_selection(call):
    """Handle course selection."""
    course_id = int(call.data.split('_')[1])
    session = get_session(call.from_user.id)
    session["data"]["course_id"] = course_id
    
    db = SessionLocal()
    
    try:
        course = crud.get_course_by_id(db, course_id)
        if not course:
            bot.answer_callback_query(call.id, "Course not found")
            return
        
        # Show week selection
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("📅 All Weeks", callback_data=f"week_all_{course_id}"))
        
        # Add week buttons
        weeks = []
        for i in range(1, 17, 4):
            row = []
            for j in range(i, min(i+4, 17)):
                row.append(types.InlineKeyboardButton(f"Week {j}", callback_data=f"week_{j}_{course_id}"))
            markup.row(*row)
        
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_to_courses"))
        
        bot.edit_message_text(
            f"📖 {course.name}\n\nSelect a week:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('week_'))
def handle_week_selection(call):
    """Handle week selection and show materials."""
    parts = call.data.split('_')
    week = parts[1]
    course_id = int(parts[2])
    
    db = SessionLocal()
    
    try:
        course = crud.get_course_by_id(db, course_id)
        if not course:
            bot.answer_callback_query(call.id, "Course not found")
            return
        
        # Get materials
        if week == 'all':
            materials = crud.get_materials_by_course(db, course_id)
            week_text = "All Weeks"
        else:
            materials = crud.get_materials_by_course(db, course_id, week=week)
            week_text = f"Week {week}"
        
        if not materials:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("◀️ Back", callback_data=f"course_{course_id}"))
            
            bot.edit_message_text(
                f"📭 No materials available for {week_text}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            return
        
        # Show materials list
        text = f"📚 {course.name} - {week_text}\n\n"
        text += f"Found {len(materials)} material(s):\n\n"
        
        for i, mat in enumerate(materials, 1):
            text += f"{i}. {mat.filename}\n"
            if mat.description:
                text += f"   {mat.description[:100]}\n"
        
        markup = types.InlineKeyboardMarkup()
        for mat in materials:
            markup.row(types.InlineKeyboardButton(
                f"📥 {mat.filename[:30]}...",
                callback_data=f"download_{mat.id}"
            ))
        
        # Add quiz button
        markup.row(types.InlineKeyboardButton(
            "🧠 Take Quiz",
            callback_data=f"quiz_menu_{course_id}_{week}"
        ))
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data=f"course_{course_id}"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('download_'))
def handle_material_download(call):
    """Handle material download."""
    material_id = int(call.data.split('_')[1])
    telegram_id = str(call.from_user.id)
    
    db = SessionLocal()
    
    try:
        material = crud.get_material_by_id(db, material_id)
        if not material:
            bot.answer_callback_query(call.id, "Material not found")
            return
        
        # Check authorization
        student = crud.get_student_by_telegram_id(db, telegram_id)
        if not student or not student.verified:
            bot.answer_callback_query(call.id, "Not authorized")
            return
        
        # Get file path
        filepath = get_file_path(material.filepath)
        
        if not filepath.exists():
            bot.answer_callback_query(call.id, "File not found")
            return
        
        bot.answer_callback_query(call.id, "📥 Sending file...")
        
        # Send file
        with open(filepath, 'rb') as f:
            bot.send_document(
                call.message.chat.id,
                f,
                caption=f"📄 {material.filename}\n\n{material.description or ''}"
            )
    
    except Exception as e:
        print(f"Download error: {e}")
        bot.answer_callback_query(call.id, "Download failed")
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('quiz_menu_'))
def handle_quiz_menu(call):
    """Show quiz difficulty selection."""
    parts = call.data.split('_')
    course_id = int(parts[2])
    week = parts[3]
    
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🟢 Easy", callback_data=f"quiz_start_easy_{course_id}_{week}"))
    markup.row(types.InlineKeyboardButton("🟡 Medium", callback_data=f"quiz_start_medium_{course_id}_{week}"))
    markup.row(types.InlineKeyboardButton("🔴 Hard", callback_data=f"quiz_start_hard_{course_id}_{week}"))
    markup.row(types.InlineKeyboardButton("◀️ Back", callback_data=f"week_{week}_{course_id}"))
    
    bot.edit_message_text(
        "🧠 Select quiz difficulty:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('quiz_start_'))
def handle_quiz_start(call):
    """Start quiz with selected difficulty - generates on demand for this student."""
    parts = call.data.split('_')
    difficulty = parts[2]
    course_id = int(parts[3])
    week = parts[4]
    student_telegram_id = str(call.from_user.id)
    
    db = SessionLocal()
    
    try:
        # Get student
        student = crud.get_student_by_telegram_id(db, student_telegram_id)
        if not student:
            bot.answer_callback_query(call.id, "Student not found")
            return
        
        # Get ALL materials for this course/week to generate quiz from
        if week == 'all':
            materials = crud.get_materials_by_course(db, course_id)
        else:
            materials = crud.get_materials_by_course(db, course_id, week=week)
        
        if not materials:
            bot.answer_callback_query(call.id, "No materials to generate quiz from")
            return
        
        # Check if quiz generation is already in progress for this student
        recent_jobs = db.query(models.BackgroundJob).filter(
            models.BackgroundJob.job_type == 'quiz_generation',
            models.BackgroundJob.course_id == course_id,
            models.BackgroundJob.student_id == student.id
        ).order_by(models.BackgroundJob.created_at.desc()).limit(1).all()
        
        if recent_jobs:
            job = recent_jobs[0]
            job_status = get_job_status(job.id)
            
            if job_status and job_status['status'] == 'running':
                # Quiz is being generated
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton("🔄 Check Again", callback_data=f"quiz_start_{difficulty}_{course_id}_{week}"))
                markup.row(types.InlineKeyboardButton("◀️ Back", callback_data=f"week_{week}_{course_id}"))
                
                bot.edit_message_text(
                    "⏳ Generating your personalized quiz...\n\n"
                    "This usually takes 30-60 seconds.\n\n"
                    "Your quiz will be unique and based on all materials from this week.",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup
                )
                bot.answer_callback_query(call.id, "Quiz generation in progress...")
                return
            
            elif job_status and job_status['status'] == 'completed':
                # Quiz ready - load it
                quiz_id = job_status.get('result', {}).get('quiz_id')
                if quiz_id:
                    quiz = crud.get_quiz_by_id(db, quiz_id)
                    if quiz:
                        questions = json.loads(quiz.data_json)
                        
                        session = get_session(call.from_user.id)
                        session["data"]["quiz_id"] = quiz.id
                        session["data"]["questions"] = questions
                        session["data"]["current_q"] = 0
                        session["data"]["answers"] = []
                        session["state"] = "taking_quiz"
                        
                        show_quiz_question(call.message.chat.id, call.message.message_id, 0, questions)
                        bot.answer_callback_query(call.id)
                        return
            
            elif job_status and job_status['status'] == 'failed':
                # Previous generation failed - allow retry
                error_msg = job_status.get('error', 'Unknown error')
                print(f"Previous quiz generation failed: {error_msg}")
        
        # Start new quiz generation for this student
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🔄 Check Status", callback_data=f"quiz_start_{difficulty}_{course_id}_{week}"))
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data=f"week_{week}_{course_id}"))
        
        bot.edit_message_text(
            "🎲 Generating your personalized quiz...\n\n"
            f"📚 Based on {len(materials)} material(s) from Week {week}\n"
            f"🎯 Difficulty: {difficulty.title()}\n\n"
            "This will take about 30-60 seconds.\n"
            "Your quiz will be unique!",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        
        # Submit quiz generation task for this student
        from app.tasks import submit_quiz_generation_task
        
        # Get professor (material uploader) for notification purposes
        professor_id = materials[0].uploader_id if materials else None
        
        job_id = submit_quiz_generation_task(
            course_id=course_id,
            week=week,
            student_id=student.id,
            professor_id=professor_id,
            difficulty=difficulty
        )
        
        print(f"📝 Started quiz generation job {job_id} for student {student.id}, course {course_id}, week {week}")
        bot.answer_callback_query(call.id, "Generating your quiz...")
    
    finally:
        db.close()


def show_quiz_question(chat_id: int, message_id: int, q_index: int, questions: list):
    """Display quiz question."""
    if q_index >= len(questions):
        # Quiz complete
        return
    
    q = questions[q_index]
    text = f"❓ Question {q_index + 1}/{len(questions)}\n\n{q['question']}\n\n"
    
    markup = types.InlineKeyboardMarkup()
    
    if q['type'] == 'mcq':
        for i, choice in enumerate(q['choices']):
            text += f"{chr(65+i)}. {choice}\n"
            markup.row(types.InlineKeyboardButton(
                f"{chr(65+i)}",
                callback_data=f"quiz_answer_{q_index}_{i}"
            ))
        
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
        else:
            bot.send_message(chat_id, text, reply_markup=markup)
    else:
        # Open-ended question - just send text without buttons
        text += "💡 Tip: This is an open-ended question. Your answer will be reviewed."
        
        if message_id:
            try:
                bot.edit_message_text(text, chat_id, message_id)
            except:
                bot.send_message(chat_id, text)
        else:
            bot.send_message(chat_id, text)


@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "taking_quiz")
def handle_quiz_text_answer(message):
    """Handle text answer for open-ended quiz questions."""
    session = get_session(message.from_user.id)
    questions = session["data"].get("questions", [])
    current_q = session["data"].get("current_q", 0)
    
    if not questions or current_q >= len(questions):
        bot.send_message(message.chat.id, "❓ I didn't understand that. Use /start to begin.")
        return
    
    # Check if current question is open-ended
    q = questions[current_q]
    if q.get('type') != 'mcq':
        # Record the text answer
        session["data"]["answers"].append(message.text.strip())
        
        next_q = current_q + 1
        
        if next_q < len(questions):
            # Show next question
            session["data"]["current_q"] = next_q
            show_quiz_question(message.chat.id, None, next_q, questions)
        else:
            # Quiz complete - for open-ended, we can't auto-grade
            complete_quiz(message.chat.id, session, questions)
    else:
        bot.send_message(message.chat.id, "Please use the buttons to answer MCQ questions.")


def complete_quiz(chat_id: int, session: dict, questions: list):
    """Complete quiz and show results."""
    answers = session["data"].get("answers", [])
    
    # Calculate score (only for MCQ questions)
    correct = 0
    mcq_count = 0
    
    for i, q in enumerate(questions):
        if i < len(answers):
            if q.get('type') == 'mcq':
                mcq_count += 1
                if q.get('answer') == answers[i]:
                    correct += 1
    
    # Calculate score based on MCQ questions only
    if mcq_count > 0:
        score = (correct / mcq_count) * 100
        text = f"🎉 Quiz Complete!\n\n"
        text += f"MCQ Score: {score:.1f}%\n"
        text += f"Correct: {correct}/{mcq_count}\n\n"
        
        if score >= 80:
            text += "Excellent work! 🏆"
        elif score >= 60:
            text += "Good job! ✅"
        else:
            text += "Keep studying! 📚"
    else:
        text = "🎉 Quiz Complete!\n\n"
        text += "Your answers have been recorded.\n"
        text += "Open-ended questions will be reviewed manually."
    
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("📖 View Explanations", callback_data="quiz_explanations"))
    markup.row(types.InlineKeyboardButton("🔄 Retake", callback_data="retake_quiz"))
    markup.row(types.InlineKeyboardButton("🏠 Home", callback_data="home"))
    
    bot.send_message(chat_id, text, reply_markup=markup)
    
    session["state"] = "quiz_complete"


@bot.callback_query_handler(func=lambda call: call.data.startswith('quiz_answer_'))
def handle_quiz_answer(call):
    """Handle quiz MCQ answer."""
    parts = call.data.split('_')
    q_index = int(parts[2])
    answer = int(parts[3])
    
    session = get_session(call.from_user.id)
    questions = session["data"].get("questions", [])
    
    if not questions or q_index >= len(questions):
        bot.answer_callback_query(call.id, "Invalid question")
        return
    
    # Record answer
    session["data"]["answers"].append(answer)
    
    next_q = q_index + 1
    
    if next_q < len(questions):
        # Show next question
        session["data"]["current_q"] = next_q
        show_quiz_question(call.message.chat.id, call.message.message_id, next_q, questions)
        bot.answer_callback_query(call.id)
    else:
        # Quiz complete
        bot.answer_callback_query(call.id, "Quiz completed!")
        complete_quiz(call.message.chat.id, session, questions)


@bot.callback_query_handler(func=lambda call: call.data == 'quiz_explanations')
def handle_quiz_explanations(call):
    """Show quiz explanations."""
    session = get_session(call.from_user.id)
    questions = session["data"].get("questions", [])
    answers = session["data"].get("answers", [])
    
    if not questions:
        bot.answer_callback_query(call.id, "No quiz data")
        return
    
    text = "📖 Quiz Explanations:\n\n"
    
    for i, q in enumerate(questions):
        user_answer = answers[i] if i < len(answers) else None
        correct_answer = q.get('answer')
        
        text += f"{i+1}. {q['question']}\n"
        
        if q['type'] == 'mcq':
            text += f"Your answer: {chr(65+user_answer) if isinstance(user_answer, int) else 'N/A'}\n"
            text += f"Correct: {chr(65+correct_answer)}\n"
        else:
            # Open-ended question
            text += f"Your answer: {user_answer if isinstance(user_answer, str) else 'N/A'}\n"
            if correct_answer:
                text += f"Expected answer: {correct_answer}\n"
        
        text += f"💡 {q.get('explanation', 'No explanation')}\n\n"
    
    # Split if too long
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            bot.send_message(call.message.chat.id, chunk)
    else:
        bot.send_message(call.message.chat.id, text)
    
    bot.answer_callback_query(call.id)


# Professor flow
@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "professor_code")
def handle_professor_code(message):
    """Handle professor code authentication."""
    code = message.text.strip()
    telegram_id = str(message.from_user.id)
    
    db = SessionLocal()
    
    try:
        professor = crud.get_professor_by_code(db, code)
        
        if not professor or not professor.active:
            bot.send_message(message.chat.id, "❌ Invalid professor code. Try again or use /start")
            return
        
        # Link telegram ID if not linked
        if not professor.telegram_id:
            crud.link_professor_telegram(db, professor.id, telegram_id)
        
        session = get_session(message.from_user.id)
        session["data"]["professor_id"] = professor.id
        session["state"] = "professor_authenticated"
        
        show_professor_dashboard(message.chat.id)
    
    finally:
        db.close()


def show_professor_dashboard(chat_id: int):
    """Show professor dashboard."""
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("📤 Upload Material", callback_data="prof_upload"))
    markup.row(types.InlineKeyboardButton("📚 Manage Materials", callback_data="prof_view"))
    markup.row(types.InlineKeyboardButton("👥 Pending Students", callback_data="prof_students"))
    markup.row(types.InlineKeyboardButton("🏠 Home", callback_data="home"))
    
    bot.send_message(
        chat_id,
        "👨‍🏫 Professor Dashboard\n\nWhat would you like to do?",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == 'prof_upload')
def handle_prof_upload(call):
    """Handle professor upload request."""
    telegram_id = str(call.from_user.id)
    db = SessionLocal()
    
    try:
        professor = crud.get_professor_by_telegram_id(db, telegram_id)
        
        if not professor or not professor.course_id:
            bot.answer_callback_query(call.id, "❌ You are not assigned to any course yet!")
            bot.edit_message_text(
                "❌ You are not assigned to a course.\n\nPlease contact an admin to assign you to a course.",
                call.message.chat.id,
                call.message.message_id
            )
            return
        
        course = crud.get_course_by_id(db, professor.course_id)
        
        session = get_session(call.from_user.id)
        session["data"]["prof_course_id"] = course.id
        session["state"] = "prof_upload_week"
        
        bot.edit_message_text(
            f"📤 Upload Material\n\n"
            f"📚 Course: {course.name}\n"
            f"🏛 University: {course.university.name}\n"
            f"📖 Major: {course.major.name}\n"
            f"📅 Year: {course.year}\n\n"
            f"Enter Week number (1-16):",
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "prof_upload_week")
def handle_prof_upload_week(message):
    """Handle week input for upload."""
    session = get_session(message.from_user.id)
    week = message.text.strip()
    
    if not week.isdigit() or int(week) < 1 or int(week) > 16:
        bot.send_message(message.chat.id, "❌ Invalid week number. Please enter 1-16:", reply_markup=types.ReplyKeyboardRemove())
        return
    
    session["data"]["upload_week"] = week
    session["state"] = "prof_upload_file"
    
    bot.send_message(
        message.chat.id,
        "Send the file (PDF, DOCX, or PPTX):\n\n"
        "You can also add a description as the file caption.",
        reply_markup=types.ReplyKeyboardRemove()
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('upload_same_week_'))
def handle_upload_same_week(call):
    """Handle uploading another file to the same week."""
    week = call.data.split('_')[-1]
    
    session = get_session(call.from_user.id)
    session["data"]["upload_week"] = week
    session["state"] = "prof_upload_file"
    
    bot.edit_message_text(
        f"📤 Upload Another File to Week {week}\n\n"
        f"Send the file (PDF, DOCX, or PPTX):\n"
        f"You can also add a description as the file caption.",
        call.message.chat.id,
        call.message.message_id
    )
    bot.answer_callback_query(call.id)


@bot.message_handler(content_types=['document'], func=lambda m: get_session(m.from_user.id).get("state") == "prof_upload_file")
def handle_prof_upload_file(message):
    """Handle file upload from professor."""
    session = get_session(message.from_user.id)
    telegram_id = str(message.from_user.id)
    
    db = SessionLocal()
    
    try:
        # Get professor
        professor = crud.get_professor_by_telegram_id(db, telegram_id)
        if not professor:
            bot.send_message(message.chat.id, "❌ Professor not found. Please authenticate again.")
            return
        
        # Check rate limit
        if not crud.check_rate_limit(db, professor.id, 'upload', config.PROF_RATE_LIMIT_PER_DAY):
            bot.send_message(
                message.chat.id,
                f"❌ Upload limit reached ({config.PROF_RATE_LIMIT_PER_DAY} per day). Try again tomorrow."
            )
            return
        
        # Get file
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Get upload data
        course_id = session["data"].get("prof_course_id")
        if not course_id:
            bot.send_message(message.chat.id, "❌ Session expired. Please start over.")
            return
        
        course = crud.get_course_by_id(db, course_id)
        if not course:
            bot.send_message(message.chat.id, "❌ Course not found.")
            return
        
        week = session["data"]["upload_week"]
        filename = message.document.file_name
        description = message.caption or ""
        
        # Save file
        from app.storage import get_storage_path, save_uploaded_file
        full_path, relative_path = get_storage_path(
            course.university.name,
            course.major.name,
            course.name,
            week,
            filename
        )
        
        if not save_uploaded_file(downloaded_file, full_path):
            bot.send_message(message.chat.id, "❌ Failed to save file")
            return
        
        # Create material record
        material = crud.create_material(
            db,
            course_id=course.id,
            uploader_id=professor.id,
            filename=filename,
            filepath=str(relative_path),
            week=week,
            description=description
        )
        
        # Increment rate limit
        crud.increment_rate_limit(db, professor.id, 'upload')
        
        # Create inline keyboard for continuation
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("➕ Upload Another File (Same Week)", callback_data=f"upload_same_week_{week}"))
        markup.row(types.InlineKeyboardButton("📚 Upload to Different Week", callback_data="prof_upload"))
        markup.row(types.InlineKeyboardButton("🏠 Dashboard", callback_data="prof_dashboard"))
        
        bot.send_message(
            message.chat.id,
            f"✅ Material uploaded successfully!\n\n"
            f"📚 Course: {course.name}\n"
            f"📅 Week: {week}\n"
            f"📄 File: {filename}\n\n"
            f"💡 Quizzes will be generated on-demand when students request them.\n\n"
            f"What would you like to do next?",
            reply_markup=markup
        )
        
        # Don't clear session yet - keep week info for potential additional uploads
        session["state"] = "prof_upload_complete"
    
    except Exception as e:
        print(f"Upload error: {e}")
        import traceback
        traceback.print_exc()
        bot.send_message(message.chat.id, f"❌ Upload failed: {str(e)}")
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'prof_view')
def handle_prof_view(call):
    """Show professor materials for management."""
    telegram_id = str(call.from_user.id)
    db = SessionLocal()
    
    try:
        professor = crud.get_professor_by_telegram_id(db, telegram_id)
        if not professor or not professor.course_id:
            bot.edit_message_text(
                "❌ You are not assigned to a course.",
                call.message.chat.id,
                call.message.message_id
            )
            bot.answer_callback_query(call.id)
            return
        
        # Get all materials uploaded by this professor
        materials = crud.get_materials_by_professor(db, professor.id)
        
        if not materials:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="prof_dashboard"))
            
            bot.edit_message_text(
                "📭 No materials uploaded yet.\\n\\nUpload materials to get started!",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            bot.answer_callback_query(call.id)
            return
        
        # Group materials by week
        from collections import defaultdict
        materials_by_week = defaultdict(list)
        for mat in materials:
            materials_by_week[mat.week].append(mat)
        
        markup = types.InlineKeyboardMarkup()
        for week in sorted(materials_by_week.keys()):
            count = len(materials_by_week[week])
            markup.row(types.InlineKeyboardButton(
                f"📅 Week {week} ({count} material{'s' if count != 1 else ''})",
                callback_data=f"prof_view_week_{week}"
            ))
        
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="prof_dashboard"))
        
        course = professor.course
        bot.edit_message_text(
            f"📚 {course.name}\\n\\nSelect a week to manage materials:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('prof_view_week_'))
def handle_prof_view_week(call):
    """Show materials for a specific week with delete options."""
    week = call.data.split('_')[3]
    telegram_id = str(call.from_user.id)
    db = SessionLocal()
    
    try:
        professor = crud.get_professor_by_telegram_id(db, telegram_id)
        if not professor:
            bot.answer_callback_query(call.id, "Not authorized")
            return
        
        materials = crud.get_materials_by_professor(db, professor.id, week=week)
        
        if not materials:
            bot.answer_callback_query(call.id, "No materials found")
            return
        
        text = f"📚 Week {week} Materials\n\n"
        
        markup = types.InlineKeyboardMarkup()
        for mat in materials:
            text += f"📄 {mat.filename}\n"
            if mat.description:
                text += f"   {mat.description[:50]}...\n"
            
            markup.row(types.InlineKeyboardButton(
                f"🗑 Delete: {mat.filename[:30]}",
                callback_data=f"prof_del_mat_{mat.id}"
            ))
        
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="prof_view"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('prof_del_mat_'))
def handle_prof_delete_material(call):
    """Confirm material deletion."""
    material_id = int(call.data.split('_')[3])
    telegram_id = str(call.from_user.id)
    db = SessionLocal()
    
    try:
        professor = crud.get_professor_by_telegram_id(db, telegram_id)
        if not professor:
            bot.answer_callback_query(call.id, "Not authorized")
            return
        
        material = crud.get_material_by_id(db, material_id)
        if not material or material.uploader_id != professor.id:
            bot.answer_callback_query(call.id, "Not authorized to delete this material")
            return
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Yes, Delete", callback_data=f"prof_del_confirm_{material_id}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data=f"prof_view_week_{material.week}")
        )
        
        bot.edit_message_text(
            f"⚠️ Confirm Deletion\n\n"
            f"📄 File: {material.filename}\n"
            f"📅 Week: {material.week}\n\n"
            f"This will permanently delete the material and any associated quizzes.\n\n"
            f"Are you sure?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('prof_del_confirm_'))
def handle_prof_delete_confirm(call):
    """Actually delete the material."""
    material_id = int(call.data.split('_')[3])
    telegram_id = str(call.from_user.id)
    db = SessionLocal()
    
    try:
        professor = crud.get_professor_by_telegram_id(db, telegram_id)
        if not professor:
            bot.answer_callback_query(call.id, "Not authorized")
            return
        
        material = crud.get_material_by_id(db, material_id)
        if not material or material.uploader_id != professor.id:
            bot.answer_callback_query(call.id, "Not authorized")
            return
        
        week = material.week
        filename = material.filename
        
        # Delete material (this will cascade delete quizzes and jobs)
        crud.delete_material(db, material_id)
        
        bot.answer_callback_query(call.id, "✅ Material deleted")
        
        # Get updated materials for this week
        materials = crud.get_materials_by_professor(db, professor.id, week=week)
        
        if materials:
            # Show updated week view
            text = f"📚 Week {week} Materials\n\n"
            markup = types.InlineKeyboardMarkup()
            
            for mat in materials:
                text += f"📄 {mat.filename}\n"
                if mat.description:
                    text += f"   {mat.description[:50]}...\n"
                
                markup.row(types.InlineKeyboardButton(
                    f"🗑 Delete: {mat.filename[:30]}",
                    callback_data=f"prof_del_mat_{mat.id}"
                ))
            
            markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="prof_view"))
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        else:
            # No materials left, go back to main view
            bot.edit_message_text(
                f"✅ Material deleted successfully!\n\n📚 No materials remaining for Week {week}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=types.InlineKeyboardMarkup([
                    [types.InlineKeyboardButton("◀️ Back", callback_data="prof_view")]
                ])
            )
        
    except Exception as e:
        print(f"Error deleting material: {e}")
        bot.answer_callback_query(call.id, "❌ Failed to delete")
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'prof_students')

def handle_prof_students(call):
    """Show pending students."""
    db = SessionLocal()
    
    try:
        students = crud.get_pending_students(db)
        
        if not students:
            bot.edit_message_text(
                "✅ No pending student approvals",
                call.message.chat.id,
                call.message.message_id
            )
            bot.answer_callback_query(call.id)
            return
        
        text = f"👥 Pending Students ({len(students)}):\n\n"
        
        markup = types.InlineKeyboardMarkup()
        for student in students[:10]:  # Limit to 10
            text += f"• {student.name} ({student.university_id}) - {student.major}\n"
            markup.row(
                types.InlineKeyboardButton(f"✅ {student.university_id}", callback_data=f"approve_student_{student.id}"),
                types.InlineKeyboardButton("❌", callback_data=f"reject_student_{student.id}")
            )
        
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="prof_dashboard"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'home')
def handle_home(call):
    """Return to home."""
    clear_session(call.from_user.id)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    handle_start(call.message)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == 'prof_dashboard')
def handle_prof_dashboard_callback(call):
    """Show professor dashboard from callback."""
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_professor_dashboard(call.message.chat.id)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_year')
def handle_back_to_year(call):
    """Navigate back to year selection."""
    session = get_session(call.from_user.id)
    telegram_id = str(call.from_user.id)
    db = SessionLocal()
    
    try:
        student = crud.get_student_by_telegram_id(db, telegram_id)
        if student:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            show_year_selection(call.message.chat.id, student.major)
        bot.answer_callback_query(call.id)
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_courses')
def handle_back_to_courses(call):
    """Navigate back to course selection."""
    session = get_session(call.from_user.id)
    year = session["data"].get("year")
    
    if year:
        # Re-trigger year selection to show courses
        call.data = f"year_{year}"
        handle_year_selection(call)
    else:
        bot.answer_callback_query(call.id, "Please start over")


# Admin commands (simplified)
@bot.message_handler(commands=['admin'])
def handle_admin_command(message):
    """Admin command."""
    bot.send_message(
        message.chat.id,
        "🔑 Enter admin code:"
    )
    session = get_session(message.from_user.id)
    session["state"] = "admin_code"


@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "admin_code")
def handle_admin_code(message):
    """Handle admin code."""
    if message.text.strip() == config.ADMIN_CODE:
        telegram_id = str(message.from_user.id)
        
        db = SessionLocal()
        try:
            # Create admin if not exists
            admin = crud.get_admin_by_telegram_id(db, telegram_id)
            if not admin:
                admin = crud.create_admin(db, telegram_id)
            
            session = get_session(message.from_user.id)
            session["state"] = "admin_authenticated"
            
            show_admin_dashboard(message.chat.id)
        
        finally:
            db.close()
    else:
        bot.send_message(message.chat.id, "❌ Invalid admin code")


def show_admin_dashboard(chat_id: int):
    """Show admin dashboard."""
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"))
    markup.row(types.InlineKeyboardButton("🏛️ Manage Universities", callback_data="admin_universities"))
    markup.row(types.InlineKeyboardButton("🎓 Manage Majors", callback_data="admin_majors"))
    markup.row(types.InlineKeyboardButton("📚 Manage Courses", callback_data="admin_courses"))
    markup.row(types.InlineKeyboardButton("➕ Create Professor", callback_data="admin_create_prof"))
    markup.row(types.InlineKeyboardButton("👥 Pending Students", callback_data="admin_students"))
    markup.row(types.InlineKeyboardButton("👨‍🏫 All Professors", callback_data="admin_professors"))
    markup.row(types.InlineKeyboardButton("🏠 Home", callback_data="home"))
    
    bot.send_message(
        chat_id,
        "⚙️ Admin Dashboard\n\nSelect an option:",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == 'admin_stats')
def handle_admin_stats(call):
    """Show admin statistics."""
    db = SessionLocal()
    
    try:
        stats = crud.get_upload_stats(db)
        
        text = "📊 System Statistics\n\n"
        text += f"🏛️ Universities: {stats['total_universities']}\n"
        text += f"🎓 Majors: {stats['total_majors']}\n"
        text += f"📚 Courses: {stats['total_courses']}\n"
        text += f"👨‍🏫 Professors: {stats['total_professors']}\n"
        text += f"✅ Verified Students: {stats['total_verified_students']}\n"
        text += f"⏳ Pending Students: {len(crud.get_pending_students(db))}\n"
        text += f"📄 Materials: {stats['total_uploads']}\n"
        text += f"🧠 Quizzes: {stats['total_quizzes']}\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_admin_dashboard"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


# ========== University Management ==========
@bot.callback_query_handler(func=lambda call: call.data == 'admin_universities')
def handle_admin_universities(call):
    """Show all universities."""
    db = SessionLocal()
    
    try:
        universities = crud.get_all_universities(db)
        
        if not universities:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("➕ Create University", callback_data="admin_create_university"))
            markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_admin_dashboard"))
            
            bot.edit_message_text(
                "📭 No universities yet",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            bot.answer_callback_query(call.id)
            return
        
        text = f"🏛️ All Universities ({len(universities)}):\n\n"
        for uni in universities:
            majors_count = len(crud.get_majors_by_university(db, uni.id))
            text += f"• {uni.name}\n  📚 {majors_count} majors\n\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("➕ Create University", callback_data="admin_create_university"))
        
        # Add edit/delete buttons for each university
        for uni in universities[:10]:  # Limit to 10
            markup.row(
                types.InlineKeyboardButton(f"✏️ {uni.name}", callback_data=f"edit_uni_{uni.id}"),
                types.InlineKeyboardButton("🗑", callback_data=f"delete_uni_{uni.id}")
            )
        
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_admin_dashboard"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'admin_create_university')
def handle_admin_create_university(call):
    """Start university creation flow."""
    session = get_session(call.from_user.id)
    session["state"] = "admin_university_name"
    
    bot.edit_message_text(
        "➕ Create New University\n\nEnter university name:",
        call.message.chat.id,
        call.message.message_id
    )
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "admin_university_name")
def handle_admin_university_name(message):
    """Handle university name input."""
    db = SessionLocal()
    
    try:
        name = message.text.strip()
        
        # Check if university already exists
        existing = crud.get_university_by_name(db, name)
        if existing:
            bot.send_message(
                message.chat.id,
                f"❌ University '{name}' already exists!",
                reply_markup=types.ReplyKeyboardRemove()
            )
            return
        
        university = crud.create_university(db, name)
        
        session = get_session(message.from_user.id)
        session["state"] = None
        
        bot.send_message(
            message.chat.id,
            f"✅ University '{university.name}' created successfully!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_admin_dashboard(message.chat.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_uni_'))
def handle_edit_university(call):
    """Start university edit flow."""
    university_id = int(call.data.split('_')[2])
    
    session = get_session(call.from_user.id)
    session["data"]["edit_university_id"] = university_id
    session["state"] = "admin_edit_university_name"
    
    db = SessionLocal()
    try:
        university = crud.get_university_by_id(db, university_id)
        if university:
            bot.edit_message_text(
                f"✏️ Edit University\n\nCurrent name: {university.name}\n\nEnter new name:",
                call.message.chat.id,
                call.message.message_id
            )
            bot.answer_callback_query(call.id)
    finally:
        db.close()


@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "admin_edit_university_name")
def handle_edit_university_name(message):
    """Handle university name edit."""
    db = SessionLocal()
    
    try:
        session = get_session(message.from_user.id)
        university_id = session["data"].get("edit_university_id")
        
        if not university_id:
            bot.send_message(message.chat.id, "❌ Session expired. Please start over.")
            show_admin_dashboard(message.chat.id)
            return
        
        new_name = message.text.strip()
        
        # Check if name already exists
        existing = crud.get_university_by_name(db, new_name)
        if existing and existing.id != university_id:
            bot.send_message(
                message.chat.id,
                f"❌ University '{new_name}' already exists!",
                reply_markup=types.ReplyKeyboardRemove()
            )
            return
        
        university = crud.update_university(db, university_id, new_name)
        
        session["state"] = None
        
        bot.send_message(
            message.chat.id,
            f"✅ University updated to '{university.name}'!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_admin_dashboard(message.chat.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_uni_'))
def handle_delete_university(call):
    """Handle university deletion with confirmation."""
    university_id = int(call.data.split('_')[2])
    
    db = SessionLocal()
    try:
        university = crud.get_university_by_id(db, university_id)
        if not university:
            bot.answer_callback_query(call.id, "University not found")
            return
        
        # Check if university has related data
        majors = crud.get_majors_by_university(db, university_id)
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_uni_{university_id}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="admin_universities")
        )
        
        warning = f"⚠️ Delete University?\n\n{university.name}\n\n"
        if majors:
            warning += f"This will also delete:\n• {len(majors)} major(s)\n• All related courses\n• All related materials\n\n"
        warning += "This action cannot be undone!"
        
        bot.edit_message_text(warning, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_uni_'))
def handle_confirm_delete_university(call):
    """Confirm and delete university."""
    university_id = int(call.data.split('_')[3])
    
    db = SessionLocal()
    try:
        university = crud.get_university_by_id(db, university_id)
        name = university.name if university else "Unknown"
        
        if crud.delete_university(db, university_id):
            bot.answer_callback_query(call.id, f"✅ '{name}' deleted!")
            success = True
        else:
            bot.answer_callback_query(call.id, "❌ Failed to delete")
            success = False
    finally:
        db.close()
    
    # Show dashboard after db is closed
    if success:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_admin_dashboard(call.message.chat.id)


# ========== Major Management ==========
@bot.callback_query_handler(func=lambda call: call.data == 'admin_majors')
def handle_admin_majors(call):
    """Show major management options."""
    db = SessionLocal()
    
    try:
        universities = crud.get_all_universities(db)
        
        if not universities:
            bot.edit_message_text(
                "❌ No universities found!\n\nPlease create a university first.",
                call.message.chat.id,
                call.message.message_id
            )
            bot.answer_callback_query(call.id)
            return
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("➕ Create Major", callback_data="admin_create_major"))
        markup.row(types.InlineKeyboardButton("📋 View All Majors", callback_data="admin_view_majors"))
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_admin_dashboard"))
        
        bot.edit_message_text(
            "🎓 Major Management\n\nSelect an option:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'admin_view_majors')
def handle_admin_view_majors(call):
    """View all majors by university."""
    db = SessionLocal()
    
    try:
        universities = crud.get_all_universities(db)
        text = "🎓 All Majors:\n\n"
        
        markup = types.InlineKeyboardMarkup()
        
        for uni in universities:
            majors = crud.get_majors_by_university(db, uni.id)
            text += f"🏛️ {uni.name}\n"
            if majors:
                for major in majors:
                    text += f"  • {major.name}\n"
                    # Add edit/delete buttons
                    markup.row(
                        types.InlineKeyboardButton(f"✏️ {major.name[:20]}", callback_data=f"edit_maj_{major.id}"),
                        types.InlineKeyboardButton("🗑", callback_data=f"delete_maj_{major.id}")
                    )
            else:
                text += "  (no majors)\n"
            text += "\n"
        
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="admin_majors"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'admin_create_major')
def handle_admin_create_major(call):
    """Start major creation flow - select university."""
    db = SessionLocal()
    
    try:
        universities = crud.get_all_universities(db)
        
        if not universities:
            bot.answer_callback_query(call.id, "❌ No universities found!")
            return
        
        session = get_session(call.from_user.id)
        session["state"] = "admin_major_university"
        
        markup = types.InlineKeyboardMarkup()
        for uni in universities:
            markup.row(types.InlineKeyboardButton(uni.name, callback_data=f"major_uni_{uni.id}"))
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="admin_majors"))
        
        bot.edit_message_text(
            "➕ Create New Major\n\nStep 1/2: Select University:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('major_uni_'))
def handle_admin_major_university(call):
    """Handle university selection for major creation."""
    university_id = int(call.data.split('_')[2])
    
    session = get_session(call.from_user.id)
    session["data"]["major_university_id"] = university_id
    session["state"] = "admin_major_name"
    
    bot.edit_message_text(
        "Step 2/2: Enter major name:",
        call.message.chat.id,
        call.message.message_id
    )
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "admin_major_name")
def handle_admin_major_name(message):
    """Handle major name input."""
    db = SessionLocal()
    
    try:
        session = get_session(message.from_user.id)
        university_id = session["data"].get("major_university_id")
        
        if not university_id:
            bot.send_message(message.chat.id, "❌ Session expired. Please start over.")
            show_admin_dashboard(message.chat.id)
            return
        
        name = message.text.strip()
        
        # Check if major already exists in this university
        existing = crud.get_major_by_name(db, university_id, name)
        if existing:
            bot.send_message(
                message.chat.id,
                f"❌ Major '{name}' already exists in this university!",
                reply_markup=types.ReplyKeyboardRemove()
            )
            return
        
        university = crud.get_university_by_id(db, university_id)
        major = crud.create_major(db, university_id, name)
        
        session["state"] = None
        
        bot.send_message(
            message.chat.id,
            f"✅ Major '{major.name}' created for {university.name}!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_admin_dashboard(message.chat.id)
    
    finally:
        db.close()


# --- Major Edit/Delete Handlers ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_maj_'))
def handle_edit_major(call):
    """Start major edit flow."""
    major_id = int(call.data.split('_')[-1])
    db = SessionLocal()
    
    try:
        major = crud.get_major_by_id(db, major_id)
        if not major:
            bot.answer_callback_query(call.id, "❌ Major not found!")
            return
        
        university = crud.get_university_by_id(db, major.university_id)
        session = get_session(call.from_user.id)
        session["state"] = "admin_edit_major_name"
        session["data"]["edit_major_id"] = major_id
        
        bot.edit_message_text(
            f"✏️ Edit Major\n\nCurrent name: {major.name}\nUniversity: {university.name}\n\nEnter new major name:",
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.message_handler(func=lambda msg: get_session(msg.from_user.id).get("state") == "admin_edit_major_name")
def handle_edit_major_name(message):
    """Process major name update."""
    db = SessionLocal()
    
    try:
        session = get_session(message.from_user.id)
        major_id = session["data"].get("edit_major_id")
        
        if not major_id:
            bot.send_message(message.chat.id, "❌ Session expired. Please start over.")
            show_admin_dashboard(message.chat.id)
            return
        
        major = crud.get_major_by_id(db, major_id)
        if not major:
            bot.send_message(message.chat.id, "❌ Major not found!")
            show_admin_dashboard(message.chat.id)
            return
        
        new_name = message.text.strip()
        
        # Check for duplicate within the same university
        existing = crud.get_major_by_name(db, major.university_id, new_name)
        if existing and existing.id != major_id:
            bot.send_message(
                message.chat.id,
                f"❌ Major '{new_name}' already exists in this university!",
                reply_markup=types.ReplyKeyboardRemove()
            )
            return
        
        updated = crud.update_major(db, major_id, new_name)
        session["state"] = None
        
        bot.send_message(
            message.chat.id,
            f"✅ Major updated: '{major.name}' → '{updated.name}'",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_admin_dashboard(message.chat.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_maj_'))
def handle_delete_major(call):
    """Show confirmation before deleting major."""
    major_id = int(call.data.split('_')[-1])
    db = SessionLocal()
    
    try:
        major = crud.get_major_by_id(db, major_id)
        if not major:
            bot.answer_callback_query(call.id, "❌ Major not found!")
            return
        
        university = crud.get_university_by_id(db, major.university_id)
        # Count courses
        courses = db.query(models.Course).filter(models.Course.major_id == major_id).all()
        course_count = len(courses)
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Confirm Delete", callback_data=f"confirm_delete_maj_{major_id}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="admin_view_majors")
        )
        
        bot.edit_message_text(
            f"⚠️ Delete Major?\n\nMajor: {major.name}\nUniversity: {university.name}\n\n"
            f"This will delete:\n• {course_count} course(s)\n• All related materials and uploads\n\n"
            f"This action cannot be undone!",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_maj_'))
def handle_confirm_delete_major(call):
    """Execute major deletion."""
    major_id = int(call.data.split('_')[-1])
    db = SessionLocal()
    
    try:
        major = crud.get_major_by_id(db, major_id)
        if not major:
            bot.answer_callback_query(call.id, "❌ Major not found!")
            return
        
        major_name = major.name
        success = crud.delete_major(db, major_id)
        
        if success:
            bot.answer_callback_query(call.id, f"✅ Major '{major_name}' deleted!")
        else:
            bot.answer_callback_query(call.id, "❌ Failed to delete major!")
            return
    
    finally:
        db.close()
    
    # Return to major list with fresh db session
    handle_admin_view_majors(call)


@bot.callback_query_handler(func=lambda call: call.data == 'admin_create_prof')
def handle_admin_create_prof(call):
    """Start professor creation flow."""
    session = get_session(call.from_user.id)
    session["state"] = "admin_create_prof_name"
    
    bot.edit_message_text(
        "➕ Create New Professor\n\nEnter professor name:",
        call.message.chat.id,
        call.message.message_id
    )
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "admin_create_prof_name")
def handle_admin_create_prof_name(message):
    """Handle professor name input."""
    import secrets
    
    name = message.text.strip()
    code = f"PROF_{secrets.token_hex(4).upper()}"
    
    db = SessionLocal()
    
    try:
        professor = crud.create_professor(db, name, code)
        
        text = f"✅ Professor created successfully!\n\n"
        text += f"👤 Name: {name}\n"
        text += f"🔑 Code: `{code}`\n\n"
        text += f"⚠️ Share this code securely with the professor."
        
        bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=types.ReplyKeyboardRemove())
        
        clear_session(message.from_user.id)
        show_admin_dashboard(message.chat.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'admin_students')
def handle_admin_students(call):
    """Show pending students for admin."""
    db = SessionLocal()
    
    try:
        students = crud.get_pending_students(db)
        
        if not students:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_admin_dashboard"))
            
            bot.edit_message_text(
                "✅ No pending student approvals",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            bot.answer_callback_query(call.id)
            return
        
        text = f"👥 Pending Students ({len(students)}):\n\n"
        
        markup = types.InlineKeyboardMarkup()
        for student in students[:10]:
            text += f"• {student.name} ({student.university_id}) - {student.major}\n"
            markup.row(
                types.InlineKeyboardButton(f"✅ {student.university_id}", callback_data=f"approve_student_{student.id}"),
                types.InlineKeyboardButton("❌", callback_data=f"reject_student_{student.id}")
            )
        
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_admin_dashboard"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'admin_courses')
def handle_admin_courses(call):
    """Show all courses for admin."""
    db = SessionLocal()
    
    try:
        courses = crud.get_courses_by_filters(db)
        
        if not courses:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("➕ Create Course", callback_data="admin_create_course"))
            markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_admin_dashboard"))
            
            bot.edit_message_text(
                "📭 No courses yet",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            bot.answer_callback_query(call.id)
            return
        
        text = f"📚 All Courses ({len(courses)}):\n\n"
        markup = types.InlineKeyboardMarkup()
        
        for course in courses[:20]:
            materials_count = len(crud.get_materials_by_course(db, course.id))
            text += f"• {course.name}\n"
            text += f"  {course.university.name} - {course.major.name} Year {course.year}\n"
            text += f"  📄 {materials_count} materials\n\n"
            
            # Add edit/delete buttons for each course
            markup.row(
                types.InlineKeyboardButton(f"✏️ {course.name[:20]}", callback_data=f"edit_course_{course.id}"),
                types.InlineKeyboardButton("🗑", callback_data=f"delete_course_{course.id}")
            )
        
        markup.row(types.InlineKeyboardButton("➕ Create Course", callback_data="admin_create_course"))
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_admin_dashboard"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == 'admin_create_course')
def handle_admin_create_course(call):
    """Start course creation flow - select university."""
    db = SessionLocal()
    
    try:
        universities = crud.get_all_universities(db)
        
        if not universities:
            bot.answer_callback_query(call.id, "❌ No universities found! Create one first.")
            return
        
        session = get_session(call.from_user.id)
        session["state"] = "admin_course_university"
        
        markup = types.InlineKeyboardMarkup()
        for uni in universities:
            markup.row(types.InlineKeyboardButton(uni.name, callback_data=f"course_uni_{uni.id}"))
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="admin_courses"))
        
        bot.edit_message_text(
            "➕ Create New Course\n\nStep 1/4: Select University:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('course_uni_'))
def handle_admin_course_university(call):
    """Handle university selection for course creation."""
    university_id = int(call.data.split('_')[2])
    db = SessionLocal()
    
    try:
        majors = crud.get_majors_by_university(db, university_id)
        
        if not majors:
            bot.answer_callback_query(call.id, "❌ No majors found for this university!")
            return
        
        session = get_session(call.from_user.id)
        session["data"]["course_university_id"] = university_id
        session["state"] = "admin_course_major"
        
        markup = types.InlineKeyboardMarkup()
        for major in majors:
            markup.row(types.InlineKeyboardButton(major.name, callback_data=f"course_maj_{major.id}"))
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="admin_create_course"))
        
        bot.edit_message_text(
            "Step 2/4: Select Major:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('course_maj_'))
def handle_admin_course_major(call):
    """Handle major selection for course creation."""
    major_id = int(call.data.split('_')[2])
    
    session = get_session(call.from_user.id)
    session["data"]["course_major_id"] = major_id
    session["state"] = "admin_course_name"
    
    bot.edit_message_text(
        "Step 3/4: Enter Course name:",
        call.message.chat.id,
        call.message.message_id
    )
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "admin_course_name")
def handle_admin_course_name(message):
    session = get_session(message.from_user.id)
    session["data"]["course_name"] = message.text.strip()
    session["state"] = "admin_course_year"
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("1", callback_data="course_year_1"),
        types.InlineKeyboardButton("2", callback_data="course_year_2"),
        types.InlineKeyboardButton("3", callback_data="course_year_3"),
        types.InlineKeyboardButton("4", callback_data="course_year_4")
    )
    
    bot.send_message(message.chat.id, "Step 4/4: Select Year:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('course_year_'))
def handle_admin_course_year(call):
    year = call.data.split('_')[2]
    session = get_session(call.from_user.id)
    
    # Check if session data exists
    if "course_university_id" not in session["data"] or "course_major_id" not in session["data"]:
        bot.answer_callback_query(call.id, "❌ Session expired. Please start over.")
        show_admin_dashboard(call.message.chat.id)
        return
    
    university_id = session["data"]["course_university_id"]
    major_id = session["data"]["course_major_id"]
    name = session["data"]["course_name"]
    
    db = SessionLocal()
    
    try:
        course = crud.get_or_create_course(db, university_id, major_id, year, name)
        university = crud.get_university_by_id(db, university_id)
        major = crud.get_major_by_id(db, major_id)
        
        bot.edit_message_text(
            f"✅ Course created successfully!\n\n"
            f"📚 {name}\n"
            f"🏛 {university.name}\n"
            f"📖 {major.name} - Year {year}",
            call.message.chat.id,
            call.message.message_id
        )
        
        clear_session(call.from_user.id)
        show_admin_dashboard(call.message.chat.id)
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


# --- Course Edit/Delete Handlers ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_course_'))
def handle_edit_course(call):
    """Start course edit flow."""
    course_id = int(call.data.split('_')[-1])
    db = SessionLocal()
    
    try:
        course = crud.get_course_by_id(db, course_id)
        if not course:
            bot.answer_callback_query(call.id, "❌ Course not found!")
            return
        
        session = get_session(call.from_user.id)
        session["state"] = "admin_edit_course_name"
        session["data"]["edit_course_id"] = course_id
        
        bot.edit_message_text(
            f"✏️ Edit Course\n\n"
            f"Current: {course.name}\n"
            f"University: {course.university.name}\n"
            f"Major: {course.major.name}\n"
            f"Year: {course.year}\n\n"
            f"Enter new course name (or type 'year' to change year):",
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.message_handler(func=lambda msg: get_session(msg.from_user.id).get("state") == "admin_edit_course_name")
def handle_edit_course_name(message):
    """Process course name or year update."""
    db = SessionLocal()
    
    try:
        session = get_session(message.from_user.id)
        course_id = session["data"].get("edit_course_id")
        
        if not course_id:
            bot.send_message(message.chat.id, "❌ Session expired. Please start over.")
            show_admin_dashboard(message.chat.id)
            return
        
        course = crud.get_course_by_id(db, course_id)
        if not course:
            bot.send_message(message.chat.id, "❌ Course not found!")
            show_admin_dashboard(message.chat.id)
            return
        
        user_input = message.text.strip()
        
        # Check if user wants to change year
        if user_input.lower() == 'year':
            session["state"] = "admin_edit_course_year"
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("1", callback_data="edit_year_1"),
                types.InlineKeyboardButton("2", callback_data="edit_year_2"),
                types.InlineKeyboardButton("3", callback_data="edit_year_3"),
                types.InlineKeyboardButton("4", callback_data="edit_year_4")
            )
            bot.send_message(message.chat.id, f"Current year: {course.year}\n\nSelect new year:", reply_markup=markup)
            return
        
        # Update course name
        updated = crud.update_course(db, course_id, user_input, course.year)
        session["state"] = None
        
        bot.send_message(
            message.chat.id,
            f"✅ Course updated: '{course.name}' → '{updated.name}'",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_admin_dashboard(message.chat.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_year_'))
def handle_edit_course_year(call):
    """Process course year update."""
    new_year = call.data.split('_')[-1]
    db = SessionLocal()
    
    try:
        session = get_session(call.from_user.id)
        course_id = session["data"].get("edit_course_id")
        
        if not course_id:
            bot.answer_callback_query(call.id, "❌ Session expired!")
            return
        
        course = crud.get_course_by_id(db, course_id)
        if not course:
            bot.answer_callback_query(call.id, "❌ Course not found!")
            return
        
        updated = crud.update_course(db, course_id, course.name, new_year)
        session["state"] = None
        
        bot.edit_message_text(
            f"✅ Course year updated: {course.year} → {updated.year}",
            call.message.chat.id,
            call.message.message_id
        )
        show_admin_dashboard(call.message.chat.id)
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_course_'))
def handle_delete_course(call):
    """Show confirmation before deleting course."""
    course_id = int(call.data.split('_')[-1])
    db = SessionLocal()
    
    try:
        course = crud.get_course_by_id(db, course_id)
        if not course:
            bot.answer_callback_query(call.id, "❌ Course not found!")
            return
        
        # Count materials and professors
        materials = crud.get_materials_by_course(db, course_id)
        professors = db.query(models.Professor).filter(models.Professor.course_id == course_id).all()
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Confirm Delete", callback_data=f"confirm_delete_course_{course_id}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="admin_courses")
        )
        
        bot.edit_message_text(
            f"⚠️ Delete Course?\n\n"
            f"Course: {course.name}\n"
            f"University: {course.university.name}\n"
            f"Major: {course.major.name} - Year {course.year}\n\n"
            f"This will delete:\n"
            f"• {len(materials)} material(s)\n"
            f"• {len(professors)} assigned professor(s)\n"
            f"• All related uploads\n\n"
            f"This action cannot be undone!",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_course_'))
def handle_confirm_delete_course(call):
    """Execute course deletion."""
    course_id = int(call.data.split('_')[-1])
    db = SessionLocal()
    
    try:
        course = crud.get_course_by_id(db, course_id)
        if not course:
            bot.answer_callback_query(call.id, "❌ Course not found!")
            return
        
        course_name = course.name
        success = crud.delete_course(db, course_id)
        
        if success:
            bot.answer_callback_query(call.id, f"✅ Course '{course_name}' deleted!")
        else:
            bot.answer_callback_query(call.id, "❌ Failed to delete course!")
            return
    
    finally:
        db.close()
    
    # Return to course list with fresh db session
    handle_admin_courses(call)


@bot.callback_query_handler(func=lambda call: call.data == 'admin_professors')
def handle_admin_professors(call):
    """Show all professors with management options."""
    db = SessionLocal()
    
    try:
        professors = crud.get_all_professors(db)
        
        if not professors:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_admin_dashboard"))
            
            bot.edit_message_text(
                "📭 No professors yet",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            bot.answer_callback_query(call.id)
            return
        
        text = f"👨‍🏫 All Professors ({len(professors)}):\n\n"
        
        for prof in professors:
            text += f"• {prof.name}\n"
            text += f"  🔑 Code: {prof.code}\n"
            text += f"  {'✅' if prof.telegram_id else '❌'} Telegram\n"
            text += f"  {'🟢' if prof.active else '🔴'} {'Active' if prof.active else 'Inactive'}\n"
            if prof.course_id:
                course = crud.get_course_by_id(db, prof.course_id)
                if course:
                    text += f"  📚 {course.name}\n"
            else:
                text += f"  📚 No course assigned\n"
            text += "\n"
        
        markup = types.InlineKeyboardMarkup()
        
        # Add action buttons for each professor
        for prof in professors[:10]:  # Limit to 10
            row = []
            row.append(types.InlineKeyboardButton(f"✏️ {prof.name[:20]}", callback_data=f"edit_prof_{prof.id}"))
            row.append(types.InlineKeyboardButton("🗑", callback_data=f"delete_prof_{prof.id}"))
            row.append(types.InlineKeyboardButton("📚", callback_data=f"assign_prof_{prof.id}"))
            markup.row(*row)
        
        markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_admin_dashboard"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_prof_'))
def handle_edit_professor(call):
    """Start professor edit flow."""
    professor_id = int(call.data.split('_')[2])
    db = SessionLocal()
    
    try:
        professor = crud.get_professor_by_id(db, professor_id)
        if not professor:
            bot.answer_callback_query(call.id, "❌ Professor not found!")
            return
        
        session = get_session(call.from_user.id)
        session["data"]["edit_professor_id"] = professor_id
        session["state"] = "admin_edit_professor_name"
        
        bot.edit_message_text(
            f"✏️ Edit Professor\n\nCurrent name: {professor.name}\n\nEnter new name:",
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.message_handler(func=lambda m: get_session(m.from_user.id).get("state") == "admin_edit_professor_name")
def handle_edit_professor_name(message):
    """Handle professor name edit."""
    db = SessionLocal()
    
    try:
        session = get_session(message.from_user.id)
        professor_id = session["data"].get("edit_professor_id")
        
        if not professor_id:
            bot.send_message(message.chat.id, "❌ Session expired. Please start over.")
            show_admin_dashboard(message.chat.id)
            return
        
        new_name = message.text.strip()
        
        if not new_name:
            bot.send_message(
                message.chat.id,
                "❌ Professor name cannot be empty!",
                reply_markup=types.ReplyKeyboardRemove()
            )
            return
        
        professor = crud.update_professor(db, professor_id, name=new_name)
        
        if not professor:
            bot.send_message(message.chat.id, "❌ Professor not found!")
            show_admin_dashboard(message.chat.id)
            return
        
        session["state"] = None
        
        bot.send_message(
            message.chat.id,
            f"✅ Professor updated: '{professor.name}'!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_admin_dashboard(message.chat.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_prof_'))
def handle_delete_professor(call):
    """Show confirmation before deleting professor."""
    professor_id = int(call.data.split('_')[2])
    db = SessionLocal()
    
    try:
        professor = crud.get_professor_by_id(db, professor_id)
        if not professor:
            bot.answer_callback_query(call.id, "❌ Professor not found!")
            return
        
        # Count uploads
        upload_count = db.query(models.Material).filter(models.Material.uploader_id == professor_id).count()
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Confirm Delete", callback_data=f"confirm_delete_prof_{professor_id}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="admin_professors")
        )
        
        warning = f"⚠️ Delete Professor?\n\nName: {professor.name}\nCode: {professor.code}\n\n"
        if upload_count > 0:
            warning += f"This professor has {upload_count} uploaded material(s).\nMaterials will remain but won't be linked to this professor.\n\n"
        warning += "This action cannot be undone!"
        
        bot.edit_message_text(warning, call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_prof_'))
def handle_confirm_delete_professor(call):
    """Confirm and delete professor."""
    professor_id = int(call.data.split('_')[3])
    db = SessionLocal()
    
    try:
        professor = crud.get_professor_by_id(db, professor_id)
        name = professor.name if professor else "Unknown"
        
        if crud.delete_professor(db, professor_id):
            bot.answer_callback_query(call.id, f"✅ '{name}' deleted!")
            success = True
        else:
            bot.answer_callback_query(call.id, "❌ Failed to delete")
            success = False
    
    finally:
        db.close()
    
    # Show professor list with fresh session
    if success:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        db = SessionLocal()
        try:
            professors = crud.get_all_professors(db)
            
            if not professors:
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_admin_dashboard"))
                bot.send_message(call.message.chat.id, "📭 No professors yet", reply_markup=markup)
                return
            
            text = f"👨‍🏫 All Professors ({len(professors)}):\n\n"
            
            for prof in professors:
                text += f"• {prof.name}\n"
                text += f"  🔑 Code: {prof.code}\n"
                text += f"  {'✅' if prof.telegram_id else '❌'} Telegram\n"
                text += f"  {'🟢' if prof.active else '🔴'} {'Active' if prof.active else 'Inactive'}\n"
                if prof.course_id:
                    course = crud.get_course_by_id(db, prof.course_id)
                    if course:
                        text += f"  📚 {course.name}\n"
                else:
                    text += f"  📚 No course assigned\n"
                text += "\n"
            
            markup = types.InlineKeyboardMarkup()
            for prof in professors[:10]:
                row = []
                row.append(types.InlineKeyboardButton(f"✏️ {prof.name[:20]}", callback_data=f"edit_prof_{prof.id}"))
                row.append(types.InlineKeyboardButton("🗑", callback_data=f"delete_prof_{prof.id}"))
                row.append(types.InlineKeyboardButton("📚", callback_data=f"assign_prof_{prof.id}"))
                markup.row(*row)
            
            markup.row(types.InlineKeyboardButton("◀️ Back", callback_data="back_admin_dashboard"))
            bot.send_message(call.message.chat.id, text, reply_markup=markup)
        finally:
            db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('assign_prof_'))
def handle_assign_professor(call):
    """Start course assignment flow."""
    try:
        print(f"🔍 DEBUG: assign_prof handler called with data: {call.data}")
        professor_id = int(call.data.split('_')[2])
        db = SessionLocal()
        
        try:
            professor = crud.get_professor_by_id(db, professor_id)
            if not professor:
                print(f"❌ DEBUG: Professor {professor_id} not found")
                bot.answer_callback_query(call.id, "❌ Professor not found!")
                return
            
            print(f"✅ DEBUG: Professor found: {professor.name}")
            
            courses = crud.get_all_courses(db)
            
            if not courses:
                bot.answer_callback_query(call.id, "❌ No courses available!")
                return
            
            session = get_session(call.from_user.id)
            session["data"]["assign_professor_id"] = professor_id
            
            markup = types.InlineKeyboardMarkup()
            
            # Group courses by university and major
            for course in courses[:20]:  # Limit to 20
                course_label = f"{course.name} (Y{course.year})"
                markup.row(types.InlineKeyboardButton(
                    course_label[:40],
                    callback_data=f"assign_course_{professor_id}_{course.id}"
                ))
            
            # Add unassign option
            if professor.course_id:
                markup.row(types.InlineKeyboardButton("❌ Unassign Course", callback_data=f"unassign_prof_{professor_id}"))
            
            markup.row(types.InlineKeyboardButton("◀️ Cancel", callback_data="admin_professors"))
            
            current_course = ""
            if professor.course_id:
                course = crud.get_course_by_id(db, professor.course_id)
                if course:
                    current_course = f"\nCurrent: {course.name}"
            
            bot.edit_message_text(
                f"📚 Assign Course\n\nProfessor: {professor.name}{current_course}\n\nSelect a course:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            bot.answer_callback_query(call.id)
        
        finally:
            db.close()
    
    except Exception as e:
        print(f"❌ ERROR in handle_assign_professor: {e}")
        import traceback
        traceback.print_exc()
        bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('assign_course_'))
def handle_assign_course_confirm(call):
    """Confirm course assignment."""
    parts = call.data.split('_')
    professor_id = int(parts[2])
    course_id = int(parts[3])
    
    db = SessionLocal()
    
    try:
        professor = crud.update_professor_course(db, professor_id, course_id)
        course = crud.get_course_by_id(db, course_id)
        
        if professor and course:
            bot.answer_callback_query(call.id, f"✅ Assigned to {course.name}")
            success = True
        else:
            bot.answer_callback_query(call.id, "❌ Assignment failed")
            success = False
    
    finally:
        db.close()
    
    # Return to professor list
    if success:
        call.data = "admin_professors"
        handle_admin_professors(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith('unassign_prof_'))
def handle_unassign_professor(call):
    """Unassign professor from course."""
    professor_id = int(call.data.split('_')[2])
    db = SessionLocal()
    
    try:
        professor = crud.get_professor_by_id(db, professor_id)
        if professor:
            professor.course_id = None
            db.commit()
            bot.answer_callback_query(call.id, "✅ Course unassigned")
            success = True
        else:
            bot.answer_callback_query(call.id, "❌ Professor not found")
            success = False
    
    finally:
        db.close()
    
    # Return to professor list
    if success:
        call.data = "admin_professors"
        handle_admin_professors(call)


@bot.callback_query_handler(func=lambda call: call.data == 'back_admin_dashboard')
def handle_back_admin_dashboard(call):
    """Return to admin dashboard."""
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_admin_dashboard(call.message.chat.id)
    bot.answer_callback_query(call.id)


# Error handler
@bot.message_handler(func=lambda message: True)
def handle_other(message):
    """Handle unrecognized messages."""
    bot.send_message(
        message.chat.id,
        "❓ I didn't understand that. Use /start to begin."
    )


def run_bot():
    """Run the Telegram bot."""
    print("🤖 Starting Telegram bot...")
    bot_info = bot.get_me()
    print(f"Bot username: @{bot_info.username}")
    
    if config.WEBHOOK_URL:
        print(f"📡 Using webhook mode: {config.WEBHOOK_URL}")
        # Webhook will be set up in FastAPI main.py
        # Bot will receive updates via webhook endpoint
    else:
        print("🔄 Using polling mode")
        bot.infinity_polling()


if __name__ == "__main__":
    config.validate()
    run_bot()
