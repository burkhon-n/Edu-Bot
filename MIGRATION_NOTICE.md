# Database Migration Notice

## Major Schema Changes

The database schema has been completely restructured to implement proper administrative control:

### Changes

1. **New Tables:**
   - `universities` - Only admins can create universities
   - `majors` - Only admins can create majors (linked to universities)

2. **Updated Relationships:**
   - `courses` now link to `universities` and `majors` via foreign keys
   - `professors` now link to specific `courses` (one course per professor)
   - `students` now link to `universities` and `majors` via foreign keys

3. **Removed Fields:**
   - Removed free-text `university` and `major` fields from `courses`
   - Removed ability for students to create universities/majors

### Migration Steps

**⚠️ This requires deleting the existing database!**

```bash
# 1. Backup your old database (if needed)
cp coursemate.db coursemate.db.backup

# 2. Delete the old database
rm coursemate.db

# 3. Run the seed script to create new schema
python seed_db.py

# 4. Start the bot
./run.sh
```

### New Workflow

1. **Admin** creates universities via bot
2. **Admin** creates majors for each university via bot
3. **Admin** creates courses linked to university/major via bot
4. **Admin** creates professors and assigns them to courses via bot
5. **Students** register by selecting from existing universities/majors
6. **Professors** upload materials only to their assigned course

### Admin Commands

After running seed_db.py, use `/admin` command to:
- Create universities
- Create majors
- Create courses
- Create professors (with course assignment)
- Approve students

### Test Data

The seed script creates:
- **University:** Tech University
- **Majors:** Computer Science, Mathematics
- **Courses:** 
  - Introduction to Programming (CS Year 1)
  - Data Structures and Algorithms (CS Year 1)
  - Database Systems (CS Year 2)
- **Professor:** Dr. Sample Professor (assigned to Intro to Programming)
- **Student:** U123456 (verified, CS Year 1)
