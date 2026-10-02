import os
import sys
import logging
import threading

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
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
from config import BOT_TOKEN
from init_db import init_db
from bot.handlers.start import start_handler
from bot.handlers.access import (
    access_start_callback,
    access_semester_callback,
    access_subject_callback,
    access_type_callback,
    download_resource_callback,
    back_to_main_callback,
)
from bot.handlers.upload import (
    upload_start_callback,
    upload_semester_callback,
    upload_subject_callback,
    upload_type_callback,
    upload_title_handler,
    upload_file_handler,
    cancel_upload_handler,
)
from bot.handlers.admin import (
    approve_resource_callback,
    reject_resource_callback,
    delete_command_handler,
    delete_semester_callback,
    delete_subject_callback,
    delete_type_callback,
    confirm_delete_callback,
    execute_delete_callback,
)
from bot.handlers.analytics import analytics_handler
from bot.states.conversation import (
    SELECT_SEMESTER,
    SELECT_SUBJECT,
    SELECT_TYPE,
    ENTER_TITLE,
    UPLOAD_FILE,
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
        .build()
    )

    # Upload ConversationHandler
    upload_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(upload_start_callback, pattern="^(main_upload|start_upload_flow)$"),
            CommandHandler("upload", upload_start_callback),
        ],
        states={
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
            CommandHandler("cancel", cancel_upload_handler),
            CommandHandler("start", start_handler),
        ],
        per_user=True,
        per_chat=True,
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(upload_conv_handler)

    # Access Resources & Navigation callbacks
    application.add_handler(CallbackQueryHandler(back_to_main_callback, pattern="^back_to_main$"))
    application.add_handler(CallbackQueryHandler(access_start_callback, pattern="^main_access$"))
    application.add_handler(CallbackQueryHandler(access_semester_callback, pattern="^access_sem_"))
    application.add_handler(CallbackQueryHandler(access_subject_callback, pattern="^access_subj_"))
    application.add_handler(CallbackQueryHandler(access_type_callback, pattern="^access_type_"))
    application.add_handler(CallbackQueryHandler(download_resource_callback, pattern="^download_"))

    # Admin Chief review callbacks & commands
    application.add_handler(CommandHandler("analytics", analytics_handler))
    application.add_handler(CommandHandler("delete", delete_command_handler))
    application.add_handler(CallbackQueryHandler(approve_resource_callback, pattern="^approve_"))
    application.add_handler(CallbackQueryHandler(reject_resource_callback, pattern="^reject_"))
    application.add_handler(CallbackQueryHandler(delete_semester_callback, pattern="^delete_sem_"))
    application.add_handler(CallbackQueryHandler(delete_subject_callback, pattern="^delete_subj_"))
    application.add_handler(CallbackQueryHandler(delete_type_callback, pattern="^delete_type_"))
    application.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern="^confirm_del_"))
    application.add_handler(CallbackQueryHandler(execute_delete_callback, pattern="^do_delete_"))

    # Register error handler
    application.add_error_handler(global_error_handler)

    logger.info("StudyFind Bot (@HighlessbestBot) is starting via polling...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
