"""Quiz API - per-knowledge-point quiz with BKT evaluation.

Flow:
  POST /quiz/start   → Generate 10 questions, return greeting + Q1
  POST /quiz/answer  → Submit answer to current question, return feedback + next Q
  GET  /quiz/result  → Final BKT evaluation after all questions
"""

import json
import re
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from ...api.deps import get_db
from ...core.session_manager import SessionManager
from ...bkt.model import BKTParams, BKTState
from ...bkt.updater import update_bkt_posterior
from ...config import settings
from ...llm.deepseek_client import deepseek
from ...llm.prompt_templates import QUESTION_BANK_PROMPT
from ...models import Session, KnowledgePoint, UserKnowledgeState, QuizAttempt

router = APIRouter(prefix="/api/v1/sessions", tags=["quiz"])

QUIZ_QUESTION_COUNT = 10
QUIZ_SYSTEM_PROMPT = """\
你是一个专业的教育测试设计系统。请为以下知识点生成{count}道选择题。

## 要求
1. 共生成**{count}道题**，全部为选择题，每道4个选项(A/B/C/D)
2. 难度由浅入深：前3道基础，中间4道中等，最后3道综合
3. 正确选项随机分布在A/B/C/D中，不要集中在某个选项
4. 每个选项看起来都应该合理，不要有显然错误的选项
5. 题目考察学生对概念的理解，而非死记硬背

## 输出格式（严格JSON）
```json
{{
  "questions": [
    {{
      "question_text": "题目内容",
      "options": [
        {{"label": "A", "text": "选项A内容"}},
        {{"label": "B", "text": "选项B内容"}},
        {{"label": "C", "text": "选项C内容"}},
        {{"label": "D", "text": "选项D内容"}}
      ],
      "correct_answer": "A",
      "difficulty": 1
    }}
  ]
}}
```

只输出JSON，不要有任何额外文字。"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if lines[0].startswith("```") else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:text.rstrip().rfind("```")]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        return {}


@router.post("/{session_id}/quiz/start")
async def start_quiz(session_id: int, kp_id: int, db: DbSession = Depends(get_db)):
    """Generate 10 MCQs for a knowledge point and start a quiz session."""
    sm = SessionManager(db)
    session = sm.get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    kp = db.query(KnowledgePoint).filter_by(id=kp_id).first()
    if not kp:
        return {"error": "Knowledge point not found"}

    # Check for existing in-progress quiz
    existing = (
        db.query(QuizAttempt)
        .filter_by(session_id=session_id, knowledge_point_id=kp_id, status="in_progress")
        .first()
    )
    if existing:
        return _format_quiz_question(existing)

    # Generate questions via LLM
    system_prompt = QUIZ_SYSTEM_PROMPT.format(count=QUIZ_QUESTION_COUNT)
    user_prompt = f"""## 知识点
**{kp.title}**
{kp.description or kp.title}

## 所属章节
（课程知识点）

