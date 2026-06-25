from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, JSON, func
from .base import Base


class Interaction(Base):
    __tablename__ = "interactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=True)
    phase = Column(String(50))
    role = Column(String(20))
    content = Column(Text, nullable=False)
    question_type = Column(String(50))
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float, nullable=True)
    p_know_before = Column(Float, nullable=True)
    p_know_after = Column(Float, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
