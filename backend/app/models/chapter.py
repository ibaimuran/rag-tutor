from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from .base import Base


class Chapter(Base):
    __tablename__ = "chapters"
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(500), nullable=False)
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())

    course = relationship("Course", back_populates="chapters")
    knowledge_points = relationship(
        "KnowledgePoint", back_populates="chapter",
        order_by="KnowledgePoint.order_index"
    )
