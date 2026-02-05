"""Tests for database session management."""

import tempfile
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from flask import Flask, g

import box_mock.db as db_module
from box_mock.db import DBProxy, get_session_class, reset_identity_data
from box_mock.models import Folder


@pytest.fixture
def temp_data_dir() -> Iterator[Path]:
    """Yield a temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_data_dir = db_module.DATA_DIR
        original_engines = db_module._engines.copy()
        db_module.DATA_DIR = Path(tmpdir)
        db_module._engines.clear()
        yield Path(tmpdir)
        db_module.DATA_DIR = original_data_dir
        db_module._engines.clear()
        db_module._engines.update(original_engines)


def test_get_session_class_creates_database(temp_data_dir: Path):
    """Test that get_session_class creates database and root folder."""
    session_class = get_session_class("test-identity")

    assert (temp_data_dir / "test-identity" / "box.db").exists()

    session = session_class()
    root = session.get(Folder, "0")
    assert root is not None
    assert root.name == "All Files"
    session.close()


def test_get_session_class_reuses_existing(temp_data_dir: Path):
    """Test that get_session_class reuses existing engine."""
    _ = temp_data_dir
    session_class_1 = get_session_class("reuse-identity")
    session_class_2 = get_session_class("reuse-identity")

    assert session_class_1 is session_class_2


def test_get_session_class_isolates_identities(temp_data_dir: Path):
    """Test that different identities have separate databases."""
    _ = temp_data_dir
    session_class_a = get_session_class("identity-a")
    session_class_b = get_session_class("identity-b")

    session_a = session_class_a()
    session_a.add(Folder(name="Folder A", parent_id="0"))
    session_a.commit()
    session_a.close()

    session_b = session_class_b()
    folders = session_b.query(Folder).filter(Folder.name == "Folder A").all()
    assert len(folders) == 0
    session_b.close()


def test_reset_identity_data_clears_database(temp_data_dir: Path):
    """Test that reset_identity_data clears all data."""
    _ = temp_data_dir
    session_class = get_session_class("reset-identity")
    session = session_class()
    session.add(Folder(name="Test Folder", parent_id="0"))
    session.commit()
    session.close()

    reset_identity_data("reset-identity")

    session_class = get_session_class("reset-identity")
    session = session_class()
    folders = session.query(Folder).filter(Folder.name == "Test Folder").all()
    assert len(folders) == 0
    root = session.get(Folder, "0")
    assert root is not None
    session.close()


def test_reset_identity_data_clears_files(temp_data_dir: Path):
    """Test that reset_identity_data removes uploaded files."""
    get_session_class("files-identity")
    files_dir = temp_data_dir / "files-identity" / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    (files_dir / "test-file.txt").write_text("content")

    reset_identity_data("files-identity")

    assert not (files_dir / "test-file.txt").exists()


def test_reset_identity_data_handles_missing_identity(temp_data_dir: Path):
    """Test that reset_identity_data handles non-existent identity."""
    _ = temp_data_dir
    reset_identity_data("nonexistent-identity")


def test_db_proxy_session_returns_g_session():
    """Test that DBProxy.session returns session from flask.g."""
    app = Flask(__name__)
    mock_session = MagicMock()

    with app.app_context(), app.test_request_context():
        g.db_session = mock_session
        proxy = DBProxy()

        assert proxy.session is mock_session
