"""Erzeugt boxen/gaerbox/include/tipsy_fonts.h: JetBrains Mono Bold als 1-Bit-GFX-Font fürs AtomS3.

Zwei Größen, nur die Zeichen, die das Display braucht (Ziffern, Komma, Grad, d, h und die
Kürzel BPM, DUB, DRY, BAR). Quelle ist dieselbe Schrift wie im Panel.

Aufruf (Abhängigkeiten nur für diesen Schritt):
    uv run --with fonttools --with brotli --with pillow python tools/make_atom_font.py
"""

from __future__ import annotations

import io
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "tipsylab" / "frontend" / "fonts" / "jetbrains-mono-latin.woff2"
TARGET = ROOT / "boxen" / "gaerbox" / "include" / "tipsy_fonts.h"

FIRST, LAST = 0x20, 0xB0  # bis zum Gradzeichen; ungenutzte Zeichen bleiben leer
FONTS = {
    # Name: (Pixelgröße des Gevierts, Zeichen)
    "TipsyMonoBig": (30, " 0123456789,.-°"),
    "TipsyMonoSmall": (13, " 0123456789,.-°dhBPMUDRYA"),
}


def bold_ttf() -> bytes:
    font = TTFont(str(SOURCE))
    if "fvar" in font:
        font = instancer.instantiateVariableFont(font, {"wght": 700})
    font.flavor = None
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def render(font: ImageFont.FreeTypeFont, size: int, ch: str) -> tuple[list[int], int, int, int, int, int]:
    """Bits (zeilenweise, ohne Auffüllung), Breite, Höhe, Vorschub, x- und y-Versatz zur Grundlinie."""
    canvas = Image.new("1", (size * 2, size * 2), 0)
    draw = ImageDraw.Draw(canvas)
    draw.fontmode = "1"  # FreeType-Monochrom mit Hinting statt Schwelle über Graustufen
    ox, oy = size // 2, int(size * 1.4)
    draw.text((ox, oy), ch, font=font, fill=1, anchor="ls")
    advance = round(font.getlength(ch))
    box = canvas.getbbox()
    if box is None:
        return [], 0, 0, advance, 0, 0
    glyph = canvas.crop(box)
    w, h = glyph.size
    bits = [1 if glyph.getpixel((x, y)) else 0 for y in range(h) for x in range(w)]
    return bits, w, h, advance, box[0] - ox, box[1] - oy


def pack(bits: list[int]) -> list[int]:
    out = []
    for i in range(0, len(bits), 8):
        chunk = bits[i : i + 8] + [0] * (8 - len(bits[i : i + 8]))
        out.append(sum(b << (7 - k) for k, b in enumerate(chunk)))
    return out


def font_source(name: str, ttf: bytes, size: int, chars: str) -> str:
    font = ImageFont.truetype(io.BytesIO(ttf), size)
    ascent, descent = font.getmetrics()
    bitmap: list[int] = []
    glyphs = []
    for code in range(FIRST, LAST + 1):
        ch = chr(code)
        if ch not in chars:
            glyphs.append((0, 0, 0, 0, 0, 0, ch))
            continue
        bits, w, h, adv, xo, yo = render(font, size, ch)
        glyphs.append((len(bitmap), w, h, adv, xo, yo, ch))
        bitmap += pack(bits)
    lines = [f"// {name}: JetBrains Mono Bold, {size} px, {len(chars)} Zeichen, {len(bitmap)} Bytes Bitmap"]
    lines.append(f"const uint8_t {name}Bitmaps[] PROGMEM = {{")
    for i in range(0, len(bitmap), 16):
        lines.append("  " + ", ".join(f"0x{b:02X}" for b in bitmap[i : i + 16]) + ",")
    lines.append("};")
    lines.append(f"const lgfx::GFXglyph {name}Glyphs[] PROGMEM = {{")
    for off, w, h, adv, xo, yo, ch in glyphs:
        label = "" if ch not in chars or ch == " " else f"  // {ch}"
        lines.append(f"  {{{off}, {w}, {h}, {adv}, {xo}, {yo}}},{label}")
    lines.append("};")
    lines.append(
        f"const lgfx::GFXfont {name} = {{(uint8_t*){name}Bitmaps, (lgfx::GFXglyph*){name}Glyphs, "
        f"0x{FIRST:02X}, 0x{LAST:02X}, {ascent + descent}}};"
    )
    return "\n".join(lines)


def main() -> None:
    ttf = bold_ttf()
    parts = [
        "// Erzeugt von tools/make_atom_font.py, nicht von Hand ändern.",
        "// JetBrains Mono: Copyright 2020 The JetBrains Mono Project Authors, SIL Open Font License 1.1",
        "// (OFL-jetbrainsmono.txt in diesem Ordner).",
        "#pragma once",
        "#include <M5GFX.h>",
        "",
    ]
    for name, (size, chars) in FONTS.items():
        parts.append(font_source(name, ttf, size, chars))
        parts.append("")
    TARGET.write_text("\n".join(parts))
    print(f"{TARGET.relative_to(ROOT)}: {TARGET.stat().st_size} Bytes")


if __name__ == "__main__":
    main()
