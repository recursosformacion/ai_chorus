from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_chorus_web_entrypoint_and_assets_exist():
    html = (WEB / "index.html").read_text("utf-8")
    assert 'href="/styles.css"' in html
    assert 'src="/app.js"' in html
    assert 'id="login-form"' in html
    assert 'id="search-form"' in html
    assert 'id="new-draft-button"' in html
    assert 'id="mxl-file"' in html


def test_web_uses_chorus_api_and_never_calls_osap_directly():
    js = (WEB / "app.js").read_text("utf-8")
    assert '"/api/v1/auth/login"' in js
    assert '"/api/v1/catalog/searches"' in js
    assert '"/api/v1/drafts"' in js
    assert '"/api/v1/drafts/"' in js
    assert '"/api/v1/auth/refresh"' in js
    assert "localStorage" not in js
    assert "sessionStorage" not in js


def test_apache_development_instructions_match_runtime_port():
    doc = (ROOT / "docs" / "apache-dev.md").read_text("utf-8")
    assert "DocumentRoot" in doc
    assert "chorus-app" in doc
    assert "127.0.0.1:9600" in doc
    assert "ProxyPass" in doc
