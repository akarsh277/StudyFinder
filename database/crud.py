import logging
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List, Optional, Dict, Any
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from database.models import User, Branch, Subject, Resource, UserEvent

logger = logging.getLogger(__name__)


def natural_sort_key(s: str) -> list:
    """
    Key for natural alphabetical sorting (A-Z, case-insensitive, with numbers ordered numerically).
    Produces clean Windows Explorer-like ordering (e.g., Unit 1, Unit 2 ... Unit 10).
    """
    if not s:
        return []
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def get_or_create_user(db: Session, telegram_id: int, username: Optional[str] = None, role: str = "STUDENT") -> User:
    """Retrieve user or create if not exists."""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id, username=username, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif username and user.username != username:
        user.username = username
        db.commit()
        db.refresh(user)
    return user


def get_subjects_by_semester(db: Session, semester: str) -> List[Subject]:
    """Retrieve all subjects for a specific semester in alphabetical order."""
    subjects = (
        db.query(Subject)
        .filter(Subject.semester == semester)
        .order_by(func.lower(Subject.name).asc(), Subject.id.asc())
        .all()
    )
    return sorted(subjects, key=lambda s: natural_sort_key(s.name))


def get_subject_by_id(db: Session, subject_id: int) -> Optional[Subject]:
    """Retrieve subject by ID."""
    return db.query(Subject).filter(Subject.id == subject_id).first()


def get_approved_resources(db: Session, semester: str, subject_id: int, resource_type: str) -> List[Resource]:
    """Retrieve approved resources matching semester, subject, and resource_type in alphabetical order."""
    resources = (
        db.query(Resource)
        .filter(
            Resource.semester == semester,
            Resource.subject_id == subject_id,
            Resource.resource_type == resource_type,
            Resource.status == "APPROVED"
        )
        .order_by(func.lower(Resource.title).asc(), Resource.id.asc())
        .all()
    )
    return sorted(resources, key=lambda r: natural_sort_key(r.title or ""))


def get_approved_semester_pyqs(db: Session, semester: str) -> List[Resource]:
    """Retrieve all approved PYQ resources for a specific semester regardless of subject in alphabetical order."""
    resources = (
        db.query(Resource)
        .filter(
            Resource.semester == semester,
            Resource.resource_type == "PYQ",
            Resource.status == "APPROVED"
        )
        .order_by(func.lower(Resource.title).asc(), Resource.id.asc())
        .all()
    )
    return sorted(resources, key=lambda r: natural_sort_key(r.title or ""))


def get_resource_by_id(db: Session, resource_id: int) -> Optional[Resource]:
    """Retrieve resource by ID."""
    return db.query(Resource).filter(Resource.id == resource_id).first()


def delete_resource(db: Session, resource_id: int) -> bool:
    """Delete a resource by ID from DB."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if resource:
        db.delete(resource)
        db.commit()
        return True
    return False


def check_duplicate_resource(
    db: Session,
    semester: str,
    subject_id: int,
    title: Optional[str] = None,
    file_name: Optional[str] = None
) -> Optional[Resource]:
    """
    Check if an active (APPROVED or PENDING) resource already exists
    with the same title or same file_name for the given subject and semester.
    """
    query = db.query(Resource).filter(
        Resource.semester == semester,
        Resource.subject_id == subject_id,
        Resource.status.in_(["APPROVED", "PENDING"])
    )

    conditions = []
    if title and title.strip():
        clean_title = title.strip().lower()
        conditions.append(func.lower(Resource.title) == clean_title)
    if file_name and file_name.strip():
        clean_file = file_name.strip().lower()
        conditions.append(func.lower(Resource.file_name) == clean_file)
        # Also check if title matches filename without extension
        base_name = os.path.splitext(clean_file)[0]
        conditions.append(func.lower(Resource.title) == base_name)

    if conditions:
        query = query.filter(or_(*conditions))
        return query.first()

    return None


def create_resource(
    db: Session,
    title: str,
    semester: str,
    subject_id: int,
    resource_type: str,
    file_id: str,
    file_name: Optional[str],
    uploaded_by: int,
    status: str = "PENDING"
) -> Resource:
    """Create a new resource submission."""
    resource = Resource(
        title=title,
        semester=semester,
        subject_id=subject_id,
        resource_type=resource_type,
        file_id=file_id,
        file_name=file_name,
        uploaded_by=uploaded_by,
        status=status
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


def update_resource_status(db: Session, resource_id: int, new_status: str) -> Optional[Resource]:
    """Update status of a resource if not already in final status."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if resource:
        resource.status = new_status
        db.commit()
        db.refresh(resource)
    return resource


