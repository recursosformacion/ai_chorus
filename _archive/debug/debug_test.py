import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings

settings = Settings.load()

# Mock auth
class FakeTransport:
    def __init__(self):
        self.profiles = {
            "token-manager": {"user_id": "mgr-1", "sub": "mgr-1", "name": "Manager", "roles": []},
        }
    
    def handle_request(self, request):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            if token in self.profiles:
                return {"user_id": self.profiles[token]["user_id"]}
        return None

from app.security import Principal
import httpx

# Patch osap_call
import app.main as main_module
original_osap_call = main_module.osap_call

def fake_osap_call(method, path, payload=None, token=None):
    if path == "/api/v1/users/me":
        return {"user_id": "mgr-1", "sub": "mgr-1", "name": "Manager", "roles": []}, None
    return {}, None

main_module.osap_call = fake_osap_call

app = create_app(settings)
client = TestClient(app)

# Create group
grp1 = client.post("/api/v1/groups", headers={"Authorization": "Bearer token-manager"}, json={"name": "Group 1"})
print("Create group:", grp1.status_code, grp1.json())

group1_id = grp1.json()["id"]

# Create preparation work
work = client.post(
    f"/api/v1/groups/{group1_id}/preparation-works",
    headers={"Authorization": "Bearer token-manager"},
    json={"title": "Group 1 Work", "destination_type": "repertoire"},
)
print("Create prep work:", work.status_code, work.json())