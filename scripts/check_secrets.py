"""Block commits that contain secrets (the GitHub repo is PUBLIC).

Usage:
  python scripts/check_secrets.py          # scan STAGED changes (used by the pre-commit hook)
  python scripts/check_secrets.py --all    # scan every tracked file (CI / security review)

A line can be exempted with the comment marker:  secret-check: ignore
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import PurePosixPath

TOKEN_RE = re.compile(r"(?<![\w])\d{8,10}:[A-Za-z0-9_-]{35}(?![\w-])")
# KEY=value assignments (env files, compose, docs). Placeholders are allowed.
ASSIGN_RE = re.compile(
    r"\b(BOT_TOKEN|PANEL_PASS|PANEL_USER|PANEL_BASE_URL|KBZ_NUMBER)\s*[=:]\s*[\"']?([^\s\"'#\\]*)"
)
# A 3X-UI style URL: explicit port or /panel|/login after a long random-looking segment.
PANEL_URL_RE = re.compile(
    r"https?://[A-Za-z0-9.-]+(?::\d{2,5})?/(?P<seg>[A-Za-z0-9_-]{10,})(?=/(?:panel|login)\b|[/\s\"'`)]|$)"
)
PLACEHOLDER_RE = re.compile(r"^(<[^>]*>|FILL_ME|CHANGEME|changeme|xxx+|\.\.\.|)$", re.I)
IGNORE_MARK = "secret-check: ignore"


def _looks_random(seg: str) -> bool:
    has_digit = any(c.isdigit() for c in seg)
    has_alpha = any(c.isalpha() for c in seg)
    return has_digit and has_alpha


def _url_value_ok(value: str) -> bool:
    """PANEL_BASE_URL is fine only when its path is a placeholder like <SECRET_PATH>."""
    m = re.match(r"https?://[^/]+/?(.*)$", value)
    if not m:
        return PLACEHOLDER_RE.match(value) is not None
    path = m.group(1)
    return path == "" or path.startswith("<") or path.startswith("$")


def scan_text(path: str, text: str) -> list[str]:
    problems = []
    for n, line in enumerate(text.splitlines(), 1):
        if IGNORE_MARK in line:
            continue
        where = f"{path}:{n}"
        if TOKEN_RE.search(line):
            problems.append(f"{where}: looks like a Telegram bot token")
        for m in ASSIGN_RE.finditer(line):
            name, value = m.group(1), m.group(2)
            # Code like `PANEL_PASS=settings.x` or `${PANEL_PASS}` is not a literal secret.
            if value.startswith(("$", "{", "os.", "settings.", "s.")):
                continue
            if name == "PANEL_BASE_URL":
                if not _url_value_ok(value):
                    problems.append(f"{where}: PANEL_BASE_URL contains a real secret path")
            elif not PLACEHOLDER_RE.match(value):
                problems.append(f"{where}: {name} has a non-placeholder value")
        for m in PANEL_URL_RE.finditer(line):
            port_or_panel = re.search(r":\d{2,5}/", m.group(0)) or "/panel" in line or "/login" in line
            if port_or_panel and _looks_random(m.group("seg")):
                problems.append(f"{where}: panel URL with a secret-looking path segment")
    return problems


def is_forbidden_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return (name == ".env" or name.startswith(".env.")) and name != ".env.example"


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout  # noqa: S603,S607


def _files(all_files: bool) -> list[str]:
    if all_files:
        out = _git("ls-files", "-z")
    else:
        out = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [p for p in out.decode().split("\0") if p]


def _content(path: str, all_files: bool) -> str | None:
    data = _git("show", f":{path}") if not all_files else open(path, "rb").read()  # noqa: SIM115
    if b"\0" in data[:8000]:
        return None  # binary
    return data.decode("utf-8", errors="replace")


def main(argv: list[str]) -> int:
    all_files = "--all" in argv
    problems: list[str] = []
    for path in _files(all_files):
        if is_forbidden_file(path):
            problems.append(f"{path}: .env files must never be committed")
            continue
        if path == "scripts/check_secrets.py":
            continue  # contains the patterns themselves
        text = _content(path, all_files)
        if text is not None:
            problems.extend(scan_text(path, text))
    if problems:
        print("\n[secret-check] Commit BLOCKED - possible secrets found:")
        for p in problems:
            print("  -", p)
        print("Remove them (use .env placeholders). If a real secret leaked, rotate it now.\n")
        return 1
    print("[secret-check] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
