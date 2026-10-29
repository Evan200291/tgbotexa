"""Install the git pre-commit hook that runs scripts/check_secrets.py (cross-platform).

Run once after cloning:  python scripts/install_hooks.py
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

HOOK = """#!/bin/sh
# Installed by scripts/install_hooks.py: blocks commits containing secrets.
for py in .venv/Scripts/python.exe .venv/bin/python python3 python; do
  if [ -x "$py" ] || command -v "$py" >/dev/null 2>&1; then
    exec "$py" scripts/check_secrets.py
  fi
done
echo "[secret-check] Python not found; refusing to commit." >&2
exit 1
"""


def main() -> None:
    git_dir = subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks"],  # noqa: S603,S607 - fixed args, git on PATH
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    hooks = Path(git_dir)
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    # newline="\n": sh on Windows (Git Bash) chokes on CRLF line endings.
    hook.write_text(HOOK, encoding="utf-8", newline="\n")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Installed pre-commit hook at {hook}")


if __name__ == "__main__":
    main()
