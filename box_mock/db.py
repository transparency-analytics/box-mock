"""Database session management with identity-based isolation."""

from __future__ import annotations

from pathlib import Path

from flask import g
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DATA_DIR = Path("/data")
# Cache key is (identity, db_url) so file-based and in-memory engines coexist.
_engines: dict[tuple[str, str | None], tuple] = {}


def _make_engine_and_session_class(
    identity: str, db_url: str | None
) -> tuple[Engine, type[Session]]:
    """Create a new engine and seed the root folder."""
    if db_url:
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
    else:
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

    return engine, session_class


def get_session_class(identity: str, db_url: str | None = None) -> type[Session]:
    """Get or create a session class for the given identity.

    When *db_url* is provided (e.g. an in-memory SQLite URL for testing) it is
    used directly.  Otherwise a file-based database under DATA_DIR is used.
    """
    key = (identity, db_url)
    if key not in _engines:
        _engines[key] = _make_engine_and_session_class(identity, db_url)
    return _engines[key][1]


def reset_identity_data(identity: str) -> None:
    """Reset all data for a specific identity (file-based engines only)."""
    key = (identity, None)
    if key in _engines:
        engine, _ = _engines[key]
        from box_mock.models import Base, Folder  # noqa: PLC0415

        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        session_class = sessionmaker(bind=engine)
        session = session_class()
        session.add(Folder(id="0", name="All Files", parent_id=None))
        session.commit()
        session.close()

        _engines[key] = (engine, session_class)

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
