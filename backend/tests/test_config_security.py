"""Tests for config validation functions and cookie security flags."""

import re

import pytest
from app.core.config import resolve_cookie_secure, resolve_environment, validate_secret_key
from starlette.responses import Response

# ---------------------------------------------------------------------------
# resolve_environment
# ---------------------------------------------------------------------------

class TestResolveEnvironment:
    def test_unset_gives_development(self):
        assert resolve_environment(None) == "development"

    def test_valid_values(self):
        for val in ("development", "test", "production"):
            assert resolve_environment(val) == val

    def test_case_insensitive(self):
        assert resolve_environment("Production") == "production"
        assert resolve_environment("  TEST  ") == "test"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="ENVIRONMENT must be one of"):
            resolve_environment("staging")


# ---------------------------------------------------------------------------
# resolve_cookie_secure
# ---------------------------------------------------------------------------

class TestResolveCookieSecure:
    def test_production_unset_returns_true(self):
        assert resolve_cookie_secure("production", None) is True

    def test_development_unset_returns_false(self):
        assert resolve_cookie_secure("development", None) is False

    def test_test_unset_returns_false(self):
        assert resolve_cookie_secure("test", None) is False

    def test_explicit_false_in_production(self):
        assert resolve_cookie_secure("production", "false") is False

    def test_explicit_true_in_development(self):
        assert resolve_cookie_secure("development", "true") is True

    def test_case_insensitive(self):
        assert resolve_cookie_secure("development", "TRUE") is True
        assert resolve_cookie_secure("production", "FALSE") is False

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError, match="COOKIE_SECURE must be"):
            resolve_cookie_secure("development", "yes")


# ---------------------------------------------------------------------------
# validate_secret_key
# ---------------------------------------------------------------------------

class TestValidateSecretKey:
    def test_production_placeholder_raises(self):
        with pytest.raises(RuntimeError, match="secrets.token_hex"):
            validate_secret_key("production", "change-me-in-production")

    def test_production_short_key_raises(self):
        with pytest.raises(RuntimeError, match="at least 32 bytes"):
            validate_secret_key("production", "a" * 31)

    def test_production_valid_key_passes(self):
        key = "a" * 32
        assert validate_secret_key("production", key) == key

    def test_development_placeholder_does_not_raise(self):
        assert validate_secret_key("development", "change-me-in-production") == "change-me-in-production"

    def test_test_weak_key_does_not_raise(self):
        assert validate_secret_key("test", "short") == "short"


# ---------------------------------------------------------------------------
# Cookie flags on set_auth_cookies / clear_auth_cookies
# ---------------------------------------------------------------------------

class TestCookieFlags:
    """Verify that set_auth_cookies and clear_auth_cookies both set
    Secure, HttpOnly, and SameSite=lax on every Set-Cookie header."""

    def _cookie_headers(self, response: Response) -> list[str]:
        return [
            v for k, v in response.raw_headers
            if k.lower() == b"set-cookie"
        ]

    def test_set_and_clear_cookies_have_secure_flags(self, monkeypatch):
        from app.core import security
        from app.core.config import settings

        monkeypatch.setattr(settings, "COOKIE_SECURE", True)

        response = Response()
        security.set_auth_cookies(response, "user-1", "admin", "inst-1")
        security.clear_auth_cookies(response)

        headers = self._cookie_headers(response)
        # set_auth_cookies sets 2 cookies, clear_auth_cookies sets 2 more
        assert len(headers) >= 4, f"Expected at least 4 Set-Cookie headers, got {len(headers)}"

        for raw in headers:
            header = raw.decode() if isinstance(raw, bytes) else raw
            lower = header.lower()
            assert "secure" in lower, f"Missing Secure in: {header}"
            assert "httponly" in lower, f"Missing HttpOnly in: {header}"
            assert re.search(r"samesite=lax", lower), f"Missing SameSite=lax in: {header}"
