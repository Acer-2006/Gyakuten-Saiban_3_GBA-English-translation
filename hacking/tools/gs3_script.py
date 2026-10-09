#!/usr/bin/env python3
"""Dump and rebuild Gyakuten Saiban 3 (GBA) script banks.

  gs3_script.py list   ROM
  gs3_script.py dump   ROM BANK OUT.txt   [--table TABLE]
  gs3_script.py insert ROM BANK IN.txt OUT.gba [--table TABLE] [--at ADDR]
  gs3_script.py table  OUT.tsv [--table en|jp]   write a built-in table as a starting point for your own

BANK is 0..43 (the compressed chapter banks) or `common` (the raw bank at 0x086e3578).
TABLE is `en` (the English build's font), `jp` (the Japanese font: Latin, kana, punctuation; kanji
stay as [hex]) or a .tsv file of lines `code<TAB>text` (code in hex).

Text file format (lossless; a dump re-inserts byte for byte):
  @section N       starts section N (every entry of the bank's table must appear)
  @section N stale 0x1234   an entry of the table that is not a section of this bank (kept
                   verbatim; partial banks carry copies of their main bank's offsets)
  {@N}             label anchor: entry N of the table points here (target of command 0x36)
  # ...            comment line (only at the start of a line)
  {xx}             command xx, {xx a b} with its hex arguments (count fixed per command)
  [xxx]            character code xxx in hex (any code can be written this way)
  other text       characters looked up in the table; \\ escapes { [ # \\ and a real newline
  real line breaks are ignored inside a section, so wrap text however you like.
The dump puts a line break after {01} (new line) and {02} {2d} {2e} (end of page).

Insert rewrites the bank in place when the compressed bank still fits; otherwise it appends the
bank to the ROM (expanding it to 16 MB) or writes it at --at, and repoints every reference.
"""
import os, sys, json, struct, argparse
from _common import *
import lz
import banks as bk

COMMON_ADDR = 0x086e3578
COMMON_SIZE = 0x264c          # ends where chapter bank 0 begins (0x086e5bc4)
COMMON_REFS = (0x0801ed64, 0x0801ed60)   # literals holding the common bank's base and base + 4
BANK_BUFFER = 0x1b000          # EWRAM buffer the game decompresses a chapter bank into (apparent size)
CMD_ARGS = {int(k, 16): v for k, v in json.load(open(os.path.join(DATA, 'cmd_args.json'))).items()}
PAGE_BREAK = {0x01, 0x02, 0x2d, 0x2e}
CHAPTER_TABLE = 0x08049b38     # 25 pointers: the main banks in order
BANK_REFS = {b: CHAPTER_TABLE + 4 * i for i, b in enumerate(bk.MAIN_BANKS)}
BANK_REFS.update({2: 0x0801ee9c, 4: 0x0801eecc, 6: 0x0801eea4, 8: 0x0801eeb4, 9: 0x0801eebc, 12: 0x0801eed4,
                  14: 0x0801eee4, 16: 0x0801ef54, 18: 0x0801eef4, 19: 0x0801eefc, 22: 0x0801ef14, 24: 0x0801ef34,
                  26: 0x0801ef74, 29: 0x0801ef6c, 33: 0x0801ef84, 35: 0x0801ef9c, 37: 0x0801efa8, 40: 0x0801efc0,
                  41: 0x0801eff0})
DIRECTORY = 0x08800000         # English build: 'GS3E', u32 1, u32 45, {u32 addr, u32 len} x 45 (len 0 = compressed)
UNCOMPRESSED = 0x08800000      # the English loader uses banks at or above this address in place

def directory(rom):
    o = rom_off(DIRECTORY)
    if len(rom) > o + 16 and rom[o:o + 4] == b'GS3E':
        n = struct.unpack_from('<I', rom, o + 8)[0]
        return [struct.unpack_from('<II', rom, o + 12 + 8 * i) for i in range(n)]
    return None

