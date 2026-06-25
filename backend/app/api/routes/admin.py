"""Admin routes: course management (create from topic, list, delete)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from ...api.deps import get_db

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/generate-course-from-topic")
async def generate_course_from_topic(
    topic: str = Query(..., description="Topic to generate course for, e.g. 初中化学"),
    db: DbSession = Depends(get_db),
):
    """Generate a complete course from a topic name using LLM."""
    import traceback
    from ...core.course_generator import CourseGenerator
    try:
        generator = CourseGenerator(db)
        result = await generator.generate_from_topic(topic)
        return result
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


@router.get("/courses")
async def list_courses(db: DbSession = Depends(get_db)):
    """List all courses in the system."""
    from ...models import Course
    courses = db.query(Course).all()
    return [
        {"id": c.id, "title": c.title, "subject": c.subject, "grade_level": c.grade_level}
        for c in courses
    ]


@router.delete("/courses/{course_id}")
async def delete_course(course_id: int, db: DbSession = Depends(get_db)):
    """Delete a course and all its data."""
    from ...models import Course, Chapter, KnowledgePoint
    from ..deps import get_vector_store

    db.query(KnowledgePoint).filter(
        KnowledgePoint.chapter_id.in_(
            db.query(Chapter.id).filter(Chapter.course_id == course_id)
        )
    ).delete(synchronize_session=False)
    db.query(Chapter).filter_by(course_id=course_id).delete(synchronize_session=False)
    db.query(Course).filter_by(id=course_id).delete()
    db.commit()

    try:
        vs = get_vector_store()
        vs.delete_collection(course_id)
    except Exception:
        pass

    return {"status": "deleted", "course_id": course_id}
