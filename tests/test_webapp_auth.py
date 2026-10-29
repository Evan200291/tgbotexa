"""Config safety now; Telegram initData validation tests are added in Phase C."""

from __future__ import annotations

import pytest

from exabyte_bot.config import ConfigError, Settings


def test_dev_mode_refuses_production():
    with pytest.raises(ConfigError, match="forbidden"):
        Settings(_env_file=None, environment="production", dev_mode=True)


def test_dev_mode_requires_localhost():
    with pytest.raises(ConfigError, match="localhost"):
        Settings(_env_file=None, environment="development", dev_mode=True, web_host="0.0.0.0")


def test_dev_mode_ok_in_development_on_localhost():
    s = Settings(_env_file=None, environment="development", dev_mode=True)
    assert s.dev_mode


def test_admin_ids_parsing_and_secret_repr(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "1877867098, 42")
    monkeypatch.setenv("PANEL_PASS", "super-secret-value")
    s = Settings(_env_file=None)
    assert s.admin_ids == [1877867098, 42] and s.is_admin(42)
    assert "super-secret-value" not in repr(s)
