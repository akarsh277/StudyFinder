import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import CHIEF_TELEGRAM_ID
from database.connection import get_db
from database.crud import (
    get_all_branches,
    get_branch_by_name,
    create_branch,
    add_semester_to_branch,
    create_subject,
    get_all_subjects,
    get_resource_by_id,
    update_resource_status,
    update_resource_title,
    delete_resource,
    get_subjects_by_semester,
    get_subject_by_id,
    get_approved_resources,
    get_approved_semester_pyqs,
)
from bot.states.conversation import (
    RENAME_TITLE,
    ENTER_BRANCH_NAME,
    SELECT_BRANCH_FOR_SEM,
    ENTER_SEM_NAME,
    SELECT_BRANCH_FOR_SUBJ,
    SELECT_SEM_FOR_SUBJ,
    ENTER_SUBJ_NAME,
)
from bot.keyboards.menus import (
    get_branches_keyboard,
    get_semesters_for_branch_keyboard,
    get_semester_keyboard,
    get_subjects_keyboard,
    get_resource_types_keyboard,
    get_resources_download_keyboard,
    get_confirm_delete_keyboard,
    get_unavailable_keyboard,
)

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
    """Handle /delete command - prompt Chief to choose branch then semester to delete resources."""
    user = update.effective_user

    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        logger.warning(f"Unauthorized access attempt to /delete by user ID {user.id if user else 'Unknown'}")
        if update.message:
            await update.message.reply_text("⛔ You are not authorized to manage or delete resources.")
        return

    try:
        with get_db() as db:
            branches = get_all_branches(db)
    except Exception as e:
        logger.error(f"Error fetching branches in delete_command_handler: {e}")
        branches = []

    text_msg = "🏛️ Select Branch to manage/delete resources:"
    reply_markup = get_branches_keyboard(branches, prefix="delete_branch", back_callback="back_to_main")

    if update.message:
        await update.message.reply_text(text=text_msg, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text_msg, reply_markup=reply_markup)


