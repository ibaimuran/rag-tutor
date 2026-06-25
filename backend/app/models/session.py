from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, func
from .base import Base


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    current_kp_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=True)
    status = Column(String(20), default="active")
    tutor_phase = Column(String(20), default="idle")
    session_context = Column(JSON, default=dict)
    started_at = Column(DateTime, default=func.now())
    ended_at = Column(DateTime, nullable=True)
