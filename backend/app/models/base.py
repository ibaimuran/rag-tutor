from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from ..config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    pool_size=5,
    max_overflow=10,
)

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """每个新连接初始化 SQLite 性能和安全参数。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")       # 写前日志，并发读写不阻塞
    cursor.execute("PRAGMA foreign_keys=ON")         # 外键约束
    cursor.execute("PRAGMA synchronous=NORMAL")      # 平衡安全与性能
    cursor.execute("PRAGMA cache_size=-8000")        # 8MB 缓存
    cursor.execute("PRAGMA busy_timeout=5000")       # 锁等待 5 秒
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
