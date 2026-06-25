"""Initialize database tables and create a default user / course."""
import sys
sys.path.insert(0, "../backend")

from app.models.base import engine, Base, SessionLocal
from app.models import User

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    existing = db.query(User).filter_by(username="default").first()
    if not existing:
        db.add(User(username="default", display_name="学习者"))
        db.commit()
        print("Created default user: 'default' / '学习者'")
    else:
        print("Default user already exists.")
finally:
    db.close()

print("Database initialized.")
