from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from .base import Base


class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    subject = Column(String(200))
    grade_level = Column(String(50))
    language = Column(String(10), default="zh")
    created_at = Column(DateTime, default=func.now())

    chapters = relationship("Chapter", back_populates="course", order_by="Chapter.order_index")
