"""
Database seeding script for initial setup.

Creates admin, sample professor, course, and student for testing.
"""

import sys
import secrets
from app.database import SessionLocal, init_db
from app import crud
from app.config import config


def seed_database():
    """Seed database with initial data."""
    print("🌱 Seeding database...")
    
    # Initialize database
    init_db()
    
    db = SessionLocal()
    
    try:
        # Create admin if BOT_OWNER_TELEGRAM_ID is set
        if config.BOT_OWNER_TELEGRAM_ID and config.BOT_OWNER_TELEGRAM_ID != 0:
            telegram_id = str(config.BOT_OWNER_TELEGRAM_ID)
            admin = crud.get_admin_by_telegram_id(db, telegram_id)
            if not admin:
                admin = crud.create_admin(db, telegram_id)
                print(f"✅ Created admin with Telegram ID: {telegram_id}")
            else:
                print(f"ℹ️  Admin already exists: {telegram_id}")
        else:
            print("⚠️  BOT_OWNER_TELEGRAM_ID not set, skipping admin creation")
        
        # Create sample university
        university = crud.get_university_by_name(db, "Tech University")
        if not university:
            university = crud.create_university(db, "Tech University")
            print(f"✅ Created university: {university.name}")
        else:
            print(f"ℹ️  University '{university.name}' already exists")
        
        # Create sample majors
        cs_major = crud.get_major_by_name(db, university.id, "Computer Science")
        if not cs_major:
            cs_major = crud.create_major(db, university.id, "Computer Science")
            print(f"✅ Created major: Computer Science")
        else:
            print(f"ℹ️  Major 'Computer Science' already exists")
        
        math_major = crud.get_major_by_name(db, university.id, "Mathematics")
        if not math_major:
            math_major = crud.create_major(db, university.id, "Mathematics")
            print(f"✅ Created major: Mathematics")
        else:
            print(f"ℹ️  Major 'Mathematics' already exists")
        
        # Create sample courses
        course1 = crud.get_or_create_course(
            db,
            university_id=university.id,
            major_id=cs_major.id,
            year="1",
            name="Introduction to Programming"
        )
        print(f"✅ Created course: {course1.name}")
        
        course2 = crud.get_or_create_course(
            db,
            university_id=university.id,
            major_id=cs_major.id,
            year="1",
            name="Data Structures and Algorithms"
        )
        print(f"✅ Created course: {course2.name}")
        
        course3 = crud.get_or_create_course(
            db,
            university_id=university.id,
            major_id=cs_major.id,
            year="2",
            name="Database Systems"
        )
        print(f"✅ Created course: {course3.name}")
        
        # Create sample professor and assign to a course
        prof_code = f"PROF_{secrets.token_hex(4).upper()}"
        existing_prof = crud.get_professor_by_code(db, prof_code)
        
        if not existing_prof:
            professor = crud.create_professor(db, "Dr. Sample Professor", prof_code, course_id=course1.id)
            print(f"✅ Created professor: Dr. Sample Professor")
            print(f"   Professor Code: {prof_code}")
            print(f"   Assigned to: {course1.name}")
            print(f"   ⚠️  SAVE THIS CODE - you'll need it to log in!")
        else:
            print(f"ℹ️  Professor code {prof_code} already exists")
        
        # Create sample verified student
        student = crud.get_student_by_university_id(db, "U123456")
        if not student:
            student = crud.create_student(
                db,
                university_id="U123456",
                db_university_id=university.id,
                db_major_id=cs_major.id,
                year="1",
                name="Test Student",
                verified=True
            )
            print(f"✅ Created verified student: U123456")
        else:
            print(f"ℹ️  Student U123456 already exists")
        
        print("\n" + "="*60)
        print("🎉 Database seeding completed!")
        print("="*60)
        print("\n📝 Quick Start:")
        print(f"1. University: {university.name}")
        print(f"2. Majors: Computer Science, Mathematics")
        print(f"3. Professor Code: {prof_code}")
        print(f"4. Test Student ID: U123456 (already verified)")
        print(f"5. Admin Telegram ID: {config.BOT_OWNER_TELEGRAM_ID or 'Not set'}")
        print("\n💡 Next steps:")
        print("1. Start the bot: python -m app.bot")
        print("2. Start the API: uvicorn app.main:app --reload")
        print("3. Or use: ./run.sh to start both")
        print("\n")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