def update_resource_title(db: Session, resource_id: int, new_title: str) -> Optional[Resource]:
    """Update title of a resource in DB."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if resource:
        resource.title = new_title
        db.commit()
        db.refresh(resource)
    return resource


def get_all_branches(db: Session) -> List[Branch]:
    """Retrieve all available branches ordered by id."""
    return db.query(Branch).order_by(Branch.id).all()


def get_branch_by_name(db: Session, name: str) -> Optional[Branch]:
    """Retrieve branch by name (case-insensitive)."""
    return db.query(Branch).filter(func.lower(Branch.name) == name.strip().lower()).first()


def create_branch(db: Session, name: str, semesters: str = "2-2,3-1") -> Branch:
    """Create a new engineering branch."""
    clean_name = name.strip()
    branch = Branch(name=clean_name, semesters=semesters.strip())
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch


def add_semester_to_branch(db: Session, branch_name: str, semester_code: str) -> Optional[Branch]:
    """Add a semester code (e.g. '3-2') to a branch's semesters list if not already present."""
    branch = get_branch_by_name(db, branch_name)
    if not branch:
        return None
    current_sems = [s.strip() for s in branch.semesters.split(",") if s.strip()]
    sem_clean = semester_code.strip()
    if sem_clean not in current_sems:
        current_sems.append(sem_clean)
        branch.semesters = ",".join(current_sems)
        db.commit()
        db.refresh(branch)
    return branch


def create_subject(db: Session, name: str, semester: str) -> Subject:
    """Dynamically create a new subject for a semester (e.g. 'ML' for 'CSE 3-1')."""
    clean_name = name.strip()
    clean_semester = semester.strip()
    existing = (
        db.query(Subject)
        .filter(func.lower(Subject.name) == clean_name.lower(), Subject.semester == clean_semester)
        .first()
    )
    if existing:
        return existing
    new_subj = Subject(name=clean_name, semester=clean_semester)
    db.add(new_subj)
    db.commit()
    db.refresh(new_subj)
    return new_subj


def get_all_subjects(db: Session) -> List[Subject]:
    """Retrieve all subjects ordered by semester, then id."""
    return db.query(Subject).order_by(Subject.semester, Subject.id).all()



def seed_initial_branches(db: Session) -> None:
    """Seed initial branches CSE and CSE(AI) if not present."""
    default_branches = [
        {"name": "CSE", "semesters": "2-2,3-1"},
        {"name": "CSE(AI)", "semesters": "2-2,3-1"},
    ]
    for b in default_branches:
        existing = db.query(Branch).filter(Branch.name == b["name"]).first()
        if not existing:
            db.add(Branch(name=b["name"], semesters=b["semesters"]))
    db.commit()


def seed_initial_subjects(db: Session) -> None:
    """Seed initial subjects for CSE 2-2, CSE 3-1, and CSE(AI) 3-1 if not already present."""
    initial_data = [
        # CSE 2-2
        {"name": "MEFA", "semester": "CSE 2-2"},
        {"name": "P&S", "semester": "CSE 2-2"},
        {"name": "DBMS", "semester": "CSE 2-2"},
        {"name": "OS", "semester": "CSE 2-2"},
        {"name": "SE", "semester": "CSE 2-2"},
        # CSE 3-1
        {"name": "DWDM", "semester": "CSE 3-1"},
        {"name": "FLAT", "semester": "CSE 3-1"},
        {"name": "CN", "semester": "CSE 3-1"},
        {"name": "EPS", "semester": "CSE 3-1"},
        # CSE(AI) 3-1
        {"name": "OS", "semester": "CSE(AI) 3-1"},
        {"name": "CN", "semester": "CSE(AI) 3-1"},
    ]

    for item in initial_data:
        existing = (
            db.query(Subject)
            .filter(Subject.name == item["name"], Subject.semester == item["semester"])
            .first()
        )
        if not existing:
            db.add(Subject(name=item["name"], semester=item["semester"]))
    db.commit()


