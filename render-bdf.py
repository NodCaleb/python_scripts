import re
import sys

try:
    from PIL import Image, ImageColor
except ModuleNotFoundError:
    print("Missing dependency: Pillow")
    print("Install it with: python -m pip install pillow")
    raise SystemExit(1)

PADDING = 4


class Glyph:
    def __init__(self, width, height, xoff, yoff, advance, rows):
        self.width = width
        self.height = height
        self.xoff = xoff
        self.yoff = yoff
        self.advance = advance
        self.rows = rows  # (value, bit count) per row; MSB is the leftmost pixel


class BdfFont:
    def __init__(self, path):
        self.glyphs = {}
        self.ascent = None
        self.descent = None
        self.bbox = (0, 0, 0, 0)  # width, height, xoff, yoff
        self.default_char = None
        self._parse(path)

        if self.ascent is None:
            self.ascent = self.bbox[1] + self.bbox[3]
        if self.descent is None:
            self.descent = -self.bbox[3]

    def _parse(self, path):
        with open(path, "r", encoding="latin-1") as f:
            lines = [line.rstrip("\r\n") for line in f]

        i = 0
        while i < len(lines):
            parts = lines[i].split()
            i += 1
            if not parts:
                continue
            key = parts[0]

            if key == "FONTBOUNDINGBOX":
                self.bbox = tuple(int(v) for v in parts[1:5])
            elif key == "FONT_ASCENT":
                self.ascent = int(parts[1])
            elif key == "FONT_DESCENT":
                self.descent = int(parts[1])
            elif key == "DEFAULT_CHAR":
                self.default_char = int(parts[1])
            elif key == "STARTCHAR":
                i = self._parse_glyph(lines, i)

        if not self.glyphs:
            raise ValueError("no glyphs found, is this a BDF file?")

    def _parse_glyph(self, lines, i):
        encoding = -1
        advance = None
        bbx = (0, 0, 0, 0)

        while i < len(lines):
            parts = lines[i].split()
            i += 1
            if not parts:
                continue
            key = parts[0]

            if key == "ENCODING":
                encoding = int(parts[1])
            elif key == "DWIDTH":
                advance = int(parts[1])
            elif key == "BBX":
                bbx = tuple(int(v) for v in parts[1:5])
            elif key == "BITMAP":
                width, height, xoff, yoff = bbx
                rows = []
                for _ in range(height):
                    data = lines[i].strip()
                    i += 1
                    rows.append((int(data, 16) if data else 0, len(data) * 4))
                if advance is None:
                    advance = width
                if encoding >= 0:
                    self.glyphs[encoding] = Glyph(width, height, xoff, yoff, advance, rows)
            elif key == "ENDCHAR":
                break

        return i

    def glyph_for(self, char):
        glyph = self.glyphs.get(ord(char))
        if glyph is None and self.default_char is not None:
            glyph = self.glyphs.get(self.default_char)
        return glyph


def render(font, text, color, background):
    line_height = font.ascent + font.descent
    lines = text.split("\n")

    widths = []
    for line in lines:
        total = 0
        for ch in line:
            glyph = font.glyph_for(ch)
            total += glyph.advance if glyph else font.bbox[0]
        widths.append(total)

    width = max(max(widths), 1) + 2 * PADDING
    height = max(line_height, 1) * len(lines) + 2 * PADDING

    img = Image.new("RGB", (width, height), background)
    pixels = img.load()

    for n, line in enumerate(lines):
        baseline = PADDING + n * line_height + font.ascent
        x = PADDING
        for ch in line:
            glyph = font.glyph_for(ch)
            if glyph is None:
                x += font.bbox[0]
                continue

            top = baseline - (glyph.yoff + glyph.height)
            for row_index, (bits, nbits) in enumerate(glyph.rows):
                for col in range(glyph.width):
                    if bits >> (nbits - 1 - col) & 1:
                        px = x + glyph.xoff + col
                        py = top + row_index
                        if 0 <= px < width and 0 <= py < height:
                            pixels[px, py] = color
            x += glyph.advance

    return img


def parse_color(value):
    # "#" starts a comment in PowerShell, so also accept hex without it
    if re.fullmatch(r"[0-9a-fA-F]{6}", value):
        value = "#" + value
    return ImageColor.getrgb(value)[:3]


def main():
    if not 4 <= len(sys.argv) <= 6:
        print("Usage: python render-bdf.py font.bdf \"text to render\" output.png [text_color] [background_color]")
        print("Colors are in #RRGGBB or RRGGBB format (defaults: #000000 and #FFFFFF)")
        print("In PowerShell quote '#' colors, otherwise the rest of the line is treated as a comment")
        return 1

    font_path, text, output = sys.argv[1:4]
    text = text.replace("\\n", "\n")
    color_arg = sys.argv[4] if len(sys.argv) > 4 else "#000000"
    background_arg = sys.argv[5] if len(sys.argv) > 5 else "#FFFFFF"

    try:
        color = parse_color(color_arg)
        background = parse_color(background_arg)
    except ValueError as e:
        print(f"Invalid color: {e}")
        return 1

    try:
        font = BdfFont(font_path)
    except (OSError, ValueError) as e:
        print(f"Cannot load font {font_path}: {e}")
        return 1

    render(font, text, color, background).save(output)
    print(f"Image saved to {output} (text color {color}, background {background})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
