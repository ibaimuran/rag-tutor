from ..llm.deepseek_client import deepseek
from ..llm.prompt_templates import SCORE_ANSWER_PROMPT


class TestScorer:
    """Scores test question answers."""

    async def score_question(self, question_text: str, user_answer: str,
                             correct_answer: str, question_type: str,
                             knowledge_point_summary: str = "") -> dict:
        if question_type in ("multiple_choice", "true_false"):
            is_correct = user_answer.strip().upper() == correct_answer.strip().upper()
            return {"score": 1.0 if is_correct else 0.0, "is_correct": is_correct}

        prompt = SCORE_ANSWER_PROMPT.format(
            question=question_text,
            expected_concept=knowledge_point_summary or question_text,
            user_answer=user_answer,
        )
        try:
            score_text = await deepseek.generate(
                system_prompt="你是一个专业的教学评估系统。只返回数字分数。",
                user_prompt=prompt,
                temperature=0.1,
                max_tokens=10,
            )
            score = self._parse_score(score_text)
        except Exception:
            score = 0.5

        return {"score": score, "is_correct": score >= 0.7}

    def _parse_score(self, text: str) -> float:
        import re
        match = re.search(r"(\d+\.?\d*)", text.strip())
        if match:
            return max(0.0, min(1.0, float(match.group(1))))
        return 0.5
