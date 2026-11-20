import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
import httpx

settings = Settings.load()

class FakeAuthResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data
    def json(self):
        return self._json
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"Status {self.status_code}", request=None, response=self)

class FakeAuthClient:
    def __init__(self, timeout=None):
        self.timeout = timeout
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def request(self, method, url, json=None, headers=None):
        auth_base_url = "http://osap-auth/auth-api"
        path = url.removeprefix(auth_base_url.rstrip("/"))
        token = (headers or {}).get("Authorization", "").removeprefix("Bearer ")
        if method == "GET" and path in ("/auth/me", "/auth/me/"):
            profiles = {
                "token-manager": {"user_id": "mgr-1", "roles": ["user"], "email_verified": True, "status": "active", "onboarding": {"required": False}, "memberships": []},
            }
            profile = profiles.get(token)
            return FakeAuthResponse(200, profile) if profile else FakeAuthResponse(401, {})
        return FakeAuthResponse(404, {})

import app.main as main_module
main_module.httpx.Client = FakeAuthClient

app = create_app(settings)
client = TestClient(app)

# Create group
grp = client.post("/api/v1/groups", headers={"Authorization": "Bearer token-manager"}, json={"name": "Files Test"})
print("Create group:", grp.status_code)
group_id = grp.json()["id"]

# Create work
work = client.post(
    f"/api/v1/groups/{group_id}/preparation-works",
    headers={"Authorization": "Bearer token-manager"},
    json={"title": "Work with files", "destination_type": "repertoire"},
)
print("Create work:", work.status_code)
work_id = work.json()["id"]
print(f"Work ID: {work_id}")
print(f"Folder path: {work.json()['folder_path']}")

# Upload files
files = [
    ("files", ("score.pdf", b"%PDF test content", "application/pdf")),
    ("files", ("part.mxl", b"<?xml version='1.0'?>", "application/vnd.recordare.musicxml")),
]
parts = [
    {"part_label": "Soprano", "purpose": "part"},
    {"part_label": "Director", "purpose": "score"},
]
import json as json_std
form_data = {"parts": json_std.dumps(parts)}
r = client.post(
    f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files",
    headers={"Authorization": "Bearer token-manager"},
    files=files,
    data=form_data,
)
print("Upload files:", r.status_code, r.json())

# List files
r = client.get(f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files", headers={"Authorization": "Bearer token-manager"})
print("List files:", r.status_code, r.json())

# Check filesystem
from pathlib import Path
root = Path(settings.storage_root).resolve()
folder_path = work.json()['folder_path']
folder = (root / folder_path).resolve()
print(f"Storage root: {root}")
print(f"Folder path: {folder_path}")
print(f"Folder exists: {folder.exists()}")
if folder.exists():
    for f in folder.iterdir():
        print(f"  File: {f.name}, is_file: {f.is_file()}")