import logging
# pyrefly: ignore [missing-import]
from telegram import Update
# pyrefly: ignore [missing-import]
from telegram.ext import ContextTypes
from config import CHIEF_TELEGRAM_ID
from database.connection import get_db
from database.crud import (
    get_all_branches,
    get_branch_by_name,
    get_subjects_by_semester,
    get_subject_by_id,
    get_approved_resources,
    get_approved_semester_pyqs,
    get_resource_by_id,
    increment_resource_download,
    log_user_event,
)
from bot.keyboards.menus import (
    get_branches_keyboard,
    get_semesters_for_branch_keyboard,
    get_semester_keyboard,
    get_subjects_keyboard,
    get_resource_types_keyboard,
    get_resources_download_keyboard,
    get_resources_manage_keyboard,
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
    """Handle '📚 Access' click - prompt user to Choose Branch."""
    query = update.callback_query
    await query.answer()

    try:
        with get_db() as db:
            branches = get_all_branches(db)
    except Exception as e:
        logger.error(f"Error fetching branches in access_start: {e}")
        branches = []

    if not branches:
        # Fallback if no branches table seeded yet
        await query.edit_message_text(
            text="Choose Semester",
            reply_markup=get_semester_keyboard(prefix="access_sem", back_callback="back_to_main")
        )
        return

    await query.edit_message_text(
        text="🏛️ Select Branch\n\nChoose your engineering branch:",
        reply_markup=get_branches_keyboard(branches, prefix="access_branch", back_callback="back_to_main")
    )


async def access_branch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle branch selection in access flow - prompt user to Choose Semester for this branch."""
    query = update.callback_query
    await query.answer()

    branch_name = query.data.replace("access_branch_", "").strip()
    context.user_data["access_branch"] = branch_name

    semesters = ["2-2", "3-1"]
    try:
        with get_db() as db:
            b_obj = get_branch_by_name(db, branch_name)
            if b_obj and b_obj.semesters:
                semesters = [s.strip() for s in b_obj.semesters.split(",") if s.strip()]
    except Exception as e:
        logger.warning(f"Could not load branch semesters for {branch_name}: {e}")

    await query.edit_message_text(
        text=f"🎓 Branch: {branch_name}\n\nSelect your Semester:",
        reply_markup=get_semesters_for_branch_keyboard(
            branch=branch_name,
            semesters=semesters,
            prefix="access_sem",
            back_callback="main_access"
        )
    )


async def access_semester_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle semester selection in access flow - retrieve subjects from DB."""
    query = update.callback_query
    await query.answer()

    # Data format: access_sem_CSE 2-2, access_sem_CSE 3-1, access_sem_CSE(AI) 3-1
    semester = query.data.replace("access_sem_", "")
    context.user_data["access_semester"] = semester

    # Identify branch for back button
    branch = context.user_data.get("access_branch")
    if not branch and " " in semester:
        branch = semester.rsplit(" ", 1)[0]
    back_to_sem_list = f"access_branch_{branch}" if branch else "main_access"

    try:
        with get_db() as db:
            subjects = get_subjects_by_semester(db, semester)
            if update.effective_user:
                log_user_event(db, update.effective_user.id, "VIEW_SEMESTER", semester)
    except Exception as e:
        logger.error(f"Error fetching subjects for {semester}: {e}")
        await query.edit_message_text("⚠️ Database error occurred. Please try again later.")
        return

    if not subjects:
        await query.edit_message_text(
            text="⚠️ Source unavailable",
            reply_markup=get_unavailable_keyboard(back_callback=back_to_sem_list)
        )
        return

    await query.edit_message_text(
        text=f"📚 {semester} — Select Subject",
        reply_markup=get_subjects_keyboard(subjects, prefix="access_subj", back_callback=back_to_sem_list)
    )


async def access_subject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle subject selection in access flow - prompt for resource type or load PYQs directly."""
    query = update.callback_query
    await query.answer()

    if query.data == "access_subj_pyq_all":
        semester = context.user_data.get("access_semester")
        if not semester:
            await query.edit_message_text("Session expired. Please start again with /start.")
            return
        context.user_data["access_is_pyq"] = True
        back_cb = f"access_sem_{semester}" if semester else "main_access"
        try:
            with get_db() as db:
                if update.effective_user:
                    log_user_event(db, update.effective_user.id, "VIEW_PYQ_ALL", semester)
                resources = get_approved_semester_pyqs(db, semester)
        except Exception as e:
            logger.error(f"Error querying PYQ resources for {semester}: {e}")
            await query.edit_message_text("⚠️ Database error occurred. Please try again.")
            return

        if not resources:
            await query.edit_message_text(
                text="⚠️ No PYQ resources available for this semester yet.",
                reply_markup=get_unavailable_keyboard(back_callback=back_cb)
            )
            return

        user = update.effective_user
        is_chief = bool(user and CHIEF_TELEGRAM_ID != 0 and user.id == CHIEF_TELEGRAM_ID)
        header_text = f"📝 {semester} PYQ Papers\n\nClick a button below to download:"
        await query.edit_message_text(
            text=header_text,
            reply_markup=get_resources_download_keyboard(resources, back_callback=back_cb, is_chief=is_chief)
        )
        return

    try:
        subject_id = int(query.data.replace("access_subj_", ""))
        context.user_data["access_subject_id"] = subject_id
    except ValueError:
        await query.edit_message_text("Invalid subject selected.")
        return

    semester = context.user_data.get("access_semester")
    back_cb = f"access_sem_{semester}" if semester else "main_access"

    try:
        with get_db() as db:
            if update.effective_user:
                log_user_event(db, update.effective_user.id, "VIEW_SUBJECT", str(subject_id))
    except Exception:
        pass

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
    context.user_data["access_is_pyq"] = False

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

    user = update.effective_user
    is_chief = bool(user and CHIEF_TELEGRAM_ID != 0 and user.id == CHIEF_TELEGRAM_ID)

    await query.edit_message_text(
        text=header_text,
        reply_markup=get_resources_download_keyboard(resources, back_callback=back_cb, is_chief=is_chief)
    )


async def access_manage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Chief clicking '✏️ Rename a File' or '🗑️ Delete a File' at the bottom of the list."""
    query = update.callback_query
    user = update.effective_user
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        await query.answer("⛔ Unauthorized", show_alert=True)
        return

    await query.answer()
    action = "rename" if "rename" in query.data else "delete"

    semester = context.user_data.get("access_semester")
    is_pyq = context.user_data.get("access_is_pyq", False)
    subject_id = context.user_data.get("access_subject_id")
    resource_type = context.user_data.get("access_resource_type")

    try:
        with get_db() as db:
            if is_pyq:
                resources = get_approved_semester_pyqs(db, semester)
            else:
                resources = get_approved_resources(db, semester, subject_id, resource_type)
    except Exception as e:
        logger.error(f"Error querying resources in access_manage_callback: {e}")
        await query.edit_message_text("⚠️ Database error occurred.")
        return

    if not resources:
        await query.edit_message_text("⚠️ No resources available to manage.")
        return

    action_label = "rename" if action == "rename" else "delete"
    action_icon = "✏️" if action == "rename" else "🗑️"
    prompt_text = f"{action_icon} Select a file to {action_label}:"

    await query.edit_message_text(
        text=prompt_text,
        reply_markup=get_resources_manage_keyboard(resources, action=action, back_callback="access_restore_view")
    )


async def access_restore_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Restore normal download view when cancelling rename/delete selection."""
    query = update.callback_query
    await query.answer()

    semester = context.user_data.get("access_semester")
    is_pyq = context.user_data.get("access_is_pyq", False)
    subject_id = context.user_data.get("access_subject_id")
    resource_type = context.user_data.get("access_resource_type")

    if not semester:
        await query.edit_message_text("Session expired. Please restart with /start.")
        return

    try:
        with get_db() as db:
            if is_pyq:
                back_cb = "main_access"
                resources = get_approved_semester_pyqs(db, semester)
                header_text = f"📝 {semester} PYQ Papers\n\nClick a button below to download:"
            else:
                back_cb = f"access_subj_{subject_id}" if subject_id else "main_access"
                subject = get_subject_by_id(db, subject_id) if subject_id else None
                subject_name = subject.name if subject else "Selected Subject"
                resources = get_approved_resources(db, semester, subject_id, resource_type)
                type_icon_map = {"NOTES": "📒", "PYQ": "📝", "ASSIGNMENT": "📋"}
                icon = type_icon_map.get(resource_type, "📚")
                header_text = f"{icon} {subject_name} {resource_type.capitalize()}\n\nClick a button below to download the resource:"
    except Exception as e:
        logger.error(f"Error restoring view in access_restore_view_callback: {e}")
        await query.edit_message_text("⚠️ Database error occurred.")
        return

    user = update.effective_user
    is_chief = bool(user and CHIEF_TELEGRAM_ID != 0 and user.id == CHIEF_TELEGRAM_ID)
    await query.edit_message_text(
        text=header_text,
        reply_markup=get_resources_download_keyboard(resources, back_callback=back_cb, is_chief=is_chief)
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
                if update.effective_user:
                    log_user_event(db, update.effective_user.id, "DOWNLOAD", str(resource_id))
        except Exception as ex:
            logger.error(f"Error incrementing download count for resource {resource_id}: {ex}")

        # Completion text message prompting start
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Type /start to return to the main menu."
        )
    except Exception as e:
        logger.error(f"Error sending document {file_id}: {e}")
        await query.message.reply_text("⚠️ Failed to send document. The file may have expired on Telegram.")
