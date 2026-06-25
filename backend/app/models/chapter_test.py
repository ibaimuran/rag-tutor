from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from .base import Base


class ChapterTest(Base):
    __tablename__ = "chapter_tests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    status = Column(String(20), default="pending")
    overall_score = Column(Float, nullable=True)
    bkt_analysis = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())

    questions = relationship("TestQuestion", back_populates="test")


class TestQuestion(Base):
    __tablename__ = "test_questions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(Integer, ForeignKey("chapter_tests.id"), nullable=False)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50))
    correct_answer = Column(Text, nullable=False)
    options_json = Column(JSON, nullable=True)
    user_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float, nullable=True)

    test = relationship("ChapterTest", back_populates="questions")
