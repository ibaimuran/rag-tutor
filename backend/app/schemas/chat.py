from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str = ""
    target_kp_id: int | None = None


class BktUpdate(BaseModel):
    kp_id: int
    p_know_before: float
    p_know_after: float
    mastery_status: str


class ChatResponse(BaseModel):
    reply: str
    phase: str
    current_kp: dict | None = None
    bkt_update: dict | None = None
    roadmap_update: dict | None = None
    test_ready: bool = False
    next_action: dict | None = None
    guessed: bool = False
