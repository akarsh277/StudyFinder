import argparse
import asyncio
import os
import sys
import logging

project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from telegram import Bot
from telegram.request import HTTPXRequest
from config import BOT_TOKEN, CHIEF_TELEGRAM_ID
from database.connection import get_db
from database.models import Subject, User
from database.crud import create_resource

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def upload_local_file(
    file_path: str,
    semester: str,
    subject_name: str,
    resource_type: str,
    title: str = None,
    status: str = "APPROVED"
):
    if not os.path.exists(file_path):
        print(f"Error: File not found at path: {file_path}", flush=True)
        return

    if not file_path.lower().endswith(".pdf"):
        print(f"Error: File '{file_path}' must be a PDF (.pdf).", flush=True)
        return

    file_name = os.path.basename(file_path)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    resource_type = resource_type.upper()

    if not title:
        title = os.path.splitext(file_name)[0]

    if resource_type not in ["NOTES", "PYQ", "ASSIGNMENT"]:
        print("Error: --type must be one of: NOTES, PYQ, ASSIGNMENT", flush=True)
        return

    # Find matching subject in DB
    with get_db() as db:
        subject = (
            db.query(Subject)
            .filter(Subject.semester == semester, Subject.name.ilike(subject_name))
            .first()
        )
        if not subject:
            subject = (
                db.query(Subject)
                .filter(Subject.semester == semester, Subject.name.ilike(f"%{subject_name}%"))
                .first()
            )

        if not subject:
            available_subjects = db.query(Subject).filter(Subject.semester == semester).all()
            avail_names = [s.name for s in available_subjects]
            print(f"Error: Subject '{subject_name}' not found for {semester}.", flush=True)
            print(f"Available subjects for {semester}: {', '.join(avail_names)}", flush=True)
            return

        subject_id = subject.id
        subject_official_name = subject.name

        # Determine target chat ID to send document to on Telegram
        latest_user = db.query(User).order_by(User.id.desc()).first()
        if latest_user:
            target_chat_id = latest_user.telegram_id
        elif CHIEF_TELEGRAM_ID != 0 and CHIEF_TELEGRAM_ID != 123456789:
            target_chat_id = CHIEF_TELEGRAM_ID
        else:
            print("Error: No registered Telegram users found in database.", flush=True)
            print("Please open @HighlessbestBot in Telegram and send /start first!", flush=True)
            return

    print(f"\nUploading '{file_name}' ({file_size_mb:.2f} MB) to Telegram server...", flush=True)

    # Set generous HTTP timeouts (5 mins write/read timeout for large files)
    request = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=300.0,
        write_timeout=300.0,
        pool_timeout=60.0
    )

    try:
        async with Bot(token=BOT_TOKEN, request=request) as bot:
            with open(file_path, "rb") as f:
                msg = await bot.send_document(
                    chat_id=target_chat_id,
                    document=f,
                    caption=f"📄 Admin Upload: {title}\nSemester: {semester} | Subject: {subject_official_name}",
                    read_timeout=300.0,
                    write_timeout=300.0,
                    connect_timeout=60.0
                )
            file_id = msg.document.file_id
            print(f"Success: Telegram File ID obtained: {file_id[:25]}...", flush=True)
    except Exception as e:
        print(f"Error: Failed to upload document to Telegram: {e}", flush=True)
        print("Make sure you have sent /start to @HighlessbestBot in Telegram first!", flush=True)
        return

    # Store in database
    with get_db() as db:
        res = create_resource(
            db=db,
            title=title,
            semester=semester,
            subject_id=subject_id,
            resource_type=resource_type,
            file_id=file_id,
            file_name=file_name,
            uploaded_by=target_chat_id,
            status=status
        )
        print(f"Resource successfully registered in DB!", flush=True)
        print(f"   ID: {res.id} | Title: '{res.title}' | Subject: {subject_official_name} | Type: {res.resource_type}", flush=True)


async def process_uploads(args):
    if args.folder:
        if not os.path.exists(args.folder):
            print(f"Error: Folder not found: {args.folder}", flush=True)
            return

        pdf_files = [os.path.join(args.folder, f) for f in os.listdir(args.folder) if f.lower().endswith(".pdf")]
        if not pdf_files:
            print(f"Error: No PDF files found in folder: {args.folder}", flush=True)
            return

        print(f"Found {len(pdf_files)} PDF file(s) in '{args.folder}'. Starting batch upload...", flush=True)
        for pdf_path in sorted(pdf_files):
            custom_title = args.title if (len(pdf_files) == 1 and args.title) else None
            await upload_local_file(
                file_path=pdf_path,
                semester=args.semester,
                subject_name=args.subject,
                resource_type=args.type,
                title=custom_title,
                status=args.status
            )
        print(f"\n🎉 All {len(pdf_files)} file(s) uploaded and registered successfully!", flush=True)

    elif args.file:
        await upload_local_file(
            file_path=args.file,
            semester=args.semester,
            subject_name=args.subject,
            resource_type=args.type,
            title=args.title,
            status=args.status
        )
    else:
        print("Error: You must specify either --file or --folder.", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Upload local PDF files/folders to StudyFind Telegram Bot")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a single local PDF file")
    group.add_argument("--folder", help="Path to a folder containing multiple PDF files")

    parser.add_argument("--semester", required=True, choices=["CSE 2-2", "CSE 3-1"], help="Semester (CSE 2-2 or CSE 3-1)")
    parser.add_argument("--subject", required=True, help="Subject name (e.g. DBMS, MEFA, DWDM, OS, etc.)")
    parser.add_argument("--type", required=True, choices=["NOTES", "PYQ", "ASSIGNMENT", "notes", "pyq", "assignment"], help="Resource type")
    parser.add_argument("--title", help="Resource title (optional for folder uploads, defaults to filename)")
    parser.add_argument("--status", default="APPROVED", choices=["APPROVED", "PENDING"], help="Status (default APPROVED)")

    args = parser.parse_args()

    asyncio.run(process_uploads(args))


if __name__ == "__main__":
    main()
