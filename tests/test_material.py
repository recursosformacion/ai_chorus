"""Biblioteca de material: importación, árbol y duplicados."""

from __future__ import annotations

import json

from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

from tests.test_agenda import _profile, install_fake_auth


def _settings(tmp_path):
    return Settings(
        auth_base_url="https://auth.test",
        database_path=str(tmp_path / "chorus.sqlite3"),
        storage_root=str(tmp_path / "private"),
        secure_cookies=False,
    )


def test_material_import_and_tree(tmp_path, monkeypatch):
    install_fake_auth(monkeypatch, {"token-material": _profile("material-1")})
    headers = {"Authorization": "Bearer token-material"}
    pdf = b"%PDF-1.4\nprueba\n%%EOF"
    metadata = {
        "work_title": "Ave verum",
        "version_label": "Original",
        "part_label": "Soprano",
    }
    with TestClient(create_app(_settings(tmp_path))) as client:
        preview = client.post(
            "/api/v1/material/import",
            headers=headers,
            data={"metadata": json.dumps({**metadata, "preview": True})},
            files=[("files", ("soprano.pdf", pdf, "application/pdf"))],
        )
        assert preview.status_code == 201
        assert preview.json()["status"] == "preview"
        assert preview.json()["files"][0]["display_name"] == "Partitura.pdf"
        response = client.post(
            "/api/v1/material/import",
            headers=headers,
            data={"metadata": json.dumps(metadata)},
            files=[("files", ("soprano.pdf", pdf, "application/pdf"))],
        )
        assert response.status_code == 201, response.text
        created = response.json()
        assert created["files"][0]["name"] == "Partitura.pdf"

        resource_id = created["resource_id"]
        reviewed = client.patch(
            f"/api/v1/material/resources/{resource_id}",
            headers=headers,
            json={"material_status": "reviewed"},
        )
        assert reviewed.status_code == 200
        published = client.post(
            f"/api/v1/material/resources/{resource_id}/publish", headers=headers
        )
        assert published.status_code == 200
        tree = client.get("/api/v1/material/tree", headers=headers).json()
        assert tree[0]["title"] == "Ave verum"
        assert tree[0]["resources"][0]["version_label"] == "Original"
        assert tree[0]["resources"][0]["files"][0]["folder_path"] == "Soprano"

        duplicate = client.post(
            "/api/v1/material/import",
            headers=headers,
            data={"metadata": json.dumps(metadata)},
            files=[("files", ("otra.pdf", pdf, "application/pdf"))],
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["status"] == "duplicate"


def test_material_rejects_unknown_format(tmp_path, monkeypatch):
    install_fake_auth(monkeypatch, {"token-material": _profile("material-2")})
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.post(
            "/api/v1/material/import",
            headers={"Authorization": "Bearer token-material"},
            data={"metadata": json.dumps({"work_title": "X"})},
            files=[("files", ("x.exe", b"MZ", "application/octet-stream"))],
        )
        assert response.status_code == 400


