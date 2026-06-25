from pydantic import BaseModel


class BktStateInfo(BaseModel):
    kp_id: int
    kp_title: str
    p_know: float
    mastery_status: str
    total_attempts: int
    correct_count: int


class ProgressSummary(BaseModel):
    user_id: int
    course_id: int
    course_title: str
    overall_progress: float
    concepts_mastered: int
    concepts_total: int
    bkt_states: list[dict]
