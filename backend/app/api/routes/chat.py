from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession
from ...api.deps import get_db, get_retriever
from ...core.qa_agent import QAAgent
from ...core.session_manager import SessionManager
from ...schemas.chat import ChatRequest

router = APIRouter(prefix="/api/v1/sessions", tags=["chat"])


@router.post("/{session_id}/chat")
async def chat(session_id: int, req: ChatRequest, db: DbSession = Depends(get_db)):
    sm = SessionManager(db)
    session = sm.get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    retriever = get_retriever()
    agent = QAAgent(db, retriever)
    response = await agent.process_message(session, req.message, req.target_kp_id)
    return response


@router.get("/{session_id}/chat/history")
async def chat_history(session_id: int, limit: int = 50, db: DbSession = Depends(get_db)):
    from ...models import Interaction
    interactions = (
        db.query(Interaction)
        .filter_by(session_id=session_id)
        .order_by(Interaction.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "messages": [
            {
                "role": i.role,
                "content": i.content,
                "phase": i.phase,
                "is_correct": i.is_correct,
                "score": i.score,
                "p_know_before": i.p_know_before,
                "p_know_after": i.p_know_after,
                "created_at": str(i.created_at),
            }
            for i in reversed(interactions)
        ]
    }
