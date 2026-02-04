"""Database session management with identity-based isolation."""

from __future__ import annotations

from pathlib import Path

from flask import g
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DATA_DIR = Path("/data")
_engines: dict[str, tuple] = {}  # identity -> (engine, SessionClass)


def get_session_class(identity: str) -> tuple[Engine, type[Session]]:
    """Get or create engine and session class for identity."""
    if identity not in _engines:
        db_dir = DATA_DIR / identity
        db_dir.mkdir(parents=True, exist_ok=True)

        engine = create_engine(
            f"sqlite:///{db_dir}/box.db",
            connect_args={"check_same_thread": False},
        )

        from box_mock.models import Base, Folder  # noqa: PLC0415

        Base.metadata.create_all(engine)

        session_class = sessionmaker(bind=engine)
        session = session_class()
        if not session.get(Folder, "0"):
            session.add(Folder(id="0", name="All Files", parent_id=None))
            session.commit()
        session.close()

        _engines[identity] = (engine, session_class)

    return _engines[identity][1]


def reset_identity_data(identity: str) -> None:
    """Reset all data for a specific identity."""
    if identity in _engines:
        engine, _ = _engines[identity]
        from box_mock.models import Base, Folder  # noqa: PLC0415

        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        session_class = sessionmaker(bind=engine)
        session = session_class()
        session.add(Folder(id="0", name="All Files", parent_id=None))
        session.commit()
        session.close()

        _engines[identity] = (engine, session_class)

    files_dir = DATA_DIR / identity / "files"
    if files_dir.exists():
        for f in files_dir.iterdir():
            f.unlink()


class DBProxy:
    """Proxy to current request's session."""

    @property
    def session(self) -> Session:
        """Get the current database session from flask.g."""
        return g.db_session


db = DBProxy()
