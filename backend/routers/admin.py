from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime
import json, random, io, csv

from ..models.database import get_db, Admin, Student, Exam, Question, ExamSession
from ..utils.auth import hash_password, verify_password, create_token, get_current_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login")
async def admin_login(response: Response, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin or not verify_password(password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"sub": str(admin.id), "username": admin.username}, role="admin")
    response.set_cookie("admin_token", token, httponly=True, max_age=43200, samesite="lax")
    return {"message": "Login successful", "username": admin.username, "full_name": admin.full_name}


@router.post("/logout")
async def admin_logout(response: Response):
    response.delete_cookie("admin_token")
    return {"message": "Logged out"}


@router.get("/me")
async def get_me(current=Depends(get_current_admin), db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.id == int(current["sub"])).first()
    return {"username": admin.username, "full_name": admin.full_name}


# ── DASHBOARD ──────────────────────────────────────────────
@router.get("/dashboard")
async def dashboard(current=Depends(get_current_admin), db: Session = Depends(get_db)):
    total_students = db.query(func.count(Student.id)).scalar()
    total_exams = db.query(func.count(Exam.id)).scalar()
    active_exams = db.query(func.count(Exam.id)).filter(Exam.is_active == True).scalar()
    active_sessions = db.query(func.count(ExamSession.id)).filter(ExamSession.is_submitted == False).scalar()
    recent_sessions = db.query(ExamSession).filter(ExamSession.is_submitted == True).order_by(ExamSession.submitted_at.desc()).limit(10).all()
    sessions_data = []
    for s in recent_sessions:
        sessions_data.append({
            "student_name": s.student.full_name,
            "student_id": s.student.student_id,
            "exam_title": s.exam.title,
            "score": s.score,
            "total": s.total_marks,
            "percentage": round(s.percentage, 1) if s.percentage else 0,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None
        })
    return {"total_students": total_students, "total_exams": total_exams,
            "active_exams": active_exams, "active_sessions": active_sessions,
            "recent_sessions": sessions_data}


# ── EXAMS ──────────────────────────────────────────────────
@router.get("/exams")
async def list_exams(current=Depends(get_current_admin), db: Session = Depends(get_db)):
    exams = db.query(Exam).order_by(Exam.created_at.desc()).all()
    result = []
    for e in exams:
        q_count = db.query(func.count(Question.id)).filter(Question.exam_id == e.id).scalar()
        s_count = db.query(func.count(ExamSession.id)).filter(ExamSession.exam_id == e.id, ExamSession.is_submitted == True).scalar()
        result.append({"id": e.id, "title": e.title, "subject": e.subject,
                       "duration_minutes": e.duration_minutes, "total_marks": e.total_marks,
                       "pass_marks": e.pass_marks, "is_active": e.is_active,
                       "randomize_questions": e.randomize_questions,
                       "show_result_immediately": e.show_result_immediately,
                       "question_count": q_count, "submission_count": s_count,
                       "created_at": e.created_at.isoformat()})
    return result


@router.post("/exams")
async def create_exam(
    title: str = Form(...), subject: str = Form(""), description: str = Form(""),
    duration_minutes: int = Form(60), pass_marks: float = Form(0),
    randomize_questions: bool = Form(True), randomize_options: bool = Form(False),
    show_result_immediately: bool = Form(True),
    current=Depends(get_current_admin), db: Session = Depends(get_db)
):
    exam = Exam(title=title, subject=subject, description=description,
                duration_minutes=duration_minutes, pass_marks=pass_marks,
                randomize_questions=randomize_questions, randomize_options=randomize_options,
                show_result_immediately=show_result_immediately,
                created_by=int(current["sub"]))
    db.add(exam); db.commit(); db.refresh(exam)
    return {"id": exam.id, "message": "Exam created successfully"}


