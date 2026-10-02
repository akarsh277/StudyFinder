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
