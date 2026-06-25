from sqlalchemy import Column, Integer, String, DateTime, func
from .base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200))
    created_at = Column(DateTime, default=func.now())
