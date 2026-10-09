#!/usr/bin/env python3
"""Script bank structure: section table with partial banks and label entries.

A bank is `u32 count` + `u32 entry[count]` + section data.  Most entries are byte offsets of
sections (section n = entry n), but two other kinds of entry exist:

* A *partial bank* (one loaded through the loader's literal pool rather than the chapter table,
  with the same entry count as the chapter's main bank) only carries some of the chapter's
  sections.  Its other entries are copies of the main bank's offsets and are never used while the
  partial bank is loaded; we call them *stale* and keep them verbatim.
* A *label entry* is `{u16 byte offset, u16 section}`, the target of command 0x36 (its argument is
  the entry index).  The three in the game sit after the last section of their bank.

`parse_bank` tells the three apart; `build_bank` writes a bank back with recomputed offsets.
"""
import os, json, struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CMD_ARGS = {int(k, 16): v for k, v in json.load(open(os.path.join(ROOT, 'data', 'cmd_args.json'))).items()}
MAIN_BANKS = [0, 1, 3, 5, 7, 10, 11, 13, 15, 17, 20, 21, 23, 25, 27, 28, 30, 31, 32, 34, 36, 38, 39, 42, 43]

def main_bank_of(idx):
    """The chapter's main bank for bank `idx` (idx itself if it is a main bank)."""
    return max(m for m in MAIN_BANKS if m <= idx)

def entries(data):
    n = struct.unpack_from('<I', data, 0)[0]
    return list(struct.unpack_from('<%dI' % n, data, 4))

def tokens(sec, cmd_args=CMD_ARGS):
    """-> list of (word index, token, args) for a section."""
    ws = [struct.unpack_from('<H', sec, i)[0] for i in range(0, len(sec) - 1, 2)]
    out = []; i = 0
    while i < len(ws):
        w = ws[i]
        if w >= 0x80: out.append((i, w, ())); i += 1
        else:
            n = cmd_args.get(w, 0); out.append((i, w, tuple(ws[i + 1:i + 1 + n]))); i += 1 + n
    return out

def parse_bank(data, main=None, cmd_args=CMD_ARGS, labels=None):
    """-> dict(n, entries, present, sections, labels, stale)
    main: the chapter's main bank (bytes) when `data` may be a partial bank, else None.
    labels: explicit set of label-entry indices (default: the targets of command 0x36 in the bank)."""
    ents = entries(data); n = len(ents); hdr = 4 + 4 * n
    # 1. monotonic chain of in-range offsets
    chain = []; last = hdr
    for i, o in enumerate(ents):
        if hdr <= o <= len(data) and o >= last: chain.append(i); last = o
    present = chain
    # 2. partial bank: entries equal to the main bank's are stale copies
    if main is not None and main is not data:
        ments = entries(main)
        if len(ments) == n and ments != ents:
            present = [i for i in chain if i == 0 or ents[i] != ments[i]]
    # 3. label entries: indices used by command 0x36
    used = set(labels) if labels is not None else set()
    pres = sorted(present)
    if labels is None:
        for k, i in enumerate(pres):
            end = ents[pres[k + 1]] if k + 1 < len(pres) else len(data)
            for _, w, args in tokens(data[ents[i]:end], cmd_args):
                if w == 0x36 and args: used.add(args[0])
    labels = {}
    for i in sorted(used):
        if i < n:
            labels[i] = (ents[i] >> 16, ents[i] & 0xffff)
            if i in present: present.remove(i)
    sections = {}
    pres = sorted(present)
    for k, i in enumerate(pres):
        end = ents[pres[k + 1]] if k + 1 < len(pres) else len(data)
        sections[i] = data[ents[i]:end]
    stale = {i: ents[i] for i in range(n) if i not in sections and i not in labels}
    return {'n': n, 'entries': ents, 'present': pres, 'sections': sections, 'labels': labels, 'stale': stale}

def build_bank(n, sections, labels=None, stale=None):
    """sections: {index: bytes}; labels: {index: (section, byte offset)}; stale: {index: raw u32}."""
    labels = labels or {}; stale = stale or {}
    hdr = 4 + 4 * n
    offs = {}; body = b''
    for i in sorted(sections):
        offs[i] = hdr + len(body); body += sections[i]
    ents = []
    for i in range(n):
        if i in sections: ents.append(offs[i])
        elif i in labels:
            sec, off = labels[i]; ents.append((sec << 16) | (off & 0xffff))
        elif i in stale: ents.append(stale[i] & 0xffffffff)
        else: raise ValueError(f'entry {i} undefined')
    return struct.pack('<I', n) + b''.join(struct.pack('<I', e) for e in ents) + body

def simple_sections(data):
    """Plain section list (every entry an offset) for banks known to have no stale/label entries."""
    p = parse_bank(data)
    return [p['sections'][i] for i in sorted(p['sections'])]
