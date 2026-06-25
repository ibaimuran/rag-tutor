"""Quiz attempt model for per-KP quick quizzes."""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, func
from .base import Base


class QuizAttempt(Base):
    """Tracks a single quiz attempt per knowledge point.

    Stores all 10 questions + user answers + BKT result in JSON columns.
    """
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=False)
    questions_json = Column(JSON, default=list)  # [{"question_text": "...", "options": [...], "correct_answer": "A"}]
    current_index = Column(Integer, default=0)
    answers_json = Column(JSON, default=list)  # [{"question_index": 0, "user_answer": "B", "is_correct": true}]
    start_p_know = Column(Float, default=0.5)
    end_p_know = Column(Float, nullable=True)
    bkt_params_json = Column(JSON, nullable=True)  # {p_l0, p_t, p_g, p_s}
    status = Column(String(20), default="in_progress")
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)