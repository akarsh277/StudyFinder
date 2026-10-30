import logging
from collections import defaultdict
from datetime import datetime, date, timezone
from typing import Optional
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes
from config import CHIEF_TELEGRAM_ID
from database.connection import get_db
from database.models import User, Subject, Resource
from database.crud import get_resources_uploaded_today, natural_sort_key

logger = logging.getLogger(__name__)


def build_daily_digest_message(db, target_date: Optional[date] = None) -> Optional[str]:
    """Build formatted digest message for resources uploaded on a given date (IST) in alphabetical order."""
    ist = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(ist)
    ref_date = target_date or now_ist.date()

    start_ist = datetime(ref_date.year, ref_date.month, ref_date.day, 0, 0, 0, tzinfo=ist)
    end_ist = datetime(ref_date.year, ref_date.month, ref_date.day, 23, 59, 59, tzinfo=ist)
    start_utc = start_ist.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_ist.astimezone(timezone.utc).replace(tzinfo=None)

    resources = (
        db.query(Resource)
        .filter(
            Resource.status == "APPROVED",
            Resource.created_at >= start_utc,
            Resource.created_at <= end_utc,
        )
        .all()
    )

    if not resources:
        return None

    # Load subjects mapping
    subj_ids = {r.subject_id for r in resources}
    subjects = {s.id: s.name for s in db.query(Subject).filter(Subject.id.in_(subj_ids)).all()} if subj_ids else {}

    # Sort resources naturally by semester, subject name, and title
    sorted_resources = sorted(
        resources,
        key=lambda r: (
            r.semester.lower(),
            subjects.get(r.subject_id, "").lower(),
            natural_sort_key(r.title or "")
        )
    )

    date_str = ref_date.strftime("%d %b %Y")
    lines = [
        f"📢 Daily Resource Digest — {date_str}",
        "",
        "Here are the new study resources added today:",
        ""
    ]

    # Group by semester
    grouped = defaultdict(list)
    for r in sorted_resources:
        subj_name = subjects.get(r.subject_id, "Subject")
        type_str = r.resource_type.capitalize()
        grouped[r.semester].append(f"• {subj_name}: {r.title} ({type_str})")

    for semester, items in grouped.items():
        lines.append(f"🎓 {semester}:")
        lines.extend(items)
        lines.append("")

    lines.append("💡 Tap /start to open StudyFind and download!")
    return "\n".join(lines).strip()


async def send_daily_digest_job(context: ContextTypes.DEFAULT_TYPE) -> int:
    """Scheduled job called at the end of the day (22:00 IST) to notify students of new resources."""
    logger.info("Executing scheduled end-of-day resource digest job...")
    try:
        with get_db() as db:
            digest_text = build_daily_digest_message(db)
            if not digest_text:
                logger.info("No new resources uploaded today. Skipping daily digest.")
                return 0

            users = db.query(User).all()
            user_ids = [u.telegram_id for u in users if u.telegram_id]

        sent_count = 0
        for uid in user_ids:
            try:
                await context.bot.send_message(chat_id=uid, text=digest_text)
                sent_count += 1
            except Exception as e:
                logger.debug(f"Could not send daily digest to {uid}: {e}")

        logger.info(f"Daily digest successfully sent to {sent_count}/{len(user_ids)} users.")
        return sent_count
    except Exception as e:
        logger.error(f"Error executing daily digest job: {e}")
        return 0


async def daily_digest_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow Chief to preview today's digest or broadcast it immediately with /daily_digest."""
    user = update.effective_user
    if not user or CHIEF_TELEGRAM_ID == 0 or user.id != CHIEF_TELEGRAM_ID:
        if update.message:
            await update.message.reply_text("⛔ Unauthorized: Only the Chief can manage daily notifications.")
        return

    args = context.args or []
    broadcast = "send" in args or "broadcast" in args

    try:
        with get_db() as db:
            digest_text = build_daily_digest_message(db)
            if not digest_text:
                await update.message.reply_text("ℹ️ No new resources were uploaded today.")
                return

            if broadcast:
                users = db.query(User).all()
                user_ids = [u.telegram_id for u in users if u.telegram_id]
                sent_count = 0
                for uid in user_ids:
                    try:
                        await context.bot.send_message(chat_id=uid, text=digest_text)
                        sent_count += 1
                    except Exception as e:
                        logger.debug(f"Could not send digest to {uid}: {e}")
                await update.message.reply_text(
                    f"✅ Daily digest broadcasted to {sent_count}/{len(user_ids)} users!\n\n"
                    f"Preview:\n\n{digest_text}"
                )
            else:
                await update.message.reply_text(
                    f"📋 Today's Daily Digest Preview:\n\n{digest_text}\n\n"
                    f"To broadcast now to all students, send:\n/daily_digest send"
                )
    except Exception as e:
        logger.error(f"Error in daily_digest_command_handler: {e}")
        if update.message:
            await update.message.reply_text(f"⚠️ Error preparing daily digest: {e}")
