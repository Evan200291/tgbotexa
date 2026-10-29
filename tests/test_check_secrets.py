"""The secret scanner must catch real-looking secrets and allow placeholders."""

from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_secrets", Path(__file__).resolve().parents[1] / "scripts" / "check_secrets.py")
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

# Built at runtime so this file itself never contains a token-shaped string.
FAKE_TOKEN = "1234567890" + ":" + "A" * 20 + "b" * 15


def test_detects_token():
    assert cs.scan_text("x.py", f'TOKEN = "{FAKE_TOKEN}"')


def test_detects_real_values_but_allows_placeholders():
    assert cs.scan_text(".env.example", "BOT_TOKEN=<FILL_ME>\nPANEL_PASS=<FILL_ME>") == []
    assert cs.scan_text("a", "PANEL_PASS=hunter2hunter2")  # secret-check: ignore (fake)
    assert cs.scan_text("a", "PANEL_BASE_URL=https://tpone.lhpvpn.online:8080/<SECRET_PATH>") == []
    assert cs.scan_text("a", "PANEL_BASE_URL=https://h.example:8080/" + "aB3dE5fG7hJ9kL")


def test_detects_panel_url_with_random_path():
    url = "https://panel.example:2053/" + "Zx81kQp2Lm9w" + "/panel/inbounds"
    assert cs.scan_text("README.md", f"open {url}")
    assert cs.scan_text("README.md", "see https://github.com/Evan200291/tgbotexa") == []


def test_env_files_forbidden():
    assert cs.is_forbidden_file(".env") and cs.is_forbidden_file("deploy/.env.prod")
    assert not cs.is_forbidden_file(".env.example")
