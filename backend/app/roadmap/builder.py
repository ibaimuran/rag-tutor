from sqlalchemy.orm import Session as DbSession
from ..models import Course, Chapter, KnowledgePoint, UserKnowledgeState


class RoadmapBuilder:
    def __init__(self, db: DbSession):
        self.db = db

    def build(self, user_id: int, course_id: int) -> dict:
        course = self.db.query(Course).filter_by(id=course_id).first()
        if not course:
            return {"error": "Course not found"}

        chapters = (
            self.db.query(Chapter)
            .filter_by(course_id=course_id)
            .order_by(Chapter.order_index)
            .all()
        )

        total_kps = 0
        mastered_kps = 0
        chapter_list = []

        for ch in chapters:
            kps = (
                self.db.query(KnowledgePoint)
                .filter_by(chapter_id=ch.id)
                .order_by(KnowledgePoint.order_index)
                .all()
            )
            kp_nodes = []
            ch_mastered = 0
            for kp in kps:
                state = (
                    self.db.query(UserKnowledgeState)
                    .filter_by(user_id=user_id, knowledge_point_id=kp.id)
                    .first()
                )
                total_kps += 1
                status = state.mastery_status if state else "not_started"
                p_know = round(state.p_know * 100) if state else 0
                if status == "mastered":
                    mastered_kps += 1
                    ch_mastered += 1
                kp_nodes.append({
                    "id": kp.id,
                    "title": kp.title,
                    "status": status,
                    "p_know": p_know,
                    "prerequisites": kp.prerequisites or [],
                    "order": kp.order_index,
                    "difficulty": kp.difficulty,
                    "chapter_id": ch.id,
                })
            chapter_list.append({
                "id": ch.id,
                "title": ch.title,
                "knowledge_points": kp_nodes,
                "chapter_progress": round(ch_mastered / max(len(kps), 1) * 100),
            })

        return {
            "course_title": course.title,
            "course_id": course_id,
            "overall_progress": round(mastered_kps / max(total_kps, 1) * 100),
            "chapters": chapter_list,
        }
