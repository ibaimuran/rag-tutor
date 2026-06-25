from ..config import settings
from ..bkt.model import BKTState


class MasteryDecision:
    MASTERED = "mastered"
    CONTINUE = "continue"
    NEEDS_RELEARN = "needs_relearn"


class MasteryGate:
    THRESHOLD_MASTERED = settings.mastery_threshold
    THRESHOLD_RELEARN = settings.relearn_threshold

    def check_mastery(self, bkt_state: BKTState) -> str:
        if bkt_state.p_know >= self.THRESHOLD_MASTERED:
            return MasteryDecision.MASTERED
        elif bkt_state.p_know < self.THRESHOLD_RELEARN:
            return MasteryDecision.NEEDS_RELEARN
        return MasteryDecision.CONTINUE

    def get_next_action(self, bkt_state: BKTState) -> dict:
        if bkt_state.p_know >= self.THRESHOLD_MASTERED:
            return {"action": "advance", "reason": "mastery_achieved"}
        elif bkt_state.p_know < self.THRESHOLD_RELEARN:
            return {"action": "relearn", "reason": "below_threshold"}
        return {"action": "continue", "reason": "in_progress"}

    def check_chapter_pass(self, concept_states: dict[int, BKTState]) -> dict[int, bool]:
        return {
            kp_id: state.p_know >= self.THRESHOLD_RELEARN
            for kp_id, state in concept_states.items()
        }
