# 🏫 School CBT System
**Computer-Based Testing Platform** — One server, up to 300 student clients on local network.

---

## 📁 Folder Structure

```
cbt-system/
├── main.py                        # FastAPI app entry point
├── setup.py                       # One-time setup & seed script
├── requirements.txt
├── data/
│   └── cbt.db                     # SQLite database (auto-created)
├── backend/
│   ├── models/
│   │   └── database.py            # SQLAlchemy models + DB setup
│   ├── routers/
│   │   ├── admin.py               # All admin API endpoints
│   │   └── student.py             # All student API endpoints
│   └── utils/
│       └── auth.py                # JWT auth + password hashing
└── frontend/
    ├── shared/
    │   ├── style.css              # Global dark-theme CSS
    │   └── app.js                 # Shared JS utilities (toast, api, etc.)
    ├── admin/
    │   ├── login.html             # Admin login
    │   ├── layout.css             # Sidebar + topbar layout
    │   ├── dashboard.html         # Stats + recent results
    │   ├── exams.html             # Create/manage exams
    │   ├── questions.html         # Add/edit/bulk-import questions
    │   ├── students.html          # Add/edit/bulk-import students
    │   ├── results.html           # View + export results
    │   └── monitor.html           # Live exam monitoring
    └── student/
        ├── login.html             # Student login
        ├── exams.html             # Available exams list
        ├── exam.html              # Exam-taking interface (timer, nav, auto-save)
        └── result.html            # Result + question review
```

---

## 🗃 Database Schema

```sql
-- Admins
CREATE TABLE admins (
    id          INTEGER PRIMARY KEY,
    username    TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name   TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Students
CREATE TABLE students (
    id          INTEGER PRIMARY KEY,
    student_id  TEXT UNIQUE NOT NULL,   -- e.g. "STU001"
    full_name   TEXT NOT NULL,
    class_name  TEXT,
    password_hash TEXT NOT NULL,
    is_active   BOOLEAN DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Exams
CREATE TABLE exams (
    id                      INTEGER PRIMARY KEY,
    title                   TEXT NOT NULL,
    subject                 TEXT,
    description             TEXT,
    duration_minutes        INTEGER DEFAULT 60,
    total_marks             REAL DEFAULT 0,
    pass_marks              REAL DEFAULT 0,
    randomize_questions     BOOLEAN DEFAULT 1,
    randomize_options       BOOLEAN DEFAULT 0,
    show_result_immediately BOOLEAN DEFAULT 1,
    is_active               BOOLEAN DEFAULT 0,
    start_time              DATETIME,
    end_time                DATETIME,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by              INTEGER REFERENCES admins(id)
);

-- Questions
CREATE TABLE questions (
    id            INTEGER PRIMARY KEY,
    exam_id       INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_type TEXT DEFAULT 'mcq',     -- mcq | true_false
    options       JSON,                   -- {"A":"...","B":"...","C":"...","D":"..."}
    correct_answer TEXT NOT NULL,         -- "A" / "B" / "C" / "D"
    marks         REAL DEFAULT 1.0,
    order_index   INTEGER DEFAULT 0
);

-- Exam Sessions (one per student per exam)
CREATE TABLE exam_sessions (
    id             INTEGER PRIMARY KEY,
    student_id     INTEGER REFERENCES students(id),
    exam_id        INTEGER REFERENCES exams(id) ON DELETE CASCADE,
    started_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    submitted_at   DATETIME,
    time_remaining INTEGER,               -- seconds left at last save
    answers        JSON DEFAULT '{}',     -- {question_id: "A"}
    question_order JSON DEFAULT '[]',     -- randomized list of question IDs
    score          REAL,
    total_marks    REAL,
    percentage     REAL,
    is_submitted   BOOLEAN DEFAULT 0,
    ip_address     TEXT
);
```

---

## ⚙️ Requirements

- Python 3.9 or higher
- pip
- A computer on the local network (Windows, macOS, or Linux)
- Students connect via any modern web browser (Chrome, Firefox, Edge)

---

## 🚀 Setup & Run (Step by Step)

### Step 1 — Download / Clone the project

```bash
# If you have git:
git clone <repo-url> cbt-system
cd cbt-system

# Or extract the zip and cd into it
cd cbt-system
```

### Step 2 — Install Python dependencies

