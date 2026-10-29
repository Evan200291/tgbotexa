"""Raw hex colours may only appear in webapp/static/css/theme.css (the design tokens)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "exabyte_bot" / "webapp" / "static"
ALLOWED = {STATIC / "css" / "theme.css"}
# Brand SVGs are standalone files (favicon, avatar) and cannot read CSS variables.
ALLOWED_DIRS = {STATIC / "brand"}
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def test_no_raw_hex_colors_outside_theme_css():
    if not STATIC.exists():  # frontend arrives in Phase C
        return
    offenders = []
    for f in STATIC.rglob("*"):
        if f.suffix not in {".css", ".js", ".html"} or f in ALLOWED:
            continue
        if any(d in f.parents for d in ALLOWED_DIRS):
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            # ignore URL fragments like href="#plans"
            for m in HEX.finditer(line):
                if not re.search(r"""(href|data-target)=["']$""", line[: m.start()]):
                    offenders.append(f"{f.relative_to(ROOT)}:{n}: {m.group()}")
    assert not offenders, "Raw colours outside theme.css:\n" + "\n".join(offenders)

