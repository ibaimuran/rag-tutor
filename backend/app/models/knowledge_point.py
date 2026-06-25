from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from .base import Base


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    content_summary = Column(Text)
    prerequisites = Column(JSON, default=list)
    order_index = Column(Integer, nullable=False)
    difficulty = Column(Integer, default=1)
    chunk_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=func.now())

    chapter = relationship("Chapter", back_populates="knowledge_points")
