import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import CHIEF_TELEGRAM_ID
from database.connection import get_db
from database.crud import get_resource_by_id, update_resource_status

logger = logging.getLogger(__name__)


async def approve_resource_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Chief clicking Approve on a submission."""
    query = update.callback_query
    user = update.effective_user

    if not user:
        return

    # Security check: Only Chief can approve
    if CHIEF_TELEGRAM_ID != 0 and user.id != CHIEF_TELEGRAM_ID:
        await query.answer("⚠️ Unauthorized: Only the Chief can approve resources.", show_alert=True)
        return

    try:
        resource_id = int(query.data.replace("approve_", ""))
    except ValueError:
        await query.answer("Invalid resource ID.", show_alert=True)
        return

    try:
        with get_db() as db:
            resource = get_resource_by_id(db, resource_id)

            if not resource:
                await query.answer("Resource not found.", show_alert=True)
                return

            if resource.status != "PENDING":
                await query.answer(f"Resource already processed ({resource.status}).", show_alert=True)
                return

            # Update status to APPROVED
            update_resource_status(db, resource_id, "APPROVED")
            uploader_id = resource.uploaded_by
            title = resource.title
    except Exception as e:
        logger.error(f"Error approving resource {resource_id}: {e}")
        await query.answer("⚠️ Error updating resource status.", show_alert=True)
        return

    await query.answer("Resource approved successfully.")

    # Update caption/text for Chief to prevent re-clicks
    current_caption = query.message.caption or query.message.text or ""
    new_caption = f"{current_caption}\n\n✅ [APPROVED BY CHIEF]"
    try:
        if query.message.caption:
            await query.edit_message_caption(caption=new_caption, reply_markup=None)
        else:
            await query.edit_message_text(text=new_caption, reply_markup=None)
    except Exception as e:
        logger.warning(f"Could not update Chief message UI: {e}")

    # Notify uploader
    try:
        await context.bot.send_message(
            chat_id=uploader_id,
            text="✅ Your resource has been approved!\n\nIt is now available to other students."
        )
    except Exception as e:
        logger.error(f"Error sending approval notification to student {uploader_id}: {e}")


async def reject_resource_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Chief clicking Reject on a submission."""
    query = update.callback_query
    user = update.effective_user

    if not user:
        return

    # Security check: Only Chief can reject
    if CHIEF_TELEGRAM_ID != 0 and user.id != CHIEF_TELEGRAM_ID:
        await query.answer("⚠️ Unauthorized: Only the Chief can reject resources.", show_alert=True)
        return

    try:
        resource_id = int(query.data.replace("reject_", ""))
    except ValueError:
        await query.answer("Invalid resource ID.", show_alert=True)
        return

    try:
        with get_db() as db:
            resource = get_resource_by_id(db, resource_id)

            if not resource:
                await query.answer("Resource not found.", show_alert=True)
                return

            if resource.status != "PENDING":
                await query.answer(f"Resource already processed ({resource.status}).", show_alert=True)
                return

            # Update status to REJECTED
            update_resource_status(db, resource_id, "REJECTED")
            uploader_id = resource.uploaded_by
    except Exception as e:
        logger.error(f"Error rejecting resource {resource_id}: {e}")
        await query.answer("⚠️ Error updating resource status.", show_alert=True)
        return

    await query.answer("Resource rejected.")

    # Update caption/text for Chief to prevent re-clicks
    current_caption = query.message.caption or query.message.text or ""
    new_caption = f"{current_caption}\n\n❌ [REJECTED BY CHIEF]"
    try:
        if query.message.caption:
            await query.edit_message_caption(caption=new_caption, reply_markup=None)
        else:
            await query.edit_message_text(text=new_caption, reply_markup=None)
    except Exception as e:
        logger.warning(f"Could not update Chief message UI: {e}")

    # Notify uploader exact text required by spec
    try:
        await context.bot.send_message(
            chat_id=uploader_id,
            text="❌ Your resource was rejected by the Chief."
        )
    except Exception as e:
        logger.error(f"Error sending rejection notification to student {uploader_id}: {e}")


async def delete_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /delete command - prompt Chief to choose semester to delete resources."""
    user = update.effective_user

    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        logger.warning(f"Unauthorized access attempt to /delete by user ID {user.id if user else 'Unknown'}")
        if update.message:
            await update.message.reply_text("⛔ You are not authorized to manage or delete resources.")
        return

    if update.message:
        await update.message.reply_text(
            text="🗑️ Select Semester to manage/delete resources:",
            reply_markup=get_semester_keyboard(prefix="delete_sem", back_callback="back_to_main")
        )


async def delete_semester_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle semester selection in /delete flow."""
    query = update.callback_query
    user = update.effective_user

    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        await query.answer("⛔ Unauthorized", show_alert=True)
        return

    await query.answer()
    semester = query.data.replace("delete_sem_", "")
    context.user_data["delete_semester"] = semester

    try:
        with get_db() as db:
            subjects = get_subjects_by_semester(db, semester)
    except Exception as e:
        logger.error(f"Error fetching subjects for delete flow: {e}")
        await query.edit_message_text("⚠️ Database error occurred.")
        return

    if not subjects:
        await query.edit_message_text("⚠️ No subjects registered for this semester yet.")
        return

    await query.edit_message_text(
        text="🗑️ Select Subject to delete resources from:",
        reply_markup=get_subjects_keyboard(subjects, prefix="delete_subj", back_callback="back_to_main")
    )


