"""Render the professional 2048x2048 Exabyte VPN Free Trial promo posters using
`Burmese Handwriting.ttf` (shaped via Headless Chrome / DirectWrite HarfBuzz),
the real Exabyte logo inside the phone screen, and both KBZ Pay + Wave Pay badges.
"""

from __future__ import annotations

import base64
import io
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ART_DIR = Path(r"C:\Users\User\.gemini\antigravity\brain\3947fff5-dee6-4ab7-a57e-bd1f56b78ebc")
OUT_DIR = ROOT / "exabyte-jpgs"
FONT_PATH = ROOT / "Burmese Handwriting.ttf"
CHROME_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]


def prepare_clean_background() -> Image.Image:
    src = Image.open(ART_DIR / "exabyte_vpn_free_trial_poster_v2_1793795225176.jpg").convert("RGBA")
    logo_sym = Image.open(
        OUT_DIR / "exabyte-jpg-colour-options" / "symbol-02-white-on-navy.jpg"
    ).convert("RGBA")

    # 1. Replace green circle avatar in phone header (cx=445, cy=396) with actual Exabyte symbol
    # First clear the old green avatar circle cleanly with the phone header background (#f4f5f7)
    ImageDraw.Draw(src).ellipse((421, 371, 471, 421), fill=(244, 245, 247, 255))
    av_size = 44
    av = logo_sym.resize((av_size, av_size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (av_size, av_size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, av_size - 1, av_size - 1), fill=255)
    src.paste(av, (445 - av_size // 2, 396 - av_size // 2), mask)
    ImageDraw.Draw(src).ellipse(
        (445 - 22, 396 - 22, 445 + 22, 396 + 22), outline=(14, 116, 144, 255), width=2
    )

    # 3. Clean out old overlays while keeping the 3D server racks, 3D phone, and 3D Outline sphere
    rgb = src.convert("RGB")

    def blur_patch(
        box: tuple[int, int, int, int],
        fill_top: tuple[int, int, int],
        fill_bot: tuple[int, int, int],
    ) -> None:
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        grad = Image.new("RGB", (w, h))
        gd = ImageDraw.Draw(grad)
        for y in range(h):
            k = y / max(h - 1, 1)
            c = tuple(int(fill_top[i] + (fill_bot[i] - fill_top[i]) * k) for i in range(3))
            gd.line([(0, y), (w, y)], fill=c)
        # Blend 75% dark gradient + 25% blurred background so server rack lights show through
        crop_blur = rgb.crop(box).filter(ImageFilter.GaussianBlur(28))
        blended = Image.blend(grad, crop_blur, 0.22)
        mask_p = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask_p).rounded_rectangle((4, 4, w - 5, h - 5), radius=18, fill=255)
        mask_p = mask_p.filter(ImageFilter.GaussianBlur(6))
        rgb.paste(blended, (x0, y0), mask_p)

    # Remove the cyan sub-banner (y: 232..302) and the "Get your key in 10 seconds" pill
    blur_patch((85, 232, 940, 303), (6, 20, 38), (8, 26, 48))
    blur_patch((468, 312, 872, 374), (6, 22, 42), (8, 28, 50))
    # Remove the entire bottom area from y=636..1020 so we can render crisp Burmese & payment cards
    blur_patch((30, 636, 994, 1018), (6, 18, 34), (4, 12, 24))

    return rgb


def build_html(bg_b64: str, font_b64: str, burmese_title: bool, clean_top_b64: str) -> str:
    bg_use = clean_top_b64 if burmese_title else bg_b64
    top_title_html = (
        '<div class="top-title-mm">အခမဲ့ စမ်းသပ်သုံးကြည့်ပါ</div>'
        if burmese_title
        else ""
    )
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @font-face {{
    font-family: 'BurmeseHandwriting';
    src: url('data:font/ttf;base64,{font_b64}') format('truetype');
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: 1024px;
    height: 1024px;
    overflow: hidden;
    background: url('data:image/jpeg;base64,{bg_use}') no-repeat center/cover;
    font-family: 'BurmeseHandwriting', 'Segoe UI', sans-serif;
    position: relative;
    color: #ffffff;
  }}
  .top-title-mm {{
    position: absolute;
    left: 60px;
    width: 715px;
    top: 118px;
    text-align: center;
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 74px;
    font-weight: 900;
    color: #6ee7b7;
    -webkit-text-stroke: 2px #a7f3d0;
    text-shadow: 0 0 22px rgba(52, 211, 153, 0.9), 0 4px 14px rgba(0, 0, 0, 0.95);
    letter-spacing: 1px;
    white-space: nowrap;
  }}
  /* Clean Telegram sent bubble over the phone's 'uük 18:33' */
  .phone-sent-bubble {{
    position: absolute;
    left: 380px;
    top: 416px;
    width: 89px;
    height: 36px;
    background: #d8f5c7;
    border-radius: 12px 12px 3px 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    font-family: 'Segoe UI', sans-serif;
    font-size: 11px;
    font-weight: 700;
    color: #1e4620;
    transform: rotate(-1.5deg);
    box-shadow: 0 1px 2px rgba(0,0,0,0.12);
  }}
  .phone-sent-bubble span {{
    font-size: 9px;
    font-weight: 600;
    color: #4b834d;
    margin-top: 2px;
  }}
  /* Sub-banner pill (y: 238..296) */
  .sub-banner {{
    position: absolute;
    left: 88px;
    right: 88px;
    top: 238px;
    height: 58px;
    border-radius: 30px;
    background: linear-gradient(90deg, #22d3ee 0%, #38bdf8 50%, #22d3ee 100%);
    box-shadow: 0 0 24px rgba(34, 211, 238, 0.55), inset 0 2px 4px rgba(255,255,255,0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 31px;
    font-weight: 800;
    color: #041326;
    letter-spacing: 0.5px;
  }}
  /* 10-second pill (Image 3: x: 472..888, y: 316..370) */
  .ten-sec-pill {{
    position: absolute;
    left: 472px;
    width: 424px;
    top: 315px;
    height: 54px;
    border-radius: 28px;
    background: linear-gradient(180deg, rgba(12, 34, 62, 0.95), rgba(7, 20, 38, 0.96));
    border: 2px solid #38bdf8;
    box-shadow: 0 0 18px rgba(56, 189, 248, 0.45), inset 0 1px 8px rgba(56, 189, 248, 0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 25px;
    font-weight: 700;
    color: #ffffff;
  }}
  .ten-sec-pill .hl {{
    color: #fde68a;
    font-weight: 800;
  }}
  /* 3-Step Bar (Image 2: x: 56..968, y: 642..696) */
  .steps-bar {{
    position: absolute;
    left: 56px;
    right: 56px;
    top: 642px;
    height: 54px;
    border-radius: 28px;
    background: linear-gradient(180deg, rgba(10, 30, 56, 0.95), rgba(6, 18, 36, 0.96));
    border: 2px solid rgba(56, 189, 248, 0.75);
    box-shadow: 0 0 20px rgba(34, 211, 238, 0.28);
    display: flex;
    align-items: center;
    justify-content: space-around;
    padding: 0 20px;
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 23px;
    font-weight: 700;
  }}
  .step-item {{
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .step-num {{
    color: #38bdf8;
    font-weight: 800;
  }}
  .step-green {{
    color: #6ee7b7;
    font-weight: 800;
  }}
  .step-sep {{
    color: #38bdf8;
    font-size: 28px;
    font-weight: 300;
    opacity: 0.85;
  }}
  /* 3 Pricing Cards (y: 710..814) */
  .plans-row {{
    position: absolute;
    left: 56px;
    right: 56px;
    top: 710px;
    height: 104px;
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 16px;
  }}
  .plan-card {{
    border-radius: 18px;
    background: linear-gradient(180deg, rgba(14, 38, 68, 0.92), rgba(8, 22, 42, 0.95));
    border: 1.8px solid rgba(56, 189, 248, 0.65);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.55), inset 0 1px 10px rgba(56, 189, 248, 0.2);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 8px 10px;
  }}
  .plan-dur {{
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 24px;
    color: #7dd3fc;
    font-weight: 700;
    margin-bottom: 2px;
  }}
  .plan-price {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 40px;
    font-weight: 900;
    color: #ffffff;
    line-height: 1.05;
  }}
  .plan-price span {{
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 28px;
    color: #38bdf8;
    font-weight: 800;
    margin-left: 4px;
  }}
  /* GB Data Plans subtitle bar (y: 826..868) */
  .gb-note {{
    position: absolute;
    left: 56px;
    right: 56px;
    top: 826px;
    height: 44px;
    border-radius: 14px;
    background: rgba(12, 32, 58, 0.88);
    border: 1.5px solid rgba(52, 211, 153, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 20px;
    color: #e2e8f0;
    gap: 10px;
    white-space: nowrap;
  }}
  .gb-note b {{
    color: #6ee7b7;
  }}
  /* Bottom CTA + Payment Row (y: 884..988) */
  .bottom-row {{
    position: absolute;
    left: 56px;
    right: 56px;
    top: 884px;
    height: 100px;
    display: grid;
    grid-template-columns: 1.35fr 1fr;
    gap: 16px;
  }}
  .tg-cta {{
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(10, 28, 52, 0.96), rgba(6, 16, 32, 0.98));
    border: 2px solid rgba(56, 189, 248, 0.8);
    box-shadow: 0 0 24px rgba(56, 189, 248, 0.25);
    display: flex;
    align-items: center;
    padding: 0 20px;
    gap: 16px;
  }}
  .tg-icon {{
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: linear-gradient(135deg, #38bdf8, #0284c7);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 0 14px rgba(56, 189, 248, 0.6);
  }}
  .tg-text-wrap {{
    display: flex;
    flex-direction: column;
  }}
  .tg-sub {{
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 21px;
    color: #7dd3fc;
  }}
  .tg-handle {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 34px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: 0.3px;
  }}
  .pay-card {{
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(14, 38, 68, 0.96), rgba(8, 22, 42, 0.98));
    border: 2px solid rgba(56, 189, 248, 0.8);
    box-shadow: 0 0 24px rgba(56, 189, 248, 0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 14px;
    padding: 0 16px;
  }}
  .pay-badge-kbz {{
    width: 78px;
    height: 66px;
    border-radius: 14px;
    background: linear-gradient(145deg, #0054a6, #003b75);
    border: 1.5px solid rgba(255,255,255,0.35);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  }}
  .pay-badge-kbz .k1 {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 20px;
    font-weight: 900;
    color: #ffffff;
    line-height: 1;
  }}
  .pay-badge-kbz .k2 {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 16px;
    font-weight: 700;
    color: #93c5fd;
    line-height: 1.1;
  }}
  .pay-badge-wave {{
    width: 86px;
    height: 66px;
    border-radius: 14px;
    background: linear-gradient(145deg, #facc15, #eab308);
    border: 1.5px solid rgba(255,255,255,0.5);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  }}
  .pay-badge-wave .w1 {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 20px;
    font-weight: 900;
    color: #0f172a;
    line-height: 1;
  }}
  .pay-badge-wave .w2 {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 15px;
    font-weight: 800;
    color: #1d4ed8;
    line-height: 1.1;
  }}
  .pay-lbl {{
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0;
    line-height: 1.25;
  }}
</style>
</head>
<body>
  {top_title_html}
  <div class="phone-sent-bubble">/start <span>18:33 ✓✓</span></div>
  <div class="sub-banner">5 GB • 7 ရက် (အပတ်စဉ်) • ငွေကြိုပေးရန် မလိုပါ</div>

  <div class="ten-sec-pill">
    <span>⚡</span>
    <span class="hl">၁၀ စက္ကန့်အတွင်း</span>
    <span>Key ချက်ချင်းရယူပါ</span>
  </div>

  <div class="steps-bar">
    <div class="step-item">
      <span class="step-num">1.</span> <span class="step-green">@exabytedigitalsbot</span> သို့ဝင်ပါ
    </div>
    <div class="step-sep">›</div>
    <div class="step-item">
      <span class="step-num">2.</span> <span class="step-green">အခမဲ့ စမ်းသပ်</span> နှိပ်ပါ
    </div>
    <div class="step-sep">›</div>
    <div class="step-item"><span class="step-num">3.</span> ချိတ်ဆက် အသုံးပြုပါ</div>
  </div>

  <div class="plans-row">
    <div class="plan-card">
      <div class="plan-dur">1 လ Plan (30 ရက်)</div>
      <div class="plan-price">5,000<span>Ks</span></div>
    </div>
    <div class="plan-card">
      <div class="plan-dur">3 လ Plan (90 ရက်)</div>
      <div class="plan-price">14,500<span>Ks</span></div>
    </div>
    <div class="plan-card">
      <div class="plan-dur">6 လ Plan (180 ရက်)</div>
      <div class="plan-price">29,000<span>Ks</span></div>
    </div>
  </div>

  <div class="gb-note">
    <span>♾️ <b>Unlimited Plan</b></span>
    <span>•</span>
    <span>🌐 <b>100GB / 300GB / 600GB Plan</b> (Server Region အားလုံး ပြောင်းသုံးနိုင်သည်)</span>
  </div>

  <div class="bottom-row">
    <div class="tg-cta">
      <div class="tg-icon">
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
          <path d="M21.2 4.4L2.9 11.5c-1.2.5-1.2 1.2-.2 1.5l4.7 1.5 10.8-6.8c.5-.3 1-.1.6.2
            l-8.8 7.9-.3 4.8c.5 0 .7-.2 1-.5l2.4-2.3 5 3.7c.9.5 1.6.2 1.8-.9L23 6
            c.3-1.3-.5-1.9-1.8-1.6z" fill="#ffffff"/>
        </svg>
      </div>
      <div class="tg-text-wrap">
        <div class="tg-sub">အခုပဲ အခမဲ့ စမ်းသပ်ရန် 👉</div>
        <div class="tg-handle">@exabytedigitalsbot</div>
      </div>
    </div>

    <div class="pay-card">
      <div class="pay-badge-kbz">
        <div class="k1">KBZ</div>
        <div class="k2">Pay</div>
      </div>
      <div class="pay-badge-wave">
        <div class="w1">Wave</div>
        <div class="w2">Pay</div>
      </div>
      <div class="pay-lbl">ဖြင့် လွယ်ကူစွာ<br>ဝယ်ယူနိုင်သည်</div>
    </div>
  </div>
</body>
</html>
"""


def main() -> None:
    chrome = next((p for p in CHROME_PATHS if p.is_file()), None)
    if chrome is None:
        raise RuntimeError("Chrome/Edge not found")

    bg_img = prepare_clean_background()
    buf = io.BytesIO()
    bg_img.save(buf, format="JPEG", quality=98)
    bg_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    # Prepare a version with left "FREE TRIAL" cleared while keeping the neon gift icon
    bg_top_clean = bg_img.copy()
    grad = Image.new("RGB", (722, 128), (6, 20, 38))
    bg_top_clean.paste(grad, (68, 104))
    buf2 = io.BytesIO()
    bg_top_clean.save(buf2, format="JPEG", quality=98)
    clean_top_b64 = base64.b64encode(buf2.getvalue()).decode("ascii")

    font_b64 = base64.b64encode(FONT_PATH.read_bytes()).decode("ascii")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        for burmese_title, suffix in [(False, "poster"), (True, "poster_burmese_title")]:
            html = build_html(bg_b64, font_b64, burmese_title, clean_top_b64)
            html_file = Path(tmpdir) / f"{suffix}.html"
            png_file = Path(tmpdir) / f"{suffix}.png"
            html_file.write_text(html, encoding="utf-8")

            subprocess.run(  # noqa: S603
                [
                    str(chrome),
                    "--headless=new",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    "--window-size=1024,1024",
                    "--force-device-scale-factor=2",
                    f"--screenshot={png_file}",
                    html_file.as_uri(),
                ],
                check=True,
            )
            im = Image.open(io.BytesIO(png_file.read_bytes())).convert("RGB")
            hi_path = OUT_DIR / f"exabyte_vpn_free_trial_{suffix}_2048x2048_highres.jpg"
            std_path = OUT_DIR / f"exabyte_vpn_free_trial_{suffix}_1080x1080.jpg"
            im.save(hi_path, quality=100, subsampling=0)
            im.resize((1080, 1080), Image.Resampling.LANCZOS).save(
                std_path, quality=100, subsampling=0
            )
            im.resize((1080, 1080), Image.Resampling.LANCZOS).save(
                ART_DIR / f"exabyte_vpn_free_trial_{suffix}_preview.jpg", quality=96
            )
            print("Saved:", hi_path.name, std_path.name)


if __name__ == "__main__":
    main()