def locate(rom, bank):
    """Where bank `bank` (0..43 or 'common') currently is: dict(addr, data, comp_size or None, ref)."""
    d = directory(rom)
    if bank == 'common':
        ref = COMMON_REFS[0]; addr = struct.unpack_from('<I', rom, rom_off(ref))[0]
        size = d[44][1] if d else COMMON_SIZE
        return {'addr': addr, 'data': rom[rom_off(addr):rom_off(addr) + size], 'comp_size': None, 'ref': ref}
    b = int(bank); ref = BANK_REFS[b]
    addr = struct.unpack_from('<I', rom, rom_off(ref))[0]
    if addr >= UNCOMPRESSED or (d and d[b][1]):
        if not d or d[b][0] != addr: sys.exit(f'bank {b}: uncompressed bank at {addr:#x} without a matching directory entry')
        return {'addr': addr, 'data': rom[rom_off(addr):rom_off(addr) + d[b][1]], 'comp_size': None, 'ref': ref}
    dec, used = lz.decompress(rom, rom_off(addr))
    return {'addr': addr, 'data': dec, 'comp_size': used, 'ref': ref}

# ---------------------------------------------------------------- character tables
KANA = ('あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんがぎ'
        'ぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽぁぃぅぇぉゃゅょっ'
        'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンガギ'
        'グゲゴザジズゼゾダヂヅデドバビブベボパピプペポァィゥェォャュョッヴ')

def builtin_table(name='en'):
    """'en': the DS English font layout (what the English build uses).
    'jp': the Japanese ROM's font: Latin, kana and the punctuation read off the font sheet
    (kanji, 0x180 and up, stay as [hex]; extend the table yourself with gs3_font.py sheet)."""
    t = {}
    for i in range(10): t[0x80 + i] = chr(48 + i)
    for i in range(26): t[0x8a + i] = chr(65 + i)
    for i in range(26): t[0xa4 + i] = chr(97 + i)
    t.update({0xbe: '!', 0xbf: '?', 0x161: '.', 0x16d: ':', 0x16f: ',', 0x173: "'", 0x17d: '☆', 0x17f: ' '})
    if name == 'en':
        # the DS English font: 0x165/0x166 are parentheses (Phoenix's thoughts), the straight
        # double quote and the hyphen are extra glyphs 0x682 / 0x681
        t.update({0x165: '(', 0x166: ')', 0x170: '+', 0x171: '/', 0x172: '*', 0x177: '%', 0x179: '~',
                  0x17c: '&', 0x17e: '♪'})
        for i, ch in enumerate('-"[]$#><=■éá;çàÇûîèâñïê'): t[0x681 + i] = ch
    else:
        for i, ch in enumerate(KANA): t[0xc0 + i] = ch
        t.update({0x163: '「', 0x164: '」', 0x165: '(', 0x166: ')', 0x167: '『', 0x168: '』', 0x169: '“', 0x16a: '”',
                  0x16b: '▼', 0x16c: '▲', 0x16e: '、', 0x170: '+', 0x171: '/', 0x172: '※', 0x174: 'ー', 0x176: '。',
                  0x177: '%', 0x178: '‥', 0x179: '〜', 0x17a: '《', 0x17b: '》', 0x17c: '&', 0x17e: '♪'})
    return t

def load_table(spec):
    if spec is None: return {}
    if spec in ('en', 'jp'): return builtin_table(spec)
    t = {}
    for ln, line in enumerate(open(spec, encoding='utf-8'), 1):
        line = line.rstrip('\n')
        if not line or line.startswith('#'): continue
        if '\t' not in line: sys.exit(f'{spec}:{ln}: expected code<TAB>text')
        code, text = line.split('\t', 1)
        t[int(code, 16)] = text
    return t

