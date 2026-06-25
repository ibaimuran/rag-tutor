from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession
from ...api.deps import get_db
from ...core.session_manager import SessionManager

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("")
async def create_session(user_id: int = 1, course_id: int = 1, db: DbSession = Depends(get_db)):
    sm = SessionManager(db)
    session = sm.create_session(user_id, course_id)
    return {
        "id": session.id,
        "user_id": session.user_id,
        "course_id": session.course_id,
        "status": session.status,
        "tutor_phase": session.tutor_phase,
        "started_at": str(session.started_at),
    }


@router.get("/{session_id}")
async def get_session(session_id: int, db: DbSession = Depends(get_db)):
    sm = SessionManager(db)
    session = sm.get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    return {
        "id": session.id,
        "user_id": session.user_id,
        "course_id": session.course_id,
        "current_kp_id": session.current_kp_id,
        "status": session.status,
        "tutor_phase": session.tutor_phase,
        "session_context": session.session_context,
        "started_at": str(session.started_at),
    }


@router.post("/{session_id}/pause")
async def pause_session(session_id: int, db: DbSession = Depends(get_db)):
    sm = SessionManager(db)
    session = sm.get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    sm.pause_session(session)
    return {"status": "paused"}


@router.post("/{session_id}/resume")
async def resume_session(session_id: int, db: DbSession = Depends(get_db)):
    sm = SessionManager(db)
    session = sm.get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    sm.resume_session(session)
    return {"status": "active", "tutor_phase": session.tutor_phase, "current_kp_id": session.current_kp_id}
