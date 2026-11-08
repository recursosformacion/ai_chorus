"""Configuration for the independent Chorus service."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    auth_base_url: str = ""
    auth_issuer: str = ""
    auth_jwks_url: str = ""
    auth_audience: str = "chorus-api"
    osap_api_base_url: str = ""
    editor_base_url: str = ""
    editor_origin: str = ""
    database_path: str = "var/chorus.sqlite3"
    storage_root: str = "var/private"
    cors_origins: tuple[str, ...] = ()
    max_upload_bytes: int = 50 * 1024 * 1024
    source_token_ttl_seconds: int = 300
    auth_timeout_seconds: float = 15.0
    osap_timeout_seconds: float = 45.0
    secure_cookies: bool = True

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Settings":
        config_path = Path(path or os.getenv("CHORUS_CONFIG", "osap.toml"))
        data = tomllib.loads(config_path.read_text("utf-8")) if config_path.exists() else {}
        auth = data.get("auth", {})
        osap = data.get("osap", {})
        editor = data.get("editor", {})
        storage = data.get("storage", {})
        app = data.get("app", {})

        def value(env: str, section: dict, key: str, default: str = "") -> str:
            return os.getenv(env, str(section.get(key, default))).strip()

        auth_base = value("CHORUS_AUTH_BASE_URL", auth, "base_url").rstrip("/")
        editor_url = value("CHORUS_EDITOR_BASE_URL", editor, "base_url").rstrip("/")
        editor_origin = value("CHORUS_EDITOR_ORIGIN", editor, "origin").rstrip("/")
        if not editor_origin and editor_url:
            parsed = urlparse(editor_url)
            editor_origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
        cors_raw = value("CHORUS_CORS_ORIGINS", app, "cors_origins")
        cors = tuple(x.strip().rstrip("/") for x in cors_raw.split(",") if x.strip())
        if not cors and isinstance(app.get("cors_origins"), list):
            cors = tuple(str(x).rstrip("/") for x in app["cors_origins"])
        jwks = value("CHORUS_AUTH_JWKS_URL", auth, "jwks_url")
        if not jwks and auth_base:
            jwks = f"{auth_base}/auth/.well-known/jwks.json"
        return cls(
            auth_base_url=auth_base,
            auth_issuer=value("CHORUS_AUTH_ISSUER", auth, "issuer"),
            auth_jwks_url=jwks,
            auth_audience=value("CHORUS_AUTH_AUDIENCE", auth, "audience", "chorus-api"),
            osap_api_base_url=value("CHORUS_OSAP_API_BASE_URL", osap, "api_base_url").rstrip("/"),
            editor_base_url=editor_url,
            editor_origin=editor_origin,
            database_path=value("CHORUS_DATABASE_PATH", storage, "database_path", "var/chorus.sqlite3"),
            storage_root=value("CHORUS_STORAGE_ROOT", storage, "root", "var/private"),
            cors_origins=cors,
            max_upload_bytes=int(value("CHORUS_MAX_UPLOAD_BYTES", storage, "max_upload_bytes", str(50 * 1024 * 1024))),
            source_token_ttl_seconds=int(value("CHORUS_SOURCE_TOKEN_TTL", editor, "source_token_ttl_seconds", "300")),
            auth_timeout_seconds=float(value("CHORUS_AUTH_TIMEOUT", auth, "timeout_seconds", "15")),
            osap_timeout_seconds=float(value("CHORUS_OSAP_TIMEOUT", osap, "timeout_seconds", "45")),
            secure_cookies=value("CHORUS_SECURE_COOKIES", app, "secure_cookies", "true").lower() not in {"0", "false", "no"},
        )

    def validate_auth(self) -> None:
        missing = [name for name, val in (
            ("auth.base_url", self.auth_base_url),
            ("auth.issuer", self.auth_issuer),
            ("auth.jwks_url", self.auth_jwks_url),
            ("auth.audience", self.auth_audience),
        ) if not val]
        if missing:
            raise RuntimeError("Chorus authentication is not configured: " + ", ".join(missing))
