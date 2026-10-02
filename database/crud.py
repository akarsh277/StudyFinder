import logging
from typing import List, Optional
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
