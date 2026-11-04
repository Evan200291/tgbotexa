"""Render the Exabyte Digital Store promotional poster (based on the official example layout)
and the professional Burmese Bot Welcome Banner (640x360 & 1280x720 HD) using
`Burmese Handwriting.ttf` via Headless Chrome (HarfBuzz / DirectWrite shaping).
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
UPLOAD_DIR = ART_DIR / ".user_uploaded"
OUT_DIR = ROOT / "exabyte-jpgs"
FONT_PATH = ROOT / "Burmese Handwriting.ttf"
LOGO_HORIZ_PATH = OUT_DIR / "exabyte-jpg" / "exabyte-logo-horizontal.jpg"
LOGO_SYM_PATH = OUT_DIR / "exabyte-jpg-colour-options" / "symbol-02-white-on-navy.jpg"
KBZ_LOGO_PATH = ART_DIR / "kbz_logo_official.png"
WAVE_LOGO_PATH = ART_DIR / "wave_logo_official.png"

CHROME_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]


def prepare_example_base() -> Image.Image:
    """Prepare the 1024x1024 base canvas from media_1793795035392_410ea9b0.jpg:
    - Replace the old 'အကောင်းဆုံး VPN SERVERS' area with seamless server rack texture from bg_left
      so the server room background and the top arc of the 3D green sphere are completely smooth,
      round, and natural with ZERO black boxes or harsh cuts.
    - Clean the right cards area and the bottom area below the pedestal for crisp Chrome 2048x2048
      HTML rendering with the user's official KBZPay and Wave Money logos.
    """
    raw = Image.open(UPLOAD_DIR / "media_1793795035392_410ea9b0.jpg").convert("RGB")
    sq = raw.crop((0, 74, 628, 702)).resize((1024, 1024), Image.Resampling.LANCZOS)

    # 1. Seamless server rack texture blend over the old VPN SERVERS text (x: 0..545, y: 155..436)
    bg_left_path = ART_DIR / "bg_left.png"
    if not bg_left_path.exists():
        im2 = Image.open(UPLOAD_DIR / "media_1793797314843_2531e800.jpg")
        im2.crop((0, 150, 150, 600)).save(bg_left_path)
    bg_left = Image.open(bg_left_path)
    bg_scaled = bg_left.crop((0, 20, 145, 450)).resize((545, 360), Image.Resampling.LANCZOS)
    darkened = Image.blend(bg_scaled, Image.new("RGB", (545, 360), (5, 14, 28)), 0.35)

    blend_mask = Image.new("L", (1024, 1024), 0)
    b_draw = ImageDraw.Draw(blend_mask)
    b_draw.rectangle((0, 155, 545, 436), fill=255)
    b_draw.rectangle((0, 436, 160, 448), fill=255)
    b_draw.rectangle((380, 436, 545, 448), fill=255)
    blend_mask = blend_mask.filter(ImageFilter.GaussianBlur(6))

    sq.paste(darkened, (0, 150), blend_mask.crop((0, 150, 545, 510)))

    # 2. Clean top header background for crisp typography
    def clean_region(
        box: tuple[int, int, int, int], c_top: tuple[int, int, int], c_bot: tuple[int, int, int]
    ) -> None:
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        grad = Image.new("RGB", (w, h))
        gd = ImageDraw.Draw(grad)
        for y in range(h):
            k = y / max(h - 1, 1)
            c = tuple(int(c_top[i] + (c_bot[i] - c_top[i]) * k) for i in range(3))
            gd.line([(0, y), (w, y)], fill=c)
        sq.paste(grad, (x0, y0))

    clean_region((0, 0, 1024, 185), (4, 13, 30), (7, 20, 44))
    clean_region((510, 180, 1024, 880), (6, 18, 38), (4, 13, 28))

    # 3. Clean the bottom area below the glowing green pedestal (y: 825..1024)
    grad_bot = Image.new("RGB", (1024, 200))
    gd_bot = ImageDraw.Draw(grad_bot)
    for y in range(200):
        k = y / 199.0
        c = (int(4 - 2 * k), int(13 - 4 * k), int(26 - 8 * k))
        gd_bot.line([(0, y), (1024, y)], fill=c)

    bot_mask = Image.new("L", (1024, 200), 255)
    b_mask_draw = ImageDraw.Draw(bot_mask)
    for y in range(16):
        b_mask_draw.line([(0, y), (1024, y)], fill=int(y * 255 / 15))

    sq.paste(grad_bot, (0, 824), bot_mask)

    return sq


def build_example_poster_html(
    bg_b64: str, font_b64: str, logo_horiz_b64: str, kbz_logo_b64: str, wave_logo_b64: str
) -> str:
    shield_svg = """<svg class="shield-ico" viewBox="0 0 64 76" fill="none">
      <defs>
        <linearGradient id="sg" x1="0" y1="0" x2="64" y2="76" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#38bdf8"/>
          <stop offset="100%" stop-color="#0284c7"/>
        </linearGradient>
      </defs>
      <path d="M32 4L8 14v22c0 18.5 10.2 31.8 24 36 13.8-4.2 24-17.5 24-36V14L32 4z"
        fill="url(#sg)" stroke="#7dd3fc" stroke-width="2.5"/>
      <rect x="22" y="34" width="20" height="16" rx="3" fill="#ffffff"/>
      <path d="M26 34v-5a6 6 0 0112 0v5" stroke="#ffffff" stroke-width="3.5" fill="none"/>
      <circle cx="32" cy="41" r="2" fill="#0284c7"/>
      <path d="M32 43v4" stroke="#0284c7" stroke-width="2.2" stroke-linecap="round"/>
    </svg>"""

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
    background: url('data:image/jpeg;base64,{bg_b64}') no-repeat center/cover;
    font-family: 'BurmeseHandwriting', 'Segoe UI', sans-serif;
    position: relative;
    color: #ffffff;
  }}
  /* Top Row: Left slogan + Right Exabyte Logo */
  .top-slogan {{
    position: absolute;
    left: 42px;
    top: 34px;
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 56px;
    font-weight: 900;
    color: #ffffff;
    text-shadow: 0 3px 14px rgba(0,0,0,0.85);
    display: flex;
    align-items: center;
    gap: 18px;
  }}
  .top-slogan .sep {{
    color: #94a3b8;
    font-weight: 400;
  }}
  .brand-pill {{
    position: absolute;
    right: 40px;
    top: 28px;
    width: 268px;
    height: 74px;
    background: #ffffff;
    border-radius: 16px;
    box-shadow: 0 6px 22px rgba(0, 0, 0, 0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px 14px;
  }}
  .brand-pill img {{
    width: 100%;
    height: 100%;
    object-fit: contain;
  }}
  .divider-line {{
    position: absolute;
    left: 42px;
    width: 520px;
    top: 112px;
    height: 2px;
    background: linear-gradient(90deg, rgba(56,189,248,0.8), rgba(56,189,248,0));
  }}
  .bypass-line {{
    position: absolute;
    left: 42px;
    right: 42px;
    top: 126px;
    font-family: 'Segoe UI', sans-serif;
    font-size: 31px;
    font-weight: 900;
    color: #a5f3fc;
    letter-spacing: 1.4px;
    text-shadow: 0 0 18px rgba(34, 211, 238, 0.85);
  }}
  /* Left Hero Block (Replacing "VPN SERVERS" with FREE TRIAL) */
  .left-hero {{
    position: absolute;
    left: 42px;
    top: 196px;
    width: 480px;
  }}
  .lh-mm-top {{
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 54px;
    font-weight: 900;
    color: #ffffff;
    line-height: 1.15;
    text-shadow: 0 4px 14px rgba(0,0,0,0.9);
  }}
  .lh-free-trial {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 74px;
    font-weight: 900;
    line-height: 1.02;
    letter-spacing: 1px;
    background: linear-gradient(180deg, #bbf7d0 0%, #4ade80 55%, #16a34a 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 4px 12px rgba(22, 163, 74, 0.55));
    margin: 2px 0 8px;
  }}
  .lh-sub-pill {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
    background: linear-gradient(90deg, rgba(16, 185, 129, 0.28), rgba(6, 182, 212, 0.25));
    border: 1.8px solid #34d399;
    border-radius: 24px;
    padding: 5px 18px;
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 24px;
    font-weight: 800;
    color: #ecfdf5;
    box-shadow: 0 0 16px rgba(52, 211, 153, 0.35);
  }}
  /* Right Side: 3 Pricing Cards */
  .right-cards {{
    position: absolute;
    right: 38px;
    top: 184px;
    width: 454px;
    display: flex;
    flex-direction: column;
    gap: 28px;
  }}
  .p-card {{
    position: relative;
    height: 204px;
    border-radius: 24px;
    background: linear-gradient(135deg, rgba(8, 28, 56, 0.94), rgba(4, 14, 32, 0.97));
    border: 2px solid rgba(56, 189, 248, 0.78);
    box-shadow: 0 0 24px rgba(34, 211, 238, 0.25), inset 0 0 18px rgba(56, 189, 248, 0.14);
    padding: 34px 24px 20px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .p-tab {{
    position: absolute;
    left: 22px;
    top: -18px;
    height: 38px;
    padding: 0 22px;
    border-radius: 12px;
    background: linear-gradient(90deg, #38bdf8, #0284c7);
    color: #ffffff;
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 24px;
    font-weight: 800;
    display: flex;
    align-items: center;
    box-shadow: 0 4px 10px rgba(0,0,0,0.45);
  }}
  .p-price-num {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 68px;
    font-weight: 900;
    color: #ffffff;
    line-height: 1;
    letter-spacing: -0.5px;
  }}
  .p-price-num span {{
    font-size: 42px;
    color: #0ea5e9;
    font-weight: 800;
    margin-left: 8px;
  }}
  .p-meta {{
    margin-top: 10px;
    white-space: nowrap;
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 21px;
    font-weight: 700;
    color: #cbd5e1;
  }}
  .p-meta b {{
    color: #6ee7b7;
  }}
  .shield-ico {{
    width: 76px;
    height: 90px;
    flex-shrink: 0;
    filter: drop-shadow(0 0 14px rgba(56, 189, 248, 0.6));
  }}
  /* Bottom Row: Contact Bot + Payment (KBZ Pay & Wave Pay) */
  .bot-row {{
    position: absolute;
    left: 30px;
    right: 30px;
    top: 894px;
    height: 104px;
    display: grid;
    grid-template-columns: 1.15fr 1fr;
    gap: 16px;
  }}
  .contact-box {{
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(10, 26, 52, 0.96), rgba(5, 14, 30, 0.98));
    border: 1.8px solid rgba(56, 189, 248, 0.65);
    display: flex;
    align-items: center;
    padding: 0 20px;
    gap: 16px;
  }}
  .tg-circle {{
    width: 60px;
    height: 60px;
    border-radius: 16px;
    background: linear-gradient(135deg, #38bdf8, #0284c7);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 0 14px rgba(56, 189, 248, 0.5);
  }}
  .c-lbl {{
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 20px;
    color: #6ee7b7;
    font-weight: 700;
  }}
  .c-bot {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 30px;
    font-weight: 900;
    color: #ffffff;
    line-height: 1.1;
  }}
  .c-sub {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 16px;
    font-weight: 700;
    color: #7dd3fc;
    letter-spacing: 0.6px;
  }}
  .payment-box {{
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(10, 26, 52, 0.96), rgba(5, 14, 30, 0.98));
    border: 1.8px solid rgba(56, 189, 248, 0.65);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;
  }}
  .pay-left {{
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .pay-left span {{
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 22px;
    font-weight: 800;
    color: #7dd3fc;
  }}
  .pay-badges-wrap {{
    background: transparent;
    padding: 0;
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .official-pay-chip {{
    height: 60px;
    border-radius: 14px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
    display: block;
    object-fit: contain;
  }}
</style>
</head>
<body>
  <div class="top-slogan">
    <span>ရှယ်တန်</span>
    <span class="sep">|</span>
    <span>လိုင်းကောင်း</span>
  </div>

  <div class="brand-pill">
    <img src="data:image/jpeg;base64,{logo_horiz_b64}" alt="Exabyte Digital Store">
  </div>

  <div class="divider-line"></div>
  <div class="bypass-line">100% FIREWALL BYPASS • NO SPEED THROTTLING</div>

  <div class="left-hero">
    <div class="lh-mm-top">အပတ်စဉ် အခမဲ့</div>
    <div class="lh-free-trial">FREE TRIAL</div>
    <div class="lh-sub-pill">🎁 5 GB • 7 ရက် အခမဲ့ စမ်းသပ်နိုင်သည်</div>
  </div>

  <div class="right-cards">
    <div class="p-card">
      <div class="p-tab">1 လ Plan (30 ရက်)</div>
      <div>
        <div class="p-price-num">5,000<span>Ks</span></div>
        <div class="p-meta">♾️ Unlimited  •  🌐 <b>100 GB</b> (All Servers)</div>
      </div>
      {shield_svg}
    </div>

    <div class="p-card">
      <div class="p-tab">3 လ Plan (90 ရက်)</div>
      <div>
        <div class="p-price-num">14,500<span>Ks</span></div>
        <div class="p-meta">♾️ Unlimited  •  🌐 <b>300 GB</b> (All Servers)</div>
      </div>
      {shield_svg}
    </div>

    <div class="p-card">
      <div class="p-tab">6 လ Plan (180 ရက်)</div>
      <div>
        <div class="p-price-num">29,000<span>Ks</span></div>
        <div class="p-meta">♾️ Unlimited  •  🌐 <b>600 GB</b> (All Servers)</div>
      </div>
      {shield_svg}
    </div>
  </div>

  <div class="bot-row">
    <div class="contact-box">
      <div class="tg-circle">
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
          <path d="M21.2 4.4L2.9 11.5c-1.2.5-1.2 1.2-.2 1.5l4.7 1.5 10.8-6.8c.5-.3 1-.1.6.2
            l-8.8 7.9-.3 4.8c.5 0 .7-.2 1-.5l2.4-2.3 5 3.7c.9.5 1.6.2 1.8-.9L23 6
            c.3-1.3-.5-1.9-1.8-1.6z" fill="#ffffff"/>
        </svg>
      </div>
      <div>
        <div class="c-lbl">အခမဲ့ စမ်းသပ်ရန် နှင့် ဝယ်ယူရန် 👉</div>
        <div class="c-bot">@exabytedigitalsbot</div>
        <div class="c-sub">SUPPORT: @EXABYTEDIGITALS</div>
      </div>
    </div>

    <div class="payment-box">
      <div class="pay-left">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2">
          <rect x="2" y="5" width="20" height="14" rx="3"/>
          <path d="M16 12h2"/>
        </svg>
        <span>ငွေပေးချေရန်</span>
      </div>
      <div class="pay-badges-wrap">
        <img class="official-pay-chip" src="data:image/png;base64,{kbz_logo_b64}" alt="KBZPay">
        <img class="official-pay-chip" src="data:image/png;base64,{wave_logo_b64}" alt="Wave Money">
      </div>
    </div>
  </div>
</body>
</html>
"""


