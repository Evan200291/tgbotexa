"""Export a 640x640 PNG avatar for BotFather from the Exabyte 'E' brand geometry.

Cross-platform (uses Pillow, which is already installed with qrcode[pil]).
Run:  python scripts/export_logo_png.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "exabyte_bot" / "webapp" / "static" / "brand" / "avatar-640.png"


def export_avatar(dest: Path = OUT, size: int = 640) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    scale = 2
    s = size * scale
    img = Image.new("RGBA", (s, s), (10, 15, 29, 255))
    draw = ImageDraw.Draw(img)

    # Vertical gradient background (#10192E -> #050811)
    for y in range(s):
        t = y / s
        r = int(16 * (1 - t) + 5 * t)
        g = int(25 * (1 - t) + 8 * t)
        b = int(46 * (1 - t) + 17 * t)
        draw.line([(0, y), (s, y)], fill=(r, g, b, 255))

    # Outer cyber cyan/blue border frame
    pad = int(s * 0.04)
    draw.rounded_rectangle(
        [pad, pad, s - pad, s - pad],
        radius=int(s * 0.18),
        outline=(0, 240, 255, 255),
        width=int(s * 0.016),
    )

    # Cyber corner HUD accents
    corner_len = int(s * 0.08)
    cyan = (0, 240, 255, 255)
    draw.line([(pad + 10, pad + 10), (pad + 10 + corner_len, pad + 10)], fill=cyan, width=6)
    draw.line([(pad + 10, pad + 10), (pad + 10, pad + 10 + corner_len)], fill=cyan, width=6)
    draw.line([(s - pad - 10, pad + 10), (s - pad - 10 - corner_len, pad + 10)], fill=cyan, width=6)
    draw.line([(s - pad - 10, pad + 10), (s - pad - 10, pad + 10 + corner_len)], fill=cyan, width=6)

    # Exabyte geometric 'E' symbol in Electric Cyan (#00F0FF)
    cyber_cyan = (0, 240, 255, 255)
    # Left vertical bar
    x0, y0, y1 = int(s * 0.203), int(s * 0.195), int(s * 0.805)
    w_bar = int(s * 0.141)
    draw.rectangle([x0, y0, x0 + w_bar, y1], fill=cyber_cyan)

    # Three right-hand angled bars
    rx = int(s * 0.395)
    bh = int(s * 0.141)
    cut = int(s * 0.098)

    # Top bar
    rt = int(s * 0.797)
    draw.polygon([(rx, y0), (rt, y0), (rt - cut, y0 + bh), (rx, y0 + bh)], fill=cyber_cyan)

    # Middle bar
    ym = int(s * 0.430)
    rm = int(s * 0.648)
    draw.polygon([(rx, ym), (rm, ym), (rm - cut, ym + bh), (rx, ym + bh)], fill=cyber_cyan)

    # Bottom bar
    yb = y1 - bh
    draw.polygon([(rx, yb), (rt, yb), (rt - cut, y1), (rx, y1)], fill=cyber_cyan)

    final = img.resize((size, size), Image.Resampling.LANCZOS)
    final.save(dest, format="PNG", optimize=True)
    return dest


if __name__ == "__main__":
    out = export_avatar()
    print(f"Exported 640x640 BotFather avatar to {out}")
