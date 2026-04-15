"""Database models for Box Mock API using plain SQLAlchemy."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class Base(DeclarativeBase):
    """Base class for all models."""


def box_time(value: datetime | None) -> str | None:
    """Return a Box/rclone-friendly RFC3339 timestamp."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def owner_dict() -> dict[str, str]:
    """Return a minimal fake owner block for Box item responses."""
    return {
        "type": "user",
        "id": "boxmock",
        "name": "Box Mock Service",
        "login": "service@boxmock.local",
    }


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
            "created_at": box_time(self.created_at),
        }


class Folder(Base):
    """Box folder. Root folder has id='0' and parent_id=None."""

    __tablename__ = "folders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_id = Column(String(36), ForeignKey("folders.id"), nullable=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

    def get_path_collection(self) -> list[dict[str, Any]]:
        """
        Return the ancestor chain from root down to
        (but not including) this folder.
        """
        ancestors: list[dict[str, Any]] = []
        node = self.parent
        while node is not None:
            ancestors.append({"type": "folder", "id": node.id, "name": node.name})
            node = node.parent
        ancestors.reverse()
        return ancestors

    def to_dict(self) -> dict[str, Any]:
        """Convert folder to dictionary representation."""
        return {
            "type": "folder",
            "id": self.id,
            "sequence_id": "0",
            "etag": self.id,
            "sha1": "",
            "name": self.name,
            "size": 0,
            "parent": {"type": "folder", "id": self.parent_id}
            if self.parent_id
            else None,
            "created_at": box_time(self.created_at),
            "modified_at": box_time(self.modified_at or self.created_at),
            "content_created_at": box_time(self.created_at),
            "content_modified_at": box_time(self.modified_at or self.created_at),
            "item_status": "active",
            "owned_by": owner_dict(),
        }

    def to_full_dict(
        self,
        limit: int = 100,
        offset: int = 0,
        sort: str = "name",
        direction: str = "asc",
    ) -> dict[str, Any]:
        """
        Return a full folder representation including item_collection
        and path_collection.

        This is the shape expected by the Box UI Elements picker.
        """
        children: list[dict[str, Any]] = [c.to_dict() for c in self.children]
        children.extend(f.to_dict() for f in self.files)

        reverse = direction.lower() == "desc"
        if sort == "name":
            children.sort(key=lambda x: (x.get("name") or "").lower(), reverse=reverse)
        elif sort == "date":
            children.sort(key=lambda x: x.get("created_at") or "", reverse=reverse)
        elif sort == "size":
            children.sort(key=lambda x: x.get("size") or 0, reverse=reverse)

        total = len(children)
        page = children[offset : offset + limit]

        path_entries = self.get_path_collection()

        return {
            "type": "folder",
            "id": self.id,
            "name": self.name,
            "parent": {"type": "folder", "id": self.parent_id}
            if self.parent_id
            else None,
            "created_at": box_time(self.created_at),
            "modified_at": box_time(self.modified_at or self.created_at),
            "content_created_at": box_time(self.created_at),
            "content_modified_at": box_time(self.modified_at or self.created_at),
            "sequence_id": "0",
            "etag": self.id,
            "sha1": "",
            "item_status": "active",
            "owned_by": owner_dict(),
            "permissions": {
                "can_download": True,
                "can_upload": True,
                "can_rename": True,
                "can_delete": True,
                "can_share": True,
                "can_set_share_access": False,
                "can_invite_collaborator": False,
            },
            "path_collection": {
                "total_count": len(path_entries),
                "entries": path_entries,
            },
            "item_collection": {
                "total_count": total,
                "limit": limit,
                "offset": offset,
                "entries": page,
            },
            "has_collaborations": False,
            "is_externally_owned": False,
            "is_download_available": True,
            "size": 0,
        }


class File(Base):
    """Box file. Content stored on filesystem at data/{identity}/files/{id}."""

    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    folder_id = Column(String(36), ForeignKey("folders.id"), nullable=False)
    name = Column(String(255), nullable=False)
    version = Column(Integer, default=1)
    size = Column(Integer, default=0)
    sha1 = Column(String(40), nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    folder = relationship("Folder", back_populates="files")

    def to_dict(self) -> dict[str, Any]:
        """Convert file to dictionary representation."""
        return {
            "type": "file",
            "id": self.id,
            "sequence_id": str(self.version or 0),
            "etag": f"{self.id}_v{self.version}",
            "name": self.name,
            "size": self.size,
            "extension": self.name.rsplit(".", 1)[-1] if "." in self.name else "",
            "sha1": self.sha1,
            "modified_at": box_time(self.modified_at or self.created_at),
            "content_created_at": box_time(self.created_at),
            "content_modified_at": box_time(self.modified_at or self.created_at),
            "item_status": "active",
            "owned_by": owner_dict(),
            "is_download_available": True,
            "authenticated_download_url": f"/2.0/files/{self.id}/content",
            "watermark_info": {"is_watermarked": False},
            "permissions": {
                "can_preview": True,
                "can_download": True,
                "can_upload": False,
            },
            "shared_link": None,
            "parent": {"type": "folder", "id": self.folder_id},
            "file_version": {
                "id": f"{self.id}_v{self.version}",
                "version_number": self.version,
            },
            "representations": {
                "entries": [
                    {
                        "representation": "pdf",
                        "status": {"state": "success"},
                        "content": {
                            "url_template": (
                                f"/2.0/files/{self.id}/content{{+asset_path}}"
                            )
                        },
                        "properties": {},
                    }
                ]
            },
            "created_at": box_time(self.created_at),
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
            "created_at": box_time(self.created_at),
        }


def get_session() -> Session:
    """Get the current database session from flask.g."""
    from box_mock.db import db  # noqa: PLC0415

    return db.session