请生成{QUIZ_QUESTION_COUNT}道选择题。"""

    try:
        response = await deepseek.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.4,
            max_tokens=4096,
        )
        data = _parse_json(response)
    except Exception:
        return {"error": "Failed to generate quiz questions. Please try again."}

    questions = data.get("questions", [])
    if len(questions) < 5:
        return {"error": "Generated too few questions. Please try again."}

    # Get BKT state
    bkt_db = sm.get_or_create_bkt_state(session.user_id, kp_id)

    # Create quiz attempt
    quiz = QuizAttempt(
        session_id=session_id,
        knowledge_point_id=kp_id,
        questions_json=questions[:QUIZ_QUESTION_COUNT],
        current_index=0,
        answers_json=[],
        start_p_know=bkt_db.p_know,
        bkt_params_json={
            "p_l0": bkt_db.p_l0,
            "p_t": bkt_db.p_t,
            "p_g": bkt_db.p_g,
            "p_s": bkt_db.p_s,
        },
        status="in_progress",
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)

    return _format_quiz_start(quiz, kp)


@router.post("/{session_id}/quiz/{quiz_id}/answer")
async def answer_quiz_question(
    session_id: int,
    quiz_id: int,
    answer: str = "",
    db: DbSession = Depends(get_db),
):
    """Submit answer to current question, get feedback and next question."""
    quiz = db.query(QuizAttempt).filter_by(id=quiz_id, session_id=session_id).first()
    if not quiz:
        return {"error": "Quiz not found"}
    if quiz.status == "completed":
        return {"error": "Quiz already completed", "completed": True}

    questions = quiz.questions_json or []
    idx = quiz.current_index
    if idx >= len(questions):
        return {"error": "All questions already answered"}

    current_q = questions[idx]
    correct_answer = current_q.get("correct_answer", "").strip().upper()
    user_answer = answer.strip().upper()
    is_correct = user_answer == correct_answer

    # Update BKT
    bkt_params = BKTParams(
        p_l0=quiz.bkt_params_json.get("p_l0", 0.50) if quiz.bkt_params_json else 0.50,
        p_t=quiz.bkt_params_json.get("p_t", 0.20) if quiz.bkt_params_json else 0.20,
        p_g=quiz.bkt_params_json.get("p_g", 0.15) if quiz.bkt_params_json else 0.15,
        p_s=quiz.bkt_params_json.get("p_s", 0.10) if quiz.bkt_params_json else 0.10,
    )
    current_p_know = quiz.end_p_know if quiz.end_p_know is not None else quiz.start_p_know
    bkt_state = BKTState(params=bkt_params, p_know=current_p_know)
    bkt_state = update_bkt_posterior(bkt_state, is_correct)

    # Record answer
    answers = list(quiz.answers_json or [])
    answers.append({
        "question_index": idx,
        "user_answer": user_answer,
        "correct_answer": correct_answer,
        "is_correct": is_correct,
        "p_know_after": round(bkt_state.p_know, 4),
    })

    # Update quiz
    quiz.answers_json = answers
    quiz.current_index = idx + 1
    quiz.end_p_know = bkt_state.p_know

    # Check if quiz is complete
    if quiz.current_index >= len(questions):
        quiz.status = "completed"
        db.commit()
        db.refresh(quiz)

        # Persist BKT to user knowledge state
        sm = SessionManager(db)
        session = sm.get_session(session_id)
        if session:
            bkt_db = sm.get_or_create_bkt_state(session.user_id, quiz.knowledge_point_id)
            bkt_db.p_know = bkt_state.p_know
            bkt_db.total_attempts = (bkt_db.total_attempts or 0) + len(answers)
            bkt_db.correct_count = (bkt_db.correct_count or 0) + sum(
                1 for a in answers if a["is_correct"]
            )
            bkt_db.mastery_status = _compute_mastery_status(bkt_state)
            sm.save_bkt_state(bkt_db)

        return _format_quiz_complete(quiz, bkt_state)

    db.commit()
    db.refresh(quiz)

    # Return feedback + next question
    next_q = questions[quiz.current_index]
    return {
        "completed": False,
        "feedback": {
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "question_index": idx,
        },
        "next_question": {
            "index": quiz.current_index,
            "total": len(questions),
            "question_text": next_q["question_text"],
            "options": next_q.get("options", []),
            "difficulty": next_q.get("difficulty", 1),
        },
        "progress": {
            "answered": quiz.current_index,
            "total": len(questions),
            "pct": round(quiz.current_index / len(questions) * 100),
        },
    }


@router.get("/{session_id}/quiz/{quiz_id}/result")
async def get_quiz_result(session_id: int, quiz_id: int, db: DbSession = Depends(get_db)):
    """Get final BKT evaluation result for a completed quiz."""
    quiz = db.query(QuizAttempt).filter_by(id=quiz_id, session_id=session_id).first()
    if not quiz:
        return {"error": "Quiz not found"}

    questions = quiz.questions_json or []
    answers = quiz.answers_json or []

    if quiz.status != "completed":
        # Compute current BKT
        bkt_params = BKTParams(
            p_l0=quiz.bkt_params_json.get("p_l0", 0.50) if quiz.bkt_params_json else 0.50,
            p_t=quiz.bkt_params_json.get("p_t", 0.20) if quiz.bkt_params_json else 0.20,
            p_g=quiz.bkt_params_json.get("p_g", 0.15) if quiz.bkt_params_json else 0.15,
            p_s=quiz.bkt_params_json.get("p_s", 0.10) if quiz.bkt_params_json else 0.10,
        )
        current_p_know = quiz.end_p_know if quiz.end_p_know is not None else quiz.start_p_know
        bkt_state = BKTState(params=bkt_params, p_know=current_p_know)
        return {
            "completed": False,
            "progress": {
                "answered": len(answers),
                "total": len(questions),
            },
            "current_p_know": round(bkt_state.p_know * 100),
        }

    # Build final result
    correct_count = sum(1 for a in answers if a["is_correct"])
    total = len(answers)
    accuracy = correct_count / max(total, 1) * 100

    p_know = quiz.end_p_know or quiz.start_p_know
    pct = round(p_know * 100)
    status = _compute_mastery_status(BKTState(p_know=p_know))

    # Determine confidence: consistent answers → high confidence
    consistent = _is_consistent(answers)

    if pct >= 80 and consistent:
        assessment = "你对这个知识点掌握得很好，是真掌握而非猜测。"
    elif pct >= 60 and consistent:
        assessment = "你对这个知识点有一定掌握，但还不够扎实。建议再复习一下教材内容。"
    elif pct >= 60 and not consistent:
        assessment = "你的答题正确率尚可，但表现不够稳定，可能存在猜测成分。建议重新学习。"
    elif pct >= 30:
        assessment = "你对此知识点的掌握还比较薄弱，需要系统性地重新学习。"
    else:
        assessment = "你尚未掌握这个知识点，建议从基础概念开始重新学习。"

    return {
        "completed": True,
        "knowledge_point": quiz.knowledge_point_id,
        "total_questions": total,
        "correct_count": correct_count,
        "accuracy_pct": round(accuracy),
        "p_know_start": round(quiz.start_p_know * 100),
        "p_know_end": pct,
        "mastery_status": status,
        "assessment": assessment,
        "consistent": consistent,
        "details": [
            {
                "question_index": a["question_index"],
                "is_correct": a["is_correct"],
                "user_answer": a.get("user_answer", ""),
                "correct_answer": a.get("correct_answer", ""),
            }
            for a in answers
        ],
    }


@router.get("/{session_id}/quiz/current")
async def get_current_quiz(session_id: int, kp_id: int, db: DbSession = Depends(get_db)):
    """Get the current quiz for a knowledge point: in-progress first, then last completed."""
    # 优先返回进行中的测验
    quiz = (
        db.query(QuizAttempt)
        .filter_by(session_id=session_id, knowledge_point_id=kp_id, status="in_progress")
        .first()
    )
    if quiz:
        return {"has_quiz": True, "quiz_id": quiz.id, "status": "in_progress",
                "current_index": quiz.current_index, "total": len(quiz.questions_json or [])}

    # 如果没有进行中的，查找最近完成的测验
    quiz = (
        db.query(QuizAttempt)
        .filter_by(session_id=session_id, knowledge_point_id=kp_id, status="completed")
        .order_by(QuizAttempt.id.desc())
        .first()
    )
    if quiz:
        return {"has_quiz": True, "quiz_id": quiz.id, "status": "completed",
                "total": len(quiz.questions_json or [])}

    return {"has_quiz": False}


def _format_quiz_start(quiz: QuizAttempt, kp: KnowledgePoint) -> dict:
    questions = quiz.questions_json or []
    first_q = questions[0] if questions else None
    return {
        "quiz_id": quiz.id,
        "greeting": f"你好，我是你的知识点掌握程度检测助手。让我们来检测你对「{kp.title}」的掌握情况。本测验共{len(questions)}道选择题，请点击选项作答。",
        "knowledge_point": {"id": kp.id, "title": kp.title},
        "total_questions": len(questions),
        "first_question": {
            "index": 0,
            "total": len(questions),
            "question_text": first_q["question_text"] if first_q else "",
            "options": first_q.get("options", []) if first_q else [],
            "difficulty": first_q.get("difficulty", 1) if first_q else 1,
        } if first_q else None,
    }


def _format_quiz_question(quiz: QuizAttempt) -> dict:
    questions = quiz.questions_json or []
    idx = quiz.current_index
    if idx >= len(questions):
        return {"error": "All questions answered", "completed": True}
    q = questions[idx]
    return {
        "quiz_id": quiz.id,
        "completed": False,
        "question": {
            "index": idx,
            "total": len(questions),
            "question_text": q["question_text"],
            "options": q.get("options", []),
            "difficulty": q.get("difficulty", 1),
        },
        "progress": {
            "answered": idx,
            "total": len(questions),
            "pct": round(idx / len(questions) * 100),
        },
    }


def _format_quiz_complete(quiz: QuizAttempt, bkt_state: BKTState) -> dict:
    answers = quiz.answers_json or []
    correct_count = sum(1 for a in answers if a["is_correct"])
    total = len(answers)
    pct = round(bkt_state.p_know * 100)
    status = _compute_mastery_status(bkt_state)
    consistent = _is_consistent(answers)

    if pct >= 80 and consistent:
        assessment = "你对这个知识点掌握得很好，是真掌握而非猜测。"
    elif pct >= 60 and consistent:
        assessment = "你对这个知识点有一定掌握，但还不够扎实。建议再复习一下教材内容。"
    elif pct >= 60 and not consistent:
        assessment = "你的答题正确率尚可，但表现不够稳定，可能存在猜测成分。建议重新学习。"
    elif pct >= 30:
        assessment = "你对此知识点的掌握还比较薄弱，需要系统性地重新学习。"
    else:
        assessment = "你尚未掌握这个知识点，建议从基础概念开始重新学习。"

    # Last question feedback
    last_answer = answers[-1] if answers else {}
    feedback = {
        "is_correct": last_answer.get("is_correct", False),
        "correct_answer": last_answer.get("correct_answer", ""),
        "question_index": last_answer.get("question_index", 0),
    }

    return {
        "completed": True,
        "quiz_id": quiz.id,
        "feedback": feedback,
        "total_questions": total,
        "correct_count": correct_count,
        "accuracy_pct": round(correct_count / max(total, 1) * 100),
        "p_know_start": round(quiz.start_p_know * 100),
        "p_know_end": pct,
        "mastery_status": status,
        "assessment": assessment,
        "consistent": consistent,
        "details": [
            {
                "question_index": a["question_index"],
                "is_correct": a["is_correct"],
                "user_answer": a.get("user_answer", ""),
                "correct_answer": a.get("correct_answer", ""),
            }
            for a in answers
        ],
    }


def _compute_mastery_status(bkt_state: BKTState) -> str:
    if bkt_state.p_know >= settings.mastery_threshold:
        return "mastered"
    elif bkt_state.p_know >= settings.relearn_threshold:
        return "learning"
    return "needs_relearn"


def _is_consistent(answers: list[dict]) -> bool:
    """Check if answer pattern is consistent (not random guessing).

    Consistent means: correct answers are clustered (not alternating).
    Random guessing produces high variance in correctness sequence.
    """
    if len(answers) < 3:
        return len(answers) > 0 and all(a["is_correct"] for a in answers)

    # Count transitions (correct→incorrect or incorrect→correct)
    transitions = 0
    for i in range(1, len(answers)):
        if answers[i]["is_correct"] != answers[i - 1]["is_correct"]:
            transitions += 1

    # High transitions relative to length suggests guessing
    # Max possible transitions = len-1
    max_transitions = len(answers) - 1
    if max_transitions == 0:
        return True

    ratio = transitions / max_transitions
    return ratio < 0.6  # If < 60% transitions, pattern is consistent
