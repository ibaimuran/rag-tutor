from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession
from ...api.deps import get_db
from ...core.session_manager import SessionManager
from ...roadmap.builder import RoadmapBuilder

router = APIRouter(prefix="/api/v1/progress", tags=["progress"])


@router.get("/{user_id}")
async def get_progress(user_id: int, course_id: int = 1, db: DbSession = Depends(get_db)):
    builder = RoadmapBuilder(db)
    roadmap = builder.build(user_id, course_id)
    total = sum(len(ch["knowledge_points"]) for ch in roadmap.get("chapters", []))
    mastered = sum(
        1 for ch in roadmap.get("chapters", [])
        for kp in ch["knowledge_points"] if kp["status"] == "mastered"
    )
    return {
        "user_id": user_id,
        "course_id": course_id,
        "course_title": roadmap.get("course_title", ""),
        "overall_progress": round(mastered / max(total, 1) * 100),
        "concepts_mastered": mastered,
        "concepts_total": total,
    }


@router.get("/{user_id}/bkt")
async def get_bkt_states(user_id: int, db: DbSession = Depends(get_db)):
    from ...models import UserKnowledgeState, KnowledgePoint
    states = (
        db.query(UserKnowledgeState, KnowledgePoint)
        .join(KnowledgePoint, UserKnowledgeState.knowledge_point_id == KnowledgePoint.id)
        .filter(UserKnowledgeState.user_id == user_id)
        .all()
    )
    return {
        str(state.knowledge_point_id): {
            "kp_title": kp.title,
            "p_know": round(state.p_know, 4),
            "mastery_status": state.mastery_status,
            "total_attempts": state.total_attempts,
            "correct_count": state.correct_count,
            "p_l0": state.p_l0,
            "p_t": state.p_t,
            "p_g": state.p_g,
            "p_s": state.p_s,
        }
        for state, kp in states
    }
