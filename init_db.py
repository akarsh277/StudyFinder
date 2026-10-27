import logging
from database.connection import engine, Base, get_db
from database.crud import seed_initial_subjects, seed_initial_branches, copy_os_resources_to_cse_ai

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

    logger.info("Seeding initial branches and subjects...")
    with get_db() as db:
        seed_initial_branches(db)
        seed_initial_subjects(db)
        copy_os_resources_to_cse_ai(db)
    logger.info("Database initialization complete.")

if __name__ == "__main__":
    init_db()
