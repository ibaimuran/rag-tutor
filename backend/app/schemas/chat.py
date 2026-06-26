from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str = ""
    target_kp_id: int | None = None


class ChatResponse(BaseModel):
    reply: str
    current_kp: dict | None = None
