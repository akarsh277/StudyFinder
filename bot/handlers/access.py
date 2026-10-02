import logging
# pyrefly: ignore [missing-import]
from telegram import Update
# pyrefly: ignore [missing-import]
from telegram.ext import ContextTypes
from database.connection import get_db
from database.crud import (
    get_subjects_by_semester,
    get_subject_by_id,
    get_approved_resources,
    get_resource_by_id,
    increment_resource_download,
)
from bot.keyboards.menus import (
    get_semester_keyboard,
    get_subjects_keyboard,
    get_resource_types_keyboard,
    get_resources_download_keyboard,
    get_unavailable_keyboard
)

logger = logging.getLogger(__name__)


async def back_to_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle returning to main menu."""
    query = update.callback_query
    if query:
        await query.answer()
        from bot.handlers.start import START_MESSAGE
        from bot.keyboards.menus import get_main_menu_keyboard
        await query.edit_message_text(
            text=START_MESSAGE,
            reply_markup=get_main_menu_keyboard()
        )


async def access_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle '📚 Access Resources' click - prompt user to Choose Semester."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        text="Choose Semester",
        reply_markup=get_semester_keyboard(prefix="access_sem", back_callback="back_to_main")
    )


async def access_semester_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle semester selection in access flow - retrieve subjects from DB."""
    query = update.callback_query
    await query.answer()

    # Data format: access_sem_CSE 2-2 or access_sem_CSE 3-1
    semester = query.data.replace("access_sem_", "")
    context.user_data["access_semester"] = semester

    try:
        with get_db() as db:
            subjects = get_subjects_by_semester(db, semester)
    except Exception as e:
        logger.error(f"Error fetching subjects for {semester}: {e}")
        await query.edit_message_text("⚠️ Database error occurred. Please try again later.")
        return

    if not subjects:
        await query.edit_message_text(
            text="⚠️ Source unavailable",
            reply_markup=get_unavailable_keyboard(back_callback="main_access")
        )
        return

    await query.edit_message_text(
        text="Select Subject",
        reply_markup=get_subjects_keyboard(subjects, prefix="access_subj", back_callback="main_access")
    )


async def access_subject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle subject selection in access flow - prompt for resource type."""
    query = update.callback_query
    await query.answer()

    try:
        subject_id = int(query.data.replace("access_subj_", ""))
        context.user_data["access_subject_id"] = subject_id
    except ValueError:
        await query.edit_message_text("Invalid subject selected.")
        return

    semester = context.user_data.get("access_semester")
    back_cb = f"access_sem_{semester}" if semester else "main_access"

    await query.edit_message_text(
        text="Select Resource Type",
        reply_markup=get_resource_types_keyboard(prefix="access_type", back_callback=back_cb)
    )


async def access_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle resource type selection - query DB for APPROVED resources."""
    query = update.callback_query
    await query.answer()

    resource_type = query.data.replace("access_type_", "")
    context.user_data["access_resource_type"] = resource_type

    semester = context.user_data.get("access_semester")
    subject_id = context.user_data.get("access_subject_id")

    if not semester or not subject_id:
        await query.edit_message_text("Session expired. Please start again with /start.")
        return

    back_cb = f"access_subj_{subject_id}"

    try:
        with get_db() as db:
            subject = get_subject_by_id(db, subject_id)
            subject_name = subject.name if subject else "Selected Subject"
            resources = get_approved_resources(db, semester, subject_id, resource_type)
    except Exception as e:
        logger.error(f"Error querying approved resources: {e}")
        await query.edit_message_text("⚠️ Database error occurred. Please try again.")
        return

    if not resources:
        await query.edit_message_text(
            text="⚠️ Source unavailable",
            reply_markup=get_unavailable_keyboard(back_callback=back_cb)
        )
        return

    type_icon_map = {"NOTES": "📒", "PYQ": "📝", "ASSIGNMENT": "📋"}
    icon = type_icon_map.get(resource_type, "📚")
    header_text = f"{icon} {subject_name} {resource_type.capitalize()}\n\nClick a button below to download the resource:"

    await query.edit_message_text(
        text=header_text,
        reply_markup=get_resources_download_keyboard(resources, back_callback=back_cb)
    )


async def download_resource_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle downloading an approved resource via its Telegram file_id."""
    query = update.callback_query
    await query.answer()

    try:
        resource_id = int(query.data.replace("download_", ""))
    except ValueError:
        await query.answer("Invalid resource selected.", show_alert=True)
        return

    try:
        with get_db() as db:
            resource = get_resource_by_id(db, resource_id)
            if not resource or resource.status != "APPROVED":
                await query.answer("⚠️ Resource is no longer available.", show_alert=True)
                return

            file_id = resource.file_id
            title = resource.title
    except Exception as e:
        logger.error(f"Error fetching resource {resource_id}: {e}")
        await query.answer("⚠️ Error retrieving resource file.", show_alert=True)
        return

    try:
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=file_id,
            caption=f"📄 {title}"
        )
        try:
            with get_db() as db:
                increment_resource_download(db, resource_id)
        except Exception as ex:
            logger.error(f"Error incrementing download count for resource {resource_id}: {ex}")
    except Exception as e:
        logger.error(f"Error sending document {file_id}: {e}")
        await query.message.reply_text("⚠️ Failed to send document. The file may have expired on Telegram.")
