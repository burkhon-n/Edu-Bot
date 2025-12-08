# 🎓 CourseMateBot - Your University Study Buddy

**A Telegram bot that helps students get course materials and take quizzes. Professors can upload files and students can study from them.**

---

## 🤔 What Does This Bot Do?

Think of it as a digital library + quiz app for your university:
- **Students** can download lecture notes and take practice quizzes
- **Professors** can upload materials and they automatically turn into quizzes
- **Everyone** uses Telegram - no new app to install!

---

## 🚀 Getting Started (Super Simple)

### Step 1: Get Your Tools Ready

You need 3 things:
1. **Python** installed on your computer (version 3.11 or newer)
2. A **Telegram Bot Token** - get it from [@BotFather](https://t.me/botfather) on Telegram
3. An **OpenAI API Key** - sign up at [OpenAI](https://platform.openai.com/)

### Step 2: Download & Install

```bash
# Go to the folder
cd "Edu Bot"

# Create a virtual environment (keeps things organized)
python -m venv .venv

# Turn on the virtual environment
source .venv/bin/activate
# (Windows users: .venv\Scripts\activate)

# Install all the code libraries needed
pip install -r requirements.txt
```

### Step 3: Set Up Your Secrets

```bash
# Copy the example file
cp .env.example .env

# Edit it with your info
nano .env
```

Put in these 4 things:
- `TELEGRAM_TOKEN` = Your bot token from BotFather
- `OPENAI_API_KEY` = Your OpenAI API key
- `BOT_OWNER_TELEGRAM_ID` = Your Telegram user ID (find it with [@userinfobot](https://t.me/userinfobot))
- `ADMIN_CODE` = Make up a secret password for admin access

### Step 4: Create the Database

```bash
python seed_db.py
```

This creates a test database with some sample courses and users.

### Step 5: Start Everything!

```bash
chmod +x run.sh
./run.sh
```

✅ Done! Your bot is now running!

---

## 📱 How to Use the Bot

### For Students

1. **Find your bot on Telegram** and click START
2. Choose **"👨‍🎓 Student"**
3. Pick your university, major, and year
4. Enter your full name when asked
5. Enter your University ID (like "U123456")
6. Wait for approval (admin will approve you)
7. Once approved, you can:
   - **Browse courses** by year
   - **Download materials** (PDFs, slides, etc.)
   - **Take quizzes** in 3 difficulty levels
   - **Edit your name** anytime from your profile

### For Professors

1. Start the bot and choose **"👨‍🏫 Professor"**
2. Enter your professor code (you'll get this from admin)
3. Use the dashboard to:
   - **Upload materials** for your course
   - **Delete materials** if you made a mistake
   - **View all your uploads** organized by week

**To upload a file**, use this command in your terminal:

```bash
curl -X POST "http://localhost:8000/upload-material/" \
  -F "university=Your University Name" \
  -F "major=Computer Science" \
  -F "course=Introduction to Programming" \
  -F "year=1" \
  -F "week=1" \
  -F "professor_code=YOUR_CODE_HERE" \
  -F "description=Week 1 lecture notes" \
  -F "file=@/path/to/your/file.pdf"
```

### For Admins

1. Send `/admin` to the bot
2. Enter your admin code
3. You can:
   - **Approve students** who register
   - **Create professor codes**
   - **View statistics**

---

## 🎯 Key Features Explained

### Personalized Quizzes
- When a student wants a quiz, the bot **generates it on-the-spot**
- Each student gets **different questions** - no cheating!
- Quizzes use **ALL materials** from that week, not just one file
- Questions are **AI-generated** from the actual course content

### Professor Material Management
- Upload PDFs, Word docs, or PowerPoints
- **No automatic quiz generation** - quizzes only made when students request them
- **Delete materials** easily if you uploaded wrong file
- See all your materials organized by week

### Smart Student Registration
- Students enter their **full name** (not just Telegram username)
- Can **edit name** anytime from profile
- **Admin-only approval** - professors can't approve students
- Secure University ID verification

---

## 📊 What's Inside?

```
Your Files Are Organized Like This:

storage/
└── Tech University/
    └── Computer Science/
        └── Intro to Programming/
            └── Week 1/
                ├── lecture_notes.pdf
                ├── slides.pptx
                └── tutorial.docx
```

Database stores:
- Who you are (student/professor/admin)
- What courses exist
- What materials are uploaded
- Quiz questions and answers

---

## 🆘 Common Problems & Solutions

### "Bot doesn't respond when I message it"
- Check if `./run.sh` is still running
- Make sure your `TELEGRAM_TOKEN` is correct
- Try restarting: press Ctrl+C then run `./run.sh` again

### "Can't upload files"
- Make sure the `storage/` folder exists
- Check you have disk space
- Verify your professor code is correct

### "Quiz generation failed"
- Check your OpenAI API key is valid
- Make sure you have credits in your OpenAI account
- The file might be too small (needs at least 100 words)

### "Database errors"
If things get really messed up, start fresh:
```bash
rm coursemate.db
python seed_db.py
./run.sh
```

---

## 🔒 Security Features

- ✅ Only approved professors can upload
- ✅ Only verified students can download
- ✅ Admin code protects admin features
- ✅ Each student gets unique quizzes
- ✅ Files are stored safely

---

## 🎓 How Quizzes Work

1. **Professor uploads** a PDF or document
2. File is saved but **no quiz yet**
3. **Student clicks "Take Quiz"**
4. Bot reads **ALL files from that week**
5. AI generates **unique questions** for that student
6. Student answers → gets instant results
7. Can retake with **different questions**

---

## 📝 Project Files Explained

```
Edu Bot/
├── app/                    # All the code
│   ├── bot.py             # Telegram bot logic
│   ├── main.py            # Web API for uploads
│   ├── models.py          # Database structure
│   ├── crud.py            # Database operations
│   └── tasks.py           # Quiz generation
├── storage/               # Where files are saved
├── .env                   # Your secret keys (don't share!)
├── requirements.txt       # List of libraries needed
├── seed_db.py            # Creates test data
└── run.sh                # Starts everything
```

---

## 💡 Tips for Success

1. **Start small** - Add 1 course, 1 professor, a few students first
2. **Test everything** - Upload a file, take a quiz, make sure it works
3. **Keep backups** - Copy your database file sometimes
4. **Check logs** - If something breaks, read the error messages
5. **Ask for help** - Open an issue on GitHub if stuck

---

## 🎉 That's It!

You now have a working university bot! Students can study, professors can upload, and everyone's happy.

**Questions?** Check the troubleshooting section above or create an issue.

**Made with ❤️ for students who want to study better**

---

## 🔧 Advanced (Optional)

### Running with Docker
```bash
docker-compose up
```

### Using PostgreSQL Instead of SQLite
Change `.env`:
```
DATABASE_URL=postgresql://user:password@localhost/coursemate
```

### Deploy to a Server
1. Get a VPS (DigitalOcean, AWS, etc.)
2. Install Docker
3. Clone this code
4. Run `docker-compose up -d`
5. Point your domain to the server

---

**Need more help?** Read the detailed sections above or open an issue!
