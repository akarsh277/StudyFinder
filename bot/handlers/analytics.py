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
        return

    try:
        with get_db() as db:
            data = get_analytics_data(db)
    except Exception as e:
        logger.error(f"Error querying analytics data: {e}")
        if update.message:
            await update.message.reply_text("⚠️ Unable to load analytics right now. Please try again.")
        return

    # Format TOP RESOURCES section
    top_resources_lines = []
    if data["top_resources"]:
        for idx, res in enumerate(data["top_resources"], start=1):
            top_resources_lines.append(f"{idx}. {res['title']} — {res['downloads']} downloads")
    else:
        top_resources_lines.append("No resources available.")

    # Format TOP SUBJECTS section
    top_subjects_lines = []
    if data["top_subjects"]:
        for idx, subj in enumerate(data["top_subjects"], start=1):
            top_subjects_lines.append(f"{idx}. {subj['name']} — {subj['downloads']} downloads")
    else:
        top_subjects_lines.append("No subject downloads yet.")

    message = (
        "📊 StudyFind Analytics\n\n"
        "👥 USERS\n"
        f"• Total Users: {data['total_users']}\n"
        f"• New Today: {data['users_today']}\n"
        f"• New This Week: {data['users_week']}\n\n"
        "📚 RESOURCES\n"
        f"• Total: {data['total_resources']}\n"
        f"• Approved: {data['approved_resources']}\n"
        f"• Pending: {data['pending_resources']}\n"
        f"• Rejected: {data['rejected_resources']}\n\n"
        "⬇️ DOWNLOADS\n"
        f"• Total Downloads: {data['total_downloads']}\n\n"
        "🔥 TOP RESOURCES\n"
        + "\n".join(top_resources_lines) + "\n\n"
        "📚 TOP SUBJECTS\n"
        + "\n".join(top_subjects_lines) + "\n\n"
        "📤 CONTRIBUTIONS\n"
        f"• Submitted: {data['total_resources']}\n"
        f"• Approved: {data['approved_resources']}\n"
        f"• Pending: {data['pending_resources']}\n"
        f"• Rejected: {data['rejected_resources']}"
    )

    if update.message:
        await update.message.reply_text(text=message)
