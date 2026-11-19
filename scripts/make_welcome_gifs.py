"""Render small looping brand animations for Telegram welcome cards."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "exabyte_bot/assets/welcome"
OUT.mkdir(parents=True, exist_ok=True)
AVATAR = OUT.parents[1] / "webapp/static/brand/avatar-640.png"

for name, letter in (("exabyte", "E"), ("outlineplus", "O")):
    frames = []
    for index in range(24):
        phase = index / 24 * math.tau
        canvas = Image.new("RGB", (480, 270), (15, 30, 35))
        draw = ImageDraw.Draw(canvas)
        glow = int(28 + 15 * (1 + math.sin(phase)))
        for radius in range(75, 105, 7):
            draw.ellipse((240-radius, 132-radius, 240+radius, 132+radius),
                         outline=(glow, 75+glow, 86+glow), width=2)
        draw.rounded_rectangle((173, 64, 307, 198), radius=34, fill=(27, 72, 65))
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 104)
        except OSError:
            font = ImageFont.load_default()
        if name == "exabyte" and AVATAR.is_file():
            logo = Image.open(AVATAR).convert("RGBA").resize((134, 134))
            canvas.paste(logo, (173, 64), logo)
        else:
            draw.text((240, 128), letter, font=font, anchor="mm", fill=(143, 235, 201))
        if name == "outlineplus":
            draw.line((318, 54, 356, 54), fill=(241, 249, 246), width=8)
            draw.line((337, 35, 337, 73), fill=(241, 249, 246), width=8)
        draw.rounded_rectangle((44, 231, 436, 236), radius=2, fill=(42, 79, 77))
        draw.rounded_rectangle((44, 231, 44+int((index+1)/24*392), 236),
                               radius=2, fill=(143, 235, 201))
        frames.append(canvas)
    frames[0].save(OUT / f"{name}.gif", save_all=True, append_images=frames[1:],
                   duration=75, loop=0, optimize=True)
