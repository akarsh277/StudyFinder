import logging
from database.connection import engine, Base, get_db
from database.crud import seed_initial_subjects

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    # Ensure download_count column exists on resources table for existing DB instances
    try:
        with engine.connect() as conn:
            if engine.dialect.name == "sqlite":
                res = conn.exec_driver_sql("PRAGMA table_info(resources)").fetchall()
                cols = [r[1] for r in res]
                if "download_count" not in cols:
                    conn.exec_driver_sql("ALTER TABLE resources ADD COLUMN download_count INTEGER DEFAULT 0")
                    conn.commit()
            else:
                conn.exec_driver_sql("ALTER TABLE resources ADD COLUMN IF NOT EXISTS download_count INTEGER DEFAULT 0")
                conn.commit()
    except Exception as e:
        logger.warning(f"Schema update notice: {e}")

    logger.info("Database tables created.")

    logger.info("Seeding initial subjects...")
    with get_db() as db:
        seed_initial_subjects(db)
    logger.info("Database initialization complete.")

if __name__ == "__main__":
    init_db()
