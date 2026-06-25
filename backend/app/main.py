from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .config import settings
from .models.base import engine, Base
from .api.routes import sessions, chat, quiz, roadmap, testing, progress, admin


def create_app() -> FastAPI:
    app = FastAPI(title="RAG Tutor - 课程知识私教助手", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create data directory
    Path(settings.database_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.chroma_persist_path).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    # Ensure default user exists
    from .models.base import SessionLocal
    from .models import User
    db_init = SessionLocal()
    try:
        if not db_init.query(User).filter_by(username="default").first():
            db_init.add(User(username="default", display_name="学习者"))
            db_init.commit()
    finally:
        db_init.close()

    # API routes
    app.include_router(sessions.router)
    app.include_router(chat.router)
    app.include_router(quiz.router)
    app.include_router(roadmap.router)
    app.include_router(testing.router)
    app.include_router(progress.router)
    app.include_router(admin.router)

    # Static files
    static_dir = Path(settings.static_dir)
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    templates_dir = Path(settings.template_dir)

    @app.get("/")
    async def root():
        landing_path = templates_dir.parent / "landing.html"
        if landing_path.exists():
            return FileResponse(str(landing_path))
        return {"message": "RAG Tutor API", "docs": "/docs"}

    @app.get("/app")
    async def app_page():
        base_path = templates_dir / "base.html"
        if base_path.exists():
            return FileResponse(str(base_path))
        return {"message": "Please create frontend templates"}

    return app


app = create_app()
