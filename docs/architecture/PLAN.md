# Plan: Implement API Endpoints for New Tables (AutoFree)

## Objective
Implement REST API endpoints, services, and integration tests for the four new tables created during OSAP→Chorus migration: `group_roles`, `group_social_links`, `legacy_uploads`, `activity_log`. Integrate with osap-auth permissions. Review `performances` classification. Update API documentation.

---

## 1. Architecture & Patterns

### Base Patterns (from `app/main.py`)
- **Pydantic models** near top of file (GroupBody, ArticleBody, etc.)
- **Dependency injection**: `current_profile` (full dict), `current_user` (Principal), `principal_dependency` (minimal)
- **Permission helpers**: `_is_admin()`, `_is_representative()`, membership queries
- **DTO helpers**: `_group_dto()`, `_article_dto()`, `_article_permissions()`, `_event_dto()`
- **Connection**: `with _connect(cfg) as conn:` with implicit commit on exit
- **Errors**: `HTTPException` with 400/401/403/404/422/502/503
- **Auth mocking**: `install_fake_auth(monkeypatch, profiles)` in tests

### New Tables (migrations 029-033)
| Table | Migration | PK | FKs | Write Perms | Read Perms |
|-------|-----------|----|-----|-------------|------------|
| `group_roles` | 029 | id | group_id→groups, parent_id→group_roles | Manager/Admin | Member+ |
| `group_social_links` | 030 | id | group_id→groups | Manager/Admin | Member+ |
| `legacy_uploads` | 031 | id | group_id→groups, created_by→users | System only | Admin/Audit |
| `activity_log` | 032 | id (auto) | group_id→groups, article_id→group_articles | System only | Admin/Audit |
| `performances` | 026 | id | (none) | TBD | TBD |

---

## 2. Implementation Plan

### Phase 2.1: Pydantic Models & DTOs
**Location**: `app/main.py` (near line 100-230)

#### `group_roles`
```python
class GroupRoleBody(BaseModel):
    scope: Literal["admin", "musical"]
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    parent_id: str | None = Field(default=None, max_length=191)
    sort_order: int = Field(default=0, ge=0)
    active: bool = True

class GroupRoleUpdateBody(BaseModel):
    scope: Literal["admin", "musical"] | None = None
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    parent_id: str | None = Field(default=None, max_length=191)
    sort_order: int | None = Field(default=None, ge=0)
    active: bool | None = None

def _group_role_dto(row: dict[str, Any], children: list | None = None) -> dict[str, Any]:
    return {
        "id": row["id"],
        "legacy_id": row["legacy_id"],
        "group_id": row["group_id"],
        "scope": row["scope"],
        "code": row["code"],
        "name": row["name"],
        "parent_id": row["parent_id"],
        "sort_order": row["sort_order"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "children": children or [],
    }
```

#### `group_social_links`
```python
class SocialLinkBody(BaseModel):
    kind: Literal["instagram", "facebook", "twitter", "youtube", "website", "other"]
    label: str | None = Field(default=None, max_length=160)
    url: str = Field(min_length=1, max_length=1024)
    position: int = Field(default=0, ge=0)

class SocialLinkUpdateBody(BaseModel):
    kind: Literal["instagram", "facebook", "twitter", "youtube", "website", "other"] | None = None
    label: str | None = Field(default=None, max_length=160)
    url: str | None = Field(default=None, min_length=1, max_length=1024)
    position: int | None = Field(default=None, ge=0)

def _social_link_dto(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "legacy_id": row["legacy_id"],
        "group_id": row["group_id"],
        "kind": row["kind"],
        "label": row["label"],
        "url": row["url"],
        "position": row["position"],
        "created_at": row["created_at"],
    }
```

#### `legacy_uploads` (read-only)
```python
def _legacy_upload_dto(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "legacy_file_id": row["legacy_file_id"],
        "group_id": row["group_id"],
        "mime_type": row["mime_type"],
        "size_bytes": row["size_bytes"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "chorus_file_id": row["chorus_file_id"],
    }
```

#### `activity_log` (read-only)
```python
def _activity_log_dto(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "legacy_id": row["legacy_id"],
        "group_id": row["group_id"],
        "article_id": row["article_id"],
        "event_type": row["event_type"],
        "actor": row["actor"],
        "from_status": row["from_status"],
        "to_status": row["to_status"],
        "detail_json": row["detail_json"],
        "created_at": row["created_at"],
    }
```

---

### Phase 2.2: Endpoint Implementation

#### A. `group_roles` — Full CRUD
**Base path**: `/api/v1/groups/{group_id}/roles`

