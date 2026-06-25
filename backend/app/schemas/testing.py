from pydantic import BaseModel


class TestAnswer(BaseModel):
    question_id: int
    answer: str


class TestSubmitRequest(BaseModel):
    answers: list[TestAnswer]


class SingleAnswerRequest(BaseModel):
    question_id: int
    answer: str


class SingleAnswerResponse(BaseModel):
    question_id: int
    is_correct: bool
    score: float
    correct_answer: str
    has_next: bool
    next_question_id: int | None = None


class TestResult(BaseModel):
    test_id: int
    chapter_id: int
    overall_score: float
    concept_results: dict
    needs_relearn: list[int]
    chapter_passed: bool
