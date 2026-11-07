from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """Dependency FastAPI: 1 session cho mỗi request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