async def delete_branch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle branch selection in /delete flow - prompt for semester."""
    query = update.callback_query
    user = update.effective_user

    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        await query.answer("⛔ Unauthorized", show_alert=True)
        return

    await query.answer()
    branch_name = query.data.replace("delete_branch_", "").strip()
    context.user_data["delete_branch"] = branch_name

    semesters = ["2-2", "3-1"]
    try:
        with get_db() as db:
            b_obj = get_branch_by_name(db, branch_name)
            if b_obj and b_obj.semesters:
                semesters = [s.strip() for s in b_obj.semesters.split(",") if s.strip()]
    except Exception as e:
        logger.warning(f"Could not load branch semesters for delete: {e}")

    await query.edit_message_text(
        text=f"🎓 Branch: {branch_name}\n\nSelect Semester to manage/delete resources:",
        reply_markup=get_semesters_for_branch_keyboard(
            branch=branch_name,
            semesters=semesters,
            prefix="delete_sem",
            back_callback="back_to_main"
        )
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

    branch = context.user_data.get("delete_branch")
    if not branch and " " in semester:
        branch = semester.rsplit(" ", 1)[0]
    back_cb = f"delete_branch_{branch}" if branch else "back_to_main"

    try:
        with get_db() as db:
            subjects = get_subjects_by_semester(db, semester)
    except Exception as e:
        logger.error(f"Error fetching subjects for delete flow: {e}")
        await query.edit_message_text("⚠️ Database error occurred.")
        return

    if not subjects:
        await query.edit_message_text(
            f"⚠️ No subjects registered for {semester} yet.\n\nType /start to return to the main menu."
        )
        return

    await query.edit_message_text(
        text=f"📚 {semester} — Select Subject to delete resources from:",
        reply_markup=get_subjects_keyboard(subjects, prefix="delete_subj", back_callback=back_cb)
    )


async def delete_subject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle subject selection in /delete flow."""
    query = update.callback_query
    user = update.effective_user

    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        await query.answer("⛔ Unauthorized", show_alert=True)
        return

    await query.answer()

    if query.data == "delete_subj_pyq_all":
        semester = context.user_data.get("delete_semester")
        if not semester:
            await query.edit_message_text("Session expired. Please start again with /delete.")
            return
        back_cb = f"delete_sem_{semester}"
        try:
            with get_db() as db:
                resources = get_approved_semester_pyqs(db, semester)
        except Exception as e:
            logger.error(f"Error querying PYQ resources for delete flow: {e}")
            await query.edit_message_text("⚠️ Database error occurred.")
            return

        if not resources:
            await query.edit_message_text(
                text="⚠️ No PYQ resources available in this section.",
                reply_markup=get_unavailable_keyboard(back_callback=back_cb)
            )
            return

        header_text = f"Manage {semester} PYQ Papers:\n\nClick 🗑️ to delete or ✏️ to rename:"
        await query.edit_message_text(
            text=header_text,
            reply_markup=get_resources_download_keyboard(resources, back_callback=back_cb, is_chief=True)
        )
        return

    try:
        subject_id = int(query.data.replace("delete_subj_", ""))
        context.user_data["delete_subject_id"] = subject_id
    except ValueError:
        await query.edit_message_text("Invalid subject selected.")
        return

    semester = context.user_data.get("delete_semester")
    back_cb = f"delete_sem_{semester}" if semester else "back_to_main"

    await query.edit_message_text(
        text="Select Resource Type:",
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

    header_text = f"Manage Resources in {subject_name} {resource_type.capitalize()}:\n\nClick 🗑️ to delete or ✏️ to rename:"
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
        await query.edit_message_text(
            text=f"✅ Resource '{title}' has been deleted successfully.\n\nType /start to return to the main menu."
        )
    else:
        await query.answer("Resource not found or already deleted.")
        await query.edit_message_text(
            text="⚠️ Resource was already deleted or not found.\n\nType /start to return to the main menu."
        )


async def rename_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Chief clicking ✏️ to rename a resource."""
    query = update.callback_query
    user = update.effective_user

    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        await query.answer("⛔ Unauthorized: Only Chief can rename resources.", show_alert=True)
        return ConversationHandler.END

    await query.answer()

    try:
        resource_id = int(query.data.replace("rename_", ""))
    except ValueError:
        await query.answer("Invalid resource ID.", show_alert=True)
        return ConversationHandler.END

    try:
        with get_db() as db:
            resource = get_resource_by_id(db, resource_id)
            if not resource:
                await query.edit_message_text("⚠️ Resource not found.")
                return ConversationHandler.END
            current_title = resource.title
    except Exception as e:
        logger.error(f"Error loading resource {resource_id} for rename: {e}")
        await query.edit_message_text("⚠️ Database error occurred.")
        return ConversationHandler.END

    context.user_data["rename_resource_id"] = resource_id

    cancel_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_rename")]
    ])

    await query.edit_message_text(
        text=(
            f"✏️ Rename Resource\n\n"
            f"Current title: {current_title}\n\n"
            f"Please enter the new title for this resource in text:"
        ),
        reply_markup=cancel_markup
    )
    return RENAME_TITLE


async def rename_title_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle entry of new title for the resource."""
    user = update.effective_user
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        return ConversationHandler.END

    new_title = update.message.text.strip()
    if not new_title:
        await update.message.reply_text("Title cannot be empty. Please enter a valid title:")
        return RENAME_TITLE

    resource_id = context.user_data.get("rename_resource_id")
    if not resource_id:
        await update.message.reply_text("Session expired. Please start again with /start.")
        return ConversationHandler.END

    try:
        with get_db() as db:
            updated = update_resource_title(db, resource_id, new_title)
            if not updated:
                await update.message.reply_text("⚠️ Resource not found or already deleted.")
                return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error updating title for resource {resource_id}: {e}")
        await update.message.reply_text("⚠️ Database error occurred while renaming.")
        return ConversationHandler.END

    context.user_data.pop("rename_resource_id", None)
    await update.message.reply_text(
        f"✅ Resource renamed successfully to:\n\"{new_title}\"\n\nType /start to return to the main menu."
    )
    return ConversationHandler.END


async def cancel_rename_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle cancelling resource rename."""
    context.user_data.pop("rename_resource_id", None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "Rename cancelled.\n\nType /start to return to the main menu."
        )
    elif update.message:
        await update.message.reply_text(
            "Rename cancelled.\n\nType /start to return to the main menu."
        )
    return ConversationHandler.END


async def add_branch_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Allow Chief to add a new engineering branch via Telegram."""
    user = update.effective_user
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        if update.message:
            await update.message.reply_text("⛔ Unauthorized: Only the Chief can add new branches.")
        return ConversationHandler.END

    args = context.args or []
    if args:
        # One-line format: /addbranch ECE or /addbranch ECE 2-2,3-1
        branch_name = args[0].strip().upper()
        semesters = args[1].strip() if len(args) > 1 else "2-2,3-1"
        try:
            with get_db() as db:
                existing = get_branch_by_name(db, branch_name)
                if existing:
                    await update.message.reply_text(f"⚠️ Branch '{branch_name}' already exists.")
                    return ConversationHandler.END
                create_branch(db, name=branch_name, semesters=semesters)
            await update.message.reply_text(
                f"✅ Branch *{branch_name}* added successfully!\n"
                f"Available semesters: {semesters}\n\n"
                f"Students can now select it in the bot menu.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error adding branch {branch_name}: {e}")
            await update.message.reply_text(f"⚠️ Database error adding branch: {e}")
        return ConversationHandler.END

    # Interactive prompt if no args provided
    cancel_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_branch")]
    ])
    await update.message.reply_text(
        "🏛️ *Add New Branch (Chief Only)*\n\n"
        "Please reply with the branch name (e.g. `ECE`, `IT`, `MECH`, `AIDS`):\n\n"
        "Or tap Cancel below to abort.",
        reply_markup=cancel_markup,
        parse_mode="Markdown"
    )
    return ENTER_BRANCH_NAME


