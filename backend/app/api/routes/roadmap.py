from pathlib import Path
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session as DbSession
from ...api.deps import get_db
from ...roadmap.builder import RoadmapBuilder
from ...roadmap.renderer import RoadmapRenderer

router = APIRouter(prefix="/api/v1/sessions", tags=["roadmap"])


@router.get("/{session_id}/roadmap")
async def get_roadmap(session_id: int, db: DbSession = Depends(get_db)):
    from ...core.session_manager import SessionManager
    sm = SessionManager(db)
    session = sm.get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    builder = RoadmapBuilder(db)
    return builder.build(session.user_id, session.course_id)


@router.get("/{session_id}/roadmap/html", response_class=HTMLResponse)
async def get_roadmap_html(session_id: int, db: DbSession = Depends(get_db)):
    from ...core.session_manager import SessionManager
    sm = SessionManager(db)
    session = sm.get_session(session_id)
    if not session:
        return "<p>Session not found</p>"

    builder = RoadmapBuilder(db)
    data = builder.build(session.user_id, session.course_id)
    renderer = RoadmapRenderer()
    return renderer.render_roadmap(data)


@router.get("/knowledge-points/{kp_id}/content")
async def get_kp_content(kp_id: int, db: DbSession = Depends(get_db)):
    """Get the raw MD content for a knowledge point."""
    from ...models import KnowledgePoint
    kp = db.query(KnowledgePoint).filter_by(id=kp_id).first()
    if not kp:
        return {"error": "Knowledge point not found"}

    # Try to locate the MD file from chunk_ids
    md_content = ""
    if kp.chunk_ids:
        for path_str in kp.chunk_ids:
            file_path = Path(path_str)
            if file_path.exists():
                md_content = file_path.read_text(encoding="utf-8")
                break

    # Fallback: generate basic content from description
    if not md_content:
        md_content = f"# {kp.title}\n\n{kp.description or kp.title}\n\n## 核心要点\n\n{kp.content_summary or ''}"

    return {
        "id": kp.id,
        "title": kp.title,
        "content": md_content,
        "chapter_id": kp.chapter_id,
    }


@router.get("/knowledge-points/{kp_id}/content/html", response_class=HTMLResponse)
async def get_kp_content_html(kp_id: int, db: DbSession = Depends(get_db)):
    """Get KP content rendered as HTML (basic MD-to-HTML conversion)."""
    from ...models import KnowledgePoint
    import re

    kp = db.query(KnowledgePoint).filter_by(id=kp_id).first()
    if not kp:
        return "<p>Knowledge point not found</p>"

    md_content = ""
    if kp.chunk_ids:
        for path_str in kp.chunk_ids:
            file_path = Path(path_str)
            if file_path.exists():
                md_content = file_path.read_text(encoding="utf-8")
                break

    if not md_content:
        md_content = f"# {kp.title}\n\n{kp.description or kp.title}\n\n## 核心要点\n\n{kp.content_summary or ''}"

    # Simple MD to HTML conversion
    html = md_content
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    html = re.sub(r'^\- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', html, flags=re.DOTALL)
    html = re.sub(r'\n\n', '</p><p>', html)
    html = f'<div class="markdown-content"><p>{html}</p></div>'

    return html
