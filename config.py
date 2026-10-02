import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8571722863:AAHSfklN9pJya_IGnM7sw56-AMnDNwyKeoc")
CHIEF_TELEGRAM_ID_RAW = os.getenv("CHIEF_TELEGRAM_ID", "0")

try:
    CHIEF_TELEGRAM_ID: int = int(CHIEF_TELEGRAM_ID_RAW)
except ValueError:
    CHIEF_TELEGRAM_ID = 0

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/studyfind"
)