def copy_os_resources_to_cse_ai(db: Session) -> int:
    """Copy all existing OS resources from CSE 2-2 to CSE(AI) 3-1."""
    # Ensure target subject exists
    target_subject = (
        db.query(Subject)
        .filter(Subject.name == "OS", Subject.semester == "CSE(AI) 3-1")
        .first()
    )
    if not target_subject:
        target_subject = Subject(name="OS", semester="CSE(AI) 3-1")
        db.add(target_subject)
        db.commit()
        db.refresh(target_subject)

    source_subject = (
        db.query(Subject)
        .filter(Subject.name == "OS", Subject.semester == "CSE 2-2")
        .first()
    )
    if not source_subject:
        return 0

    source_resources = (
        db.query(Resource)
        .filter(Resource.subject_id == source_subject.id, Resource.status == "APPROVED")
        .all()
    )

    copied_count = 0
    for res in source_resources:
        already_exists = (
            db.query(Resource)
            .filter(
                Resource.semester == "CSE(AI) 3-1",
                Resource.subject_id == target_subject.id,
                Resource.title == res.title,
                Resource.file_id == res.file_id,
            )
            .first()
        )
        if not already_exists:
            new_res = Resource(
                title=res.title,
                semester="CSE(AI) 3-1",
                subject_id=target_subject.id,
                resource_type=res.resource_type,
                file_id=res.file_id,
                file_name=res.file_name,
                uploaded_by=res.uploaded_by,
                status="APPROVED",
                download_count=0,
                created_at=datetime.utcnow(),
            )
            db.add(new_res)
            copied_count += 1

    if copied_count > 0:
        db.commit()
        logger.info(f"Copied {copied_count} OS resources to CSE(AI) 3-1")
    return copied_count


def copy_cn_resources_to_cse_ai(db: Session) -> int:
    """Copy all existing CN resources from CSE 3-1 to CSE(AI) 3-1."""
    # Ensure target subject exists
    target_subject = (
        db.query(Subject)
        .filter(Subject.name == "CN", Subject.semester == "CSE(AI) 3-1")
        .first()
    )
    if not target_subject:
        target_subject = Subject(name="CN", semester="CSE(AI) 3-1")
        db.add(target_subject)
        db.commit()
        db.refresh(target_subject)

    source_subject = (
        db.query(Subject)
        .filter(Subject.name == "CN", Subject.semester == "CSE 3-1")
        .first()
    )
    if not source_subject:
        return 0

    source_resources = (
        db.query(Resource)
        .filter(Resource.subject_id == source_subject.id, Resource.status == "APPROVED")
        .all()
    )

    copied_count = 0
    for res in source_resources:
        already_exists = (
            db.query(Resource)
            .filter(
                Resource.semester == "CSE(AI) 3-1",
                Resource.subject_id == target_subject.id,
                Resource.title == res.title,
                Resource.file_id == res.file_id,
            )
            .first()
        )
        if not already_exists:
            new_res = Resource(
                title=res.title,
                semester="CSE(AI) 3-1",
                subject_id=target_subject.id,
                resource_type=res.resource_type,
                file_id=res.file_id,
                file_name=res.file_name,
                uploaded_by=res.uploaded_by,
                status="APPROVED",
                download_count=0,
                created_at=datetime.utcnow(),
            )
            db.add(new_res)
            copied_count += 1

    if copied_count > 0:
        db.commit()
        logger.info(f"Copied {copied_count} CN resources to CSE(AI) 3-1")
    return copied_count


def get_resources_uploaded_today(db: Session) -> List[Resource]:
    """Retrieve all approved resources created today in IST timezone."""
    ist = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(ist)
    start_ist = datetime(now_ist.year, now_ist.month, now_ist.day, 0, 0, 0, tzinfo=ist)
    end_ist = datetime(now_ist.year, now_ist.month, now_ist.day, 23, 59, 59, tzinfo=ist)
    start_utc = start_ist.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_ist.astimezone(timezone.utc).replace(tzinfo=None)

    return (
        db.query(Resource)
        .filter(
            Resource.status == "APPROVED",
            Resource.created_at >= start_utc,
            Resource.created_at <= end_utc,
        )
        .order_by(Resource.semester, Resource.subject_id, Resource.created_at.asc())
        .all()
    )



def log_user_event(db: Session, telegram_id: int, event_type: str, details: Optional[str] = None) -> None:
    """Log a user interaction event for analytics."""
    try:
        event = UserEvent(telegram_id=telegram_id, event_type=event_type, details=details)
        db.add(event)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to log user event: {e}")


