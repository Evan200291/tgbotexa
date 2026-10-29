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
    # Render at 2x and downsample with LANCZOS for crisp anti-aliased edges.
    scale = 2
    s = size * scale
    img = Image.new("RGBA", (s, s), (18, 11, 12, 255))
    draw = ImageDraw.Draw(img)

    # Vertical gradient background (#2A1B1E -> #120B0C)
    for y in range(s):
        t = y / s
        r = int(42 * (1 - t) + 18 * t)
        g = int(27 * (1 - t) + 11 * t)
        b = int(30 * (1 - t) + 12 * t)
        draw.line([(0, y), (s, y)], fill=(r, g, b, 255))

    # Outer gold border frame
    pad = int(s * 0.04)
    draw.rounded_rectangle(
        [pad, pad, s - pad, s - pad],
        radius=int(s * 0.18),
        outline=(212, 162, 58, 255),
        width=int(s * 0.016),
    )

    # Subtle pagoda hti crown accent at top center
    cx = s // 2
    draw.polygon(
        [(cx, int(s * 0.09)), (cx + int(s * 0.025), int(s * 0.14)), (cx - int(s * 0.025), int(s * 0.14))],
        fill=(243, 217, 139, 110),
    )

    # Exabyte geometric 'E' symbol in warm Shwedagon gold (#E5BA58)
    gold = (229, 186, 88, 255)
    # Left vertical bar
    x0, y0, y1 = int(s * 0.203), int(s * 0.195), int(s * 0.805)
    w_bar = int(s * 0.141)
    draw.rectangle([x0, y0, x0 + w_bar, y1], fill=gold)

    # Three right-hand angled bars
    rx = int(s * 0.395)
    bh = int(s * 0.141)
    cut = int(s * 0.098)

    # Top bar
    rt = int(s * 0.797)
    draw.polygon([(rx, y0), (rt, y0), (rt - cut, y0 + bh), (rx, y0 + bh)], fill=gold)

    # Middle bar
    ym = int(s * 0.430)
    rm = int(s * 0.648)
    draw.polygon([(rx, ym), (rm, ym), (rm - cut, ym + bh), (rx, ym + bh)], fill=gold)

    # Bottom bar
    yb = y1 - bh
    draw.polygon([(rx, yb), (rt, yb), (rt - cut, y1), (rx, y1)], fill=gold)

    final = img.resize((size, size), Image.Resampling.LANCZOS)
    final.save(dest, format="PNG", optimize=True)
    return dest


if __name__ == "__main__":
    out = export_avatar()
    print(f"Exported 640x640 BotFather avatar to {out}")