async def add_branch_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text input for new branch name."""
    user = update.effective_user
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        return ConversationHandler.END

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Branch name cannot be empty. Please enter a valid name:")
        return ENTER_BRANCH_NAME

    parts = text.split(maxsplit=1)
    branch_name = parts[0].strip().upper()
    semesters = parts[1].strip() if len(parts) > 1 else "2-2,3-1"

    try:
        with get_db() as db:
            existing = get_branch_by_name(db, branch_name)
            if existing:
                await update.message.reply_text(f"⚠️ Branch '{branch_name}' already exists.\n\nType /start to return.")
                return ConversationHandler.END
            create_branch(db, name=branch_name, semesters=semesters)
        await update.message.reply_text(
            f"✅ Branch *{branch_name}* added successfully!\n"
            f"Available semesters: {semesters}\n\n"
            f"Students can now select it in the bot menu.\nType /start to return to menu.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error creating branch: {e}")
        await update.message.reply_text(f"⚠️ Database error creating branch: {e}")
    return ConversationHandler.END


async def cancel_add_branch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle cancelling add branch flow."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Add branch cancelled.\n\nType /start to return.")
    elif update.message:
        await update.message.reply_text("Add branch cancelled.\n\nType /start to return.")
    return ConversationHandler.END


async def list_branches_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all configured branches."""
    user = update.effective_user
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        if update.message:
            await update.message.reply_text("⛔ Unauthorized: Chief only.")
        return

    try:
        with get_db() as db:
            branches = get_all_branches(db)
        if not branches:
            await update.message.reply_text("No branches found in database.")
            return

        lines = ["🏛️ *Configured Engineering Branches:*", ""]
        for idx, b in enumerate(branches, 1):
            lines.append(f"{idx}. *{b.name}* (Semesters: {b.semesters})")
        lines.append("")
        lines.append("To add a new branch, use: `/addbranch <name>`")
        lines.append("To add a semester, use: `/addsem <branch> <sem>`")
        lines.append("To add a subject, use: `/addsubject <branch> <sem> <subject>`")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error listing branches: {e}")
        await update.message.reply_text(f"⚠️ Error retrieving branches: {e}")


