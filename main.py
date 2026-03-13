from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.database import create_tables, SessionLocal, Admin
from backend.utils.auth import hash_password
from backend.routers.admin import router as admin_router
from backend.routers.student import router as student_router

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(title="School CBT System", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(admin_router)
app.include_router(student_router)

# Serve static files
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/static/student/login.html")


@app.get("/admin")
async def admin_redirect():
    return RedirectResponse(url="/static/admin/login.html")


@app.on_event("startup")
async def startup():
    create_tables()
    # Create default admin if none exists
    db = SessionLocal()
    try:
        if not db.query(Admin).first():
            admin = Admin(username="admin", password_hash=hash_password("admin123"),
                          full_name="System Administrator")
            db.add(admin)
            db.commit()
            print("✅ Default admin created: username=admin, password=admin123")
    finally:
        db.close()
    print("✅ CBT System started!")
    print("📚 Student portal: http://localhost:8000")
    print("🔧 Admin panel:    http://localhost:8000/admin")


if __name__ == "__main__":
    import uvicorn
    import os
    import socket

    port = int(os.environ.get("PORT", 8000))  # <-- use Railway PORT

    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"\n{'='*50}")
    print(f"🏫 School CBT System")
    print(f"{'='*50}")
    print(f"Local access:    http://localhost:{port}")
    print(f"Network access:  http://{local_ip}:{port}")
    print(f"Admin panel:     http://localhost:{port}/admin")
    print(f"{'='*50}\n")

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)