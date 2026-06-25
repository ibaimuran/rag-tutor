from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint, func
from .base import Base


class UserKnowledgeState(Base):
    __tablename__ = "user_knowledge_states"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=False)
    p_l0 = Column(Float, default=0.50)
    p_t = Column(Float, default=0.20)
    p_g = Column(Float, default=0.15)
    p_s = Column(Float, default=0.10)
    p_know = Column(Float, default=0.50)
    mastery_status = Column(String(20), default="not_started")
    total_attempts = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    last_interaction_at = Column(DateTime)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("user_id", "knowledge_point_id"),)
