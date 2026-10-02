import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config import CHIEF_TELEGRAM_ID
from database.connection import get_db
from database.crud import get_subjects_by_semester, get_subject_by_id, create_resource
from bot.keyboards.menus import (
    get_semester_keyboard,
    get_subjects_keyboard,
    get_resource_types_keyboard,
    get_admin_review_keyboard
)
from bot.states.conversation import (
    SELECT_SEMESTER,
    SELECT_SUBJECT,
    SELECT_TYPE,
    ENTER_TITLE,
    UPLOAD_FILE
)

logger = logging.getLogger(__name__)


async def upload_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the resource upload conversation - prompt for semester."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            text="Select Semester",
            reply_markup=get_semester_keyboard(prefix="upload_sem", back_callback="back_to_main")
        )
    else:
        await update.message.reply_text(
            text="Select Semester",
            reply_markup=get_semester_keyboard(prefix="upload_sem", back_callback="back_to_main")
        )
    return SELECT_SEMESTER


async def upload_semester_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle semester selection in upload flow - load subjects from DB."""
    query = update.callback_query
    await query.answer()

    semester = query.data.replace("upload_sem_", "")
    context.user_data["upload_semester"] = semester

    try:
        with get_db() as db:
            subjects = get_subjects_by_semester(db, semester)
    except Exception as e:
        logger.error(f"Error getting subjects for upload: {e}")
        await query.edit_message_text("⚠️ Database error occurred. Upload cancelled.")
        return ConversationHandler.END

    if not subjects:
        await query.edit_message_text("⚠️ No subjects registered for this semester yet.")
        return ConversationHandler.END

    await query.edit_message_text(
        text="Select Subject",
        reply_markup=get_subjects_keyboard(subjects, prefix="upload_subj", back_callback="main_upload")
    )
    return SELECT_SUBJECT


async def upload_subject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle subject selection in upload flow - prompt for resource type."""
    query = update.callback_query
    await query.answer()

    try:
        subject_id = int(query.data.replace("upload_subj_", ""))
        context.user_data["upload_subject_id"] = subject_id
    except ValueError:
        await query.edit_message_text("Invalid subject selected.")
        return ConversationHandler.END

    semester = context.user_data.get("upload_semester")
    back_cb = f"upload_sem_{semester}" if semester else "main_upload"

    await query.edit_message_text(
        text="Select Resource Type",
        reply_markup=get_resource_types_keyboard(prefix="upload_type", back_callback=back_cb)
    )
    return SELECT_TYPE


async def upload_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle resource type selection - prompt for title."""
    query = update.callback_query
    await query.answer()

    resource_type = query.data.replace("upload_type_", "")
    context.user_data["upload_resource_type"] = resource_type

    await query.edit_message_text(text="📝 Enter the resource title.\n\nExample: DBMS Unit 3 Notes")
    return ENTER_TITLE


async def upload_title_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle title entry - prompt user to upload PDF file."""
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("Title cannot be empty. Please enter a valid resource title.")
        return ENTER_TITLE

    context.user_data["upload_title"] = title

    await update.message.reply_text(
        "Please upload the resource document (PDF file)."
    )
    return UPLOAD_FILE


async def upload_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle file upload, validate PDF, save to DB with PENDING status, and notify Chief."""
    user = update.effective_user
    doc = update.message.document

    if not doc:
        await update.message.reply_text(
            "⚠️ Unsupported file or content. Please upload a valid PDF document."
        )
        return UPLOAD_FILE

    # File validation (PDF format check)
    file_name = doc.file_name or ""
    mime_type = doc.mime_type or ""
    if not (file_name.lower().endswith(".pdf") or "pdf" in mime_type.lower()):
        await update.message.reply_text(
            "⚠️ Unsupported file type. Please upload a PDF document (.pdf)."
        )
        return UPLOAD_FILE

    title = context.user_data.get("upload_title")
    semester = context.user_data.get("upload_semester")
    subject_id = context.user_data.get("upload_subject_id")
    resource_type = context.user_data.get("upload_resource_type")

    if not all([title, semester, subject_id, resource_type]):
        await update.message.reply_text("Session timed out or incomplete. Please restart with /start.")
        return ConversationHandler.END

    try:
        with get_db() as db:
            subject = get_subject_by_id(db, subject_id)
            subject_name = subject.name if subject else "Unknown Subject"

            new_resource = create_resource(
                db=db,
                title=title,
                semester=semester,
                subject_id=subject_id,
                resource_type=resource_type,
                file_id=doc.file_id,
                file_name=file_name,
                uploaded_by=user.id,
                status="PENDING"
            )
            resource_id = new_resource.id
    except Exception as e:
        logger.error(f"Error saving resource to DB: {e}")
        await update.message.reply_text("⚠️ Failed to submit resource due to database error. Please try again.")
        return ConversationHandler.END

    # Success response to student
    await update.message.reply_text(
        "✅ Resource submitted successfully.\n\n"
        "Your resource has been sent to the Chief for approval."
    )

    # Notify Chief if CHIEF_TELEGRAM_ID is configured
    if CHIEF_TELEGRAM_ID and CHIEF_TELEGRAM_ID != 0:
        student_username = f"@{user.username}" if user.username else f"User {user.id}"
        type_display = resource_type.capitalize()

        chief_text = (
            f"📥 New Resource Submission\n\n"
            f"Title: {title}\n"
            f"Semester: {semester}\n"
            f"Subject: {subject_name}\n"
            f"Type: {type_display}\n"
            f"Submitted by: {student_username}"
        )

        try:
            # Send uploaded document directly to Chief with review buttons
            await context.bot.send_document(
                chat_id=CHIEF_TELEGRAM_ID,
                document=doc.file_id,
                caption=chief_text,
                reply_markup=get_admin_review_keyboard(resource_id)
            )
        except Exception as e:
            logger.error(f"Error notifying Chief {CHIEF_TELEGRAM_ID}: {e}")

    # Clear upload state
    context.user_data.pop("upload_title", None)
    context.user_data.pop("upload_semester", None)
    context.user_data.pop("upload_subject_id", None)
    context.user_data.pop("upload_resource_type", None)

    return ConversationHandler.END


async def cancel_upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel upload flow."""
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("Upload process cancelled.")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Upload process cancelled.")
    return ConversationHandler.END