@router.get("/exams/{exam_id}")
async def get_exam(exam_id: int, current=Depends(get_current_admin), db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(404, "Exam not found")
    questions = []
    for q in sorted(exam.questions, key=lambda x: x.order_index):
        questions.append({"id": q.id, "question_text": q.question_text, "question_type": q.question_type,
                          "options": q.options, "correct_answer": q.correct_answer,
                          "marks": q.marks, "order_index": q.order_index})
    return {"id": exam.id, "title": exam.title, "subject": exam.subject,
            "description": exam.description, "duration_minutes": exam.duration_minutes,
            "total_marks": exam.total_marks, "pass_marks": exam.pass_marks,
            "is_active": exam.is_active, "randomize_questions": exam.randomize_questions,
            "randomize_options": exam.randomize_options,
            "show_result_immediately": exam.show_result_immediately,
            "questions": questions}


@router.put("/exams/{exam_id}")
async def update_exam(
    exam_id: int, title: str = Form(...), subject: str = Form(""),
    description: str = Form(""), duration_minutes: int = Form(60),
    pass_marks: float = Form(0), randomize_questions: bool = Form(True),
    randomize_options: bool = Form(False), show_result_immediately: bool = Form(True),
    current=Depends(get_current_admin), db: Session = Depends(get_db)
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam: raise HTTPException(404, "Exam not found")
    exam.title = title; exam.subject = subject; exam.description = description
    exam.duration_minutes = duration_minutes; exam.pass_marks = pass_marks
    exam.randomize_questions = randomize_questions; exam.randomize_options = randomize_options
    exam.show_result_immediately = show_result_immediately
    db.commit()
    return {"message": "Exam updated"}


@router.patch("/exams/{exam_id}/toggle")
async def toggle_exam(exam_id: int, current=Depends(get_current_admin), db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam: raise HTTPException(404, "Exam not found")
    exam.is_active = not exam.is_active
    if exam.is_active:
        exam.start_time = datetime.utcnow()
    db.commit()
    return {"is_active": exam.is_active, "message": f"Exam {'activated' if exam.is_active else 'deactivated'}"}


@router.delete("/exams/{exam_id}")
async def delete_exam(exam_id: int, current=Depends(get_current_admin), db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam: raise HTTPException(404, "Exam not found")
    db.delete(exam); db.commit()
    return {"message": "Exam deleted"}


# ── QUESTIONS ──────────────────────────────────────────────
@router.post("/exams/{exam_id}/questions")
async def add_question(
    exam_id: int, question_text: str = Form(...), question_type: str = Form("mcq"),
    option_a: str = Form(""), option_b: str = Form(""), option_c: str = Form(""),
    option_d: str = Form(""), correct_answer: str = Form(...), marks: float = Form(1.0),
    current=Depends(get_current_admin), db: Session = Depends(get_db)
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam: raise HTTPException(404, "Exam not found")
    options = None
    if question_type == "mcq":
        options = {"A": option_a, "B": option_b, "C": option_c, "D": option_d}
    elif question_type == "true_false":
        options = {"A": "True", "B": "False"}
    max_idx = db.query(func.max(Question.order_index)).filter(Question.exam_id == exam_id).scalar() or 0
    q = Question(exam_id=exam_id, question_text=question_text, question_type=question_type,
                 options=options, correct_answer=correct_answer.upper(), marks=marks, order_index=max_idx + 1)
    db.add(q); db.commit()
    exam.total_marks = db.query(func.sum(Question.marks)).filter(Question.exam_id == exam_id).scalar() or 0
    db.commit()
    return {"id": q.id, "message": "Question added"}


@router.put("/exams/{exam_id}/questions/{q_id}")
async def update_question(
    exam_id: int, q_id: int, question_text: str = Form(...), question_type: str = Form("mcq"),
    option_a: str = Form(""), option_b: str = Form(""), option_c: str = Form(""),
    option_d: str = Form(""), correct_answer: str = Form(...), marks: float = Form(1.0),
    current=Depends(get_current_admin), db: Session = Depends(get_db)
):
    q = db.query(Question).filter(Question.id == q_id, Question.exam_id == exam_id).first()
    if not q: raise HTTPException(404, "Question not found")
    q.question_text = question_text; q.question_type = question_type
    q.correct_answer = correct_answer.upper(); q.marks = marks
    if question_type == "mcq":
        q.options = {"A": option_a, "B": option_b, "C": option_c, "D": option_d}
    elif question_type == "true_false":
        q.options = {"A": "True", "B": "False"}
    db.commit()
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    exam.total_marks = db.query(func.sum(Question.marks)).filter(Question.exam_id == exam_id).scalar() or 0
    db.commit()
    return {"message": "Question updated"}


@router.delete("/exams/{exam_id}/questions/{q_id}")
async def delete_question(exam_id: int, q_id: int, current=Depends(get_current_admin), db: Session = Depends(get_db)):
    q = db.query(Question).filter(Question.id == q_id, Question.exam_id == exam_id).first()
    if not q: raise HTTPException(404, "Question not found")
    db.delete(q); db.commit()
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    exam.total_marks = db.query(func.sum(Question.marks)).filter(Question.exam_id == exam_id).scalar() or 0
    db.commit()
    return {"message": "Question deleted"}


@router.post("/exams/{exam_id}/questions/bulk")
async def bulk_upload_questions(exam_id: int, file: UploadFile = File(...),
                                current=Depends(get_current_admin), db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam: raise HTTPException(404, "Exam not found")
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    count = 0
    max_idx = db.query(func.max(Question.order_index)).filter(Question.exam_id == exam_id).scalar() or 0
    for row in reader:
        try:
            q_type = row.get("type", "mcq").lower()
            options = None
            if q_type == "mcq":
                options = {"A": row.get("A",""), "B": row.get("B",""), "C": row.get("C",""), "D": row.get("D","")}
            elif q_type == "true_false":
                options = {"A": "True", "B": "False"}
            max_idx += 1
            q = Question(exam_id=exam_id, question_text=row["question"], question_type=q_type,
                         options=options, correct_answer=row["answer"].upper(),
                         marks=float(row.get("marks", 1.0)), order_index=max_idx)
            db.add(q); count += 1
        except Exception:
            continue
    db.commit()
    exam.total_marks = db.query(func.sum(Question.marks)).filter(Question.exam_id == exam_id).scalar() or 0
    db.commit()
    return {"message": f"{count} questions imported"}


# ── STUDENTS ───────────────────────────────────────────────
@router.get("/students")
async def list_students(current=Depends(get_current_admin), db: Session = Depends(get_db)):
    students = db.query(Student).order_by(Student.class_name, Student.full_name).all()
    return [{"id": s.id, "student_id": s.student_id, "full_name": s.full_name,
             "class_name": s.class_name, "is_active": s.is_active,
             "created_at": s.created_at.isoformat()} for s in students]


@router.post("/students")
async def create_student(
    student_id: str = Form(...), full_name: str = Form(...),
    class_name: str = Form(""), password: str = Form(...),
    current=Depends(get_current_admin), db: Session = Depends(get_db)
):
    existing = db.query(Student).filter(Student.student_id == student_id).first()
    if existing: raise HTTPException(400, "Student ID already exists")
    s = Student(student_id=student_id, full_name=full_name, class_name=class_name,
                password_hash=hash_password(password))
    db.add(s); db.commit()
    return {"id": s.id, "message": "Student created"}


@router.put("/students/{student_id_param}")
async def update_student(
    student_id_param: int, full_name: str = Form(...), class_name: str = Form(""),
    password: Optional[str] = Form(None), is_active: bool = Form(True),
    current=Depends(get_current_admin), db: Session = Depends(get_db)
):
    s = db.query(Student).filter(Student.id == student_id_param).first()
    if not s: raise HTTPException(404, "Student not found")
    s.full_name = full_name; s.class_name = class_name; s.is_active = is_active
    if password:
        s.password_hash = hash_password(password)
    db.commit()
    return {"message": "Student updated"}


@router.delete("/students/{student_id_param}")
async def delete_student(student_id_param: int, current=Depends(get_current_admin), db: Session = Depends(get_db)):
    s = db.query(Student).filter(Student.id == student_id_param).first()
    if not s: raise HTTPException(404, "Student not found")
    db.delete(s); db.commit()
    return {"message": "Student deleted"}


@router.post("/students/bulk")
async def bulk_upload_students(file: UploadFile = File(...), current=Depends(get_current_admin), db: Session = Depends(get_db)):
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    count = 0; errors = []
    for row in reader:
        try:
            sid = row.get("student_id", "").strip()
            if not sid: continue
            if db.query(Student).filter(Student.student_id == sid).first():
                errors.append(f"{sid} already exists"); continue
            password = row.get("password", sid)
            s = Student(student_id=sid, full_name=row.get("full_name","").strip(),
                        class_name=row.get("class_name","").strip(),
                        password_hash=hash_password(password))
            db.add(s); count += 1
        except Exception as e:
            errors.append(str(e))
    db.commit()
    return {"imported": count, "errors": errors}


# ── RESULTS ────────────────────────────────────────────────
@router.get("/results")
async def get_results(exam_id: Optional[int] = None, current=Depends(get_current_admin), db: Session = Depends(get_db)):
    q = db.query(ExamSession).filter(ExamSession.is_submitted == True)
    if exam_id:
        q = q.filter(ExamSession.exam_id == exam_id)
    sessions = q.order_by(ExamSession.submitted_at.desc()).all()
    return [{"id": s.id, "student_name": s.student.full_name, "student_id": s.student.student_id,
             "class_name": s.student.class_name, "exam_title": s.exam.title,
             "exam_subject": s.exam.subject, "score": s.score, "total_marks": s.total_marks,
             "percentage": round(s.percentage, 2) if s.percentage else 0,
             "passed": s.score >= s.exam.pass_marks if s.score is not None else None,
             "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
             "duration_used": (s.submitted_at - s.started_at).seconds // 60 if s.submitted_at else None} for s in sessions]


@router.get("/results/export")
async def export_results(exam_id: Optional[int] = None, current=Depends(get_current_admin), db: Session = Depends(get_db)):
    q = db.query(ExamSession).filter(ExamSession.is_submitted == True)
    if exam_id:
        q = q.filter(ExamSession.exam_id == exam_id)
    sessions = q.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student ID","Student Name","Class","Exam","Subject","Score","Total","Percentage","Passed","Submitted At"])
    for s in sessions:
        passed = "Yes" if s.score >= s.exam.pass_marks else "No" if s.score is not None else "N/A"
        writer.writerow([s.student.student_id, s.student.full_name, s.student.class_name,
                         s.exam.title, s.exam.subject, s.score, s.total_marks,
                         f"{s.percentage:.1f}%" if s.percentage else "0%", passed,
                         s.submitted_at.isoformat() if s.submitted_at else ""])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=results.csv"})


@router.get("/results/{session_id}")
async def get_session_detail(session_id: int, current=Depends(get_current_admin), db: Session = Depends(get_db)):
    s = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not s: raise HTTPException(404, "Session not found")
    answers = s.answers or {}
    questions = db.query(Question).filter(Question.exam_id == s.exam_id).all()
    detail = []
    for q in questions:
        given = answers.get(str(q.id), "")
        detail.append({"question": q.question_text, "options": q.options,
                       "correct": q.correct_answer, "given": given,
                       "is_correct": given.upper() == q.correct_answer.upper() if given else False,
                       "marks": q.marks})
    return {"student": s.student.full_name, "exam": s.exam.title, "score": s.score,
            "total": s.total_marks, "percentage": s.percentage, "questions": detail}


# ── MONITOR ────────────────────────────────────────────────
@router.get("/monitor")
async def monitor_exams(current=Depends(get_current_admin), db: Session = Depends(get_db)):
    active = db.query(ExamSession).filter(ExamSession.is_submitted == False).all()
    return [{"session_id": s.id, "student_name": s.student.full_name,
             "student_id": s.student.student_id, "exam_title": s.exam.title,
             "started_at": s.started_at.isoformat(), "time_remaining": s.time_remaining,
             "answers_count": len(s.answers or {}),
             "total_questions": len(s.question_order or [])} for s in active]
