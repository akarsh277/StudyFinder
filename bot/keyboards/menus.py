from typing import List, Optional
# pyrefly: ignore [missing-import]
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.models import Branch, Subject, Resource
from database.crud import natural_sort_key

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Return main menu buttons below start message."""
    keyboard = [
        [
            InlineKeyboardButton("📤 Upload", callback_data="main_upload"),
            InlineKeyboardButton("📚 Access", callback_data="main_access"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_branch_icon(name: str) -> str:
    """Return appropriate emoji icon for an engineering branch."""
    n = name.upper()
    if "AI" in n:
        return "🤖"
    elif "CSE" in n or "CS" in n:
        return "💻"
    elif "IT" in n:
        return "🌐"
    elif "ECE" in n or "ETC" in n:
        return "📡"
    elif "EEE" in n:
        return "⚡"
    elif "MECH" in n:
        return "⚙️"
    elif "CIVIL" in n:
        return "🏗️"
    return "🎓"


def get_branches_keyboard(
    branches: List[Branch],
    prefix: str = "branch",
    back_callback: Optional[str] = "back_to_main"
) -> InlineKeyboardMarkup:
    """Return inline keyboard listing engineering branches (CSE, CSE(AI), etc.)."""
    keyboard = []
    row = []
    for b in branches:
        icon = get_branch_icon(b.name)
        row.append(InlineKeyboardButton(f"{icon} {b.name}", callback_data=f"{prefix}_{b.name}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    if back_callback:
        keyboard.append([
            InlineKeyboardButton("⏪ Back to Main Menu", callback_data=back_callback)
        ])
    return InlineKeyboardMarkup(keyboard)


def get_semesters_for_branch_keyboard(
    branch: str,
    semesters: Optional[List[str]] = None,
    prefix: str = "sem",
    back_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Return semester buttons for a selected branch (e.g. 2-2, 3-1)."""
    if not semesters:
        semesters = ["2-2", "3-1"]
    keyboard = []
    row = []
    for sem in semesters:
        sem_clean = sem.strip()
        callback_data = f"{prefix}_{branch} {sem_clean}"
        row.append(InlineKeyboardButton(f"🎓 {sem_clean}", callback_data=callback_data))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    if back_callback:
        keyboard.append([
            InlineKeyboardButton("⏪ Back to Branches", callback_data=back_callback)
        ])
    return InlineKeyboardMarkup(keyboard)


def get_semester_keyboard(prefix: str = "sem", back_callback: Optional[str] = "back_to_main") -> InlineKeyboardMarkup:
    """Return semester selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🎓 CSE 2-2", callback_data=f"{prefix}_CSE 2-2"),
            InlineKeyboardButton("🎓 CSE 3-1", callback_data=f"{prefix}_CSE 3-1"),
        ]
    ]
    if back_callback:
        keyboard.append([
            InlineKeyboardButton("⏪ Back to Main Menu", callback_data=back_callback)
        ])
    return InlineKeyboardMarkup(keyboard)


def get_subjects_keyboard(
    subjects: List[Subject],
    prefix: str = "subj",
    back_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Return inline keyboard listing subjects for a semester in alphabetical order, plus PYQ section button."""
    sorted_subjects = sorted(subjects, key=lambda s: natural_sort_key(s.name))
    keyboard = []
    for subject in sorted_subjects:
        keyboard.append([
            InlineKeyboardButton(subject.name, callback_data=f"{prefix}_{subject.id}")
        ])
    keyboard.append([
        InlineKeyboardButton("📝 PYQ Papers", callback_data=f"{prefix}_pyq_all")
    ])
    if back_callback:
        keyboard.append([
            InlineKeyboardButton("⏪ Back", callback_data=back_callback)
        ])
    return InlineKeyboardMarkup(keyboard)


def get_resource_types_keyboard(
    prefix: str = "type",
    back_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Return resource type selection keyboard without PYQ (available at semester level)."""
    keyboard = [
        [
            InlineKeyboardButton("📒 Notes", callback_data=f"{prefix}_NOTES"),
            InlineKeyboardButton("📋 Assignments", callback_data=f"{prefix}_ASSIGNMENT"),
        ]
    ]
    if back_callback:
        keyboard.append([
            InlineKeyboardButton("⏪ Back", callback_data=back_callback)
        ])
    return InlineKeyboardMarkup(keyboard)


def get_resources_download_keyboard(
    resources: List[Resource],
    back_callback: Optional[str] = None,
    is_chief: bool = False,
    manage_prefix: str = "access_manage"
) -> InlineKeyboardMarkup:
    """Return keyboard with full-width download buttons in alphabetical order, plus bottom action row for Chief."""
    sorted_resources = sorted(resources, key=lambda r: natural_sort_key(r.title or ""))
    keyboard = []
    for res in sorted_resources:
        button_text = f"⬇️ {res.title}"
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"download_{res.id}")
        ])
    if is_chief and sorted_resources:
        keyboard.append([
            InlineKeyboardButton("✏️ Rename a File", callback_data=f"{manage_prefix}_rename"),
            InlineKeyboardButton("🗑️ Delete a File", callback_data=f"{manage_prefix}_delete")
        ])
    if back_callback:
        keyboard.append([
            InlineKeyboardButton("⏪ Back", callback_data=back_callback)
        ])
    return InlineKeyboardMarkup(keyboard)


def get_resources_manage_keyboard(
    resources: List[Resource],
    action: str,
    back_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Return keyboard listing resources full-width in alphabetical order for renaming or deleting."""
    sorted_resources = sorted(resources, key=lambda r: natural_sort_key(r.title or ""))
    keyboard = []
    for res in sorted_resources:
        if action == "rename":
            btn_text = f"✏️ {res.title}"
            cb = f"rename_{res.id}"
        else:
            btn_text = f"🗑️ {res.title}"
            cb = f"confirm_del_{res.id}"
        keyboard.append([
            InlineKeyboardButton(btn_text, callback_data=cb)
        ])
    if back_callback:
        keyboard.append([
            InlineKeyboardButton("⏪ Cancel", callback_data=back_callback)
        ])
    return InlineKeyboardMarkup(keyboard)


def get_confirm_delete_keyboard(resource_id: int, back_callback: Optional[str] = None) -> InlineKeyboardMarkup:
    """Return confirmation keyboard for deleting a resource."""
    keyboard = [
        [
            InlineKeyboardButton("🗑️ Yes, Delete", callback_data=f"do_delete_{resource_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=back_callback or "main_access")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_unavailable_keyboard(back_callback: Optional[str] = None) -> InlineKeyboardMarkup:
    """Return keyboard shown when source is unavailable."""
    keyboard = [
        [
            InlineKeyboardButton("📤 Upload", callback_data="start_upload_flow")
        ]
    ]
    if back_callback:
        keyboard.append([
            InlineKeyboardButton("⏪ Back", callback_data=back_callback)
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("⏪ Back to Main Menu", callback_data="back_to_main")
        ])
    return InlineKeyboardMarkup(keyboard)


def get_admin_review_keyboard(resource_id: int) -> InlineKeyboardMarkup:
    """Return Approve / Reject keyboard for Chief."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{resource_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{resource_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
