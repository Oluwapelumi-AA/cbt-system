from fastapi import APIRouter, Depends, HTTPException, Form, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import random

from ..models.database import get_db, Student, Exam, Question, ExamSession
from ..utils.auth import verify_password, create_token, get_current_student

router = APIRouter(prefix="/api/student", tags=["student"])


@router.post("/login")
async def student_login(response: Response, request: Request,
                        student_id: str = Form(...), password: str = Form(...),
                        db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.student_id == student_id, Student.is_active == True).first()
    if not student or not verify_password(password, student.password_hash):
        raise HTTPException(status_code=401, detail="Invalid student ID or password")
    token = create_token({"sub": str(student.id), "student_id": student.student_id}, role="student")
    response.set_cookie("student_token", token, httponly=True, max_age=43200, samesite="lax")
    return {"message": "Login successful", "student_id": student.student_id, "full_name": student.full_name}


@router.post("/logout")
async def student_logout(response: Response):
    response.delete_cookie("student_token")
    return {"message": "Logged out"}


@router.get("/me")
async def get_me(current=Depends(get_current_student), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == int(current["sub"])).first()
    return {"student_id": student.student_id, "full_name": student.full_name, "class_name": student.class_name}


@router.get("/exams/available")
async def available_exams(current=Depends(get_current_student), db: Session = Depends(get_db)):
    student_db_id = int(current["sub"])
    active_exams = db.query(Exam).filter(Exam.is_active == True).all()
    result = []
    for exam in active_exams:
        session = db.query(ExamSession).filter(
            ExamSession.student_id == student_db_id,
            ExamSession.exam_id == exam.id
        ).first()
        q_count = len(exam.questions)
        result.append({
            "id": exam.id, "title": exam.title, "subject": exam.subject,
            "description": exam.description, "duration_minutes": exam.duration_minutes,
            "total_marks": exam.total_marks, "pass_marks": exam.pass_marks,
            "question_count": q_count,
            "status": "submitted" if session and session.is_submitted else
                      "in_progress" if session else "not_started",
            "session_id": session.id if session else None
        })
    return result


@router.post("/exams/{exam_id}/start")
async def start_exam(exam_id: int, request: Request,
                     current=Depends(get_current_student), db: Session = Depends(get_db)):
    student_db_id = int(current["sub"])
    exam = db.query(Exam).filter(Exam.id == exam_id, Exam.is_active == True).first()
    if not exam:
        raise HTTPException(404, "Exam not found or not active")
    existing = db.query(ExamSession).filter(
        ExamSession.student_id == student_db_id, ExamSession.exam_id == exam_id
    ).first()
    if existing and existing.is_submitted:
        raise HTTPException(400, "You have already submitted this exam")
    if existing:
        return {"session_id": existing.id, "message": "Resuming exam"}
    questions = exam.questions[:]
    if exam.randomize_questions:
        random.shuffle(questions)
    question_order = [q.id for q in questions]
    client_ip = request.client.host
    session = ExamSession(student_id=student_db_id, exam_id=exam_id,
                          question_order=question_order, answers={},
                          time_remaining=exam.duration_minutes * 60, ip_address=client_ip)
    db.add(session); db.commit(); db.refresh(session)
    return {"session_id": session.id, "message": "Exam started"}


@router.get("/sessions/{session_id}")
async def get_session(session_id: int, current=Depends(get_current_student), db: Session = Depends(get_db)):
    student_db_id = int(current["sub"])
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id, ExamSession.student_id == student_db_id
    ).first()
    if not session: raise HTTPException(404, "Session not found")
    if session.is_submitted:
        return await _get_result(session, db)
    exam = session.exam
    questions_data = []
    for qid in session.question_order:
        q = db.query(Question).filter(Question.id == qid).first()
        if not q: continue
        options = q.options
        if exam.randomize_options and options and q.question_type == "mcq":
            items = list(options.items())
            random.shuffle(items)
            options = dict(items)
        questions_data.append({
            "id": q.id, "question_text": q.question_text,
            "question_type": q.question_type, "options": options, "marks": q.marks
        })
    return {
        "session_id": session.id, "exam_title": exam.title, "exam_subject": exam.subject,
        "duration_minutes": exam.duration_minutes, "time_remaining": session.time_remaining,
        "started_at": session.started_at.isoformat(), "answers": session.answers or {},
        "questions": questions_data, "is_submitted": False
    }


@router.patch("/sessions/{session_id}/answer")
async def save_answer(session_id: int, question_id: int = Form(...), answer: str = Form(...),
                      time_remaining: int = Form(0), current=Depends(get_current_student),
                      db: Session = Depends(get_db)):
    student_db_id = int(current["sub"])
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id, ExamSession.student_id == student_db_id
    ).first()
    if not session: raise HTTPException(404, "Session not found")
    if session.is_submitted: raise HTTPException(400, "Exam already submitted")
    answers = dict(session.answers or {})
    answers[str(question_id)] = answer
    session.answers = answers
    session.time_remaining = time_remaining
    db.commit()
    return {"message": "Answer saved"}


@router.post("/sessions/{session_id}/submit")
async def submit_exam(session_id: int, time_remaining: int = Form(0),
                      current=Depends(get_current_student), db: Session = Depends(get_db)):
    student_db_id = int(current["sub"])
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id, ExamSession.student_id == student_db_id
    ).first()
    if not session: raise HTTPException(404, "Session not found")
    if session.is_submitted: raise HTTPException(400, "Already submitted")
    answers = session.answers or {}
    questions = db.query(Question).filter(Question.exam_id == session.exam_id).all()
    score = 0.0
    total = 0.0
    for q in questions:
        total += q.marks
        given = answers.get(str(q.id), "")
        if given and given.upper() == q.correct_answer.upper():
            score += q.marks
    session.score = score
    session.total_marks = total
    session.percentage = (score / total * 100) if total > 0 else 0
    session.is_submitted = True
    session.submitted_at = datetime.utcnow()
    session.time_remaining = time_remaining
    db.commit()
    exam = session.exam
    if exam.show_result_immediately:
        return {"submitted": True, "score": score, "total": total,
                "percentage": round(session.percentage, 2),
                "passed": score >= exam.pass_marks, "pass_marks": exam.pass_marks}
    return {"submitted": True, "message": "Exam submitted successfully. Results will be announced later."}


async def _get_result(session, db):
    exam = session.exam
    answers = session.answers or {}
    questions = db.query(Question).filter(Question.exam_id == session.exam_id).all()
    detail = []
    for q in questions:
        given = answers.get(str(q.id), "")
        detail.append({"id": q.id, "question_text": q.question_text, "options": q.options,
                       "correct_answer": q.correct_answer, "given_answer": given,
                       "is_correct": given.upper() == q.correct_answer.upper() if given else False,
                       "marks": q.marks})
    return {"session_id": session.id, "is_submitted": True, "exam_title": exam.title,
            "score": session.score, "total_marks": session.total_marks,
            "percentage": round(session.percentage, 2), "passed": session.score >= exam.pass_marks,
            "pass_marks": exam.pass_marks, "show_detail": exam.show_result_immediately,
            "questions": detail if exam.show_result_immediately else []}