| Method | Endpoint | Permissions | Description |
|--------|----------|-------------|-------------|
| GET | `/roles` | Member+ | List roles (filter: `?scope=admin\|musical&active=true`) |
| POST | `/roles` | Manager/Admin | Create role (validate group membership) |
| PATCH | `/roles/{role_id}` | Manager/Admin | Update role (validate ownership) |
| DELETE | `/roles/{role_id}` | Manager/Admin | Delete role (cascade: set NULL on members) |

**Permission logic**:
```python
member = conn.execute("SELECT role FROM group_members WHERE group_id=? AND user_sub=? AND status='active'", (group_id, user_id)).fetchone()
admin = _is_admin(profile)
can_write = admin or (member and member["role"] == "manager")
can_read = admin or member is not None
```

**Hierarchy support**: `parent_id` FK → `group_roles.id`. On GET, optionally include children.

#### B. `group_social_links` — Full CRUD
**Base path**: `/api/v1/groups/{group_id}/social-links`

| Method | Endpoint | Permissions |
|--------|----------|-------------|
| GET | `/social-links` | Member+ |
| POST | `/social-links` | Manager/Admin |
| PATCH | `/social-links/{link_id}` | Manager/Admin |
| DELETE | `/social-links/{link_id}` | Manager/Admin |

Same permission pattern as `group_roles`.

#### C. `legacy_uploads` — Read-only
**Base path**: `/api/v1/groups/{group_id}/legacy-uploads`, `/api/v1/legacy-uploads/{id}`

| Method | Endpoint | Permissions |
|--------|----------|-------------|
| GET | `/legacy-uploads` | Admin only (or group manager for own group) |
| GET | `/legacy-uploads/{id}` | Admin / group manager |

**Filters**: `?group_id=...&mime_type=...&date_from=...&date_to=...`

#### D. `activity_log` — Read-only
**Base path**: `/api/v1/groups/{group_id}/activity-log`, `/api/v1/admin/activity-log`

| Method | Endpoint | Permissions |
|--------|----------|-------------|
| GET | `/groups/{group_id}/activity-log` | Group manager/admin |
| GET | `/admin/activity-log` | Global admin only |

**Filters**: `?event_type=...&actor=...&date_from=...&date_to=...&article_id=...&limit=50&offset=0`

---

### Phase 2.3: Integration with Existing Endpoints

#### 1. `GET /api/v1/groups/{group_id}/members`
- Resolve `group_admin_role_id` → `group_roles.code/name`
- Resolve `group_musical_role_id` → `group_roles.code/name`
- Add to response: `admin_role: {id, code, name} | null`, `musical_role: {id, code, name} | null`

#### 2. `PATCH /api/v1/groups/{group_id}/members/{user_sub}`
- Already accepts `admin_role_id`, `musical_role_id` in `MemberUpdateBody`
- Validate FK exists in `group_roles` for same `group_id`
- Validate scope: `admin_role` must be `scope='admin'`, `musical_role` must be `scope='musical'`

#### 3. `GET /api/v1/groups/{group_id}` (optional)
- Embed `social_links` array in group response

#### 4. System triggers for `activity_log`
- On article publish/withdraw: insert `activity_log` row
- On member role change: insert `activity_log` row
- Use existing `utcnow()` for timestamp

---

### Phase 2.4: `performances` Classification Review

**Current state**: Table exists (migration 026), 1 record migrated from `amigos_actuaciones`. No API.

**Decision needed**: 
- If classified as **public events** → CRUD API similar to `events` but with performance-specific fields (ticketing, metrics)
- If classified as **group activities** → nest under groups, similar permissions
- If **standalone** → separate endpoint with own permissions

**Recommendation**: Implement as standalone public-facing resource with admin editorial control (matches `editorial_status` column). Minimal read-only API first:
- `GET /api/v1/performances` (list, filters)
- `GET /api/v1/performances/{id}` (detail)
- Admin: `POST/PATCH/DELETE /api/v1/admin/performances`

---

## 3. Tests

### Test Files to Create/Extend

| File | Tests |
|------|-------|
| `tests/test_group_roles.py` | CRUD + permissions (admin/manager/member/outsider) + hierarchy |
| `tests/test_group_social_links.py` | CRUD + permissions |
| `tests/test_legacy_uploads.py` | List/get + filters + permissions |
| `tests/test_activity_log.py` | List/get + filters + admin view + trigger verification |
| `tests/test_performances.py` | (if API added) |

### Test Patterns (from `test_coral_fields.py`, `test_articles.py`)
1. **Fixtures**: Use `@pytest.mark.integration` + `integration_settings`, `@pytest.mark.db` + `unit_db`
2. **Auth**: `install_fake_auth(monkeypatch, profiles)` with multiple tokens
3. **Data creation**: POST to create group → join → create entities
4. **Assertions**: 200/201/400/401/403/404/422, response structure, permission boundaries
5. **Schema tests**: `@pytest.mark.migrations` query `information_schema.COLUMNS`

