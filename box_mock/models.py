"""Database models for Box Mock API using plain SQLAlchemy."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class Base(DeclarativeBase):
    """Base class for all models."""


class User(Base):
    """Box app user."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    login = Column(String(255), nullable=True)
    is_platform_access_only = Column(Boolean, default=False)
    job_title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert user to dictionary representation."""
        return {
            "type": "user",
            "id": self.id,
            "name": self.name,
            "login": self.login,
            "email": self.email,
            "is_platform_access_only": self.is_platform_access_only,
            "job_title": self.job_title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Folder(Base):
    """Box folder. Root folder has id='0' and parent_id=None."""

    __tablename__ = "folders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_id = Column(String(36), ForeignKey("folders.id"), nullable=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    parent = relationship(
        "Folder",
        remote_side=[id],
        back_populates="children",
    )
    children = relationship(
        "Folder",
        back_populates="parent",
    )
    files = relationship(
        "File",
        back_populates="folder",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert folder to dictionary representation."""
        return {
            "type": "folder",
            "id": self.id,
            "name": self.name,
            "parent": {"type": "folder", "id": self.parent_id}
            if self.parent_id
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class File(Base):
    """Box file. Content stored on filesystem at data/{identity}/files/{id}."""

    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    folder_id = Column(String(36), ForeignKey("folders.id"), nullable=False)
    name = Column(String(255), nullable=False)
    version = Column(Integer, default=1)
    size = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    folder = relationship("Folder", back_populates="files")

    def to_dict(self) -> dict[str, Any]:
        """Convert file to dictionary representation."""
        return {
            "type": "file",
            "id": self.id,
            "name": self.name,
            "size": self.size,
            "parent": {"type": "folder", "id": self.folder_id},
            "file_version": {
                "id": f"{self.id}_v{self.version}",
                "version_number": self.version,
            },
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SignRequest(Base):
    """Box Sign request. Stores signers/files as JSON for simplicity."""

    __tablename__ = "sign_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String(50), default="created")
    parent_folder_id = Column(String(36), nullable=True)
    redirect_url = Column(String(1024), nullable=True)
    signers_json = Column(Text, nullable=True)
    files_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert sign request to dictionary representation."""
        signers = json.loads(self.signers_json) if self.signers_json else []
        files = json.loads(self.files_json) if self.files_json else []
        return {
            "type": "sign-request",
            "id": self.id,
            "status": self.status,
            "signers": signers,
            "sign_files": {"files": files},
            "parent_folder": {"type": "folder", "id": self.parent_folder_id}
            if self.parent_folder_id
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def get_session() -> Session:
    """Get the current database session from flask.g."""
    from box_mock.db import db  # noqa: PLC0415

    return db.session
