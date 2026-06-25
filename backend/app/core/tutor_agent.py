from enum import Enum
from sqlalchemy.orm import Session as DbSession
from ..models import Session, KnowledgePoint, Interaction, UserKnowledgeState
from ..config import settings
from ..bkt.model import BKTParams, BKTState
from ..bkt.updater import update_bkt_posterior
from ..core.session_manager import SessionManager
from ..core.socratic_engine import SocraticEngine
from ..core.mastery_gate import MasteryGate, MasteryDecision
from ..llm.deepseek_client import deepseek
from ..llm.prompt_templates import (
    SYSTEM_PROMPT_SOCRATIC,
    DIAGNOSTIC_PROMPT,
    TEACHING_PROMPT,
    MASTERY_CHECK_PROMPT,
    ANSWER_FEEDBACK_PROMPT,
    RESPONSE_STRATEGIES,
)


class TutorPhase(str, Enum):
    IDLE = "idle"
    DIAGNOSING = "diagnosing"
    TEACHING = "teaching"
    MASTERY_CHECK = "mastery_check"
    TESTING = "testing"
    REMEDIATING = "remediating"


class AnswerFeedback:
    def __init__(self, is_correct: bool, correct_answer: str, explanation: str,
                 p_know_before: float, p_know_after: float):
        self.is_correct = is_correct
        self.correct_answer = correct_answer
        self.explanation = explanation
        self.p_know_before = round(p_know_before, 4)
        self.p_know_after = round(p_know_after, 4)


class TutorResponse:
    def __init__(self, reply: str, phase: str, current_kp: dict | None = None,
                 bkt_update: dict | None = None, roadmap_update: dict | None = None,
                 test_ready: bool = False, next_action: dict | None = None,
                 guessed: bool = False, answer_feedback: AnswerFeedback | None = None):
        self.reply = reply
        self.phase = phase
        self.current_kp = current_kp
        self.bkt_update = bkt_update
        self.roadmap_update = roadmap_update
        self.test_ready = test_ready
        self.next_action = next_action
        self.guessed = guessed
        self.answer_feedback = answer_feedback


