import re
from sqlalchemy.orm import Session as DbSession
from ..models import Interaction, KnowledgePoint
from ..llm.deepseek_client import deepseek
from ..llm.prompt_templates import (
    QA_SYSTEM_PROMPT,
    QA_USER_PROMPT,
    CHEMICAL_EQUATION_PROMPT,
)
from ..config import settings


class QAAgent:
    """知识问答 Agent —— 基于 RAG 检索 + 教材内容回答用户问题，支持化学方程式配平。"""

    def __init__(self, db: DbSession, retriever=None):
        self.db = db
        self.retriever = retriever

    async def process_message(self, session, user_message: str, target_kp_id: int | None = None) -> dict:
        kp = self._resolve_kp(session, target_kp_id)
        current_kp = None
        if kp:
            current_kp = {"id": kp.id, "title": kp.title, "chapter_id": kp.chapter_id}

        # 更新 session 当前知识点（持久化到数据库，刷新后保留）
        if kp and session.current_kp_id != kp.id:
            session.current_kp_id = kp.id
            self.db.commit()

        if not user_message.strip():
            return {"reply": "你好！我是 AI 知识问答助手。请针对当前知识点提问，或者发送化学方程式让我帮你配平。", "current_kp": current_kp}

        # 保存用户消息
        self._save_interaction(session, kp.id if kp else None, "user", user_message)

        # RAG 检索教材内容
        retrieved_context = ""
        if kp and self.retriever:
            chunks = self.retriever.retrieve_for_concept(
                session.course_id, kp.title, kp.description or "", settings.retrieval_top_k
            )
            if chunks:
                retrieved_context = "\n\n".join(
                    f"【资料 {i+1}】{c['text'][:800]}" for i, c in enumerate(chunks[:3])
                )

        # 聊天历史
        chat_history = self._get_chat_history(session)

        # 检测是否为配平请求
        if self._detect_equation_balance(user_message):
            reply = await self._handle_equation_balance(user_message, kp, retrieved_context, chat_history)
        else:
            reply = await self._handle_qa(user_message, kp, retrieved_context, chat_history)

        # 保存 AI 回答
        self._save_interaction(session, kp.id if kp else None, "assistant", reply)

        return {"reply": reply, "current_kp": current_kp}

    # ─── 内部方法 ───

    def _resolve_kp(self, session, target_kp_id: int | None):
        kp_id = target_kp_id or session.current_kp_id
        if kp_id:
            return self.db.query(KnowledgePoint).filter_by(id=kp_id).first()
        return None

    def _detect_equation_balance(self, text: str) -> bool:
        """检测是否为化学方程式配平请求。"""
        if any(kw in text for kw in ["配平", "化学方程式", "配平方程式", "平衡方程式"]):
            return True
        if re.search(r'[A-Z][a-z]?\d*\s*[\+=→]\s*', text) or re.search(r'[→=]\s*[A-Z][a-z]?\d*', text):
            return True
        if '+' in text and any(kw in text for kw in ["反应", "生成", "燃烧", "加热", "高温", "催化剂"]):
            return True
        return False

    def _get_chat_history(self, session, limit: int = 10) -> str:
        interactions = (
            self.db.query(Interaction)
            .filter_by(session_id=session.id)
            .order_by(Interaction.created_at.desc())
            .limit(limit)
            .all()
        )
        if not interactions:
            return "（无历史对话）"

        lines = []
        for i in reversed(interactions):
            role = "用户" if i.role == "user" else "AI"
            content = i.content[:300] if i.content else ""
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)

    async def _handle_qa(self, user_message: str, kp, retrieved_context: str, chat_history: str) -> str:
        concept_title = kp.title if kp else "通用知识"
        concept_desc = kp.description or "" if kp else ""
        context = retrieved_context or "（暂无相关教材资料）"

        system_prompt = QA_SYSTEM_PROMPT
        user_prompt = QA_USER_PROMPT.format(
            concept_title=concept_title,
            concept_description=concept_desc,
            retrieved_context=context,
            chat_history=chat_history,
            user_question=user_message,
        )

        return await deepseek.generate(system_prompt, user_prompt, temperature=0.7, max_tokens=2048)

    async def _handle_equation_balance(self, user_message: str, kp, retrieved_context: str, chat_history: str) -> str:
        system_prompt = CHEMICAL_EQUATION_PROMPT
        user_prompt = f"## 用户请求\n{user_message}\n\n请配平以上化学方程式，严格使用 LaTeX 格式书写。"

        return await deepseek.generate(system_prompt, user_prompt, temperature=0.3, max_tokens=2048)

    def _save_interaction(self, session, kp_id: int | None, role: str, content: str):
        interaction = Interaction(
            session_id=session.id,
            user_id=session.user_id,
            knowledge_point_id=kp_id,
            role=role,
            content=content,
        )
        self.db.add(interaction)
        self.db.commit()
