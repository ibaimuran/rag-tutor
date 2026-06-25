from sqlalchemy.orm import Session as DbSession
from ..models import Session, UserKnowledgeState, KnowledgePoint, Chapter
from ..config import settings


class SessionManager:
    def __init__(self, db: DbSession):
        self.db = db

    def create_session(self, user_id: int, course_id: int) -> Session:
        s = Session(
            user_id=user_id,
            course_id=course_id,
            tutor_phase="idle",
            session_context={"rounds_on_concept": 0, "diagnostic_count": 0},
        )
        self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        return s

    def get_session(self, session_id: int) -> Session | None:
        return self.db.query(Session).filter_by(id=session_id).first()

    def update_phase(self, session: Session, phase: str) -> None:
        session.tutor_phase = phase
        self.db.commit()

    def update_context(self, session: Session, key: str, value) -> None:
        ctx = dict(session.session_context or {})
        ctx[key] = value
        session.session_context = ctx
        self.db.commit()

    def get_context(self, session: Session, key: str, default=None):
        ctx = session.session_context or {}
        return ctx.get(key, default)

    def pause_session(self, session: Session) -> None:
        session.status = "paused"
        self.db.commit()

    def resume_session(self, session: Session) -> None:
        session.status = "active"
        self.db.commit()

    def complete_session(self, session: Session) -> None:
        session.status = "completed"
        from datetime import datetime
        session.ended_at = datetime.now()
        self.db.commit()

    def get_or_create_bkt_state(self, user_id: int, kp_id: int) -> UserKnowledgeState:
        state = (
            self.db.query(UserKnowledgeState)
            .filter_by(user_id=user_id, knowledge_point_id=kp_id)
            .first()
        )
        if not state:
            state = UserKnowledgeState(
                user_id=user_id,
                knowledge_point_id=kp_id,
                p_l0=settings.bkt_default_p_l0,
                p_t=settings.bkt_default_p_t,
                p_g=settings.bkt_default_p_g,
                p_s=settings.bkt_default_p_s,
                p_know=settings.bkt_default_p_l0,
            )
            self.db.add(state)
            self.db.commit()
            self.db.refresh(state)
        return state

    def save_bkt_state(self, state: UserKnowledgeState) -> None:
        from datetime import datetime
        state.updated_at = datetime.now()
        self.db.add(state)
        self.db.commit()

    def get_chapter_knowledge_points(self, chapter_id: int) -> list[KnowledgePoint]:
        return (
            self.db.query(KnowledgePoint)
            .filter_by(chapter_id=chapter_id)
            .order_by(KnowledgePoint.order_index)
            .all()
        )

    def get_current_chapter_for_kp(self, kp_id: int) -> Chapter | None:
        kp = self.db.query(KnowledgePoint).filter_by(id=kp_id).first()
        if kp:
            return self.db.query(Chapter).filter_by(id=kp.chapter_id).first()
        return None

    def are_all_chapter_kps_mastered(self, user_id: int, chapter_id: int) -> bool:
        kps = self.get_chapter_knowledge_points(chapter_id)
        for kp in kps:
            state = self.get_or_create_bkt_state(user_id, kp.id)
            if state.mastery_status != "mastered":
                return False
        return True
