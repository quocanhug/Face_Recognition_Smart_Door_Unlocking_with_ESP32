"""
=============================================================
 DATABASE - SQLAlchemy Engine & Session
=============================================================
 Kết nối SQLite (có thể đổi sang PostgreSQL).
=============================================================
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database path
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'attendance.db')}"

# Để đổi sang PostgreSQL:
# DATABASE_URL = "postgresql://user:password@localhost/attendance"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite only
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency: tạo DB session cho mỗi request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
