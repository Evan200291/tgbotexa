"""Render the 4 step-by-step Outline setup guide images used by the bot's guide menu.

Run:  python scripts/make_guide_images.py
Output: exabyte_bot/assets/guides/step1.jpg .. step4.jpg (1080x1350)
"""

from __future__ import annotations

import base64
import io
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1350
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "exabyte_bot" / "assets" / "guides"
AVATAR_PNG = ROOT / "exabyte_bot" / "webapp" / "static" / "brand" / "avatar-640.png"
FONT_MM = ROOT / "Burmese Handwriting.ttf"
CHROME_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]

NAVY_TOP = (8, 16, 38)
NAVY_BOT = (14, 40, 70)
CYAN = (34, 211, 238)
GREEN = (52, 211, 153)
ORANGE = (255, 122, 26)
WHITE = (255, 255, 255)
OUTLINE_TEAL = (0, 150, 136)
OUTLINE_DARK = (38, 50, 56)
TG_BG = (14, 22, 33)
TG_HEADER = (23, 33, 43)
TG_BUBBLE = (24, 37, 51)

FONT_DIRS = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu")]


def font(names: list[str], size: int) -> ImageFont.FreeTypeFont:
    for d in FONT_DIRS:
        for n in names:
            p = d / n
            if p.is_file():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def F(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return font(["segoeuib.ttf", "DejaVuSans-Bold.ttf"] if bold else ["segoeui.ttf", "DejaVuSans.ttf"], size)


def MONO(size: int) -> ImageFont.FreeTypeFont:
    return font(["consola.ttf", "DejaVuSansMono.ttf"], size)


def background() -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        c = tuple(int(NAVY_TOP[i] + (NAVY_BOT[i] - NAVY_TOP[i]) * k) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    # subtle grid
    for x in range(0, W, 60):
        d.line([(x, 0), (x, H)], fill=(20, 45, 75))
    for y in range(0, H, 60):
        d.line([(0, y), (W, y)], fill=(20, 45, 75))
    return img


def header(img: Image.Image, step: int, title: str) -> None:
    d = ImageDraw.Draw(img)
    chrome = next((p for p in CHROME_PATHS if p.is_file()), None)
    if not (chrome and FONT_MM.is_file()):
        d.rounded_rectangle([50, 46, 270, 126], radius=40, fill=CYAN)
        d.text((160, 86), f"STEP {step}", font=F(46, True), fill=NAVY_TOP, anchor="mm")
        d.text((300, 86), title, font=F(52, True), fill=WHITE, anchor="lm")
    d.text((W - 50, H - 30), "EXABYTE DIGITAL STORE", font=F(26, True), fill=(120, 170, 200), anchor="rm")


def overlay_burmese_header(img: Image.Image, step: int, mm_title: str) -> Image.Image:
    chrome = next((p for p in CHROME_PATHS if p.is_file()), None)
    if not (chrome and FONT_MM.is_file()):
        return img
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=98)
    bg_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    font_b64 = base64.b64encode(FONT_MM.read_bytes()).decode("ascii")
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@font-face {{
  font-family: 'BurmeseHandwriting';
  src: url('data:font/ttf;base64,{font_b64}') format('truetype');
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  width: 1080px; height: 1350px; overflow: hidden;
  background: url('data:image/jpeg;base64,{bg_b64}') no-repeat center/cover;
  font-family: 'BurmeseHandwriting', 'Segoe UI', sans-serif;
}}
.hdr {{
  position: absolute; left: 46px; right: 46px; top: 44px; height: 86px;
  display: flex; align-items: center; gap: 22px;
}}
.badge {{
  height: 80px; padding: 0 32px; border-radius: 40px;
  background: #22d3ee; color: #081026;
  font-size: 42px; font-weight: 900;
  display: flex; align-items: center; justify-content: center;
  white-space: nowrap;
}}
.title {{
  color: #ffffff; font-size: 46px; font-weight: 800;
  white-space: nowrap;
}}
</style></head><body>
<div class="hdr">
  <div class="badge">အဆင့် {step}</div>
  <div class="title">{mm_title}</div>
</div>
</body></html>"""
    with tempfile.TemporaryDirectory() as tmpdir:
        html_file = Path(tmpdir) / "step.html"
        png_file = Path(tmpdir) / "step.png"
        html_file.write_text(html, encoding="utf-8")
        subprocess.run(  # noqa: S603
            [
                str(chrome),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--window-size=1080,1350",
                f"--screenshot={png_file}",
                html_file.as_uri(),
            ],
            check=True,
        )
        return Image.open(io.BytesIO(png_file.read_bytes())).convert("RGB")


PX0, PY0, PX1, PY1 = 250, 175, 830, 1300  # phone body
SX0, SY0, SX1, SY1 = PX0 + 22, PY0 + 22, PX1 - 22, PY1 - 22  # screen


def phone(img: Image.Image, screen_bg: tuple[int, int, int]) -> ImageDraw.ImageDraw:
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [PX0 + 10, PY0 + 20, PX1 + 10, PY1 + 20], radius=80, fill=(0, 0, 0, 160)
    )
    blurred = shadow.filter(ImageFilter.GaussianBlur(24))
    img.paste(blurred, (0, 0), blurred)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([PX0, PY0, PX1, PY1], radius=80, fill=(30, 34, 40), outline=(90, 100, 115), width=4)
    d.rounded_rectangle([SX0, SY0, SX1, SY1], radius=60, fill=screen_bg)
    # dynamic island
    cx = (SX0 + SX1) // 2
    d.rounded_rectangle([cx - 80, SY0 + 16, cx + 80, SY0 + 52], radius=18, fill=(0, 0, 0))
    return d


def status_bar(d: ImageDraw.ImageDraw, color: tuple[int, int, int]) -> None:
    d.text((SX0 + 48, SY0 + 34), "9:41", font=F(26, True), fill=color, anchor="lm")
    d.text((SX1 - 48, SY0 + 34), "5G  100%", font=F(22, True), fill=color, anchor="rm")


def highlight(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int], pad: int = 14) -> None:
    x0, y0, x1, y1 = box
    for i in range(3):
        d.rounded_rectangle(
            [x0 - pad - i * 2, y0 - pad - i * 2, x1 + pad + i * 2, y1 + pad + i * 2],
            radius=22 + i * 2,
            outline=ORANGE,
            width=5,
        )


def tap_dot(img: Image.Image, cx: int, cy: int) -> None:
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], fill=(255, 122, 26, 70))
    od.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=(255, 122, 26, 200), outline=WHITE, width=4)
    img.paste(ov, (0, 0), ov)


def arrow(d: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int]) -> None:
    d.line([start, end], fill=ORANGE, width=10)
    ex, ey = end
    sx, sy = start
    import math

    ang = math.atan2(ey - sy, ex - sx)
    L = 38
    p1 = (ex - L * math.cos(ang - 0.5), ey - L * math.sin(ang - 0.5))
    p2 = (ex - L * math.cos(ang + 0.5), ey - L * math.sin(ang + 0.5))
    d.polygon([end, p1, p2], fill=ORANGE)


def outline_logo(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=OUTLINE_TEAL)
    d.ellipse([cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55], fill=WHITE)
    d.ellipse([cx - r * 0.3, cy - r * 0.3, cx + r * 0.3, cy + r * 0.3], fill=OUTLINE_TEAL)


def outline_topbar(d: ImageDraw.ImageDraw) -> tuple[int, int, int, int]:
    top = SY0 + 70
    d.rectangle([SX0, top, SX1, top + 110], fill=OUTLINE_DARK)
    # 3-bar hamburger menu icon
    for dy in (-14, 0, 14):
        d.line([(SX0 + 38, top + 55 + dy), (SX0 + 74, top + 55 + dy)], fill=WHITE, width=5)
    d.text((SX0 + 104, top + 55), "Outline", font=F(38, True), fill=WHITE, anchor="lm")
    plus_box = (SX1 - 100, top + 20, SX1 - 30, top + 90)
    d.text(((plus_box[0] + plus_box[2]) // 2, top + 52), "+", font=F(72, True), fill=WHITE, anchor="mm")
    return plus_box


KEY_SHORT = "ss://Y2hhY2hhMjAtaWV0Zi1w..."


def step1() -> Image.Image:
    img = background()
    header(img, 1, "Tap the key to copy")
    d = phone(img, TG_BG)
    status_bar(d, WHITE)
    top = SY0 + 70
    d.rectangle([SX0, top, SX1, top + 100], fill=TG_HEADER)
    d.text((SX0 + 36, top + 50), "‹", font=F(56, True), fill=CYAN, anchor="lm")
    if AVATAR_PNG.is_file():
        av = Image.open(AVATAR_PNG).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        mask = Image.new("L", (64, 64), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 63, 63), fill=255)
        img.paste(av.convert("RGB"), (SX0 + 80, top + 18), mask)
        d = ImageDraw.Draw(img)
        d.ellipse([SX0 + 80, top + 18, SX0 + 144, top + 82], outline=CYAN, width=2)
    else:
        d.ellipse([SX0 + 80, top + 18, SX0 + 144, top + 82], fill=CYAN)
        d.text((SX0 + 112, top + 50), "E", font=F(36, True), fill=NAVY_TOP, anchor="mm")
    d.text((SX0 + 160, top + 34), "Exabyte Digital Store", font=F(28, True), fill=WHITE, anchor="lm")
    d.text((SX0 + 160, top + 68), "bot", font=F(22), fill=(130, 150, 170), anchor="lm")

    bx0, by0, bx1, by1 = SX0 + 26, top + 150, SX1 - 60, top + 690
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=26, fill=TG_BUBBLE)
    y = by0 + 34
    d.text((bx0 + 28, y), "Exabyte Digital Store", font=F(28, True), fill=WHITE)
    y += 48
    d.line([bx0 + 28, y, bx0 + 300, y], fill=WHITE, width=2)
    y += 26
    d.text((bx0 + 28, y), "Your VPN Key", font=F(28, True), fill=WHITE)
    y += 52
    d.text((bx0 + 28, y), "• Status: Active", font=F(25), fill=(200, 210, 220))
    y += 42
    d.text((bx0 + 28, y), "• Expiry: 30 days left", font=F(25), fill=(200, 210, 220))
    y += 62
    d.text((bx0 + 28, y), "Key Link (tap to copy):", font=F(26, True), fill=WHITE)
    y += 50
    code = (bx0 + 24, y, bx1 - 24, y + 120)
    d.rounded_rectangle(code, radius=14, fill=(32, 52, 72))
    d.text((code[0] + 18, y + 20), "ss://Y2hhY2hhMjAtaWV0", font=MONO(26), fill=(120, 200, 255))
    d.text((code[0] + 18, y + 62), "Zi1w...@tpone:45349", font=MONO(26), fill=(120, 200, 255))
    highlight(d, code, pad=10)
    tap_dot(img, (code[0] + code[2]) // 2 + 60, y + 70)
    d = ImageDraw.Draw(img)

    toast = (SX0 + 70, SY1 - 190, SX1 - 70, SY1 - 110)
    d.rounded_rectangle(toast, radius=40, fill=(60, 70, 85))
    tcx, tcy = toast[0] + 54, (toast[1] + toast[3]) // 2
    d.ellipse([tcx - 18, tcy - 18, tcx + 18, tcy + 18], fill=GREEN)
    d.line([(tcx - 8, tcy), (tcx - 2, tcy + 7), (tcx + 10, tcy - 7)], fill=NAVY_TOP, width=4)
    d.text(((toast[0] + toast[2]) // 2 + 18, tcy), "Copied to clipboard",
           font=F(30, True), fill=WHITE, anchor="mm")
    return img


def step2() -> Image.Image:
    img = background()
    header(img, 2, "Open Outline, tap  +")
    d = phone(img, (245, 247, 248))
    status_bar(d, WHITE)
    d.rectangle([SX0 + 40, SY0, SX1 - 40, SY0 + 70], fill=OUTLINE_DARK)
    d.rectangle([SX0, SY0 + 60, SX1, SY0 + 70], fill=OUTLINE_DARK)
    d.rounded_rectangle([SX0, SY0, SX1, SY0 + 120], radius=60, fill=OUTLINE_DARK)
    d.rectangle([SX0, SY0 + 60, SX1, SY0 + 70], fill=OUTLINE_DARK)
    status_bar(d, WHITE)
    cx0 = (SX0 + SX1) // 2
    d.rounded_rectangle([cx0 - 80, SY0 + 16, cx0 + 80, SY0 + 52], radius=18, fill=(0, 0, 0))
    plus = outline_topbar(d)
    cx, cy = (SX0 + SX1) // 2, SY0 + 520
    outline_logo(d, cx, cy, 110)
    d.text((cx, cy + 180), "Add a server to", font=F(36, True), fill=(60, 70, 80), anchor="mm")
    d.text((cx, cy + 230), "get started", font=F(36, True), fill=(60, 70, 80), anchor="mm")
    d.text((cx, cy + 300), "Tap + to add a new server", font=F(26), fill=(120, 130, 140), anchor="mm")
    highlight(d, plus, pad=8)
    arrow(d, (SX1 - 200, SY0 + 380), (plus[0] + 20, plus[3] + 24))
    return img


def step3() -> Image.Image:
    img = background()
    header(img, 3, "Tap  ADD SERVER")
    d = phone(img, (245, 247, 248))
    d.rounded_rectangle([SX0, SY0, SX1, SY0 + 120], radius=60, fill=OUTLINE_DARK)
    d.rectangle([SX0, SY0 + 60, SX1, SY0 + 70], fill=OUTLINE_DARK)
    status_bar(d, WHITE)
    cx0 = (SX0 + SX1) // 2
    d.rounded_rectangle([cx0 - 80, SY0 + 16, cx0 + 80, SY0 + 52], radius=18, fill=(0, 0, 0))
    outline_topbar(d)
    outline_logo(d, cx0, SY0 + 520, 110)
    # dim overlay
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle([SX0, SY0 + 180, SX1, SY1], radius=60, fill=(0, 0, 0, 140))
    img.paste(ov, (0, 0), ov)
    d = ImageDraw.Draw(img)
    dx0, dy0, dx1, dy1 = SX0 + 34, SY0 + 360, SX1 - 34, SY0 + 820
    d.rounded_rectangle([dx0, dy0, dx1, dy1], radius=24, fill=WHITE)
    d.text((dx0 + 36, dy0 + 50), "Access key detected", font=F(36, True), fill=(30, 40, 50), anchor="lm")
    d.text(
        (dx0 + 36, dy0 + 110), "Add this server to Outline?", font=F(26), fill=(100, 110, 120), anchor="lm"
    )
    fld = (dx0 + 36, dy0 + 160, dx1 - 36, dy0 + 240)
    d.rounded_rectangle(fld, radius=10, fill=(238, 241, 243), outline=OUTLINE_TEAL, width=3)
    d.text((fld[0] + 18, (fld[1] + fld[3]) // 2), KEY_SHORT, font=MONO(24), fill=(40, 50, 60), anchor="lm")
    ign = (dx0 + 24, dy1 - 120, dx0 + 170, dy1 - 40)
    add = (dx1 - 285, dy1 - 120, dx1 - 36, dy1 - 40)
    d.text(((ign[0] + ign[2]) // 2, (ign[1] + ign[3]) // 2), "IGNORE", font=F(28, True),
           fill=(110, 120, 130), anchor="mm")
    d.rounded_rectangle(add, radius=12, fill=OUTLINE_TEAL)
    d.text(((add[0] + add[2]) // 2, (add[1] + add[3]) // 2), "ADD SERVER", font=F(28, True),
           fill=WHITE, anchor="mm")
    highlight(d, add, pad=10)
    tap_dot(img, (add[0] + add[2]) // 2 + 40, (add[1] + add[3]) // 2 + 10)
    return img


def step4() -> Image.Image:
    img = background()
    header(img, 4, "Tap CONNECT — done!")
    d = phone(img, (245, 247, 248))
    d.rounded_rectangle([SX0, SY0, SX1, SY0 + 120], radius=60, fill=OUTLINE_DARK)
    d.rectangle([SX0, SY0 + 60, SX1, SY0 + 70], fill=OUTLINE_DARK)
    status_bar(d, WHITE)
    cx0 = (SX0 + SX1) // 2
    d.rounded_rectangle([cx0 - 80, SY0 + 16, cx0 + 80, SY0 + 52], radius=18, fill=(0, 0, 0))
    outline_topbar(d)
    card = (SX0 + 30, SY0 + 210, SX1 - 30, SY0 + 860)
    d.rounded_rectangle(card, radius=22, fill=WHITE, outline=(220, 225, 230), width=2)
    d.text((card[0] + 34, card[1] + 46), "Exabyte", font=F(36, True), fill=(30, 40, 50), anchor="lm")
    d.text((card[0] + 34, card[1] + 94), "tpone.lhpvpn.online", font=F(26), fill=(110, 120, 130), anchor="lm")
    for dy in (-12, 0, 12):
        d.ellipse(
            [card[2] - 44, card[1] + 54 + dy - 4, card[2] - 36, card[1] + 54 + dy + 4],
            fill=(110, 120, 130),
        )
    bcx, bcy, r = (card[0] + card[2]) // 2, card[1] + 330, 135
    d.ellipse([bcx - r - 18, bcy - r - 18, bcx + r + 18, bcy + r + 18], fill=(200, 240, 225))
    d.ellipse([bcx - r, bcy - r, bcx + r, bcy + r], fill=GREEN)
    d.ellipse([bcx - 54, bcy - 54, bcx + 54, bcy + 54], outline=WHITE, width=12)
    d.line([bcx, bcy - 78, bcx, bcy - 18], fill=WHITE, width=14)
    d.text((bcx, card[3] - 110), "Connected", font=F(40, True), fill=(16, 160, 110), anchor="mm")
    d.text((bcx, card[3] - 54), "DISCONNECT", font=F(25, True), fill=(110, 120, 130), anchor="mm")
    highlight(d, (bcx - r - 18, bcy - r - 18, bcx + r + 18, bcy + r + 18), pad=12)
    pop = (SX0 + 50, SY1 - 195, SX1 - 50, SY1 - 65)
    d.rounded_rectangle(pop, radius=20, fill=(55, 65, 80))
    d.text((pop[0] + 30, pop[1] + 40), "Connection request", font=F(26, True), fill=WHITE, anchor="lm")
    d.text((pop[0] + 30, pop[1] + 88), "Allow VPN?", font=F(24), fill=(200, 210, 220), anchor="lm")
    d.text((pop[2] - 36, pop[1] + 88), "OK", font=F(30, True), fill=CYAN, anchor="rm")
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    steps = [
        (step1, "Key ကို နှိပ်၍ Copy ကူးပါ"),
        (step2, "Outline ဖွင့်ပြီး + ကိုနှိပ်ပါ"),
        (step3, "ADD SERVER ကို နှိပ်ပါ"),
        (step4, "CONNECT နှိပ်ပါ — သုံးနိုင်ပါပြီ!"),
    ]
    for i, (fn, mm_title) in enumerate(steps, start=1):
        p = OUT / f"step{i}.jpg"
        im = overlay_burmese_header(fn(), i, mm_title)
        im.save(p, quality=92, optimize=True)
        print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

