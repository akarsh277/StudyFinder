import logging
from database.connection import engine, Base, get_db
from database.crud import seed_initial_subjects

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created.")

    logger.info("Seeding initial subjects...")
    with get_db() as db:
        seed_initial_subjects(db)
    logger.info("Database initialization complete.")

if __name__ == "__main__":
    init_db()