```bash
pip install -r requirements.txt
# On Linux/macOS you may need:
pip install -r requirements.txt --break-system-packages
# Or use a virtual environment:
python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### Step 3 — Run the setup script (first time only)

```bash
python setup.py
```

This will:
- Create the `data/cbt.db` SQLite database
- Create the default admin account: `admin` / `admin123`
- Add 3 demo students (STU001–STU003, password: `pass123`)

### Step 4 — Start the server

```bash
python main.py
```

Output will show:
```
==================================================
🏫 School CBT System
==================================================
Local access:    http://localhost:8000
Network access:  http://192.168.1.10:8000
Admin panel:     http://localhost:8000/admin
==================================================
```

### Step 5 — Access the system

| Who        | URL                                  | Default Credentials          |
|------------|--------------------------------------|------------------------------|
| Admin      | `http://<server-ip>:8000/admin`      | `admin` / `admin123`         |
| Students   | `http://<server-ip>:8000`            | Student ID + password        |

> **Find your server IP:**
> - Windows: `ipconfig` → look for IPv4 Address
> - Linux/macOS: `ip addr` or `ifconfig`

---

## 👩‍💻 Admin Workflow

1. **Login** at `/admin` → Dashboard
2. **Create an Exam**: Exams → Create Exam → set title, duration, pass marks
3. **Add Questions**: Click "✏ Questions" on the exam card
   - Add manually (MCQ or True/False)
   - Or bulk import via CSV (`question,type,A,B,C,D,answer,marks`)
4. **Add Students**: Students → Add Student or Bulk Import CSV (`student_id,full_name,class_name,password`)
5. **Activate the Exam**: Click "▶ Activate" on the exam card — students can now see it
6. **Monitor Live**: Monitor tab shows who's testing, time remaining, answers progress
7. **View Results**: Results tab — filter by exam, view per-student detail, export CSV

---

## 🎓 Student Workflow

1. Open browser → `http://<server-ip>:8000`
2. Login with Student ID and password
3. Click **Start Exam** on an available exam
4. Answer questions (auto-saved every keystroke + every 30 seconds)
5. Navigate freely using the question grid panel
6. Submit or wait for the timer to auto-submit
7. View score and question review immediately (if enabled by admin)

---

## 🌐 Network Setup for 300 Students

1. Connect the admin laptop and all student laptops to the **same Wi-Fi or LAN switch**
2. Ensure the admin laptop's **firewall allows port 8000**:
   ```bash
   # Windows:
   netsh advfirewall firewall add rule name="CBT System" dir=in action=allow protocol=TCP localport=8000

   # Linux:
   sudo ufw allow 8000
   ```
3. Students open their browser and go to: `http://<admin-laptop-IP>:8000`
4. For better performance with 300+ students, run uvicorn with multiple workers:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

---

## 🔐 Security Notes

- **Change the default admin password** immediately after first login (edit in Students page or DB)
- **Change the SECRET_KEY** in `backend/utils/auth.py` before production use
- For a real deployment, use HTTPS (nginx + certbot) in front of uvicorn
- Student sessions expire after 12 hours

---

## 📊 Features Summary

| Feature                     | Status |
|-----------------------------|--------|
| Admin login (JWT cookie)    | ✅     |
| Create / edit / delete exams| ✅     |
| MCQ + True/False questions  | ✅     |
| Bulk import questions (CSV) | ✅     |
| Add / edit / delete students| ✅     |
| Bulk import students (CSV)  | ✅     |
| Student login               | ✅     |
| Countdown timer             | ✅     |
| Auto-submit on timeout      | ✅     |
| Auto-save answers           | ✅     |
| Randomize question order    | ✅     |
| Randomize answer options    | ✅     |
| Question navigator panel    | ✅     |
| Instant auto-scoring        | ✅     |
| Show/hide result to student | ✅     |
| Question review after exam  | ✅     |
| Admin results dashboard     | ✅     |
| Export results to CSV       | ✅     |
| Live exam monitoring        | ✅     |
| Per-student result detail   | ✅     |
| Prevent back-navigation     | ✅     |

---

## 🛠 Troubleshooting

| Problem | Solution |
|---------|----------|
| Port 8000 already in use | Change port: `python main.py --port 8001` |
| Students can't connect | Check firewall, confirm same network, use IP not hostname |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| DB errors | Delete `data/cbt.db` and re-run `python setup.py` |
| Slow with 300 students | Use `uvicorn main:app --workers 4 --host 0.0.0.0 --port 8000` |