def write_table(path, name='jp'):
    with open(path, 'w', encoding='utf-8') as f:
        f.write('# code<TAB>text   (character token in hex; glyph index = token - 0x80)\n')
        for k, v in sorted(builtin_table(name).items()): f.write(f'{k:x}\t{v}\n')
    print(f'wrote {path}')

# ---------------------------------------------------------------- dump
def words(b):
    return [struct.unpack_from('<H', b, i)[0] for i in range(0, len(b) - 1, 2)]

def dump_section(ws, table, anchors=None):
    """anchors: {word index: label index} -> emits {@N} before that token."""
    out = []
    i = 0
    while i < len(ws):
        if anchors and i in anchors: out.append('{@%d}' % anchors[i])
        w = ws[i]
        if w >= 0x80:
            s = table.get(w)
            if s is None: out.append(f'[{w:x}]')
            else: out.append(''.join('\\' + c if c in '{[#\\' else c for c in s))
            i += 1
        else:
            n = CMD_ARGS.get(w, 0)
            args = ws[i + 1:i + 1 + n]
            if len(args) < n: out.append(f'# truncated command {w:02x}\n'); i = len(ws); break
            out.append('{%02x%s}' % (w, (' ' + ' '.join(f'{a:x}' for a in args)) if n else ''))
            if w in PAGE_BREAK: out.append('\n')
            i += 1 + n
    if anchors and len(ws) in anchors: out.append('{@%d}' % anchors[len(ws)])
    return ''.join(out)

def read_bank(rom, bank):
    """-> (parsed bank, location) ; location = locate(rom, bank)"""
    loc = locate(rom, bank)
    if bank == 'common':
        return bk.parse_bank(loc['data']), loc
    b = int(bank); m = bk.main_bank_of(b)
    main = locate(rom, m)['data'] if m != b else None
    return bk.parse_bank(loc['data'], main), loc