async def delete_subject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle subject selection in /delete flow."""
    query = update.callback_query
    user = update.effective_user

    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        await query.answer("⛔ Unauthorized", show_alert=True)
        return

    await query.answer()
    try:
        subject_id = int(query.data.replace("delete_subj_", ""))
        context.user_data["delete_subject_id"] = subject_id
    except ValueError:
        await query.edit_message_text("Invalid subject selected.")
        return

    semester = context.user_data.get("delete_semester")
    back_cb = f"delete_sem_{semester}" if semester else "back_to_main"

    await query.edit_message_text(
        text="🗑️ Select Resource Type:",
        reply_markup=get_resource_types_keyboard(prefix="delete_type", back_callback=back_cb)
    )


async def delete_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle resource type selection in /delete flow."""
    query = update.callback_query
    user = update.effective_user

    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        await query.answer("⛔ Unauthorized", show_alert=True)
        return

    await query.answer()
    resource_type = query.data.replace("delete_type_", "")
    semester = context.user_data.get("delete_semester")
    subject_id = context.user_data.get("delete_subject_id")

    if not semester or not subject_id:
        await query.edit_message_text("Session expired. Please start again with /delete.")
        return

    back_cb = f"delete_subj_{subject_id}"

    try:
        with get_db() as db:
            subject = get_subject_by_id(db, subject_id)
            subject_name = subject.name if subject else "Selected Subject"
            resources = get_approved_resources(db, semester, subject_id, resource_type)
    except Exception as e:
        logger.error(f"Error querying resources for delete flow: {e}")
        await query.edit_message_text("⚠️ Database error occurred.")
        return

    if not resources:
        await query.edit_message_text(
            text="⚠️ No resources available to delete in this section.",
            reply_markup=get_unavailable_keyboard(back_callback=back_cb)
        )
        return

    header_text = f"🗑️ Delete Resources in {subject_name} {resource_type.capitalize()}:\n\nClick '🗑️ Delete' next to a resource to remove it:"
    await query.edit_message_text(
        text=header_text,
        reply_markup=get_resources_download_keyboard(resources, back_callback=back_cb, is_chief=True)
    )


async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt Chief with confirmation dialog before deleting resource."""
    query = update.callback_query
    user = update.effective_user

    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        await query.answer("⛔ Unauthorized: Only Chief can delete resources.", show_alert=True)
        return

    await query.answer()
    try:
        resource_id = int(query.data.replace("confirm_del_", ""))
    except ValueError:
        await query.answer("Invalid resource ID.", show_alert=True)
        return

    try:
        with get_db() as db:
            resource = get_resource_by_id(db, resource_id)
            if not resource:
                await query.edit_message_text("⚠️ Resource not found or already deleted.")
                return
            title = resource.title
            semester = resource.semester
            resource_type = resource.resource_type
    except Exception as e:
        logger.error(f"Error loading resource {resource_id} for delete confirmation: {e}")
        await query.edit_message_text("⚠️ Database error occurred.")
        return

    confirm_text = (
        f"⚠️ Confirm Resource Deletion\n\n"
        f"Title: {title}\n"
        f"Semester: {semester}\n"
        f"Type: {resource_type}\n\n"
        f"Are you sure you want to permanently delete this resource?"
    )

    await query.edit_message_text(
        text=confirm_text,
        reply_markup=get_confirm_delete_keyboard(resource_id, back_callback="main_access")
    )


async def execute_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute resource deletion after confirmation."""
    query = update.callback_query
    user = update.effective_user

    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        await query.answer("⛔ Unauthorized: Only Chief can delete resources.", show_alert=True)
        return

    try:
        resource_id = int(query.data.replace("do_delete_", ""))
    except ValueError:
        await query.answer("Invalid resource ID.", show_alert=True)
        return

    try:
        with get_db() as db:
            resource = get_resource_by_id(db, resource_id)
            title = resource.title if resource else "Resource"
            success = delete_resource(db, resource_id)
    except Exception as e:
        logger.error(f"Error deleting resource {resource_id}: {e}")
        await query.answer("⚠️ Failed to delete resource.", show_alert=True)
        return

    if success:
        await query.answer("Resource deleted successfully.")
        await query.edit_message_text(text=f"✅ Resource '{title}' has been deleted successfully.")
    else:
        await query.answer("Resource not found or already deleted.")
        await query.edit_message_text(text="⚠️ Resource was already deleted or not found.")
