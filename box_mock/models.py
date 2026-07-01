"""Database models for Box Mock API using plain SQLAlchemy."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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
    memberships = relationship(
        "GroupMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )

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


class Group(Base):
    """Box group."""

    __tablename__ = "groups"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    provenance = Column(String(255), nullable=True)
    external_sync_identifier = Column(String(255), nullable=True)
    invitability_level = Column(String(32), nullable=True)
    member_viewability_level = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memberships = relationship(
        "GroupMembership",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert group to dictionary representation."""
        return {
            "type": "group",
            "id": self.id,
            "name": self.name,
            "group_type": "managed_group",
            "description": self.description,
            "provenance": self.provenance,
            "external_sync_identifier": self.external_sync_identifier,
            "invitability_level": self.invitability_level,
            "member_viewability_level": self.member_viewability_level,
            "created_at": box_time(self.created_at),
            "modified_at": box_time(self.modified_at or self.created_at),
        }


class GroupMembership(Base):
    """Box group membership linking a user and group."""

    __tablename__ = "group_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_group_membership"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=False)
    role = Column(String(32), nullable=False, default="member")
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="memberships")
    group = relationship("Group", back_populates="memberships")

    def to_dict(self) -> dict[str, Any]:
        """Convert membership to dictionary representation."""
        return {
            "type": "group_membership",
            "id": self.id,
            "role": self.role,
            "user": {
                "type": "user",
                "id": self.user.id,
                "name": self.user.name,
                "login": self.user.login,
            },
            "group": {
                "type": "group",
                "id": self.group.id,
                "name": self.group.name,
            },
            "created_at": box_time(self.created_at),
            "modified_at": box_time(self.modified_at or self.created_at),
        }


class FileVersion(Base):
    """Immutable content snapshot for a file."""

    __tablename__ = "file_versions"
    __table_args__ = (UniqueConstraint("file_id", "version_number"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(36), ForeignKey("files.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    size = Column(Integer, default=0)
    sha1 = Column(String(40), nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    file = relationship("File", back_populates="versions")

    def to_dict(self) -> dict[str, Any]:
        """Convert file version to dictionary representation."""
        return {
            "type": "file_version",
            "id": self.id,
            "name": self.name,
            "size": self.size,
            "sha1": self.sha1,
            "created_at": box_time(self.created_at),
            "modified_at": box_time(self.modified_at or self.created_at),
            "modified_by": owner_dict(),
            "version_number": str(self.version_number),
        }


class File(Base):
    """
    Box file wrapper. Content stored per version at
    data/{identity}/files/{id}/{version_id}.
    """

    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    folder_id = Column(String(36), ForeignKey("folders.id"), nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    folder = relationship("Folder", back_populates="files")
    versions = relationship(
        "FileVersion",
        back_populates="file",
        order_by="FileVersion.version_number",
        cascade="all, delete-orphan",
    )

    @property
    def current_version(self) -> FileVersion | None:
        """Return the latest version, or None if the file has no versions."""
        if not self.versions:
            return None
        return self.versions[-1]

    def to_dict(self) -> dict[str, Any]:
        """Convert file to dictionary representation."""
        version = self.current_version
        version_number = version.version_number if version else 0
        size = version.size if version else 0
        sha1 = version.sha1 if version else ""
        content_modified_at = (
            version.modified_at or version.created_at if version else self.created_at
        )
        file_version_id = version.id if version else ""
        first_version = self.versions[0] if self.versions else None
        content_created_at = (
            first_version.created_at if first_version else self.created_at
        )

        return {
            "type": "file",
            "id": self.id,
            "sequence_id": str(version_number),
            "etag": f"{self.id}_v{version_number}",
            "name": self.name,
            "size": size,
            "extension": self.name.rsplit(".", 1)[-1] if "." in self.name else "",
            "sha1": sha1,
            "version_number": str(version_number),
            "modified_at": box_time(content_modified_at),
            "modified_by": owner_dict(),
            "content_created_at": box_time(content_created_at),
            "content_modified_at": box_time(content_modified_at),
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
                "id": file_version_id,
                "type": "file_version",
                "sha1": sha1,
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
    finished_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert sign request to dictionary representation."""
        signers = json.loads(self.signers_json) if self.signers_json else []
        files = json.loads(self.files_json) if self.files_json else []
        return {
            "type": "sign-request",
            "id": self.id,
            "status": self.status,
            "signers": signers,
            "sign_files": {"files": files, "is_ready_for_download": True},
            "parent_folder": {"type": "folder", "id": self.parent_folder_id}
            if self.parent_folder_id
            else None,
            "redirect_url": self.redirect_url,
            "created_at": box_time(self.created_at),
            "finished_at": box_time(self.finished_at),
        }


def get_session() -> Session:
    """Get the current database session from flask.g."""
    from box_mock.db import db  # noqa: PLC0415

    return db.session
