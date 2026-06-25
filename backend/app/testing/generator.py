import json
from sqlalchemy.orm import Session as DbSession
from ..models import Chapter, KnowledgePoint, ChapterTest, TestQuestion
from ..llm.deepseek_client import deepseek
from ..llm.prompt_templates import TEST_GENERATION_PROMPT
from ..rag.retriever import Retriever


class TestGenerator:
    def __init__(self, db: DbSession, retriever: Retriever | None = None):
        self.db = db
        self.retriever = retriever

    async def generate_chapter_test(self, session_id: int, chapter_id: int) -> ChapterTest:
        test = ChapterTest(session_id=session_id, chapter_id=chapter_id, status="generating")
        self.db.add(test)
        self.db.commit()
        self.db.refresh(test)

        chapter = self.db.query(Chapter).filter_by(id=chapter_id).first()
        if not chapter:
            test.status = "failed"
            self.db.commit()
            return test

        kps = (
            self.db.query(KnowledgePoint)
            .filter_by(chapter_id=chapter_id)
            .order_by(KnowledgePoint.order_index)
            .all()
        )

        kp_list = "\n".join(
            f"- ID={kp.id}: {kp.title}（{kp.description or kp.title}）" for kp in kps
        )

        retrieved_context = ""
        if self.retriever:
            all_chunks = []
            for kp in kps:
                chunks = self.retriever.retrieve_for_concept(
                    chapter.course_id, kp.title, kp.description or "", top_k=2
                )
                all_chunks.extend(chunks)
            retrieved_context = "\n\n".join(c["text"][:300] for c in all_chunks[:8])

        prompt = TEST_GENERATION_PROMPT.format(
            chapter_title=chapter.title,
            knowledge_points_list=kp_list,
            retrieved_context=retrieved_context or "无",
        )

        try:
            response = await deepseek.generate(
                system_prompt="你是一个专业的教育测试设计系统，严格按JSON格式输出。",
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=4096,
            )
            data = self._parse_json(response)
            if not data or "questions" not in data:
                test.status = "failed"
                self.db.commit()
                return test

            for q in data["questions"]:
                tq = TestQuestion(
                    test_id=test.id,
                    knowledge_point_id=q.get("knowledge_point_id"),
                    question_text=q["question_text"],
                    question_type=q.get("question_type", "multiple_choice"),
                    correct_answer=str(q.get("correct_answer", "")),
                    options_json=q.get("options"),
                )
                self.db.add(tq)

            test.status = "ready"
        except Exception as e:
            test.status = "failed"

        self.db.commit()
        self.db.refresh(test)
        return test

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
