from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession
from ...api.deps import get_db
from ...core.session_manager import SessionManager

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.get("/active")
async def get_active_session(user_id: int = 1, course_id: int = 1, db: DbSession = Depends(get_db)):
    """Get the best active session for a user+course — 优先返回有聊天记录的 session。"""
    from ...models import Session as SessionModel, Interaction

    # 查找所有活跃 session，按创建时间倒序
    sessions = (
        db.query(SessionModel)
        .filter_by(user_id=user_id, course_id=course_id, status="active")
        .order_by(SessionModel.started_at.desc())
        .all()
    )
    if not sessions:
        return {"has_session": False}

    # 优先返回有聊天记录的 session
    for s in sessions:
        has_interactions = db.query(Interaction).filter_by(session_id=s.id).first() is not None
        if has_interactions:
            return {
                "has_session": True,
                "id": s.id,
                "user_id": s.user_id,
                "course_id": s.course_id,
                "current_kp_id": s.current_kp_id,
                "status": s.status,
                "started_at": str(s.started_at),
            }

    # 都没有记录则返回最新的
    s = sessions[0]
    return {
        "has_session": True,
        "id": s.id,
        "user_id": s.user_id,
        "course_id": s.course_id,
        "current_kp_id": s.current_kp_id,
        "status": s.status,
        "started_at": str(s.started_at),
    }


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
