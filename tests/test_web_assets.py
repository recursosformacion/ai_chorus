import pytest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


@pytest.mark.unit
def test_chorus_web_entrypoint_and_assets_exist():
    html = (WEB / "index.html").read_text("utf-8")
    assert 'href="/styles.css' in html
    assert 'src="/app.js' in html
    assert 'id="login-form"' in html
    assert 'id="search-form"' in html
    assert 'id="new-draft-button"' in html
    assert 'id="mxl-file"' in html
    assert 'id="dashboard"' in html
    assert 'id="dash-search-form"' in html


@pytest.mark.unit
def test_web_uses_chorus_api_and_never_calls_osap_directly():
    js = (WEB / "app.js").read_text("utf-8")
    assert '"/api/v1/auth/login"' in js
    assert '"/api/v1/catalog/searches"' in js
    assert '"/api/v1/drafts"' in js
    assert '"/api/v1/drafts/"' in js
    assert '"/api/v1/auth/refresh"' in js
    assert "localStorage" not in js
    assert "sessionStorage" not in js


@pytest.mark.unit
def test_apache_development_instructions_match_runtime_port():
    doc = (ROOT / "docs" / "apache-dev.md").read_text("utf-8")
    assert "DocumentRoot" in doc
    assert "chorus-app" in doc
    assert "127.0.0.1:9600" in doc
    assert "ProxyPass" in doc


@pytest.mark.unit
def test_oidc_login_entrypoint_and_callback_exist():
    html = (WEB / "index.html").read_text("utf-8")
    assert 'id="oidc-login"' in html
    js = (WEB / "app.js").read_text("utf-8")
    assert '"/api/v1/auth/oidc/start"' in js
    callback = (WEB / "auth-callback.html").read_text("utf-8")
    assert "chorus-oidc" in callback
    assert "access_token" in callback

