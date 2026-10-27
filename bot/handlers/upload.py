import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config import CHIEF_TELEGRAM_ID
from database.connection import get_db
from database.crud import (
    get_all_branches,
    get_branch_by_name,
    get_subjects_by_semester,
    get_subject_by_id,
    create_resource,
)
from bot.keyboards.menus import (
    get_branches_keyboard,
    get_semesters_for_branch_keyboard,
    get_semester_keyboard,
    get_subjects_keyboard,
    get_resource_types_keyboard,
)
from bot.states.conversation import (
    SELECT_BRANCH,
    SELECT_SEMESTER,
    SELECT_SUBJECT,
    SELECT_TYPE,
    ENTER_TITLE,
    UPLOAD_FILE
)

logger = logging.getLogger(__name__)


async def upload_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the resource upload conversation - prompt for engineering branch."""
    query = update.callback_query
    if query:
        await query.answer()

    try:
        with get_db() as db:
            branches = get_all_branches(db)
    except Exception as e:
        logger.error(f"Error getting branches for upload: {e}")
        branches = []

    text_msg = "🏛️ Select Branch\n\nChoose the engineering branch for upload:"
    if branches:
        reply_markup = get_branches_keyboard(branches, prefix="upload_branch", back_callback="back_to_main")
        state_to_return = SELECT_BRANCH
    else:
        text_msg = "Select Semester"
        reply_markup = get_semester_keyboard(prefix="upload_sem", back_callback="back_to_main")
        state_to_return = SELECT_SEMESTER

    if query:
        await query.edit_message_text(text=text_msg, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(text=text_msg, reply_markup=reply_markup)
    return state_to_return


async def upload_branch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle branch selection in upload flow - prompt for semester."""
    query = update.callback_query
    await query.answer()

    branch_name = query.data.replace("upload_branch_", "").strip()
    context.user_data["upload_branch"] = branch_name

    semesters = ["2-2", "3-1"]
    try:
        with get_db() as db:
            b_obj = get_branch_by_name(db, branch_name)
            if b_obj and b_obj.semesters:
                semesters = [s.strip() for s in b_obj.semesters.split(",") if s.strip()]
    except Exception as e:
        logger.warning(f"Could not load branch semesters for upload: {e}")

    await query.edit_message_text(
        text=f"🎓 Branch: {branch_name}\n\nSelect Semester:",
        reply_markup=get_semesters_for_branch_keyboard(
            branch=branch_name,
            semesters=semesters,
            prefix="upload_sem",
            back_callback="main_upload"
        )
    )
    return SELECT_SEMESTER


async def upload_semester_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle semester selection in upload flow - load subjects from DB."""
    query = update.callback_query
    await query.answer()

    semester = query.data.replace("upload_sem_", "")
    context.user_data["upload_semester"] = semester

    branch = context.user_data.get("upload_branch")
    if not branch and " " in semester:
        branch = semester.rsplit(" ", 1)[0]
    back_cb = f"upload_branch_{branch}" if branch else "main_upload"

    try:
        with get_db() as db:
            subjects = get_subjects_by_semester(db, semester)
    except Exception as e:
        logger.error(f"Error getting subjects for upload: {e}")
        await query.edit_message_text("⚠️ Database error occurred. Upload cancelled.")
        return ConversationHandler.END

    if not subjects:
        await query.edit_message_text(
            f"⚠️ No subjects registered for {semester} yet.\n\nType /start to return to the main menu."
        )
        return ConversationHandler.END

    await query.edit_message_text(
        text=f"📚 {semester} — Select Subject",
        reply_markup=get_subjects_keyboard(subjects, prefix="upload_subj", back_callback=back_cb)
    )
    return SELECT_SUBJECT


async def upload_subject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle subject selection in upload flow - prompt for resource type or jump to title for combined PYQ."""
    query = update.callback_query
    await query.answer()

    if query.data == "upload_subj_pyq_all":
        semester = context.user_data.get("upload_semester")
        context.user_data["upload_resource_type"] = "PYQ"
        try:
            with get_db() as db:
                subjects = get_subjects_by_semester(db, semester)
                if subjects:
                    context.user_data["upload_subject_id"] = subjects[0].id
                else:
                    context.user_data["upload_subject_id"] = 1
        except Exception:
            context.user_data["upload_subject_id"] = 1

        await query.edit_message_text(text="📝 Enter the title for the PYQ paper(s).\n\nExample: PYQ Papers 2022-2024")
        return ENTER_TITLE

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
    """Handle title entry - prompt user to upload document file."""
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("Title cannot be empty. Please enter a valid resource title.")
        return ENTER_TITLE

    context.user_data["upload_title"] = title

    await update.message.reply_text(
        "Please upload the resource document (.pdf, .doc, or .docx file)."
    )
    return UPLOAD_FILE


async def upload_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle file upload, validate PDF/DOC/DOCX, save to DB with PENDING status, and notify Chief."""
    user = update.effective_user
    doc = update.message.document

    if not doc:
        await update.message.reply_text(
            "⚠️ Unsupported file or content. Please upload a valid document (.pdf, .doc, .docx)."
        )
        return UPLOAD_FILE

    # File validation (.pdf, .doc, .docx format check)
    file_name = (doc.file_name or "").lower()
    mime_type = (doc.mime_type or "").lower()
    allowed_exts = (".pdf", ".doc", ".docx")
    allowed_mimes = ("pdf", "msword", "wordprocessingml")

    if not (any(file_name.endswith(ext) for ext in allowed_exts) or any(m in mime_type for m in allowed_mimes)):
        await update.message.reply_text(
            "⚠️ Unsupported file type. Please upload a PDF, DOC, or DOCX document (.pdf, .doc, .docx)."
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

            # Check if uploader is Admin / Chief (auto-approved, no approval required)
            is_admin = bool(user and CHIEF_TELEGRAM_ID != 0 and user.id == CHIEF_TELEGRAM_ID)
            status = "APPROVED" if is_admin else "PENDING"

            new_resource = create_resource(
                db=db,
                title=title,
                semester=semester,
                subject_id=subject_id,
                resource_type=resource_type,
                file_id=doc.file_id,
                file_name=file_name,
                uploaded_by=user.id,
                status=status
            )
            resource_id = new_resource.id
    except Exception as e:
        logger.error(f"Error saving resource to DB: {e}")
        await update.message.reply_text("⚠️ Failed to submit resource due to database error. Please try again.")
        return ConversationHandler.END

    # Success completion message in text
    await update.message.reply_text(
        "✅ Resource uploaded successfully!\n\n"
        "Type /start to return to the main menu."
    )

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
