from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.config import Settings
from app.main import initialise_database, validate_mxl


def make_mxl(root_xml: str = '<score-partwise version="4.0"/>') -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", (
            '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="score.xml" media-type="application/vnd.recordare.musicxml+xml"/>'
            '</rootfiles></container>'
        ))
        archive.writestr("score.xml", root_xml)
    return stream.getvalue()


def test_valid_mxl_container_and_score_are_accepted():
    assert validate_mxl(make_mxl(), "ave-verum.mxl") == "score.xml"


@pytest.mark.parametrize("filename", ["score.xml", "score.pdf", "score.zip"])
def test_only_mxl_extension_is_accepted(filename):
    with pytest.raises(ValueError, match="compressed MusicXML"):
        validate_mxl(make_mxl(), filename)


def test_zip_without_container_is_rejected():
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("score.xml", '<score-partwise/>')
    with pytest.raises(ValueError, match="container.xml"):
        validate_mxl(stream.getvalue(), "score.mxl")


def test_non_musicxml_root_is_rejected():
    with pytest.raises(ValueError, match="not a MusicXML score"):
        validate_mxl(make_mxl("<html/>"), "score.mxl")


def test_path_traversal_inside_archive_is_rejected():
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("META-INF/container.xml", (
            '<container><rootfiles><rootfile full-path="../score.xml"/></rootfiles></container>'
        ))
        archive.writestr("../score.xml", "<score-partwise/>")
    with pytest.raises(ValueError, match="Unsafe path"):
        validate_mxl(stream.getvalue(), "score.mxl")


def test_database_migrations_are_repeatable(tmp_path):
    settings = Settings(
        database_path=str(tmp_path / "chorus.sqlite3"),
        storage_root=str(tmp_path / "private"),
    )
    initialise_database(settings)
    initialise_database(settings)
    import sqlite3

    with sqlite3.connect(settings.database_path) as conn:
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"works", "resources", "files", "creation_drafts", "editor_source_tokens"} <= tables
        applied = conn.execute("SELECT COUNT(*) FROM chorus_schema_migrations").fetchone()[0]
        assert applied == 2