def build_welcome_banner_html(
    font_b64: str, logo_sym_b64: str, kbz_logo_b64: str, wave_logo_b64: str
) -> str:
    """Professional 1280x720 (16:9) Exabyte Digital Store Welcome Banner in Burmese.
    Uses `Burmese Handwriting.ttf` (no cartoon rockets, no 'High-Speed VPN Servers').
    """
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
    width: 1280px;
    height: 720px;
    overflow: hidden;
    background: radial-gradient(circle at 26% 50%, #0d2b4e 0%, #061326 55%, #030914 100%);
    font-family: 'BurmeseHandwriting', 'Segoe UI', sans-serif;
    position: relative;
    color: #ffffff;
    display: flex;
    align-items: center;
  }}
  /* Subtle architectural grid */
  .grid-bg {{
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(56, 189, 248, 0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(56, 189, 248, 0.05) 1px, transparent 1px);
    background-size: 48px 48px;
  }}
  /* Top and bottom neon accent lines */
  .top-bar {{
    position: absolute;
    top: 0; left: 0; right: 0; height: 4px;
    background: linear-gradient(90deg, transparent, #22d3ee, #34d399, transparent);
  }}
  .bot-bar {{
    position: absolute;
    bottom: 0; left: 0; right: 0; height: 4px;
    background: linear-gradient(90deg, transparent, #38bdf8, transparent);
  }}
  /* Left Emblem Section */
  .left-col {{
    position: relative;
    width: 470px;
    height: 720px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }}
  .ring-outer {{
    width: 350px;
    height: 350px;
    border-radius: 50%;
    border: 2px solid rgba(56, 189, 248, 0.35);
    box-shadow: 0 0 60px rgba(34, 211, 238, 0.22), inset 0 0 40px rgba(34, 211, 238, 0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
  }}
  .ring-mid {{
    width: 286px;
    height: 286px;
    border-radius: 50%;
    border: 3px solid #22d3ee;
    box-shadow: 0 0 32px rgba(34, 211, 238, 0.55);
    background: radial-gradient(circle, #0b223e 0%, #061325 100%);
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .logo-box {{
    width: 196px;
    height: 196px;
    border-radius: 38px;
    overflow: hidden;
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.65);
    border: 2px solid rgba(125, 211, 252, 0.5);
  }}
  .logo-box img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
  }}
  /* Right Content Section */
  .right-col {{
    position: relative;
    flex: 1;
    padding: 0 58px 0 12px;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }}
  .welcome-mm {{
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 40px;
    font-weight: 800;
    color: #38bdf8;
    margin-bottom: 2px;
  }}
  .brand-en {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 68px;
    font-weight: 900;
    letter-spacing: 2px;
    color: #ffffff;
    line-height: 1.02;
    text-shadow: 0 4px 20px rgba(0, 0, 0, 0.7);
  }}
  .brand-sub {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 32px;
    font-weight: 800;
    letter-spacing: 5px;
    color: #fb923c;
    margin-top: 2px;
    margin-bottom: 18px;
  }}
  .trial-pill {{
    display: inline-flex;
    align-items: center;
    gap: 12px;
    align-self: flex-start;
    background: linear-gradient(90deg, rgba(16, 185, 129, 0.22), rgba(34, 211, 238, 0.22));
    border: 2px solid #34d399;
    border-radius: 30px;
    padding: 8px 26px;
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 31px;
    font-weight: 800;
    color: #6ee7b7;
    box-shadow: 0 0 22px rgba(52, 211, 153, 0.28);
    margin-bottom: 22px;
  }}
  .feat-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 24px;
  }}
  .feat-row {{
    display: flex;
    align-items: center;
    gap: 14px;
    font-family: 'BurmeseHandwriting', sans-serif;
    font-size: 29px;
    font-weight: 700;
    color: #f1f5f9;
  }}
  .feat-dot {{
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: rgba(56, 189, 248, 0.18);
    border: 1.5px solid #38bdf8;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
  }}
  .footer-strip {{
    display: flex;
    align-items: center;
    gap: 16px;
  }}
  .bot-chip {{
    background: rgba(15, 38, 68, 0.9);
    border: 1.8px solid #38bdf8;
    border-radius: 14px;
    padding: 8px 20px;
    font-family: 'Segoe UI', sans-serif;
    font-size: 24px;
    font-weight: 800;
    color: #ffffff;
  }}
  .pay-chip {{
    background: #ffffff;
    border-radius: 12px;
    padding: 6px 14px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }}
  .pay-chip-logo {{
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: block;
  }}
  .pay-chip-text {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 19px;
    font-weight: 900;
  }}
  .kbz-text {{ color: #0054a6; }}
  .wave-text {{ color: #0c4f7c; }}
</style>
</head>
<body>
  <div class="grid-bg"></div>
  <div class="top-bar"></div>
  <div class="bot-bar"></div>

  <div class="left-col">
    <div class="ring-outer">
      <div class="ring-mid">
        <div class="logo-box">
          <img src="data:image/jpeg;base64,{logo_sym_b64}" alt="Exabyte">
        </div>
      </div>
    </div>
  </div>

  <div class="right-col">
    <div class="welcome-mm">✨ နွေးထွေးစွာ ကြိုဆိုပါသည် ✨</div>
    <div class="brand-en">EXABYTE</div>
    <div class="brand-sub">DIGITAL STORE</div>

    <div class="trial-pill">🎁 အပတ်စဉ် အခမဲ့ စမ်းသပ် — 5 GB (7 ရက်)</div>

    <div class="feat-list">
      <div class="feat-row">
        <div class="feat-dot">⚡</div>
        <span>၁၀ စက္ကန့်အတွင်း Key အလိုအလျောက် ချက်ချင်းရယူနိုင်သည်</span>
      </div>
      <div class="feat-row">
        <div class="feat-dot">🛡️</div>
        <span>လုံခြုံ စိတ်ချရပြီး ၂၄ နာရီ အချိန်မရွေး အကူအညီရယူနိုင်သည်</span>
      </div>
    </div>

    <div class="footer-strip">
      <div class="bot-chip">🤖 @exabytedigitalsbot</div>
      <img style="height: 44px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.4);"
        src="data:image/png;base64,{kbz_logo_b64}" alt="KBZPay">
      <img style="height: 44px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.4);"
        src="data:image/png;base64,{wave_logo_b64}" alt="Wave Money">
    </div>
  </div>
</body>
</html>
"""


def main() -> None:
    chrome = next((p for p in CHROME_PATHS if p.is_file()), None)
    if chrome is None:
        raise RuntimeError("Chrome/Edge not found")

    # 1. Clean out unnecessary old/duplicate .jpg files in exabyte-jpgs/ root
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_f in OUT_DIR.glob("*.jpg"):
        old_f.unlink()

    font_b64 = base64.b64encode(FONT_PATH.read_bytes()).decode("ascii")
    logo_horiz_b64 = base64.b64encode(LOGO_HORIZ_PATH.read_bytes()).decode("ascii")
    logo_sym_b64 = base64.b64encode(LOGO_SYM_PATH.read_bytes()).decode("ascii")
    kbz_logo_b64 = base64.b64encode(KBZ_LOGO_PATH.read_bytes()).decode("ascii")
    wave_logo_b64 = base64.b64encode(WAVE_LOGO_PATH.read_bytes()).decode("ascii")

    # 2. Render the Example-Based Promo Poster (2048x2048 High-Res)
    ex_bg = prepare_example_base()
    buf = io.BytesIO()
    ex_bg.save(buf, format="JPEG", quality=98)
    ex_bg_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    with tempfile.TemporaryDirectory() as tmpdir:
        poster_html = build_example_poster_html(
            ex_bg_b64, font_b64, logo_horiz_b64, kbz_logo_b64, wave_logo_b64
        )
        p_html_file = Path(tmpdir) / "poster.html"
        p_png_file = Path(tmpdir) / "poster.png"
        p_html_file.write_text(poster_html, encoding="utf-8")

        subprocess.run(  # noqa: S603
            [
                str(chrome),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--window-size=1024,1024",
                "--force-device-scale-factor=2",
                f"--screenshot={p_png_file}",
                p_html_file.as_uri(),
            ],
            check=True,
        )
        poster_im = Image.open(io.BytesIO(p_png_file.read_bytes())).convert("RGB")
        poster_out = OUT_DIR / "exabyte_promo_poster_highres.jpg"
        poster_im.save(poster_out, quality=100, subsampling=0)
        poster_im.resize((1080, 1080), Image.Resampling.LANCZOS).save(
            ART_DIR / "exabyte_promo_poster_highres.jpg", quality=96
        )
        print("Saved:", poster_out.name)

        # 3. Render the New Professional Burmese Welcome Banner (1280x720 HD & 640x360 BotFather)
        welcome_html = build_welcome_banner_html(
            font_b64, logo_sym_b64, kbz_logo_b64, wave_logo_b64
        )
        w_html_file = Path(tmpdir) / "welcome.html"
        w_png_file = Path(tmpdir) / "welcome.png"
        w_html_file.write_text(welcome_html, encoding="utf-8")

        subprocess.run(  # noqa: S603
            [
                str(chrome),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--window-size=1280,720",
                "--force-device-scale-factor=1",
                f"--screenshot={w_png_file}",
                w_html_file.as_uri(),
            ],
            check=True,
        )
        wel_im = Image.open(io.BytesIO(w_png_file.read_bytes())).convert("RGB")
        wel_hd_out = OUT_DIR / "exabyte_welcome_1280x720_hd.jpg"
        wel_bf_out = OUT_DIR / "exabyte_welcome_640x360_botfather.jpg"
        wel_im.save(wel_hd_out, quality=100, subsampling=0)
        wel_im.resize((640, 360), Image.Resampling.LANCZOS).save(
            wel_bf_out, quality=100, subsampling=0
        )
        wel_im.save(ART_DIR / "exabyte_welcome_1280x720_hd.jpg", quality=96)
        print("Saved:", wel_hd_out.name, wel_bf_out.name)


if __name__ == "__main__":
    main()
