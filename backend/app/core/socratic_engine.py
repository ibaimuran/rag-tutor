import json
from ..llm.deepseek_client import deepseek
from ..llm.prompt_templates import SCORE_ANSWER_PROMPT


class SocraticEngine:
    """Scores user answers and classifies AI questions."""

    async def score_answer(
        self, question_text: str, user_answer: str,
        knowledge_point_summary: str, question_type: str = "open",
        correct_answer: str = "",
    ) -> float:
        if question_type in ("multiple_choice", "true_false") and correct_answer:
            user_clean = user_answer.strip().upper()
            correct_clean = correct_answer.strip().upper()
            # If user sent "B. text...", extract just the letter
            import re
            m = re.match(r'^([A-D])[\.\)、．]', user_clean)
            if m:
                user_clean = m.group(1)
            return 1.0 if user_clean == correct_clean else 0.0

        if question_type in ("open", "short_answer"):
            prompt = SCORE_ANSWER_PROMPT.format(
                question=question_text,
                expected_concept=knowledge_point_summary,
                user_answer=user_answer,
            )
            try:
                score_text = await deepseek.generate(
                    system_prompt="你是一个专业的教学评估系统。只返回数字分数。",
                    user_prompt=prompt,
                    temperature=0.1,
                    max_tokens=10,
                )
                return self._parse_score(score_text)
            except Exception:
                return self._heuristic_score(user_answer, knowledge_point_summary)

        return 0.5

    def has_question(self, text: str) -> bool:
        return "?" in text or "？" in text

    def classify_question_type(self, text: str) -> str:
        import re
        # Check for at least 2 option markers (A. and B., etc.)
        option_matches = re.findall(r'\b([A-D])[\.\)、．]', text)
        if len(set(option_matches)) >= 2:
            return "multiple_choice"
        markers = {
            "true_false": ["正确", "错误", "对", "错", "判断"],
        }
        for qtype, words in markers.items():
            if any(w in text for w in words):
                return qtype
        return "open"

    def _parse_score(self, text: str) -> float:
        import re
        match = re.search(r"(\d+\.?\d*)", text.strip())
        if match:
            score = float(match.group(1))
            return max(0.0, min(1.0, score))
        return 0.5

    def _heuristic_score(self, user_answer: str, expected_summary: str) -> float:
        if not user_answer.strip():
            return 0.0
        if len(user_answer) < 5:
            return 0.3
        return 0.6

    def is_likely_guess(self, user_answer: str, question_type: str) -> bool:
        """Detect if a correct answer is likely a guess (no real understanding)."""
        import re
        if question_type != "multiple_choice":
            return False
        cleaned = user_answer.strip()
        # Just a single letter (A/B/C/D) with no explanation = likely guess
        if re.match(r'^[A-Da-d]\.?\s*$', cleaned):
            return True
        # Contains option letter AND explanation text → not a guess
        if re.match(r'^[A-Da-d][\.\)、．]\s*\S', cleaned) and len(cleaned) > 3:
            return False
        # Very short answer (< 5 chars) with no reasoning = likely guess
        if len(cleaned) < 5:
            return True
        return False
