import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
import httpx

settings = Settings.load()

# Mock auth using the same pattern as tests
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

# Patch httpx.Client
import app.main as main_module
original_client = main_module.httpx.Client
main_module.httpx.Client = FakeAuthClient

app = create_app(settings)

# Print all routes
print("=== ROUTES ===")
for route in app.routes:
    if hasattr(route, 'path') and 'preparation' in route.path:
        print(f"  {route.methods} {route.path}")

client = TestClient(app)

# Create group
grp1 = client.post("/api/v1/groups", headers={"Authorization": "Bearer token-manager"}, json={"name": "Group 1"})
print("Create group:", grp1.status_code, grp1.json())

group1_id = grp1.json()["id"]

# Try to access the endpoint directly
print(f"\nTrying GET /api/v1/groups/{group1_id}/preparation-works")
resp = client.get(f"/api/v1/groups/{group1_id}/preparation-works", headers={"Authorization": "Bearer token-manager"})
print("GET prep works:", resp.status_code, resp.json())