def cmd_dump(a):
    rom = load_rom(a.rom); warn_not_gs3(rom)
    table = load_table(a.table)
    p, loc = read_bank(rom, a.bank)
    secs = p['sections']
    # label anchors: {section: {word index: label index}}; a label not on a token boundary is kept verbatim
    anchors = {}; verbatim = dict(p['stale'])
    for idx, (sec, off) in p['labels'].items():
        bounds = {i * 2: True for i, _, _ in bk.tokens(secs[sec])} if sec in secs else {}
        bounds[len(secs.get(sec, b''))] = True
        if sec in secs and off in bounds:
            anchors.setdefault(sec, {})[off // 2] = idx
        else:
            print(f'warning: label entry {idx} -> section {sec} offset {off:#x} is not on a token boundary; kept verbatim', file=sys.stderr)
            verbatim[idx] = p['entries'][idx]
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(f'# gs3_script dump: bank {a.bank} (ROM {loc["addr"]:#x}), {p["n"]} entries, '
                f'{len(secs)} sections, {len(p["labels"])} labels, {len(p["stale"])} stale\n')
        f.write('# {xx a b} = command, [xxx] = character code, {@N} = label anchor; see gs3_script.py --help\n')
        for n in range(p['n']):
            if n in secs:
                s = secs[n]
                f.write(f'\n@section {n}\n')
                if len(s) % 2: f.write(f'# odd section length {len(s)}; last byte {s[-1]:02x} kept as [odd {s[-1]:02x}]\n')
                f.write(dump_section(words(s), table, anchors.get(n)))
                if len(s) % 2: f.write(f'[odd {s[-1]:02x}]')
                f.write('\n')
            elif n in verbatim:
                f.write(f'@section {n} stale {verbatim[n]:#x}\n')
    print(f'wrote {a.out}: {len(secs)} sections, {sum(len(s) for s in secs.values())} bytes'
          + (f', {len(p["stale"])} stale entries (partial bank)' if p['stale'] else '')
          + (f', labels {sorted(p["labels"])}' if p['labels'] else ''))

# ---------------------------------------------------------------- insert
def parse_text(path, table):
    rev = {}
    for code, s in table.items():
        rev.setdefault(s, code)
    maxlen = max((len(s) for s in table.values()), default=1)
    secs = {}; stale = {}; labels = {}
    cur = None; buf = None; odd = None
    def flush():
        if cur is not None:
            b = b''.join(struct.pack('<H', w) for w in buf)
            if odd is not None: b += bytes([odd])
            secs[cur] = b
    for ln, line in enumerate(open(path, encoding='utf-8'), 1):
        line = line.rstrip('\n').rstrip('\r')
        if line.startswith('#'): continue
        if line.startswith('@section'):
            flush()
            parts = line.split()
            if len(parts) >= 4 and parts[2] == 'stale':
                stale[int(parts[1])] = int(parts[3], 0); cur = None; continue
            cur = int(parts[1]); buf = []; odd = None; continue
        if cur is None:
            if line.strip(): sys.exit(f'{path}:{ln}: text before the first @section')
            continue
        i = 0
        while i < len(line):
            c = line[i]
            if c == '\\':
                if i + 1 >= len(line): break
                s = line[i + 1]
                code = rev.get(s)
                if code is None: sys.exit(f'{path}:{ln}: escaped character {s!r} is not in the table')
                buf.append(code); i += 2; continue
            if c == '{':
                j = line.find('}', i)
                if j < 0: sys.exit(f'{path}:{ln}: unterminated {{')
                parts = line[i + 1:j].split()
                if parts[0].startswith('@'):
                    labels[int(parts[0][1:])] = (cur, len(buf) * 2); i = j + 1; continue
                cmd = int(parts[0], 16); args = [int(x, 16) for x in parts[1:]]
                if cmd >= 0x80: sys.exit(f'{path}:{ln}: {{{parts[0]}}} is not a command')
                if len(args) != CMD_ARGS.get(cmd, 0):
                    sys.exit(f'{path}:{ln}: command {cmd:02x} takes {CMD_ARGS.get(cmd, 0)} arguments, {len(args)} given')
                buf.append(cmd); buf.extend(args); i = j + 1; continue
            if c == '[':
                j = line.find(']', i)
                if j < 0: sys.exit(f'{path}:{ln}: unterminated [')
                body = line[i + 1:j].split()
                if body[0] == 'odd': odd = int(body[1], 16)
                else:
                    code = int(body[0], 16)
                    if code < 0x80: sys.exit(f'{path}:{ln}: [{body[0]}] is below 0x80 (use {{..}} for commands)')
                    buf.append(code)
                i = j + 1; continue
            # table lookup, longest match first
            for L in range(min(maxlen, len(line) - i), 0, -1):
                code = rev.get(line[i:i + L])
                if code is not None: buf.append(code); i += L; break
            else:
                sys.exit(f'{path}:{ln}: character {c!r} is not in the table (write it as [hex])')
    flush()
    if not secs: sys.exit(f'{path}: no sections')
    n = max(list(secs) + list(stale) + list(labels)) + 1
    missing = [k for k in range(n) if k not in secs and k not in stale and k not in labels]
    if missing: sys.exit(f'{path}: table entries without a section, stale line or label anchor: {missing}')
    return bk.build_bank(n, secs, labels, stale)

def cmd_insert(a):
    rom = bytearray(load_rom(a.rom)); warn_not_gs3(rom)
    table = load_table(a.table)
    data = parse_text(a.infile, table)
    loc = locate(rom, a.bank)
    d = directory(rom)
    old = loc['addr']
    if loc['comp_size'] is None:
        # uncompressed bank (common bank, or any bank of the English build)
        slot = len(loc['data'])
        if len(data) <= slot and a.at is None:
            rom[rom_off(old):rom_off(old) + slot] = data + b'\0' * (slot - len(data))
            new = old
            print(f'bank {a.bank} rewritten in place ({len(data)} of {slot} bytes)')
        else:
            if a.bank != 'common' and (a.at is not None and a.at < UNCOMPRESSED):
                sys.exit(f'an uncompressed bank must be placed at or above {UNCOMPRESSED:#x}')
            new = place(rom, data, a.at, 4, f'bank {a.bank}')
            n = repoint(rom, old, new, (0, 4) if a.bank == 'common' else (0,))
            print(f'{n} reference(s) updated')
        if d is not None:
            i = 44 if a.bank == 'common' else int(a.bank)
            struct.pack_into('<II', rom, rom_off(DIRECTORY) + 12 + 8 * i, new, len(data))
    else:
        if len(data) > BANK_BUFFER:
            print(f'warning: bank is {len(data):#x} bytes, more than the {BANK_BUFFER:#x}-byte EWRAM buffer', file=sys.stderr)
        comp = lz.compress(data, vram_safe=False)     # the game decompresses banks to EWRAM
        slot = (loc['comp_size'] + 3) & ~3           # the next object starts at the next 4-byte boundary
        if len(comp) <= slot and a.at is None:
            o = rom_off(old)
            rom[o:o + slot] = comp + b'\0' * (slot - len(comp))
            print(f'bank {a.bank} rewritten in place ({len(comp)} of {slot} compressed bytes, {len(data)} decompressed)')
        else:
            if d is not None and a.at is None:
                # English build: store it uncompressed in the expansion area instead
                new = place(rom, data, None, 4, f'bank {a.bank}')
                struct.pack_into('<II', rom, rom_off(DIRECTORY) + 12 + 8 * int(a.bank), new, len(data))
            else:
                if a.at is not None and a.at >= UNCOMPRESSED and d is not None:
                    sys.exit(f'a compressed bank cannot go at or above {UNCOMPRESSED:#x} in the English build')
                new = place(rom, comp, a.at, 4, f'bank {a.bank}')
            n = repoint(rom, old, new)
            print(f'{n} reference(s) updated')
            if n == 0: sys.exit('no reference found: the bank table of this ROM differs')
    save_rom(rom, a.out)

def cmd_list(a):
    rom = load_rom(a.rom); warn_not_gs3(rom)
    d = directory(rom)
    print('English build (bank directory present)' if d else 'original layout (compressed banks)')
    print(' bank  address      stored     size  sections')
    for idx in range(44):
        p, loc = read_bank(rom, idx)
        stored = f'{loc["comp_size"]:6} LZ' if loc['comp_size'] is not None else '  raw    '
        extra = f'  partial bank of {bk.main_bank_of(idx)} ({len(p["stale"])} stale entries)' if p['stale'] and bk.main_bank_of(idx) != idx else ''
        if p['labels']: extra += f'  labels {sorted(p["labels"])}'
        print(f'{idx:5}  {loc["addr"]:#x}  {stored} {len(loc["data"]):6}  {len(p["sections"]):5}{extra}')
    p, loc = read_bank(rom, 'common')
    print(f'common {loc["addr"]:#x}    raw     {len(loc["data"]):6}  {len(p["sections"]):5}')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('list'); p.add_argument('rom'); p.set_defaults(fn=cmd_list)
    p = sub.add_parser('dump'); p.add_argument('rom'); p.add_argument('bank'); p.add_argument('out')
    p.add_argument('--table'); p.set_defaults(fn=cmd_dump)
    p = sub.add_parser('insert'); p.add_argument('rom'); p.add_argument('bank'); p.add_argument('infile'); p.add_argument('out')
    p.add_argument('--table'); p.add_argument('--at', type=num); p.set_defaults(fn=cmd_insert)
    p = sub.add_parser('table'); p.add_argument('out'); p.add_argument('--table', default='jp')
    p.set_defaults(fn=lambda a: write_table(a.out, a.table))
    a = ap.parse_args()
    a.fn(a)

if __name__ == '__main__':
    main()
