"""
=============================================================
 MODELS - SQLAlchemy Database Schema
=============================================================
 3 bảng chính:
   - users:            Thông tin người dùng
   - face_embeddings:  Face vectors (512-d FaceNet)
   - attendance_logs:  Lịch sử điểm danh
=============================================================
"""

import numpy as np
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime,
    LargeBinary, ForeignKey, Text
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class User(Base):
    """Bảng người dùng."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    mssv = Column(String(20), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    embeddings = relationship(
        "FaceEmbedding", back_populates="user",
        cascade="all, delete-orphan"
    )
    attendance_logs = relationship(
        "AttendanceLog", back_populates="user",
        cascade="all, delete-orphan"
    )

    @property
    def face_count(self):
        return len(self.embeddings)

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', mssv='{self.mssv}')>"


class FaceEmbedding(Base):
    """Bảng face embeddings (512-d vector)."""
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    embedding = Column(LargeBinary, nullable=False)  # numpy bytes
    created_at = Column(DateTime, default=datetime.now)

    # Relationship
    user = relationship("User", back_populates="embeddings")

    def get_vector(self) -> np.ndarray:
        """Decode embedding bytes → numpy array."""
        return np.frombuffer(self.embedding, dtype=np.float32).copy()

    @staticmethod
    def from_vector(vector: np.ndarray) -> bytes:
        """Encode numpy array → bytes for storage."""
        return vector.astype(np.float32).tobytes()

    def __repr__(self):
        return f"<FaceEmbedding(id={self.id}, user_id={self.user_id})>"


class AttendanceLog(Base):
    """Bảng log điểm danh."""
    __tablename__ = "attendance_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_name = Column(String(100), nullable=True)
    mssv = Column(String(20), nullable=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    status = Column(String(20), nullable=False)  # GRANTED / DENIED
    confidence = Column(Float, default=0.0)

    # Relationship
    user = relationship("User", back_populates="attendance_logs")

    def __repr__(self):
        return (f"<AttendanceLog(id={self.id}, user='{self.user_name}', "
                f"status='{self.status}', time='{self.timestamp}')>")
