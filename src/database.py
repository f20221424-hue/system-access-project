"""SQLAlchemy ORM models and database session management."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_PATH = DATABASE_DIR / "access_governance.db"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(20), primary_key=True)
    employee_name = Column(String(100), nullable=False)
    department = Column(String(50), nullable=False)
    location = Column(String(50), nullable=False)
    manager = Column(String(100), nullable=False)
    current_role = Column(String(80), nullable=False)
    employment_status = Column(String(20), nullable=False, default="Active")

    access_requests = relationship("AccessRequest", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    exceptions = relationship("Exception", back_populates="user")


class ApprovedRole(Base):
    __tablename__ = "approved_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String(80), nullable=False, unique=True)
    allowed_systems = Column(Text, nullable=False)


class AccessRequest(Base):
    __tablename__ = "access_requests"

    request_id = Column(String(20), primary_key=True)
    user_id = Column(String(20), ForeignKey("users.user_id"), nullable=False)
    requested_system = Column(String(80), nullable=False)
    request_date = Column(Date, nullable=False)
    approval_status = Column(String(20), nullable=False)
    closure_status = Column(String(20), nullable=False)

    user = relationship("User", back_populates="access_requests")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.user_id"), nullable=True)
    event_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    description = Column(Text, nullable=False)

    user = relationship("User", back_populates="audit_logs")


class Exception(Base):
    __tablename__ = "exceptions"

    exception_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.user_id"), nullable=False)
    user_name = Column(String(100), nullable=False)
    issue_type = Column(String(80), nullable=False)
    severity = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="exceptions")


def get_engine(db_path: Path | None = None):
    path = db_path or DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", echo=False)


def get_session_factory(engine=None) -> sessionmaker[Session]:
    engine = engine or get_engine()
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_database(engine=None) -> None:
    engine = engine or get_engine()
    Base.metadata.create_all(engine)


def clear_operational_tables(session: Session) -> None:
    """Remove derived data before a fresh pipeline run."""
    session.query(Exception).delete()
    session.query(AuditLog).delete()
    session.commit()
