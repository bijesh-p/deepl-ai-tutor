from backend.analytics.auth import check_admin_password, is_admin_username


def test_is_admin_username_matches_allowlist(monkeypatch):
    monkeypatch.setenv("AI_TUTOR_ADMIN_USERNAMES", "admin, hareesh")
    assert is_admin_username("admin") is True
    assert is_admin_username("hareesh") is True
    assert is_admin_username("alice") is False


def test_is_admin_username_unset(monkeypatch):
    monkeypatch.delenv("AI_TUTOR_ADMIN_USERNAMES", raising=False)
    assert is_admin_username("admin") is False


def test_check_admin_password_matches(monkeypatch):
    monkeypatch.setenv("AI_TUTOR_ADMIN_PASSWORD", "secret")
    assert check_admin_password("secret") is True
    assert check_admin_password("wrong") is False


def test_check_admin_password_unset(monkeypatch):
    monkeypatch.delenv("AI_TUTOR_ADMIN_PASSWORD", raising=False)
    assert check_admin_password("anything") is False
    assert check_admin_password("") is False
