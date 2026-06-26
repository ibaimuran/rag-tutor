from sqlalchemy.orm import Session as DbSession
from ..models import ChapterTest, TestQuestion, UserKnowledgeState
from ..bkt.model import BKTState, BKTParams
from ..bkt.updater import update_bkt_posterior
from ..core.mastery_gate import MasteryGate, MasteryDecision
from ..core.session_manager import SessionManager


class AdaptiveController:
    """
    After a chapter test:
    1. Updates BKT for all tested concepts from test answers
    2. Identifies concepts with P(know) < 0.60 for forced relearning
    3. Updates mastery status across all tested concepts
    """

    def __init__(self, db: DbSession):
        self.db = db
        self.sm = SessionManager(db)
        self.gate = MasteryGate()

    async def process_test_results(self, test: ChapterTest) -> dict:
        session = self.sm.get_session(test.session_id)
        if not session:
            return {"error": "Session not found"}

        user_id = session.user_id
        concept_results = {}

        for question in test.questions:
            kp_id = question.knowledge_point_id
            if not kp_id:
                continue
            if not question.user_answer:
                continue

            if kp_id not in concept_results:
                db_state = self.sm.get_or_create_bkt_state(user_id, kp_id)
                concept_results[kp_id] = {
                    "bkt_state": BKTState(
                        params=BKTParams(db_state.p_l0, db_state.p_t, db_state.p_g, db_state.p_s),
                        p_know=db_state.p_know,
                    ),
                    "db_state": db_state,
                    "test_answers": [],
                    "correct_count": 0,
                    "total_count": 0,
                }

            bst = concept_results[kp_id]["bkt_state"]
            is_correct = question.is_correct or False
            concept_results[kp_id]["bkt_state"] = update_bkt_posterior(bst, is_correct)
            concept_results[kp_id]["total_count"] += 1
            if is_correct:
                concept_results[kp_id]["correct_count"] += 1

        # Analyze and update
        bkt_analysis = {}
        needs_relearn = []
        all_passed = True

        for kp_id, data in concept_results.items():
            new_bkt = data["bkt_state"]
            db_state = data["db_state"]
            p_know_before = db_state.p_know  # 在更新前捕获原始值

            db_state.p_know = new_bkt.p_know
            db_state.total_attempts += data["total_count"]
            db_state.correct_count += data["correct_count"]

            passed = self.gate.check_chapter_pass({kp_id: new_bkt}).get(kp_id, False)
            if passed:
                db_state.mastery_status = "mastered"
            else:
                db_state.mastery_status = "needs_relearn"
                needs_relearn.append(kp_id)
                all_passed = False

            self.sm.save_bkt_state(db_state)

            bkt_analysis[str(kp_id)] = {
                "p_know_before": round(p_know_before, 4),
                "p_know_after": round(new_bkt.p_know, 4),
                "mastery_status": db_state.mastery_status,
                "needs_relearn": not passed,
                "correct_answers": f"{data['correct_count']}/{data['total_count']}",
            }

        # Update test
        overall = sum(
            d["correct_count"] / max(d["total_count"], 1) for d in concept_results.values()
        ) / max(len(concept_results), 1)
        test.overall_score = round(overall * 100)
        test.bkt_analysis = bkt_analysis
        test.status = "completed"
        self.db.commit()

        return {
            "test_id": test.id,
            "chapter_id": test.chapter_id,
            "overall_score": round(overall * 100),
            "concept_results": bkt_analysis,
            "needs_relearn": needs_relearn,
            "chapter_passed": all_passed,
        }
