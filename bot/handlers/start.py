import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import CHIEF_TELEGRAM_ID
from database.connection import get_db
from database.crud import get_or_create_user, log_user_event
from bot.keyboards.menus import get_main_menu_keyboard

logger = logging.getLogger(__name__)

START_MESSAGE = """Hello Maawa!!
Notes ledha,
Digulu endhuku Dhandaga nenu unna neeku Andagaa 🫶🏻"""


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with exact specified text and main menu keyboard."""
    user = update.effective_user
    if not user:
        return

    role = "CHIEF" if user.id == CHIEF_TELEGRAM_ID else "STUDENT"

    try:
        with get_db() as db:
            get_or_create_user(db, telegram_id=user.id, username=user.username, role=role)
            log_user_event(db, user.id, "START")
    except Exception as e:
        logger.error(f"Error registering user in start_handler: {e}")

    reply_markup = get_main_menu_keyboard()

    if update.message:
        await update.message.reply_text(
            text=START_MESSAGE,
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=START_MESSAGE,
            reply_markup=reply_markup
        )
