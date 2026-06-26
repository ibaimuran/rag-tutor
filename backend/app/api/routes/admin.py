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
    """Delete a course and all its data (cascade: sessions, interactions, quizzes, tests, BKT states)."""
    import shutil, re, traceback
    from sqlalchemy import text
    from ...models import Course, Chapter, KnowledgePoint, Session as SessionModel, Interaction
    from ...models import QuizAttempt, ChapterTest, TestQuestion, UserKnowledgeState
    from ..deps import get_vector_store

    try:
        course = db.query(Course).filter_by(id=course_id).first()
        if not course:
            return {"error": "Course not found"}
        course_title = course.title

        # 获取该课程下的所有关联 ID
        chapter_ids = [r[0] for r in db.query(Chapter.id).filter_by(course_id=course_id).all()]
        kp_ids = []
        if chapter_ids:
            kp_ids = [r[0] for r in db.query(KnowledgePoint.id).filter(
                KnowledgePoint.chapter_id.in_(chapter_ids)).all()]
        session_ids = [r[0] for r in db.query(SessionModel.id).filter_by(course_id=course_id).all()]

        # 暂时关闭外键约束，简化级联删除
        db.execute(text("PRAGMA foreign_keys=OFF"))

        # 删除所有关联数据（顺序不重要，FK 已关闭）
        if session_ids:
            db.query(Interaction).filter(Interaction.session_id.in_(session_ids)).delete(synchronize_session=False)
            db.query(SessionModel).filter(SessionModel.id.in_(session_ids)).delete(synchronize_session=False)

        if chapter_ids:
            test_ids = [r[0] for r in db.query(ChapterTest.id).filter(
                ChapterTest.chapter_id.in_(chapter_ids)).all()]
            if test_ids:
                db.query(TestQuestion).filter(TestQuestion.test_id.in_(test_ids)).delete(synchronize_session=False)
                db.query(ChapterTest).filter(ChapterTest.id.in_(test_ids)).delete(synchronize_session=False)

        if kp_ids:
            db.query(QuizAttempt).filter(QuizAttempt.knowledge_point_id.in_(kp_ids)).delete(synchronize_session=False)
            db.query(UserKnowledgeState).filter(UserKnowledgeState.knowledge_point_id.in_(kp_ids)).delete(synchronize_session=False)
            db.query(KnowledgePoint).filter(KnowledgePoint.id.in_(kp_ids)).delete(synchronize_session=False)

        if chapter_ids:
            db.query(Chapter).filter(Chapter.id.in_(chapter_ids)).delete(synchronize_session=False)

        db.query(Course).filter_by(id=course_id).delete()
        db.commit()

        # 重新开启外键约束
        db.execute(text("PRAGMA foreign_keys=ON"))

        # 清理 ChromaDB
        try:
            vs = get_vector_store()
            vs.delete_collection(course_id)
        except Exception:
            pass

        # 清理 materials 文件夹
        safe_name = course_title.strip()
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', safe_name)
        safe_name = re.sub(r'\s+', '_', safe_name)
        safe_name = safe_name[:80]
        from ...config import BASE_DIR
        materials_dir = BASE_DIR / "data" / "materials" / safe_name
        if materials_dir.exists():
            shutil.rmtree(materials_dir, ignore_errors=True)

        return {"status": "deleted", "course_id": course_id}

    except Exception as e:
        db.rollback()
        try:
            db.execute(text("PRAGMA foreign_keys=ON"))
        except Exception:
            pass
        traceback.print_exc()
        return {"error": str(e)}