async def admin_panel_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display interactive Chief control panel with action buttons."""
    user = update.effective_user
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        if update.message:
            await update.message.reply_text("⛔ Unauthorized: Chief only.")
        return

    keyboard = [
        [
            InlineKeyboardButton("🏛️ Add Branch", callback_data="admin_btn_addbranch"),
            InlineKeyboardButton("🎓 Add Semester", callback_data="admin_btn_addsem"),
        ],
        [
            InlineKeyboardButton("📖 Add Subject", callback_data="admin_btn_addsubj"),
            InlineKeyboardButton("📚 View Subjects", callback_data="admin_btn_viewsubj"),
        ],
        [
            InlineKeyboardButton("🗑️ Manage / Delete Files", callback_data="delete_main"),
            InlineKeyboardButton("📢 Daily Digest", callback_data="admin_btn_digest"),
        ],
        [
            InlineKeyboardButton("📊 30-Day Analytics", callback_data="admin_btn_stats"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main"),
        ]
    ]

    text = (
        "🛠️ *Chief Control Center*\n\n"
        "Manage branches, semesters, subjects, and resources directly without touching code:"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


# --- Add Semester Handlers ---
async def add_sem_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Add a semester to a branch (e.g. /addsem CSE 3-2 or interactive)."""
    user = update.effective_user
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        if update.message:
            await update.message.reply_text("⛔ Unauthorized: Chief only.")
        return ConversationHandler.END

    args = context.args or []
    if len(args) >= 2:
        branch_name = args[0].strip().upper()
        sem_code = args[1].strip()
        try:
            with get_db() as db:
                b = add_semester_to_branch(db, branch_name, sem_code)
                if not b:
                    await update.message.reply_text(f"⚠️ Branch '{branch_name}' not found. Add it first with /addbranch {branch_name}")
                    return ConversationHandler.END
            await update.message.reply_text(
                f"✅ Semester *{sem_code}* added to branch *{branch_name}*!\n\n"
                f"Active semesters: {b.semesters}\nStudents can now select it.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error adding semester: {e}")
            await update.message.reply_text(f"⚠️ Error: {e}")
        return ConversationHandler.END

    # Interactive flow
    try:
        with get_db() as db:
            branches = get_all_branches(db)
    except Exception as e:
        branches = []

    if not branches:
        msg = "⚠️ No branches found. Please add a branch first with /addbranch"
        if update.message:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.edit_message_text(msg)
        return ConversationHandler.END

    keyboard = []
    row = []
    for b in branches:
        row.append(InlineKeyboardButton(f"🏛️ {b.name}", callback_data=f"addsem_br_{b.name}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_sem")])

    text = "🎓 *Add Semester (Chief Only)*\n\nSelect which branch to add a semester to:"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return SELECT_BRANCH_FOR_SEM


async def add_sem_branch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle branch selection in add semester flow."""
    query = update.callback_query
    await query.answer()

    branch_name = query.data.replace("addsem_br_", "").strip()
    context.user_data["addsem_branch"] = branch_name

    cancel_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_sem")]
    ])
    await query.edit_message_text(
        f"🎓 Branch: *{branch_name}*\n\n"
        f"Please reply with the semester code to add (e.g. `1-1`, `1-2`, `2-1`, `2-2`, `3-1`, `3-2`, `4-1`, `4-2`):",
        reply_markup=cancel_markup,
        parse_mode="Markdown"
    )
    return ENTER_SEM_NAME


async def add_sem_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text input for new semester code."""
    user = update.effective_user
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        return ConversationHandler.END

    sem_code = update.message.text.strip()
    branch_name = context.user_data.get("addsem_branch")
    if not branch_name:
        await update.message.reply_text("Session expired. Please restart with /addsem")
        return ConversationHandler.END

    try:
        with get_db() as db:
            b = add_semester_to_branch(db, branch_name, sem_code)
            if not b:
                await update.message.reply_text(f"⚠️ Branch '{branch_name}' not found.")
                return ConversationHandler.END
        context.user_data.pop("addsem_branch", None)
        await update.message.reply_text(
            f"✅ Semester *{sem_code}* added to *{branch_name}*!\n\n"
            f"Active semesters: {b.semesters}\n"
            f"Type /start or /admin to continue.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error adding semester: {e}")
        await update.message.reply_text(f"⚠️ Database error adding semester: {e}")
    return ConversationHandler.END


async def cancel_add_sem_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle cancelling add semester flow."""
    context.user_data.pop("addsem_branch", None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Add semester cancelled.\n\nType /start or /admin to return.")
    elif update.message:
        await update.message.reply_text("Add semester cancelled.\n\nType /start or /admin to return.")
    return ConversationHandler.END


# --- Add Subject Handlers ---
async def add_subj_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Add a subject dynamically to a branch & semester without touching code."""
    user = update.effective_user
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        if update.message:
            await update.message.reply_text("⛔ Unauthorized: Chief only.")
        return ConversationHandler.END

    args = context.args or []
    if len(args) >= 3:
        # One line: /addsubject CSE 3-1 MachineLearning
        branch_name = args[0].strip().upper()
        sem_code = args[1].strip()
        subject_name = " ".join(args[2:]).strip()
        full_sem = f"{branch_name} {sem_code}"
        try:
            with get_db() as db:
                add_semester_to_branch(db, branch_name, sem_code)
                s = create_subject(db, name=subject_name, semester=full_sem)
            await update.message.reply_text(
                f"✅ Subject *{s.name}* added successfully to *{full_sem}*!\n\n"
                f"Students can now immediately upload and access notes for this subject.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error adding subject: {e}")
            await update.message.reply_text(f"⚠️ Error: {e}")
        return ConversationHandler.END

    # Interactive flow
    try:
        with get_db() as db:
            branches = get_all_branches(db)
    except Exception as e:
        branches = []

    if not branches:
        msg = "⚠️ No branches configured yet. Add one with /addbranch"
        if update.message:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.edit_message_text(msg)
        return ConversationHandler.END

    keyboard = []
    row = []
    for b in branches:
        row.append(InlineKeyboardButton(f"🏛️ {b.name}", callback_data=f"addsub_br_{b.name}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_subj")])

    text = "📖 *Add Subject (Chief Only)*\n\nStep 1: Select Branch:"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return SELECT_BRANCH_FOR_SUBJ


