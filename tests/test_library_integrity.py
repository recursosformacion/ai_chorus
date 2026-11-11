from __future__ import annotations

import sqlite3
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_mxl(root_xml: str = '<score-partwise version="4.0"/>') -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "META-INF/container.xml",
            (
                '<?xml version="1.0"?><container '
                'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                '<rootfiles><rootfile full-path="score.xml" '
                'media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>'
            ),
        )
        archive.writestr("score.xml", root_xml)
    return stream.getvalue()


class FakeAuthResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def install_fake_auth(monkeypatch, profiles):
    class FakeAuthClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method, url, json=None, headers=None):
            path = url.removeprefix("https://auth.test")
            token = (headers or {}).get("Authorization", "").removeprefix("Bearer ")
            if method == "GET" and path == "/auth/me":
                profile = profiles.get(token)
                return FakeAuthResponse(200, profile) if profile else FakeAuthResponse(401, {})
            return FakeAuthResponse(404, {})

    monkeypatch.setattr("app.main.httpx.Client", FakeAuthClient)


def _profiles():
    return {
        "token-user-1": {
            "user_id": "user-1",
            "roles": ["user"],
            "email_verified": True,
            "status": "active",
            "onboarding": {"required": False},
        },
        "token-user-2": {
            "user_id": "user-2",
            "roles": ["user"],
            "email_verified": True,
            "status": "active",
            "onboarding": {"required": False},
        },
    }


def _settings(tmp_path) -> Settings:
    return Settings(
        auth_base_url="https://auth.test",
        database_path=str(tmp_path / "chorus.sqlite3"),
        storage_root=str(tmp_path / "private"),
        secure_cookies=False,
    )


def _headers(token: str = "token-user-1") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload(client: TestClient, title: str) -> dict:
    created = client.post(
        "/api/v1/drafts", headers=_headers(), json={"title": title}
    )
    assert created.status_code == 201, created.text
    draft_id = created.json()["id"]
    uploaded = client.post(
        f"/api/v1/drafts/{draft_id}/files",
        headers=_headers(),
        files={
            "file": (
                "score.mxl",
                make_mxl(f'<score-partwise version="4.0"><work><work-title>{title}</work-title></work></score-partwise>'),
                "application/zip",
            )
        },
    )
    assert uploaded.status_code == 201, uploaded.text
    return uploaded.json()


def _pointer(settings: Settings, file_id: str) -> Path:
    with sqlite3.connect(settings.database_path) as conn:
        pointer = conn.execute(
            "SELECT storage_pointer FROM files WHERE id = ?", (file_id,)
        ).fetchone()[0]
    return Path(settings.storage_root) / pointer


def test_upload_creates_integrity_and_library_entry(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        install_fake_auth(monkeypatch, _profiles())
        result = _upload(client, "Ave verum")

        integrity = client.get(
            f"/api/v1/works/{result['work_id']}/integrity", headers=_headers()
        )
        assert integrity.status_code == 200, integrity.text
        assert integrity.json()["status"] == "ok"
        assert integrity.json()["actual_sha256"] == result["sha256"]

        library = client.get("/api/v1/library", headers=_headers())
        assert library.status_code == 200, library.text
        items = library.json()["items"]
        assert len(items) == 1
        assert items[0]["kind"] == "local_work"
        item_id = items[0]["id"]

        again = client.post(
            f"/api/v1/library/works/{result['work_id']}", headers=_headers()
        )
        assert again.status_code == 201
        assert again.json()["id"] == item_id

        reference = client.post(
            "/api/v1/library/references",
            headers=_headers(),
            json={
                "work_id": "osap-work-1",
                "representation_id": "osap-resource-1",
                "title": "Referencia OSAP",
            },
        )
        assert reference.status_code == 201, reference.text
        duplicate = client.post(
            "/api/v1/library/references",
            headers=_headers(),
            json={
                "work_id": "osap-work-1",
                "representation_id": "osap-resource-1",
                "title": "Otra vez",
            },
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["id"] == reference.json()["id"]

        collection = client.post(
            "/api/v1/collections", headers=_headers(), json={"name": "Ensayo"}
        )
        assert collection.status_code == 201, collection.text
        collection_id = collection.json()["id"]
        added = client.post(
            f"/api/v1/collections/{collection_id}/items",
            headers=_headers(),
            json={"library_item_id": item_id},
        )
        assert added.status_code == 201, added.text
        collections = client.get("/api/v1/collections", headers=_headers()).json()[
            "collections"
        ]
        assert collections[0]["item_count"] == 1


def test_uploads_are_separate_versions_and_keep_previous_files(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        install_fake_auth(monkeypatch, _profiles())
        first = _upload(client, "Primera versión")
        second = _upload(client, "Segunda versión")

        assert first["work_id"] != second["work_id"]
        assert first["file_id"] != second["file_id"]
        for result in (first, second):
            integrity = client.get(
                f"/api/v1/works/{result['work_id']}/integrity", headers=_headers()
            )
            assert integrity.json()["status"] == "ok"

        library = client.get("/api/v1/library", headers=_headers()).json()["items"]
        assert len([item for item in library if item["kind"] == "local_work"]) == 2


def test_integrity_reports_missing_and_corrupted_files(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        install_fake_auth(monkeypatch, _profiles())
        result = _upload(client, "Integridad")
        path = _pointer(settings, result["file_id"])

        path.unlink()
        missing = client.get(
            f"/api/v1/works/{result['work_id']}/integrity", headers=_headers()
        )
        assert missing.json()["status"] == "missing"

        path.write_bytes(b"corrupted")
        corrupted = client.get(
            f"/api/v1/works/{result['work_id']}/integrity", headers=_headers()
        )
        assert corrupted.json()["status"] == "mismatch"
        assert corrupted.json()["actual_sha256"] != result["sha256"]


def test_library_items_are_scoped_to_the_authenticated_user(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        install_fake_auth(monkeypatch, _profiles())
        result = _upload(client, "Privada")

        hidden = client.get(
            f"/api/v1/works/{result['work_id']}/integrity", headers=_headers("token-user-2")
        )
        assert hidden.status_code == 404
        other_library = client.get(
            "/api/v1/library", headers=_headers("token-user-2")
        ).json()["items"]
        assert other_library == []
