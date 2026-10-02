import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from database.models import User, Subject, Resource

logger = logging.getLogger(__name__)

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
    """Retrieve all subjects for a specific semester."""
    return db.query(Subject).filter(Subject.semester == semester).order_by(Subject.id).all()


def get_subject_by_id(db: Session, subject_id: int) -> Optional[Subject]:
    """Retrieve subject by ID."""
    return db.query(Subject).filter(Subject.id == subject_id).first()


def get_approved_resources(db: Session, semester: str, subject_id: int, resource_type: str) -> List[Resource]:
    """Retrieve approved resources matching semester, subject, and resource_type."""
    return (
        db.query(Resource)
        .filter(
            Resource.semester == semester,
            Resource.subject_id == subject_id,
            Resource.resource_type == resource_type,
            Resource.status == "APPROVED"
        )
        .order_by(Resource.created_at.desc())
        .all()
    )


def get_resource_by_id(db: Session, resource_id: int) -> Optional[Resource]:
    """Retrieve resource by ID."""
    return db.query(Resource).filter(Resource.id == resource_id).first()


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


def seed_initial_subjects(db: Session) -> None:
    """Seed initial subjects for CSE 2-2 and CSE 3-1 if not already present."""
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


def increment_resource_download(db: Session, resource_id: int) -> None:
    """Increment download_count for a resource upon successful delivery."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if resource:
        resource.download_count = (resource.download_count or 0) + 1
        db.commit()


def get_analytics_data(db: Session) -> Dict[str, Any]:
    """Calculate all StudyFind analytics metrics directly from the database using SQL aggregations."""
    now = datetime.utcnow()
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = now - timedelta(days=7)

    # User statistics
    total_users = db.query(func.count(User.id)).scalar() or 0
    users_today = db.query(func.count(User.id)).filter(User.created_at >= start_of_today).scalar() or 0
    users_week = db.query(func.count(User.id)).filter(User.created_at >= seven_days_ago).scalar() or 0

    # Resource statistics
    total_resources = db.query(func.count(Resource.id)).scalar() or 0
    approved_resources = db.query(func.count(Resource.id)).filter(Resource.status == "APPROVED").scalar() or 0
    pending_resources = db.query(func.count(Resource.id)).filter(Resource.status == "PENDING").scalar() or 0
    rejected_resources = db.query(func.count(Resource.id)).filter(Resource.status == "REJECTED").scalar() or 0

    # Total downloads
    total_downloads = db.query(func.coalesce(func.sum(Resource.download_count), 0)).scalar() or 0

    # Top resources (Top 5 approved resources ordered by download_count desc)
    top_resources_query = (
        db.query(Resource.title, Resource.download_count)
        .filter(Resource.status == "APPROVED")
        .order_by(Resource.download_count.desc(), Resource.id.asc())
        .limit(5)
        .all()
    )
    top_resources = [
        {"title": r.title, "downloads": r.download_count or 0}
        for r in top_resources_query
    ]

    # Top subjects (Top 5 subjects ordered by sum of downloads of their approved resources desc)
    top_subjects_query = (
        db.query(Subject.name, func.coalesce(func.sum(Resource.download_count), 0).label("total_downloads"))
        .join(Resource, Subject.id == Resource.subject_id)
        .filter(Resource.status == "APPROVED")
        .group_by(Subject.id, Subject.name)
        .order_by(func.sum(Resource.download_count).desc(), Subject.name.asc())
        .limit(5)
        .all()
    )
    top_subjects = [
        {"name": s.name, "downloads": s.total_downloads or 0}
        for s in top_subjects_query
    ]

    return {
        "total_users": total_users,
        "users_today": users_today,
        "users_week": users_week,
        "total_resources": total_resources,
        "approved_resources": approved_resources,
        "pending_resources": pending_resources,
        "rejected_resources": rejected_resources,
        "total_downloads": total_downloads,
        "top_resources": top_resources,
        "top_subjects": top_subjects,
    }

