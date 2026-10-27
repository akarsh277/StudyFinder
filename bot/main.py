import os
import sys
import logging
import threading

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, BotCommand, BotCommandScopeChat, BotCommandScopeDefault, BotCommandScopeAllPrivateChats
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from datetime import time as dtime
from zoneinfo import ZoneInfo
from config import BOT_TOKEN, CHIEF_TELEGRAM_ID
from init_db import init_db
from bot.handlers.start import start_handler
from bot.handlers.access import (
    access_start_callback,
    access_branch_callback,
    access_semester_callback,
    access_subject_callback,
    access_type_callback,
    access_manage_callback,
    access_restore_view_callback,
    download_resource_callback,
    back_to_main_callback,
)
from bot.handlers.upload import (
    upload_start_callback,
    upload_branch_callback,
    upload_semester_callback,
    upload_subject_callback,
    upload_type_callback,
    upload_title_handler,
    upload_file_handler,
    upload_more_callback,
    cancel_upload_handler,
)
from bot.handlers.admin import (
    approve_resource_callback,
    reject_resource_callback,
    delete_command_handler,
    delete_branch_callback,
    delete_semester_callback,
    delete_subject_callback,
    delete_type_callback,
    confirm_delete_callback,
    execute_delete_callback,
    rename_start_callback,
    rename_title_handler,
    cancel_rename_callback,
    admin_panel_command_handler,
    add_branch_command_handler,
    add_branch_name_handler,
    cancel_add_branch_handler,
    list_branches_command_handler,
    add_sem_command_handler,
    add_sem_branch_callback,
    add_sem_name_handler,
    cancel_add_sem_handler,
    add_subj_command_handler,
    add_subj_branch_callback,
    add_subj_sem_callback,
    add_subj_name_handler,
    cancel_add_subj_handler,
    list_subjects_command_handler,
)
from bot.handlers.notifications import (
    send_daily_digest_job,
    daily_digest_command_handler,
)
from bot.handlers.analytics import analytics_handler
from bot.states.conversation import (
    SELECT_BRANCH,
    SELECT_SEMESTER,
    SELECT_SUBJECT,
    SELECT_TYPE,
    ENTER_TITLE,
    UPLOAD_FILE,
    RENAME_TITLE,
    ENTER_BRANCH_NAME,
    SELECT_BRANCH_FOR_SEM,
    ENTER_SEM_NAME,
    SELECT_BRANCH_FOR_SUBJ,
    SELECT_SEM_FOR_SUBJ,
    ENTER_SUBJ_NAME,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP Health check handler allowing deployment as a Free Web Service on Render/Koyeb."""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"StudyFind Bot is running live!")

    def log_message(self, format, *args):
        pass  # Suppress HTTP access logging


def start_health_server():
    """Start background HTTP health check server for cloud Web Service platforms."""
    try:
        port = int(os.getenv("PORT", "10000"))
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Health check HTTP server listening on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.warning(f"Health check server error: {e}")


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates and send user-friendly message if possible."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An unexpected error occurred. Please try again with /start."
            )
        except Exception:
            pass


async def setup_bot_commands(application) -> None:
    """Register menu commands with Telegram so users see the command menu button."""
    try:
        student_commands = [
            BotCommand("start", "Open main menu"),
            BotCommand("upload", "Upload study material"),
        ]
        # Register for both default scope and all private chats so students only see /start and /upload
        await application.bot.set_my_commands(student_commands, scope=BotCommandScopeDefault())
        await application.bot.set_my_commands(student_commands, scope=BotCommandScopeAllPrivateChats())

        if CHIEF_TELEGRAM_ID and CHIEF_TELEGRAM_ID != 0:
            chief_commands = [
                BotCommand("start", "Open main menu"),
                BotCommand("upload", "Upload study material"),
                BotCommand("admin", "Chief Control Center"),
                BotCommand("addbranch", "Add a new branch (Chief)"),
                BotCommand("addsem", "Add semester to branch (Chief)"),
                BotCommand("addsubject", "Add a subject (Chief)"),
                BotCommand("subjects", "List all subjects (Chief)"),
                BotCommand("branches", "List configured branches (Chief)"),
                BotCommand("delete", "Manage, rename & delete files (Chief)"),
                BotCommand("daily_digest", "Preview/send today's digest (Chief)"),
                BotCommand("stats", "View 30-day analytics (Chief)"),
            ]
            await application.bot.set_my_commands(
                chief_commands,
                scope=BotCommandScopeChat(chat_id=CHIEF_TELEGRAM_ID)
            )
        logger.info("Bot commands menu registered successfully.")
    except Exception as e:
        logger.warning(f"Could not register bot commands with Telegram: {e}")


def main() -> None:
    """Initialize database and start the Telegram bot using polling."""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("❌ CRITICAL: BOT_TOKEN is missing or invalid! Please add BOT_TOKEN in Render Environment Variables.")
        sys.exit(1)

    # Start background health check HTTP server for Render/Koyeb Free Web Service
    threading.Thread(target=start_health_server, daemon=True).start()

    # Ensure database tables and initial seed data exist
    init_db()

    # Set custom network request timeouts to handle network latency gracefully
    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request)
        .get_updates_request(request)
        .post_init(setup_bot_commands)
        .build()
    )

    # Upload ConversationHandler
    upload_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(upload_start_callback, pattern="^(main_upload|start_upload_flow)$"),
            CommandHandler("upload", upload_start_callback),
            CallbackQueryHandler(upload_more_callback, pattern="^upload_more_same$"),
        ],
        states={
            SELECT_BRANCH: [
                CallbackQueryHandler(upload_branch_callback, pattern="^upload_branch_")
            ],
            SELECT_SEMESTER: [
                CallbackQueryHandler(upload_semester_callback, pattern="^upload_sem_")
            ],
            SELECT_SUBJECT: [
                CallbackQueryHandler(upload_subject_callback, pattern="^upload_subj_")
            ],
            SELECT_TYPE: [
                CallbackQueryHandler(upload_type_callback, pattern="^upload_type_")
            ],
            ENTER_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, upload_title_handler)
            ],
            UPLOAD_FILE: [
                MessageHandler(filters.ALL & ~filters.COMMAND, upload_file_handler)
            ],
        },
        fallbacks=[
            CommandHandler("start", start_handler),
        ],
        per_user=True,
        per_chat=True,
    )

    # Rename ConversationHandler (Chief only)
    rename_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(rename_start_callback, pattern="^rename_"),
        ],
        states={
            RENAME_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rename_title_handler)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_rename_callback, pattern="^cancel_rename$"),
            CommandHandler("start", start_handler),
        ],
        per_user=True,
        per_chat=True,
    )

    # Add Branch ConversationHandler (Chief only)
    add_branch_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("addbranch", add_branch_command_handler),
            CallbackQueryHandler(add_branch_command_handler, pattern="^admin_btn_addbranch$"),
        ],
        states={
            ENTER_BRANCH_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_branch_name_handler)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_add_branch_handler, pattern="^cancel_add_branch$"),
            CommandHandler("start", start_handler),
        ],
        per_user=True,
        per_chat=True,
    )

    # Add Semester ConversationHandler (Chief only)
    add_sem_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler(["addsem", "addsemester"], add_sem_command_handler),
            CallbackQueryHandler(add_sem_command_handler, pattern="^admin_btn_addsem$"),
        ],
        states={
            SELECT_BRANCH_FOR_SEM: [
                CallbackQueryHandler(add_sem_branch_callback, pattern="^addsem_br_")
            ],
            ENTER_SEM_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_sem_name_handler)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_add_sem_handler, pattern="^cancel_add_sem$"),
            CommandHandler("start", start_handler),
        ],
        per_user=True,
        per_chat=True,
    )

    # Add Subject ConversationHandler (Chief only)
    add_subj_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler(["addsubject", "addsubj"], add_subj_command_handler),
            CallbackQueryHandler(add_subj_command_handler, pattern="^admin_btn_addsubj$"),
        ],
        states={
            SELECT_BRANCH_FOR_SUBJ: [
                CallbackQueryHandler(add_subj_branch_callback, pattern="^addsub_br_")
            ],
            SELECT_SEM_FOR_SUBJ: [
                CallbackQueryHandler(add_subj_sem_callback, pattern="^addsub_sem_")
            ],
            ENTER_SUBJ_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_subj_name_handler)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_add_subj_handler, pattern="^cancel_add_subj$"),
            CommandHandler("start", start_handler),
        ],
        per_user=True,
        per_chat=True,
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(upload_conv_handler)
    application.add_handler(rename_conv_handler)
    application.add_handler(add_branch_conv_handler)
    application.add_handler(add_sem_conv_handler)
    application.add_handler(add_subj_conv_handler)

    # Access Navigation callbacks
    application.add_handler(CallbackQueryHandler(back_to_main_callback, pattern="^back_to_main$"))
    application.add_handler(CallbackQueryHandler(access_start_callback, pattern="^main_access$"))
    application.add_handler(CallbackQueryHandler(access_branch_callback, pattern="^access_branch_"))
    application.add_handler(CallbackQueryHandler(access_semester_callback, pattern="^access_sem_"))
    application.add_handler(CallbackQueryHandler(access_subject_callback, pattern="^access_subj_"))
    application.add_handler(CallbackQueryHandler(access_type_callback, pattern="^access_type_"))
    application.add_handler(CallbackQueryHandler(access_manage_callback, pattern="^access_manage_"))
    application.add_handler(CallbackQueryHandler(access_restore_view_callback, pattern="^access_restore_view$"))
    application.add_handler(CallbackQueryHandler(download_resource_callback, pattern="^download_"))

    # Admin Chief Control Center & Commands
    application.add_handler(CommandHandler(["admin", "manage"], admin_panel_command_handler))
    application.add_handler(CommandHandler(["stats", "analytics"], analytics_handler))
    application.add_handler(CommandHandler("branches", list_branches_command_handler))
    application.add_handler(CommandHandler("subjects", list_subjects_command_handler))
    application.add_handler(CallbackQueryHandler(list_subjects_command_handler, pattern="^admin_btn_viewsubj$"))
    application.add_handler(CallbackQueryHandler(analytics_handler, pattern="^admin_btn_stats$"))
    application.add_handler(CallbackQueryHandler(daily_digest_command_handler, pattern="^admin_btn_digest$"))
    application.add_handler(CommandHandler(["daily_digest", "digest", "daily_notification"], daily_digest_command_handler))
    application.add_handler(CommandHandler("delete", delete_command_handler))
    application.add_handler(CallbackQueryHandler(delete_command_handler, pattern="^delete_main$"))
    application.add_handler(CallbackQueryHandler(approve_resource_callback, pattern="^approve_"))
    application.add_handler(CallbackQueryHandler(reject_resource_callback, pattern="^reject_"))
    application.add_handler(CallbackQueryHandler(delete_branch_callback, pattern="^delete_branch_"))
    application.add_handler(CallbackQueryHandler(delete_semester_callback, pattern="^delete_sem_"))
    application.add_handler(CallbackQueryHandler(delete_subject_callback, pattern="^delete_subj_"))
    application.add_handler(CallbackQueryHandler(delete_type_callback, pattern="^delete_type_"))
    application.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern="^confirm_del_"))
    application.add_handler(CallbackQueryHandler(execute_delete_callback, pattern="^do_delete_"))

    # Schedule end-of-day digest at 22:00 (10:00 PM) IST every day
    if application.job_queue:
        ist = ZoneInfo("Asia/Kolkata")
        target_time = dtime(hour=22, minute=0, tzinfo=ist)
        application.job_queue.run_daily(
            send_daily_digest_job,
            time=target_time,
            name="daily_resource_digest"
        )
        logger.info("Daily resource digest job scheduled for 22:00 IST.")
    else:
        logger.warning("JobQueue not initialized. Scheduled daily digests disabled.")

    # Register error handler
    application.add_error_handler(global_error_handler)

    logger.info("StudyFind Bot (@HighlessbestBot) is starting via polling...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
