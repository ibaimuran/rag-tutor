"""Course generator: creates complete courses from a topic name using LLM."""

import json
import re
from pathlib import Path
from sqlalchemy.orm import Session as DbSession

from ..models import Course, Chapter, KnowledgePoint
from ..config import settings
from ..llm.deepseek_client import deepseek
from ..llm.prompt_templates import KP_CONTENT_MD_PROMPT
from ..rag.embedder import Embedder
from ..rag.vector_store import VectorStore


class CourseGenerator:
    def __init__(self, db: DbSession):
        self.db = db
        self.embedder = Embedder(
            model_name=settings.embedding_model,
            device=settings.embedding_device,
            hf_endpoint=settings.hf_endpoint,
            local_files_only=settings.hf_local_files_only,
        )
        self.vs = VectorStore(settings.chroma_persist_path)

    async def generate_from_topic(self, topic: str) -> dict:
        """Generate a complete course from a topic name using LLM."""
        import traceback
        from ..llm.prompt_templates import COURSE_FROM_TOPIC_PROMPT

        # Step 1: Generate course structure via LLM
        prompt = COURSE_FROM_TOPIC_PROMPT.format(user_topic=topic)
        try:
            raw_response = await deepseek.generate(
                system_prompt="你是一个专业的课程设计系统。严格按JSON格式输出，不要有任何额外文字。",
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=8192,
            )
            structure = self._parse_json(raw_response)
        except Exception as e:
            traceback.print_exc()
            print(f"[WARN] LLM course generation failed ({e}), using fallback structure")
            structure = self._fallback_topic_structure(topic)

        if not structure.get("chapters"):
            structure = self._fallback_topic_structure(topic)

        # Ensure all values are proper types
        structure["course_title"] = str(structure.get("course_title", topic))
        structure["subject"] = str(structure.get("subject", ""))
        structure["grade_level"] = str(structure.get("grade_level", ""))

        # Step 2: Create course in DB
        course = Course(
            title=structure["course_title"],
            subject=structure["subject"],
            grade_level=structure["grade_level"],
        )
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)

        # Step 3: Create chapters and knowledge points + generate MD files
        base_dir = Path("data") / "materials" / self._safe_filename(course.title)
        base_dir.mkdir(parents=True, exist_ok=True)

        plan_md = self._build_course_plan_md(structure)
        (base_dir / "课程大纲.md").write_text(plan_md, encoding="utf-8")

        all_kps = []
        for ch_data in structure.get("chapters", []):
            chapter = Chapter(
                course_id=course.id,
                title=str(ch_data.get("title", "")),
                order_index=ch_data.get("order", len(getattr(course, 'chapters', [])) + 1),
            )
            self.db.add(chapter)
            self.db.commit()
            self.db.refresh(chapter)

            ch_dir = base_dir / self._safe_filename(chapter.title)
            ch_dir.mkdir(parents=True, exist_ok=True)

            for idx, kp_data in enumerate(ch_data.get("knowledge_points", [])):
                prerequisites = kp_data.get("prerequisites", [])
                if not isinstance(prerequisites, list):
                    prerequisites = []
                difficulty = kp_data.get("difficulty", 1)
                if not isinstance(difficulty, int):
                    try:
                        difficulty = int(difficulty)
                    except (ValueError, TypeError):
                        difficulty = 1
                kp = KnowledgePoint(
                    chapter_id=chapter.id,
                    title=str(kp_data.get("title", "")),
                    description=str(kp_data.get("description", "")),
                    content_summary=str(kp_data.get("content_summary", "")),
                    prerequisites=prerequisites,
                    order_index=kp_data.get("order", idx + 1) if isinstance(kp_data.get("order"), int) else idx + 1,
                    difficulty=min(max(difficulty, 1), 5),
                )
                self.db.add(kp)
                self.db.commit()
                self.db.refresh(kp)
                all_kps.append(kp)

                try:
                    md_content = await self._generate_kp_md_content(
                        kp.title, chapter.title, course.title, KP_CONTENT_MD_PROMPT
                    )
                    self._save_kp_markdown(kp, md_content, ch_dir)
                except Exception:
                    pass

        # Step 4: Minimal vector store
        try:
            all_chunks = []
            for kp in all_kps:
                desc = kp.description or ""
                summary = kp.content_summary or ""
                text = f"# {kp.title}\n\n{desc}\n\n{summary}"
                all_chunks.append({
                    "text": text,
                    "metadata": {"source": "generated", "kp_id": kp.id, "chapter_id": kp.chapter_id},
                })
            if all_chunks:
                texts = [c["text"] for c in all_chunks]
                embeddings = self.embedder.embed(texts)
                self.vs.add_chunks(course.id, all_chunks, embeddings)
        except Exception:
            pass

        return {
            "course_id": course.id,
            "course_title": course.title,
            "chapters_count": len(structure.get("chapters", [])),
            "knowledge_points_count": len(all_kps),
            "chunks_ingested": len(all_chunks),
        }

    async def _generate_kp_md_content(self, kp_title: str, chapter_title: str,
                                       course_title: str, prompt_template: str) -> str:
        prompt = prompt_template.format(
            knowledge_point_title=kp_title,
            chapter_context=chapter_title,
            course_context=course_title,
        )
        return await deepseek.generate(
            system_prompt="你是一个专业的教材编写专家，使用Markdown格式编写教学内容。",
            user_prompt=prompt,
            temperature=0.3,
            max_tokens=2048,
        )

    def _save_kp_markdown(self, kp: KnowledgePoint, md_content: str, ch_dir: Path) -> Path:
        file_path = ch_dir / f"{kp.order_index:02d}_{self._safe_filename(kp.title)}.md"
        file_path.write_text(md_content, encoding="utf-8")
        kp.chunk_ids = [str(file_path)]
        self.db.commit()
        return file_path

    def _build_course_plan_md(self, structure: dict) -> str:
        lines = [
            f"# {structure.get('course_title', '课程大纲')}",
            "",
            f"- 学科：{structure.get('subject', '')}",
            f"- 年级：{structure.get('grade_level', '')}",
            f"- 章节数：{len(structure.get('chapters', []))}",
            "",
        ]
        for ch in structure.get("chapters", []):
            lines.append(f"## {ch.get('title', '')}")
            lines.append("")
            for kp in ch.get("knowledge_points", []):
                deps = ", ".join(str(p) for p in kp.get("prerequisites", [])) or "无"
                diff = kp.get("difficulty", 1)
                lines.append(f"- **{kp.get('title', '')}**（难度：{'★' * int(diff) if isinstance(diff, (int, str)) else '★'}，前置依赖：{deps}）")
                lines.append(f"  {kp.get('description', '')}")
            lines.append("")
        return "\n".join(lines)

    def _fallback_topic_structure(self, topic: str) -> dict:
        return {
            "course_title": topic,
            "subject": "",
            "grade_level": "",
            "chapters": [
                {
                    "title": f"第一章 {topic}基础",
                    "order": 1,
                    "knowledge_points": [
                        {"title": f"{topic}入门概念", "description": f"学习{topic}的基本概念和术语", "content_summary": f"{topic}的基础知识", "difficulty": 1, "prerequisites": [], "order": 1},
                        {"title": f"{topic}核心原理", "description": f"理解{topic}的核心原理和规律", "content_summary": f"{topic}的核心内容", "difficulty": 2, "prerequisites": [1], "order": 2},
                        {"title": f"{topic}应用实践", "description": f"将{topic}的知识应用到实际问题中", "content_summary": f"{topic}的实践应用", "difficulty": 3, "prerequisites": [2], "order": 3},
                    ],
                }
            ],
        }

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:]) if lines[0].startswith("```") else text
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:text.rstrip().rfind("```")]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {"course_title": "", "chapters": []}

    @staticmethod
    def _safe_filename(name: str) -> str:
        name = name.strip()
        name = re.sub(r'[\\/:*?"<>|]', '_', name)
        name = re.sub(r'\s+', '_', name)
        return name[:80]