async def add_subj_branch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle branch selection in add subject flow - show semesters."""
    query = update.callback_query
    await query.answer()

    branch_name = query.data.replace("addsub_br_", "").strip()
    context.user_data["addsub_branch"] = branch_name

    semesters = ["2-2", "3-1"]
    try:
        with get_db() as db:
            b_obj = get_branch_by_name(db, branch_name)
            if b_obj and b_obj.semesters:
                semesters = [s.strip() for s in b_obj.semesters.split(",") if s.strip()]
    except Exception as e:
        logger.warning(f"Error reading branch semesters: {e}")

    keyboard = []
    row = []
    for sem in semesters:
        row.append(InlineKeyboardButton(f"🎓 {sem}", callback_data=f"addsub_sem_{sem}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_subj")])

    await query.edit_message_text(
        f"📖 *Add Subject — {branch_name}*\n\nStep 2: Select Semester:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return SELECT_SEM_FOR_SUBJ


async def add_subj_sem_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle semester selection in add subject flow - prompt for subject name."""
    query = update.callback_query
    await query.answer()

    sem_code = query.data.replace("addsub_sem_", "").strip()
    branch_name = context.user_data.get("addsub_branch", "CSE")
    full_sem = f"{branch_name} {sem_code}"
    context.user_data["addsub_semester"] = full_sem

    cancel_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_subj")]
    ])
    await query.edit_message_text(
        f"📖 *Add Subject to {full_sem}*\n\n"
        f"Step 3: Please reply with the Subject Name (e.g. `Machine Learning`, `AI`, `Signals & Systems`):",
        reply_markup=cancel_markup,
        parse_mode="Markdown"
    )
    return ENTER_SUBJ_NAME


async def add_subj_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text input for subject name and save to DB."""
    user = update.effective_user
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        return ConversationHandler.END

    subj_name = update.message.text.strip()
    full_sem = context.user_data.get("addsub_semester")
    if not full_sem:
        await update.message.reply_text("Session expired. Please restart with /addsubject")
        return ConversationHandler.END

    try:
        with get_db() as db:
            s = create_subject(db, name=subj_name, semester=full_sem)
        context.user_data.pop("addsub_branch", None)
        context.user_data.pop("addsub_semester", None)
        await update.message.reply_text(
            f"✅ Subject *{s.name}* created successfully for *{full_sem}*!\n\n"
            f"It is now immediately available in the bot for notes upload and access.\n"
            f"Type /start or /admin to return.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error creating subject: {e}")
        await update.message.reply_text(f"⚠️ Database error creating subject: {e}")
    return ConversationHandler.END


async def cancel_add_subj_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle cancelling add subject flow."""
    context.user_data.pop("addsub_branch", None)
    context.user_data.pop("addsub_semester", None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Add subject cancelled.\n\nType /start or /admin to return.")
    elif update.message:
        await update.message.reply_text("Add subject cancelled.\n\nType /start or /admin to return.")
    return ConversationHandler.END


async def list_subjects_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all registered subjects grouped by semester."""
    user = update.effective_user
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        if update.message:
            await update.message.reply_text("⛔ Unauthorized: Chief only.")
        return

    try:
        with get_db() as db:
            subjects = get_all_subjects(db)
        if not subjects:
            text = "No subjects registered yet in the database."
        else:
            from collections import defaultdict
            grouped = defaultdict(list)
            for s in subjects:
                grouped[s.semester].append(s.name)

            lines = ["📚 *Registered Subjects in StudyFind:*", ""]
            for sem, subj_list in grouped.items():
                lines.append(f"🎓 *{sem}* ({len(subj_list)} subjects):")
                lines.append("  • " + ", ".join(subj_list))
                lines.append("")
            lines.append("To add a new subject, use: `/addsubject`")
            text = "\n".join(lines).strip()

        if update.message:
            await update.message.reply_text(text, parse_mode="Markdown")
        elif update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error listing subjects: {e}")
        if update.message:
            await update.message.reply_text(f"⚠️ Error: {e}")


