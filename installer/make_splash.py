"""Regenerate installer/splash.png from installer/novotree.ico.

The PNG is committed, so this is NOT part of the build and Pillow is NOT a
project dependency -- build.ps1 never runs it. Re-run it only when the branding
changes, then commit the result:

    python -m pip install --target .venv-tmp pillow
    PYTHONPATH=.venv-tmp python installer/make_splash.py .

Deriving the splash from the .ico keeps it in step with the icon already used
for the setup wizard, the executable, and the Start Menu shortcut.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(sys.argv[1])
ICON = REPO / "installer" / "novotree.ico"
OUT = REPO / "installer" / "splash.png"

W, H = 440, 268
BAND = 46                   # bottom strip the bootloader writes the status into
BG = (255, 255, 255)
INK = (17, 24, 39)          # gray-900, matches the app's headings
MUTED = (107, 114, 128)     # gray-500
RULE = (229, 231, 235)      # gray-200
LOGO = 96

canvas = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(canvas)

# Hairline border so the splash reads as a window on a light desktop.
draw.rectangle([0, 0, W - 1, H - 1], outline=RULE)

# The .ico is 24bpp with a 1-bit AND mask; Pillow applies it, giving us the
# rounded corners as alpha instead of the black they are stored as.
icon = Image.open(ICON).convert("RGBA").resize((LOGO, LOGO), Image.LANCZOS)
canvas.paste(icon, ((W - LOGO) // 2, 34), icon)


def font(size, bold=False):
    """Segoe UI where available (every supported Windows has it), else default."""
    for name in (("segoeuib.ttf", "segoeui.ttf") if bold else ("segoeui.ttf",)):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def centre(text, y, fnt, fill):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=fnt)
    draw.text(((W - (right - left)) // 2 - left, y), text, font=fnt, fill=fill)


centre("NovoTree", 146, font(26, bold=True), INK)
centre("Your family tree, on your own computer", 182, font(11), MUTED)

# A distinct band for the status line. The bootloader anchors that text south-
# west (see text_pos in installer/novotree.spec), so it is left-aligned no
# matter what it says; giving it its own strip makes that read as deliberate
# rather than as a centred layout gone wrong.
draw.rectangle([1, H - BAND, W - 2, H - 2], fill=(249, 250, 251))
draw.line([1, H - BAND, W - 2, H - BAND], fill=RULE)

canvas.save(OUT, "PNG", optimize=True)
print(f"wrote {OUT}  {W}x{H}  {OUT.stat().st_size / 1024:.1f} KB")
