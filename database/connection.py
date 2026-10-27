import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

logger = logging.getLogger(__name__)

db_url = DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine_kwargs = {}
if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 300
    engine_kwargs["connect_args"] = {"connect_timeout": 15}

connected = False
for attempt in range(1, 4):
    try:
        test_engine = create_engine(db_url, **engine_kwargs)
        with test_engine.connect() as conn:
            pass
        engine = test_engine
        logger.info(f"Connected to database successfully: {db_url}")
        connected = True
        break
    except Exception as e:
        logger.warning(f"Connection attempt {attempt}/3 to DATABASE_URL failed: {e}")
        import time
        time.sleep(1)

if not connected:
    logger.warning("Could not connect to configured DATABASE_URL. Falling back to SQLite studyfind.db.")
    fallback_url = "sqlite:///studyfind.db"
    engine = create_engine(fallback_url, connect_args={"check_same_thread": False, "timeout": 30})
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

# expire_on_commit=False allows accessing attributes after session closes
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
Base = declarative_base()

@contextmanager
def get_db():
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()
