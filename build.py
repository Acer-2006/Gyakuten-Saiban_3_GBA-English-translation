#!/usr/bin/env python3
"""Build the English Gyakuten Saiban 3 ROM from your own two cartridge images.

    python3 build.py gs3_jp.gba tt_us.nds [-o gs3_en.gba]

Needs only Python 3.8+.  gs3_jp.gba is Gyakuten Saiban 3 (Japan, GBA); tt_us.nds is Phoenix Wright:
Ace Attorney - Trials and Tribulations (USA, DS).  The English text, font, graphics and voices are
taken from the DS image while building; this tool itself contains only the code changes.
"""
import os, sys, argparse, time
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'tools')); sys.path.insert(0, ROOT)
from rom import Rom, save_cache
from pipeline import BuildContext

def build(gba_path, nds_path, out_path):
    t0 = time.time()
    ctx = BuildContext(gba_path, nds_path)
    ctx.convert()
    rom = Rom(ctx.gba, 0x1000000)
    # free regions: the old Japanese font (within Thumb BL range of the engine) and the expansion area
    rom.region('font', 0x1f31cc, 0x2231cc)
    rom.region('ext', 0x800000, 0x1000000)
    from patches import apply_all
    apply_all(rom, ctx)
    rom.save(out_path)
    save_cache()
    print(f"done: {out_path} ({time.time() - t0:.0f} s; font area used {rom.regions['font'].used:#x}, "
          f"expansion used {rom.regions['ext'].used / 1e6:.2f} MB)")
    return rom

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('gba', nargs='?', default=os.path.join(ROOT, 'roms', 'gs3_jp.gba'), help='Gyakuten Saiban 3 (Japan) .gba')
    ap.add_argument('nds', nargs='?', default=os.path.join(ROOT, 'roms', 'tt_us.nds'), help='Trials and Tribulations (USA) .nds')
    ap.add_argument('-o', '--out', default=None, help='output ROM (default: out/gs3_en.gba)')
    a = ap.parse_args()
    out = a.out or os.path.join(ROOT, 'out', 'gs3_en.gba')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    build(a.gba, a.nds, out)
