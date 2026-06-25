from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession
from ...api.deps import get_db, get_retriever
from ...core.tutor_agent import TutorAgent
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
    agent = TutorAgent(db, retriever)
    response = await agent.process_message(session, req.message, req.target_kp_id)
    result = {
        "reply": response.reply,
        "phase": response.phase,
        "current_kp": response.current_kp,
        "bkt_update": response.bkt_update,
        "roadmap_update": response.roadmap_update,
        "test_ready": response.test_ready,
        "next_action": response.next_action,
        "guessed": response.guessed,
    }
    if response.answer_feedback:
        result["answer_feedback"] = {
            "is_correct": response.answer_feedback.is_correct,
            "correct_answer": response.answer_feedback.correct_answer,
            "explanation": response.answer_feedback.explanation,
            "p_know_before": response.answer_feedback.p_know_before,
            "p_know_after": response.answer_feedback.p_know_after,
        }
    return result


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
