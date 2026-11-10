import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import CHIEF_TELEGRAM_ID
from database.connection import get_db
from database.crud import get_analytics_data

logger = logging.getLogger(__name__)


async def analytics_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Chief/Admin-only /analytics command."""
    user = update.effective_user

    # Security check: Authorization MUST happen before any analytics data is queried
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        logger.warning(f"Unauthorized access attempt to /analytics by user ID {user.id if user else 'Unknown'}")
        if update.message:
            await update.message.reply_text("⛔ You are not authorized to access StudyFind analytics.")
        elif update.callback_query:
            await update.callback_query.answer("⛔ Unauthorized", show_alert=True)
        return

    if update.callback_query:
        await update.callback_query.answer()

    try:
        with get_db() as db:
            data = get_analytics_data(db)
    except Exception as e:
        logger.error(f"Error querying analytics data: {e}")
        if update.message:
            await update.message.reply_text("⚠️ Unable to load analytics right now. Please try again.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("⚠️ Unable to load analytics right now. Please try again.")
        return

    # Format TOP SUBJECTS
    top_subjects_lines = []
    if data["top_subjects"]:
        for idx, subj in enumerate(data["top_subjects"], start=1):
            top_subjects_lines.append(f"{idx}. {subj['name']} — {subj['downloads']} downloads")
    else:
        top_subjects_lines.append("No subject downloads recorded yet.")

    # Format TOP RESOURCES section
    top_resources_lines = []
    if data["top_resources"]:
        for idx, res in enumerate(data["top_resources"], start=1):
            top_resources_lines.append(f"{idx}. {res['title']} — {res['downloads']} downloads")
    else:
        top_resources_lines.append("No resource downloads recorded yet.")

    message = (
        "📊 StudyFind Analytics Dashboard\n\n"
        "👥 STUDENT AUDIENCE\n"
        f"• Total Registered Students: {data['total_users']}\n"
        f"• Active This Week: {data['active_this_week']} students\n"
        f"• Bounce Rate: {data['bounce_rate']}%\n\n"
        "📅 ACTIVITY & MOMENTUM\n"
        f"• Today's Downloads: {data['today_downloads']} 📥\n"
        f"• This Week's Downloads: {data['week_downloads']} 📥\n"
        f"• All-Time Total Downloads: {data['all_time_downloads']} 📥\n\n"
        f"🔥 PEAK DAY: {data['peak_day_str']}\n"
        f"• Users: {data['peak_day_users']}\n"
        f"• Downloads: {data['peak_day_downloads']}\n\n"
        "🏆 TOP SUBJECTS\n"
        + "\n".join(top_subjects_lines)
        + "\n\n"
        "🔥 TOP RESOURCES\n"
        + "\n".join(top_resources_lines)
    )

    if update.message:
        await update.message.reply_text(text=message)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text=message)
