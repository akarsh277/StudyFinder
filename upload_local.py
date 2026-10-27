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
from database.crud import (
    create_resource,
    create_subject,
    create_branch,
    get_branch_by_name,
    add_semester_to_branch,
)

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

    allowed_exts = (".pdf", ".doc", ".docx")
    if not any(file_path.lower().endswith(ext) for ext in allowed_exts):
        print(f"Error: File '{file_path}' must be a PDF, DOC, or DOCX document (.pdf, .doc, .docx).", flush=True)
        return

    file_name = os.path.basename(file_path)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    resource_type = resource_type.upper()

    if not title:
        title = os.path.splitext(file_name)[0]

    if resource_type not in ["NOTES", "PYQ", "ASSIGNMENT"]:
        print("Error: --type must be one of: NOTES, PYQ, ASSIGNMENT", flush=True)
        return

    # Find matching subject in DB (or auto-create dynamically)
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
            print(f"Notice: Subject '{subject_name}' does not exist for {semester}. Auto-creating...", flush=True)
            subject = create_subject(db, name=subject_name, semester=semester)
            # Ensure branch and semester registered
            if " " in semester:
                b_name, sem_code = semester.rsplit(" ", 1)
                b_obj = get_branch_by_name(db, b_name)
                if not b_obj:
                    create_branch(db, name=b_name, semesters=sem_code)
                else:
                    add_semester_to_branch(db, b_name, sem_code)
            print(f"Auto-created subject '{subject.name}' for {semester} in database!", flush=True)

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
    if args.batch:
        if not os.path.exists(args.batch):
            print(f"Error: Batch directory not found: {args.batch}", flush=True)
            return

        subdirs = [os.path.join(args.batch, d) for d in os.listdir(args.batch) if os.path.isdir(os.path.join(args.batch, d))]
        if not subdirs:
            print(f"Error: No subject subfolders found inside '{args.batch}'.", flush=True)
            return

        print(f"Found {len(subdirs)} subject folder(s) in '{args.batch}'. Starting batch sync...", flush=True)
        total_uploaded = 0
        for subj_dir in sorted(subdirs):
            subj_name = os.path.basename(subj_dir)
            doc_files = [
                os.path.join(subj_dir, f) for f in os.listdir(subj_dir)
                if any(f.lower().endswith(ext) for ext in (".pdf", ".doc", ".docx"))
            ]
            if not doc_files:
                continue
            print(f"\n📂 Processing Subject: {subj_name} ({len(doc_files)} file(s))...", flush=True)
            for file_path in sorted(doc_files):
                await upload_local_file(
                    file_path=file_path,
                    semester=args.semester,
                    subject_name=subj_name,
                    resource_type=args.type,
                    title=None,
                    status=args.status
                )
                total_uploaded += 1
        print(f"\n🎉 Batch upload complete! Total {total_uploaded} files uploaded across {len(subdirs)} subjects.", flush=True)

    elif args.folder:
        if not os.path.exists(args.folder):
            print(f"Error: Folder not found: {args.folder}", flush=True)
            return

        pdf_files = [os.path.join(args.folder, f) for f in os.listdir(args.folder) if any(f.lower().endswith(ext) for ext in (".pdf", ".doc", ".docx"))]
        if not pdf_files:
            print(f"Error: No document files found in folder: {args.folder}", flush=True)
            return

        if not args.subject:
            print("Error: --subject is required when using --folder.", flush=True)
            return

        print(f"Found {len(pdf_files)} document file(s) in '{args.folder}'. Starting batch upload...", flush=True)
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
        if not args.subject:
            print("Error: --subject is required when using --file.", flush=True)
            return

        await upload_local_file(
            file_path=args.file,
            semester=args.semester,
            subject_name=args.subject,
            resource_type=args.type,
            title=args.title,
            status=args.status
        )
    else:
        print("Error: You must specify --file, --folder, or --batch.", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Upload local PDF/DOC files or full multi-subject folders to StudyFind")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a single local document file")
    group.add_argument("--folder", help="Path to a folder containing files for a single subject")
    group.add_argument("--batch", help="Path to a directory containing subfolders per subject (e.g. root/DBMS/*.pdf, root/OS/*.pdf)")

    parser.add_argument("--semester", required=True, help="Semester (e.g. 'CSE 2-2', 'CSE 3-1', 'CSE(AI) 3-1')")
    parser.add_argument("--subject", help="Subject name (e.g. DBMS, OS). Auto-inferred from folder name when using --batch.")
    parser.add_argument("--type", default="NOTES", choices=["NOTES", "PYQ", "ASSIGNMENT", "notes", "pyq", "assignment"], help="Resource type (default NOTES)")
    parser.add_argument("--title", help="Resource title (optional, defaults to filename without extension)")
    parser.add_argument("--status", default="APPROVED", choices=["APPROVED", "PENDING"], help="Status (default APPROVED)")

    args = parser.parse_args()

    asyncio.run(process_uploads(args))


if __name__ == "__main__":
    main()
