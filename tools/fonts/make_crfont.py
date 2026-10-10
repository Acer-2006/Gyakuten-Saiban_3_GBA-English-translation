#!/usr/bin/env python3
"""Make inter-medium-10.txt, the Court Record descriptions' font (tools/crfont.py), from Inter
Medium (Inter 4.0, OFL-1.1, see LICENSE.inter).  Needs Pillow with FreeType; the build itself only
reads the text file this writes.

    python3 make_crfont.py /usr/share/fonts/opentype/inter/Inter-Medium.otf inter-medium-10.txt

Each glyph is rendered at 10 px with FreeType's anti-aliasing and its coverage kept in five
levels (0 = background .. 4 = full); the advances are kept in 1/64 pixel, with the kerning of
every pair of the characters below."""
import sys
from PIL import Image, ImageDraw, ImageFont

SIZE = 10
CHARS = ''.join(chr(c) for c in range(0x20, 0x7f)) + 'éèêëáàâäçÇñïîûüöô×☆“”‘’…'
PAD = 8

def main(src, out):
    font = ImageFont.truetype(src, SIZE)
    asc, desc = font.getmetrics()
    lines = [f'# Inter Medium {SIZE} px: glyphs as five coverage levels (. 1 2 3 4), advances and',
             '# kerning in 1/64 pixel.  Made by make_crfont.py from Inter 4.0, The Inter Project',
             '# Authors, SIL Open Font License 1.1 (LICENSE.inter).',
             f'size {SIZE} ascent {asc} descent {desc}']
    for ch in CHARS:
        adv = round(font.getlength(ch) * 64)
        im = Image.new('L', (SIZE * 3, SIZE * 3), 0)
        ImageDraw.Draw(im).text((PAD, PAD + asc), ch, font=font, fill=255, anchor='ls')
        box = im.getbbox()
        if box is None:
            lines.append(f'glyph {ord(ch):04x} {adv} 0 0 0 0'); continue
        x0, y0, x1, y1 = box
        lines.append(f'glyph {ord(ch):04x} {adv} {x0 - PAD} {y0 - PAD - asc} {x1 - x0} {y1 - y0}')
        for y in range(y0, y1):
            row = ''
            for x in range(x0, x1):
                lv = min(4, int(im.getpixel((x, y)) / 255 * 4 + 0.5))
                row += '.' if lv == 0 else str(lv)
            lines.append(' ' + row)
    for a in CHARS:
        for b in CHARS:
            k = font.getlength(a + b) - font.getlength(a) - font.getlength(b)
            k = round(k * 64)
            if k: lines.append(f'kern {ord(a):04x} {ord(b):04x} {k}')
    open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
