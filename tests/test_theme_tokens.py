"""Raw hex colours may only appear in webapp/static/css/theme.css + WCAG contrast checks."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "exabyte_bot" / "webapp" / "static"
ALLOWED = {STATIC / "css" / "theme.css"}
# Brand SVGs are standalone files (favicon, avatar) and cannot read CSS variables.
ALLOWED_DIRS = {STATIC / "brand"}
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _rel_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def _c(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * _c(r) + 0.7152 * _c(g) + 0.0722 * _c(b)


def contrast_ratio(c1: str, c2: str) -> float:
    l1, l2 = _rel_luminance(c1), _rel_luminance(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def test_no_raw_hex_colors_outside_theme_css():
    assert STATIC.exists()
    offenders = []
    for f in STATIC.rglob("*"):
        if f.suffix not in {".css", ".js", ".html"} or f in ALLOWED:
            continue
        if any(d in f.parents for d in ALLOWED_DIRS):
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for m in HEX.finditer(line):
                if not re.search(r"""(href|data-target)=["']$""", line[: m.start()]):
                    offenders.append(f"{f.relative_to(ROOT)}:{n}: {m.group()}")
    assert not offenders, "Raw colours outside theme.css:\n" + "\n".join(offenders)


def test_wcag_contrast_ratios_in_dark_and_light_themes():
    # Dark theme text/background pairs (must all be >= 4.5:1 for normal text)
    assert contrast_ratio("#F7EFDD", "#120B0C") >= 4.5
    assert contrast_ratio("#F7EFDD", "#1F1416") >= 4.5
    assert contrast_ratio("#BFAE95", "#120B0C") >= 4.5
    assert contrast_ratio("#BFAE95", "#1F1416") >= 4.5
    assert contrast_ratio("#F3D98B", "#1F1416") >= 4.5
    assert contrast_ratio("#1A1012", "#D4A23A") >= 4.5  # primary gold button text

    # Light theme text/background pairs (including #8A5A0C gold text on light surfaces)
    assert contrast_ratio("#2A1A14", "#FAF4E6") >= 4.5
    assert contrast_ratio("#2A1A14", "#FFFFFF") >= 4.5
    assert contrast_ratio("#6B5646", "#FAF4E6") >= 4.5
    assert contrast_ratio("#6B5646", "#FFFFFF") >= 4.5
    assert contrast_ratio("#8A5A0C", "#FAF4E6") >= 4.5
    assert contrast_ratio("#8A5A0C", "#FFFFFF") >= 4.5