class TutorAgent:
    def __init__(self, db: DbSession, retriever=None):
        self.db = db
        self.sm = SessionManager(db)
        self.scorer = SocraticEngine()
        self.gate = MasteryGate()
        self.retriever = retriever

    async def process_message(
        self, session: Session, user_message: str, target_kp_id: int | None = None
    ) -> TutorResponse:
        # Step 1: Resolve current knowledge point
        kp = self._resolve_kp(session, target_kp_id)
        if not kp:
            return TutorResponse(
                reply="请先选择一个课程和知识点开始学习。",
                phase="idle",
            )

        # Step 2: Get or create BKT state
        bkt_db = self.sm.get_or_create_bkt_state(session.user_id, kp.id)
        bkt_state = BKTState(
            params=BKTParams(bkt_db.p_l0, bkt_db.p_t, bkt_db.p_g, bkt_db.p_s),
            p_know=bkt_db.p_know,
        )

        # Step 3: Score previous answer if pending
        prev_q = self._get_last_assistant_interaction(session)
        score = None
        guessed = False
        if prev_q and prev_q.question_type and user_message.strip():
            score = await self.scorer.score_answer(
                question_text=prev_q.content,
                user_answer=user_message,
                knowledge_point_summary=kp.content_summary or kp.title,
                question_type=prev_q.question_type,
                correct_answer=(prev_q.metadata_json or {}).get("correct_answer", ""),
            )
            # Guess detection: correct MCQ but no explanation
            if score >= 0.7 and self.scorer.is_likely_guess(user_message, prev_q.question_type):
                guessed = True
                score = 0.4  # Penalize guessed answers
            is_correct = score >= 0.7
            bkt_state = update_bkt_posterior(bkt_state, is_correct)
            self._save_interaction(
                session, kp.id, "user", user_message,
                phase=session.tutor_phase, is_correct=is_correct, score=score,
                p_know_before=bkt_db.p_know, p_know_after=bkt_state.p_know,
                metadata_json={"guessed": guessed},
            )

        # Step 4: Update BKT state in DB
        bkt_db.p_know = bkt_state.p_know
        bkt_db.total_attempts = (bkt_db.total_attempts or 0) + 1
        if score is not None and score >= 0.7:
            bkt_db.correct_count = (bkt_db.correct_count or 0) + 1
        bkt_db.mastery_status = self._compute_mastery_status(bkt_state)
        self.sm.save_bkt_state(bkt_db)

        # Step 5: Transition phase
        phase = TutorPhase(session.tutor_phase)
        session = self._transition_phase(session, kp, bkt_state, phase)

        # Compute next action from mastery gate
        next_action = self.gate.get_next_action(bkt_state)

        # Step 6: Handle idle message (initial concept selection)
        if not user_message.strip() and phase == TutorPhase.IDLE:
            return await self._start_concept(session, kp, bkt_state)

        # Step 7: Build context and generate response
        response_text = await self._generate_response(session, kp, bkt_state, user_message)

        # Step 8: Strip correct answer marker from displayed text, store in metadata
        correct_answer = self._extract_correct_answer(response_text)
        clean_response = self._strip_correct_answer_marker(response_text)

        # Step 9: Save assistant interaction (clean text, answer in metadata)
        qtype = self.scorer.classify_question_type(clean_response) if self.scorer.has_question(clean_response) else "none"
        metadata = {}
        if qtype in ("multiple_choice", "true_false") and correct_answer:
            metadata["correct_answer"] = correct_answer
        self._save_interaction(
            session, kp.id, "assistant", clean_response,
            phase=session.tutor_phase, question_type=qtype if qtype != "none" else None,
            metadata_json=metadata,
        )

        # Step 10: Generate answer feedback if we just scored an answer
        # Only generate feedback when we have a known correct answer (MCQ/True-False)
        answer_feedback = None
        if score is not None and prev_q and not guessed:
            prev_correct = (prev_q.metadata_json or {}).get("correct_answer", "")
            if prev_correct:
                prev_options = self._format_options_for_feedback(prev_q.content)
                feedback_text = await self._generate_feedback(
                    concept_title=kp.title,
                    question_text=prev_q.content,
                    options_text=prev_options,
                    correct_answer=prev_correct,
                    user_answer=user_message,
                    is_correct=score >= 0.7,
                )
                answer_feedback = AnswerFeedback(
                    is_correct=score >= 0.7,
                    correct_answer=prev_correct,
                    explanation=feedback_text,
                    p_know_before=bkt_db.p_know,
                    p_know_after=bkt_state.p_know,
                )

        # Step 11: Build roadmap snapshot
        roadmap_update = self._build_roadmap_snapshot(session)

        # Step 12: Check if chapter test is ready
        test_ready = False
        chapter = self.sm.get_current_chapter_for_kp(kp.id)
        if chapter and self.sm.are_all_chapter_kps_mastered(session.user_id, chapter.id):
            from ..models import ChapterTest
            existing_test = (
                self.db.query(ChapterTest)
                .filter_by(session_id=session.id, chapter_id=chapter.id, status="pending")
                .first()
            )
            if not existing_test:
                test_ready = True

        return TutorResponse(
            reply=clean_response,
            phase=session.tutor_phase,
            current_kp={"id": kp.id, "title": kp.title, "chapter_id": kp.chapter_id},
            bkt_update={
                "kp_id": kp.id,
                "p_know_before": bkt_db.p_know if score is not None else bkt_state.p_know,
                "p_know_after": bkt_state.p_know,
                "mastery_status": bkt_db.mastery_status,
            } if score is not None else None,
            roadmap_update=roadmap_update,
            test_ready=test_ready,
            next_action=next_action,
            guessed=guessed,
            answer_feedback=answer_feedback,
        )

    def _resolve_kp(self, session: Session, target_kp_id: int | None) -> KnowledgePoint | None:
        kp_id = target_kp_id or session.current_kp_id
        if not kp_id:
            return None
        return self.db.query(KnowledgePoint).filter_by(id=kp_id).first()

    def _transition_phase(self, session: Session, kp: KnowledgePoint,
                          bkt_state: BKTState, current_phase: TutorPhase) -> Session:
        ctx = session.session_context or {}
        rounds = ctx.get("rounds_on_concept", 0)
        diag_count = ctx.get("diagnostic_count", 0)

        if current_phase == TutorPhase.IDLE:
            session.tutor_phase = TutorPhase.DIAGNOSING.value
            ctx["diagnostic_count"] = 0
            ctx["rounds_on_concept"] = 0
        elif current_phase == TutorPhase.DIAGNOSING:
            diag_count += 1
            ctx["diagnostic_count"] = diag_count
            if diag_count >= settings.diagnose_rounds:
                session.tutor_phase = TutorPhase.TEACHING.value
                ctx["rounds_on_concept"] = 0
        elif current_phase == TutorPhase.TEACHING:
            rounds += 1
            ctx["rounds_on_concept"] = rounds
            if rounds >= settings.teach_rounds:
                session.tutor_phase = TutorPhase.MASTERY_CHECK.value
        elif current_phase == TutorPhase.MASTERY_CHECK:
            decision = self.gate.check_mastery(bkt_state)
            if decision == MasteryDecision.MASTERED:
                next_kp = self._get_next_kp(kp)
                if next_kp:
                    session.current_kp_id = next_kp.id
                session.tutor_phase = TutorPhase.IDLE.value
                ctx["rounds_on_concept"] = 0
                ctx["diagnostic_count"] = 0
            elif decision == MasteryDecision.NEEDS_RELEARN:
                session.tutor_phase = TutorPhase.REMEDIATING.value
                ctx["rounds_on_concept"] = 0
            else:
                session.tutor_phase = TutorPhase.TEACHING.value
                ctx["rounds_on_concept"] = 0
        elif current_phase == TutorPhase.REMEDIATING:
            decision = self.gate.check_mastery(bkt_state)
            if decision == MasteryDecision.MASTERED:
                next_kp = self._get_next_kp(kp)
                if next_kp:
                    session.current_kp_id = next_kp.id
                session.tutor_phase = TutorPhase.IDLE.value
                ctx["rounds_on_concept"] = 0
            elif decision == MasteryDecision.NEEDS_RELEARN:
                pass  # Stay in remediating
            else:
                session.tutor_phase = TutorPhase.TEACHING.value
                ctx["rounds_on_concept"] = 0

        session.session_context = ctx
        self.db.commit()
        return session

    async def _start_concept(self, session: Session, kp: KnowledgePoint,
                             bkt_state: BKTState) -> TutorResponse:
        retrieved = self._retrieve_context(session.course_id, kp)
        pr = (kp.prerequisites or [])
        sys_prompt = SYSTEM_PROMPT_SOCRATIC.format(
            subject="本课程",
            p_know=bkt_state.p_know,
            response_strategies=RESPONSE_STRATEGIES["diagnosing"],
        )
        user_prompt = DIAGNOSTIC_PROMPT.format(
            concept_title=kp.title,
            concept_description=kp.description or kp.title,
            prerequisites_mastered=", ".join(str(p) for p in pr) if pr else "无",
        )
        if retrieved:
            user_prompt += f"\n\n## 参考课程资料\n{chr(10).join(r['text'][:500] for r in retrieved[:2])}"

        reply = await deepseek.generate(sys_prompt, user_prompt)
        # Strip correct answer marker, store in metadata
        correct_answer = self._extract_correct_answer(reply)
        clean_reply = self._strip_correct_answer_marker(reply)
        qtype = self.scorer.classify_question_type(clean_reply) if self.scorer.has_question(clean_reply) else "none"
        metadata = {}
        if qtype in ("multiple_choice", "true_false") and correct_answer:
            metadata["correct_answer"] = correct_answer
        self._save_interaction(session, kp.id, "assistant", clean_reply,
                               phase=session.tutor_phase, question_type=qtype if qtype != "none" else None,
                               metadata_json=metadata)
        return TutorResponse(
            reply=clean_reply,
            phase=session.tutor_phase,
            current_kp={"id": kp.id, "title": kp.title, "chapter_id": kp.chapter_id},
        )

    async def _generate_response(self, session: Session, kp: KnowledgePoint,
                                 bkt_state: BKTState, user_message: str) -> str:
        phase = session.tutor_phase
        retrieved = self._retrieve_context(session.course_id, kp)
        ctx = retrieved_context = "\n\n".join(r["text"] for r in retrieved) if retrieved else "（无参考课程资料）"
        history = self._get_chat_history(session)

        strategies = RESPONSE_STRATEGIES.get(phase, RESPONSE_STRATEGIES["teaching"])
        sys_prompt = SYSTEM_PROMPT_SOCRATIC.format(
            subject="本课程",
            p_know=bkt_state.p_know,
            response_strategies=strategies,
        )

        if phase == TutorPhase.DIAGNOSING.value:
            pr = (kp.prerequisites or [])
            user_prompt = DIAGNOSTIC_PROMPT.format(
                concept_title=kp.title,
                concept_description=kp.description or kp.title,
                prerequisites_mastered=", ".join(str(p) for p in pr) if pr else "无",
            )
            return await deepseek.generate(sys_prompt, user_prompt)
        elif phase == TutorPhase.MASTERY_CHECK.value:
            db_state = self.sm.get_or_create_bkt_state(session.user_id, kp.id)
            correct_rate = (
                db_state.correct_count / max(db_state.total_attempts, 1) * 100
            )
            template = MASTERY_CHECK_PROMPT.format(
                concept_title=kp.title,
                concept_description=kp.description or kp.title,
                p_know=bkt_state.p_know,
                rounds=self.sm.get_context(session, "rounds_on_concept", 0),
                correct_rate=correct_rate,
            )
            sys_prompt = sys_prompt  # already formatted above
            user_prompt = template
            return await deepseek.generate(sys_prompt, user_prompt)
        else:
            template = TEACHING_PROMPT

        user_prompt = template.format(
            concept_title=kp.title,
            concept_description=kp.description or kp.title,
            retrieved_context=ctx,
            chat_history=history,
            p_know=bkt_state.p_know,
        )
        return await deepseek.generate(sys_prompt, user_prompt)

    def _retrieve_context(self, course_id: int, kp: KnowledgePoint) -> list[dict]:
        if not self.retriever:
            return []
        try:
            return self.retriever.retrieve_for_concept(
                course_id, kp.title, kp.description or "", settings.retrieval_top_k
            )
        except Exception:
            return []

    def _get_last_assistant_interaction(self, session: Session) -> Interaction | None:
        return (
            self.db.query(Interaction)
            .filter_by(session_id=session.id, role="assistant")
            .filter(Interaction.question_type != None)
            .order_by(Interaction.created_at.desc())
            .first()
        )

    def _get_chat_history(self, session: Session, limit: int = 10) -> str:
        interactions = (
            self.db.query(Interaction)
            .filter_by(session_id=session.id)
            .order_by(Interaction.created_at.desc())
            .limit(limit)
            .all()
        )
        lines = []
        for i in reversed(interactions):
            role = "导师" if i.role == "assistant" else "学生"
            lines.append(f"[{role}]: {i.content[:500]}")
        return "\n".join(lines)

    def _save_interaction(self, session: Session, kp_id: int, role: str, content: str,
                          phase: str | None = None, question_type: str | None = None,
                          is_correct: bool | None = None, score: float | None = None,
                          p_know_before: float | None = None, p_know_after: float | None = None,
                          metadata_json: dict | None = None):
        interaction = Interaction(
            session_id=session.id,
            user_id=session.user_id,
            knowledge_point_id=kp_id,
            phase=phase,
            role=role,
            content=content,
            question_type=question_type,
            is_correct=is_correct,
            score=score,
            p_know_before=p_know_before,
            p_know_after=p_know_after,
            metadata_json=metadata_json or {},
        )
        self.db.add(interaction)
        self.db.commit()

    def _compute_mastery_status(self, bkt_state: BKTState) -> str:
        if bkt_state.p_know >= settings.mastery_threshold:
            return "mastered"
        elif bkt_state.p_know >= settings.relearn_threshold:
            return "learning"
        else:
            return "needs_relearn"

    def _build_roadmap_snapshot(self, session: Session) -> dict:
        """Build a lightweight roadmap status snapshot."""
        from ..models import Chapter, KnowledgePoint as KP
        chapters = (
            self.db.query(Chapter)
            .filter_by(course_id=session.course_id)
            .order_by(Chapter.order_index)
            .all()
        )
        total_kps = 0
        mastered_kps = 0
        ch_data = []
        for ch in chapters:
            kps = (
                self.db.query(KP)
                .filter_by(chapter_id=ch.id)
                .order_by(KP.order_index)
                .all()
            )
            kp_nodes = []
            for kp in kps:
                state = self.sm.get_or_create_bkt_state(session.user_id, kp.id)
                total_kps += 1
                if state.mastery_status == "mastered":
                    mastered_kps += 1
                kp_nodes.append({
                    "id": kp.id,
                    "title": kp.title,
                    "status": state.mastery_status,
                    "p_know": round(state.p_know * 100),
                })
            ch_data.append({"id": ch.id, "title": ch.title, "knowledge_points": kp_nodes})

        return {
            "overall_progress": round(mastered_kps / max(total_kps, 1) * 100),
            "chapters": ch_data,
        }

    def _get_next_kp(self, kp: KnowledgePoint) -> KnowledgePoint | None:
        """Get the next knowledge point in sequence within the same chapter."""
        from ..models import KnowledgePoint as KP
        return (
            self.db.query(KP)
            .filter(KP.chapter_id == kp.chapter_id, KP.order_index > kp.order_index)
            .order_by(KP.order_index)
            .first()
        )

    def _extract_correct_answer(self, text: str) -> str:
        import re
        patterns = [
            r"正确答案[：:]\s*([A-Da-d])",
            r"答案[：:]\s*([A-Da-d])",
            r"[（(]\s*([A-Da-d])\s*[)）]",
            r"正确选项[：:]\s*([A-Da-d])",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1).upper()
        return ""

    def _strip_correct_answer_marker(self, text: str) -> str:
        """Remove [正确答案: X] line(s) from the displayed text."""
        import re
        text = re.sub(r'\n?\s*\[正确答案[：:]\s*[A-Da-d]\]\s*', '', text)
        text = re.sub(r'\n?\s*\[答案[：:]\s*[A-Da-d]\]\s*', '', text)
        text = re.sub(r'\n?\s*正确答案[：:]\s*[A-Da-d]\s*', '', text)
        return text.strip()

    def _format_options_for_feedback(self, question_text: str) -> str:
        """Extract option lines from question text for feedback prompt."""
        import re
        options = re.findall(r'([A-D][\.\)、．]\s*.+?)(?=\s*(?:[A-D][\.\)、．]|$|<br|</p))', question_text)
        if options:
            return '; '.join(o.strip() for o in options)
        return question_text[:200]

    async def _generate_feedback(self, concept_title: str, question_text: str,
                                  options_text: str, correct_answer: str,
                                  user_answer: str, is_correct: bool) -> str:
        """Generate brief encouraging feedback with explanation."""
        judgment = "正确" if is_correct else "错误"
        prompt = ANSWER_FEEDBACK_PROMPT.format(
            concept_title=concept_title,
            question_text=question_text[:300],
            options_text=options_text[:300],
            correct_answer=correct_answer,
            user_answer=user_answer[:200],
            judgment=judgment,
        )
        try:
            result = await deepseek.generate(
                system_prompt="你是一位耐心友善的导师。请给出简洁的反馈和解析。",
                user_prompt=prompt,
                temperature=0.4,
                max_tokens=200,
            )
            return result.strip()
        except Exception:
            if is_correct:
                return f"回答正确！选项 {correct_answer} 是正确答案。"
            else:
                return f"正确答案是 {correct_answer}。让我们看看为什么。"
