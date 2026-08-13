import pytest

import app as runcoach


@pytest.fixture
def ui_client(tmp_path, monkeypatch):
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "ui.db")
    runcoach._database_ready = False
    runcoach.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, DEMO_MODE=True)
    runcoach.setup_database()
    with runcoach.app.test_client() as client:
        yield client


def test_login_is_rico_only_branded_entrance(ui_client):
    html = ui_client.get("/login").get_data(as_text=True)
    assert 'class="auth-shell"' in html
    assert 'class="auth-hero"' in html
    assert "Run with someone who remembers." in html
    assert "Hey, I’m Rico." in html
    assert "Iggy" not in html and "Luna" not in html
    assert "Explore the demo" in html and "Explore Demo" in html
    assert "demo@runcoach.test" not in html and "demo123" not in html
    assert "data-password-toggle" in html
    assert 'role="alert"' not in html


def test_login_error_has_accessible_invalid_state(ui_client):
    response = ui_client.post("/login", data={"email": "nobody@example.test", "password": "wrong-pass"})
    html = response.get_data(as_text=True)
    assert 'role="alert"' in html
    assert html.count('aria-invalid="true"') == 2


def test_rico_chat_is_one_stateful_component(ui_client):
    user_id = runcoach.create_user("rico-ui@example.test", "safe-password")
    with ui_client.session_transaction() as session:
        session["user_id"] = user_id
    html = ui_client.get("/").get_data(as_text=True)
    assert html.count('data-rico-dock') == 1
    assert 'data-state="collapsed"' in html
    assert 'class="rico-chat-header"' in html
    assert 'class="rico-chat-body"' in html
    assert 'class="rico-chat-footer"' in html
    assert 'class="rico-composer"' in html
    assert 'class="rico-send"' in html
    assert "rico-dock-panel" not in html and "rico-dock-toggle" not in html


def test_css_defines_desktop_mobile_and_reduced_motion_contracts():
    css = (runcoach.BASE_DIR / "static" / "design-system.css").read_text(encoding="utf-8")
    assert "width:clamp(360px,29vw,420px)" in css
    assert "height:min(610px,calc(100vh - 38px))" in css
    assert "overflow-x:hidden" in css
    assert "height:100dvh" in css
    assert "prefers-reduced-motion:reduce" in css