def increment_resource_download(db: Session, resource_id: int) -> None:
    """Increment download_count for a resource upon successful delivery."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if resource:
        resource.download_count = (resource.download_count or 0) + 1
        db.commit()


def get_analytics_data(db: Session) -> Dict[str, Any]:
    """Calculate accurate StudyFind analytics metrics directly from database using SQL aggregations."""
    ist = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(ist)
    start_today_ist = datetime(now_ist.year, now_ist.month, now_ist.day, 0, 0, 0, tzinfo=ist)
    start_today_utc = start_today_ist.astimezone(timezone.utc).replace(tzinfo=None)
    seven_days_ago_utc = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)

    # Total Registered Students
    total_users = db.query(func.count(User.id)).scalar() or 0

    # Active This Week (Unique students with activity in last 7 days)
    active_this_week = (
        db.query(func.count(func.distinct(UserEvent.telegram_id)))
        .filter(UserEvent.created_at >= seven_days_ago_utc)
        .scalar() or 0
    )

    # Bounce Rate (% of visitors with only 1 event total)
    total_visitors = db.query(func.count(func.distinct(UserEvent.telegram_id))).scalar() or total_users or 1
    single_event_users = (
        db.query(UserEvent.telegram_id)
        .group_by(UserEvent.telegram_id)
        .having(func.count(UserEvent.id) == 1)
        .count()
    )
    bounce_rate = round((single_event_users / total_visitors) * 100) if total_visitors > 0 else 0

    # Downloads
    today_downloads = (
        db.query(func.count(UserEvent.id))
        .filter(UserEvent.event_type == "DOWNLOAD", UserEvent.created_at >= start_today_utc)
        .scalar() or 0
    )
    week_downloads = (
        db.query(func.count(UserEvent.id))
        .filter(UserEvent.event_type == "DOWNLOAD", UserEvent.created_at >= seven_days_ago_utc)
        .scalar() or 0
    )
    res_downloads_sum = db.query(func.coalesce(func.sum(Resource.download_count), 0)).scalar() or 0
    event_downloads_count = db.query(func.count(UserEvent.id)).filter(UserEvent.event_type == "DOWNLOAD").scalar() or 0
    all_time_downloads = max(res_downloads_sum, event_downloads_count)

    # Peak Day (Day with highest downloads in history)
    date_col = func.date(UserEvent.created_at)
    peak_row = (
        db.query(
            date_col.label("p_date"),
            func.count(func.distinct(UserEvent.telegram_id)).label("users"),
            func.count(UserEvent.id).label("downloads")
        )
        .filter(UserEvent.event_type == "DOWNLOAD")
        .group_by(date_col)
        .order_by(func.count(UserEvent.id).desc())
        .first()
    )
    if peak_row:
        p_dt = peak_row.p_date
        if isinstance(p_dt, str):
            p_dt = datetime.strptime(p_dt, "%Y-%m-%d").date()
        peak_day_str = p_dt.strftime("%d %b")
        peak_day_users = peak_row.users
        peak_day_downloads = peak_row.downloads
    else:
        peak_day_str = "N/A"
        peak_day_users = 0
        peak_day_downloads = 0

    # Top Subjects (Top 5 subjects grouped by name)
    top_subjects_query = (
        db.query(Subject.name, func.coalesce(func.sum(Resource.download_count), 0).label("dls"))
        .join(Resource, Subject.id == Resource.subject_id)
        .filter(Resource.status == "APPROVED")
        .group_by(Subject.name)
        .order_by(func.sum(Resource.download_count).desc(), Subject.name.asc())
        .limit(5)
        .all()
    )
    top_subjects = [
        {"name": r[0], "downloads": r[1]}
        for r in top_subjects_query if r[1] > 0
    ]

    # Top Resources (Top 5 individual resources by download count)
    top_resources_query = (
        db.query(Resource.title, Resource.download_count)
        .filter(Resource.status == "APPROVED", Resource.download_count > 0)
        .order_by(Resource.download_count.desc(), Resource.id.asc())
        .limit(5)
        .all()
    )
    top_resources = [
        {"title": r.title, "downloads": r.download_count or 0}
        for r in top_resources_query
    ]

    return {
        "total_users": total_users,
        "active_this_week": active_this_week,
        "bounce_rate": bounce_rate,
        "today_downloads": today_downloads,
        "week_downloads": week_downloads,
        "all_time_downloads": all_time_downloads,
        "peak_day_str": peak_day_str,
        "peak_day_users": peak_day_users,
        "peak_day_downloads": peak_day_downloads,
        "top_subjects": top_subjects,
        "top_resources": top_resources,
    }

