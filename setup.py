#!/usr/bin/env python3
"""
Quick setup script for School CBT System
Run this once to set up the environment and seed initial data.
"""
import os, sys, subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

def run(cmd):
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"  [ERROR] Command failed: {cmd}")
        sys.exit(1)

print("\n" + "="*50)
print("  School CBT System — Setup")
print("="*50 + "\n")

# Install dependencies
print("📦 Installing dependencies...")
run(f"{sys.executable} -m pip install -r requirements.txt --break-system-packages -q")

# Create data directory
os.makedirs("data", exist_ok=True)
print("✅ Data directory ready")

# Initialize DB and seed
print("\n🗃  Initializing database...")
sys.path.insert(0, BASE)
from backend.models.database import create_tables, SessionLocal, Admin, Student
from backend.utils.auth import hash_password

create_tables()

db = SessionLocal()
try:
    if not db.query(Admin).filter(Admin.username == "admin").first():
        db.add(Admin(username="admin", password_hash=hash_password("admin123"), full_name="System Administrator"))
        db.commit()
        print("✅ Admin account created  →  username: admin  |  password: admin123")
    else:
        print("ℹ  Admin account already exists")

    # Seed demo students
    demo = [
        ("STU001", "Alice Johnson",    "JSS1A", "pass123"),
        ("STU002", "Bob Smith",        "JSS1A", "pass123"),
        ("STU003", "Carol Williams",   "JSS1B", "pass123"),
        ("STU004", "David Brown",      "JSS2A", "pass123"),
        ("STU005", "Eve Davis",        "JSS2B", "pass123"),
    ]
    added = 0
    for sid, name, cls, pw in demo:
        if not db.query(Student).filter(Student.student_id == sid).first():
            db.add(Student(student_id=sid, full_name=name, class_name=cls, password_hash=hash_password(pw)))
            added += 1
    db.commit()
    if added:
        print(f"✅ {added} demo students added (password: pass123 for all)")
finally:
    db.close()

print("\n" + "="*50)
print("  Setup complete! Start the server with:")
print()
print("  python main.py")
print()
print("  Admin panel:    http://localhost:8000/admin")
print("  Student portal: http://localhost:8000")
print("="*50 + "\n")
