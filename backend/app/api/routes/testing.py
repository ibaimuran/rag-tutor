from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession
from ...api.deps import get_db, get_retriever
from ...core.session_manager import SessionManager
from ...testing.generator import TestGenerator
from ...testing.adaptive_controller import AdaptiveController
from ...schemas.testing import TestSubmitRequest, SingleAnswerRequest

router = APIRouter(prefix="/api/v1/sessions", tags=["testing"])


@router.post("/{session_id}/test/generate")
async def generate_test(session_id: int, chapter_id: int, db: DbSession = Depends(get_db)):
    retriever = get_retriever()
    generator = TestGenerator(db, retriever)
    test = await generator.generate_chapter_test(session_id, chapter_id)
    questions = [
        {
            "id": q.id,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": q.options_json,
            "knowledge_point_id": q.knowledge_point_id,
        }
        for q in (test.questions or [])
    ]
    return {
        "test_id": test.id,
        "chapter_id": test.chapter_id,
        "status": test.status,
        "total_questions": len(questions),
        "questions": questions,
    }


@router.get("/{session_id}/test/{test_id}")
async def get_test(session_id: int, test_id: int, db: DbSession = Depends(get_db)):
    from ...models import ChapterTest
    test = db.query(ChapterTest).filter_by(id=test_id, session_id=session_id).first()
    if not test:
        return {"error": "Test not found"}
    return {
        "test_id": test.id,
        "chapter_id": test.chapter_id,
        "status": test.status,
        "overall_score": test.overall_score,
        "questions": [
            {
                "id": q.id,
                "question_text": q.question_text,
                "question_type": q.question_type,
                "options": q.options_json,
                "knowledge_point_id": q.knowledge_point_id,
                "user_answer": q.user_answer,
                "is_correct": q.is_correct,
                "score": q.score,
            }
            for q in (test.questions or [])
        ],
    }


@router.get("/{session_id}/test/{test_id}/next")
async def get_next_question(session_id: int, test_id: int, db: DbSession = Depends(get_db)):
    """Return the next unanswered question in the test (one at a time)."""
    from ...models import ChapterTest, TestQuestion
    test = db.query(ChapterTest).filter_by(id=test_id, session_id=session_id).first()
    if not test:
        return {"error": "Test not found"}

    # Count answered and total
    all_questions = test.questions or []
    answered = [q for q in all_questions if q.user_answer is not None]
    unanswered = [q for q in all_questions if q.user_answer is None]

    if not unanswered:
        return {
            "complete": True,
            "total": len(all_questions),
            "answered": len(answered),
            "overall_score": test.overall_score,
        }

    next_q = unanswered[0]
    return {
        "complete": False,
        "question": {
            "id": next_q.id,
            "question_text": next_q.question_text,
            "question_type": next_q.question_type,
            "options": next_q.options_json,
            "knowledge_point_id": next_q.knowledge_point_id,
        },
        "total": len(all_questions),
        "answered": len(answered),
        "remaining": len(unanswered),
    }


@router.post("/{session_id}/test/{test_id}/answer")
async def submit_single_answer(session_id: int, test_id: int, req: SingleAnswerRequest,
                                db: DbSession = Depends(get_db)):
    """Submit a single answer and get immediate feedback."""
    from ...models import ChapterTest, TestQuestion
    from ...testing.scorer import TestScorer

    test = db.query(ChapterTest).filter_by(id=test_id, session_id=session_id).first()
    if not test:
        return {"error": "Test not found"}

    question = db.query(TestQuestion).filter_by(id=req.question_id, test_id=test_id).first()
    if not question:
        return {"error": "Question not found"}

    scorer = TestScorer()
    result = await scorer.score_question(
        question.question_text, req.answer,
        question.correct_answer, question.question_type,
    )
    question.user_answer = req.answer
    question.is_correct = result["is_correct"]
    question.score = result["score"]
    db.commit()

    # Check if this was the last question
    all_questions = test.questions or []
    remaining = [q for q in all_questions if q.user_answer is None]
    next_q = remaining[0] if remaining else None

    # If all answered, run adaptive controller
    overall_result = None
    if not remaining:
        controller = AdaptiveController(db)
        overall_result = await controller.process_test_results(test)

    return {
        "question_id": req.question_id,
        "is_correct": result["is_correct"],
        "score": result["score"],
        "correct_answer": question.correct_answer,
        "has_next": next_q is not None,
        "next_question_id": next_q.id if next_q else None,
        "overall_result": overall_result,
    }


@router.post("/{session_id}/test/{test_id}/submit")
async def submit_test(session_id: int, test_id: int, req: TestSubmitRequest, db: DbSession = Depends(get_db)):
    from ...models import ChapterTest, TestQuestion
    from ...testing.scorer import TestScorer

    test = db.query(ChapterTest).filter_by(id=test_id, session_id=session_id).first()
    if not test:
        return {"error": "Test not found"}

    scorer = TestScorer()
    for ans in req.answers:
        question = db.query(TestQuestion).filter_by(id=ans.question_id, test_id=test_id).first()
        if not question:
            continue
        result = await scorer.score_question(
            question.question_text, ans.answer,
            question.correct_answer, question.question_type,
        )
        question.user_answer = ans.answer
        question.is_correct = result["is_correct"]
        question.score = result["score"]
    db.commit()

    controller = AdaptiveController(db)
    result = await controller.process_test_results(test)
    return result


@router.get("/{session_id}/check-test-ready")
async def check_test_ready(session_id: int, chapter_id: int | None = None, db: DbSession = Depends(get_db)):
    sm = SessionManager(db)
    session = sm.get_session(session_id)
    if not session:
        return {"test_ready": False, "chapter_id": None}

    if chapter_id and sm.are_all_chapter_kps_mastered(session.user_id, chapter_id):
        return {"test_ready": True, "chapter_id": chapter_id}

    return {"test_ready": False, "chapter_id": chapter_id}
