from typing import List, Optional
# pyrefly: ignore [missing-import]
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.models import Subject, Resource

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Return main menu buttons below start message."""
    keyboard = [
        [
            InlineKeyboardButton("📤 Upload Resource", callback_data="main_upload"),
            InlineKeyboardButton("📚 Access Resources", callback_data="main_access"),
        ]
    ]
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
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data=back_callback)
        ])
    return InlineKeyboardMarkup(keyboard)


def get_subjects_keyboard(
    subjects: List[Subject],
    prefix: str = "subj",
    back_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Return inline keyboard listing subjects for a semester."""
    keyboard = []
    for subject in subjects:
        keyboard.append([
            InlineKeyboardButton(subject.name, callback_data=f"{prefix}_{subject.id}")
        ])
    if back_callback:
        keyboard.append([
            InlineKeyboardButton("🔙 Back", callback_data=back_callback)
        ])
    return InlineKeyboardMarkup(keyboard)


def get_resource_types_keyboard(
    prefix: str = "type",
    back_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Return resource type selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📒 Notes", callback_data=f"{prefix}_NOTES"),
            InlineKeyboardButton("📝 PYQs", callback_data=f"{prefix}_PYQ"),
            InlineKeyboardButton("📋 Assignments", callback_data=f"{prefix}_ASSIGNMENT"),
        ]
    ]
    if back_callback:
        keyboard.append([
            InlineKeyboardButton("🔙 Back", callback_data=back_callback)
        ])
    return InlineKeyboardMarkup(keyboard)


def get_resources_download_keyboard(
    resources: List[Resource],
    back_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Return keyboard with individual download buttons for available resources."""
    keyboard = []
    for res in resources:
        button_text = f"⬇️ {res.title}"
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"download_{res.id}")
        ])
    if back_callback:
        keyboard.append([
            InlineKeyboardButton("🔙 Back", callback_data=back_callback)
        ])
    return InlineKeyboardMarkup(keyboard)


def get_unavailable_keyboard(back_callback: Optional[str] = None) -> InlineKeyboardMarkup:
    """Return keyboard shown when source is unavailable."""
    keyboard = [
        [
            InlineKeyboardButton("📤 Upload Resource", callback_data="start_upload_flow")
        ]
    ]
    if back_callback:
        keyboard.append([
            InlineKeyboardButton("🔙 Back", callback_data=back_callback)
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
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