### Example Test Structure (`test_group_roles.py`)
```python
@pytest.mark.integration
def test_group_roles_crud_and_permissions(integration_settings, monkeypatch):
    profiles = {
        "token-admin": _profile("admin", roles=["admin"]),
        "token-manager": _profile("mgr"),
        "token-member": _profile("mem"),
        "token-outsider": _profile("out"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)
    
    with TestClient(create_app(integration_settings)) as client:
        # Manager creates group
        mgr = client.post("/api/v1/groups", headers={"Authorization": "Bearer token-manager"}, json={"name": "Test Group"}).json()
        group_id = mgr["id"]
        
        # Manager creates admin role
        r = client.post(f"/api/v1/groups/{group_id}/roles", headers={"Authorization": "Bearer token-manager"}, json={"scope": "admin", "code": "president", "name": "Presidency"})
        assert r.status_code == 201
        role_id = r.json()["id"]
        
        # Member can read
        r = client.get(f"/api/v1/groups/{group_id}/roles", headers={"Authorization": "Bearer token-member"})
        assert r.status_code == 200
        
        # Outsider cannot read
        r = client.get(f"/api/v1/groups/{group_id}/roles", headers={"Authorization": "Bearer token-outsider"})
        assert r.status_code == 403
        
        # Member cannot write
        r = client.post(f"/api/v1/groups/{group_id}/roles", headers={"Authorization": "Bearer token-member"}, json={"scope": "musical", "code": "singer", "name": "Singer"})
        assert r.status_code == 403
```

---

## 4. Documentation Updates

### Files to Update
1. **`docs/api.md`** (or equivalent): Add endpoint specs for all 4 tables
2. **OpenAPI schema** (auto-generated by FastAPI): Verify descriptions, examples
3. **Migration docs**: `migrations/mysql/029-033` already exist

### Documentation Format
- Endpoint: method, path, params, request body, response, status codes, permissions
- Example requests/responses
- Error codes

---

## 5. Verification & Execution

### Commands
```bash
# Run all tests
python run_tests.py

# Run specific integration tests
CHORUS_DATABASE_URL=... python -m pytest tests/test_group_roles.py -v
CHORUS_DATABASE_URL=... python -m pytest tests/test_group_social_links.py -v
CHORUS_DATABASE_URL=... python -m pytest tests/test_legacy_uploads.py -v
CHORUS_DATABASE_URL=... python -m pytest tests/test_activity_log.py -v

# Run migration tests
CHORUS_DATABASE_URL=... python -m pytest tests/ -k migrations -v
```

### Acceptance Criteria
- [ ] All 65 existing tests pass
- [ ] New integration tests pass (admin/manager/member/outsider boundaries)
- [ ] Schema tests verify column types, nullability, FKs
- [ ] Idempotency: re-run migrations + scripts → no duplicates
- [ ] Referential integrity: FK constraints enforced
- [ ] Activity log triggers work on article publish/member changes
- [ ] Documentation updated with all endpoints

---

## 6. Files to Modify

### Core
- `app/main.py` — Add models, DTOs, endpoints, permission checks (~400-500 lines)
- `migrations/mysql/` — Already exist (029-033)

### Tests
- `tests/test_group_roles.py` (new)
- `tests/test_group_social_links.py` (new)
- `tests/test_legacy_uploads.py` (new)
- `tests/test_activity_log.py` (new)
- `tests/test_performances.py` (new, optional)

### Documentation
- `docs/api.md` or `docs/endpoints/` — New endpoint specs

---

## 7. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Permission logic bugs | Exhaustive test matrix (admin/manager/member/outsider × CRUD) |
| FK constraint violations | Validate in PATCH before write; cascade tested in schema tests |
| Activity log spam | Batch writes, async logging, retention policy later |
| Performance on activity_log | Indexes exist; add pagination (limit/offset) |
| Circular parent_id in group_roles | Validate depth limit (e.g., max 3 levels) |

---

## 8. Timeline Estimate

| Phase | Effort |
|-------|--------|
| Models & DTOs | 1h |
| group_roles CRUD | 2h |
| group_social_links CRUD | 1.5h |
| legacy_uploads read | 1h |
| activity_log read + triggers | 2h |
| Integration with members/groups | 1h |
| Tests (4 files × ~10 tests) | 3h |
| Documentation | 1h |
| **Total** | **~12.5h** |

---

## Next Steps
1. User approves plan
2. Implement models & DTOs
2. Implement `group_roles` endpoints
3. Implement `group_social_links` endpoints
4. Implement `legacy_uploads` endpoints
5. Implement `activity_log` endpoints + triggers
6. Integrate with `group_members`/`groups`
7. Write tests
8. Update documentation
9. Run full suite
10. Deliver final report