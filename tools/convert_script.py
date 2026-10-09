#!/usr/bin/env python3
"""Three-way merge: DS English text + DS English command edits, converted to GBA conventions.

For every section:  G = GBA-JP, J = DS-JP, E = DS-EN.
  * J<->E share the command skeleton (text differs)        -> maps each E command to a J command
  * G<->J share the text (DS-specific commands/args differ)  -> maps each J command to a G command
Output = E's stream with: DS-only commands dropped, args taken from G where E==J, otherwise
E's args translated through a learned DS->GBA argument map.
Choice menu labels (absent on DS) are taken from G for now (Japanese) unless an override exists.
"""
import os, sys, json, difflib, struct, pickle
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mes import load_bank, save_bank, words, pack

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = {int(k, 16): v for k, v in json.load(open(os.path.join(ROOT, 'data/cmd_args.json'))).items()}
ADS = dict(A); ADS.update({0x74: 2, 0x75: 4, 0x76: 2, 0x77: 2, 0x78: 1,
                           0x3a: 3})   # DS 0x3a is (slot, x, y); the GBA packs it as (slot<<8, x<<8|y)
TEXT_CMDS = {0x01, 0x02, 0x03, 0x0b, 0x0c, 0x2d, 0x2e, 0x45}   # emitted verbatim from E
DS_ONLY = {0x74, 0x75, 0x76, 0x77, 0x78}                       # never emitted
# 0x53 exists on both (33 uses on the GBA, 117 on the DS): it is kept where it lines up with a GBA
# 0x53 and dropped where the DS added it.
CHOICE_END = {0x08, 0x09, 0x0a}

def tok(ws, tab):
    out = []; i = 0
    while i < len(ws):
        w = ws[i]
        if w >= 0x80: out.append(('t', w, ())); i += 1
        else:
            n = tab.get(w, 0); out.append(('c', w, tuple(ws[i + 1:i + 1 + n]))); i += 1 + n
    return out

def cmds(items):
    return [(k, it) for k, it in enumerate(items) if it[0] == 'c']

def align(a_items, b_items, with_args):
    """Return dict: index in b -> index in a for matched commands."""
    ca, cb = cmds(a_items), cmds(b_items)
    ka = [(it[1], it[2]) if with_args else it[1] for _, it in ca]
    kb = [(it[1], it[2]) if with_args else it[1] for _, it in cb]
    sm = difflib.SequenceMatcher(a=ka, b=kb, autojunk=False)
    m = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for x in range(i2 - i1): m[cb[j1 + x][0]] = ca[i1 + x][0]
        elif tag == 'replace' and not with_args:
            pass
    if with_args:
        # second pass: match leftover commands by cmd id only (EN arg edits)
        left_a = [(k, it) for k, it in ca if k not in m.values()]
        left_b = [(k, it) for k, it in cb if k not in m]
        sm = difflib.SequenceMatcher(a=[it[1] for _, it in left_a], b=[it[1] for _, it in left_b], autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                for x in range(i2 - i1): m[left_b[j1 + x][0]] = left_a[i1 + x][0]
    return m

def learn_argmap(pairs):
    """pairs: iterable of (G items, J items). Returns {(cmd,pos): {jval: gval}}."""
    mp = defaultdict(lambda: defaultdict(Counter))
    for g, j in pairs:
        m = align(g, j, False)
        for jk, gk in m.items():
            gi, ji = g[gk], j[jk]
            if len(gi[2]) != len(ji[2]): continue      # layout differs (0x3a), see ds_to_gba_args
            for pos, (ga, ja) in enumerate(zip(gi[2], ji[2])):
                mp[(gi[1], pos)][ja][ga] += 1
    out = {}
    for key, d in mp.items():
        m = {jv: c.most_common(1)[0][0] for jv, c in d.items()}
        gvals = set(m.values())
        if len(gvals) == 1: m['*'] = next(iter(gvals))   # G side constant for this slot
        out[key] = m
    return out

def ds_to_gba_args(cmd, args):
    """Commands whose argument layout differs between the DS and GBA scripts."""
    if cmd == 0x3a and len(args) == 3:          # (slot, x, y) -> (slot << 8, x << 8 | y)
        return (args[0] << 8 & 0xffff, (args[1] & 0xff) << 8 | (args[2] & 0xff))
    return None

def map_args(cmd, args, argmap):
    fixed = ds_to_gba_args(cmd, args)
    if fixed is not None: return fixed
    res = []
    for p, a in enumerate(args):
        m = argmap.get((cmd, p))
        if m is None: res.append(a)
        elif a in m: res.append(m[a])
        elif '*' in m: res.append(m['*'])
        else: res.append(a)
    return tuple(res)

def convert_section(g, j, e, argmap, labels=None, stats=None, emap=None):
    """emap (optional dict) receives E item index -> output item index, for label entries."""
    je = align(j, e, True)          # e index -> j index
    gj = align(g, j, False)         # j index -> g index
    out = []
    i = 0
    while i < len(e):
        if emap is not None: emap[i] = len(out)
        it = e[i]
        if it[0] == 't':
            out.append(it); i += 1; continue
        c = it[1]
        if c == 0x07:
            # choice menu: take labels from G (or override), then the terminator from G
            gk = None
            jk = je.get(i)
            if jk is not None: gk = gj.get(jk)
            if gk is None:
                gk = next((k for k, x in enumerate(g) if x[0] == 'c' and x[1] == 0x07), None)
            out.append(('c', 0x07, ()))
            if gk is not None:
                k = gk + 1
                glabels = []
                while k < len(g) and not (g[k][0] == 'c' and g[k][1] in CHOICE_END):
                    glabels.append(g[k]); k += 1
                term = g[k] if k < len(g) else None
                if labels is not None:
                    for n, lab in enumerate(labels):
                        if n: out.append(('c', 0x01, ()))
                        out.extend(('t', ch, ()) for ch in lab)
                    if stats is not None: stats['labels_en'] += 1
                else:
                    out.extend(glabels)
            else:
                term = None
            # skip E's (empty) labels up to its terminator
            i += 1
            while i < len(e) and not (e[i][0] == 'c' and e[i][1] in CHOICE_END): i += 1
            if i < len(e):
                eterm = e[i]; i += 1
                out.append(term if term is not None else eterm)
            if stats is not None: stats['choices'] += 1
            continue
        if c in TEXT_CMDS:
            out.append(it); i += 1; continue
        if c in DS_ONLY:
            i += 1
            if stats is not None: stats['dropped_dsonly'] += 1
            continue
        jk = je.get(i)
        if jk is None and c == 0x53:
            i += 1
            if stats is not None: stats['dropped_dsonly'] += 1
            continue
        if jk is None:
            # EN-only command: translate args
            out.append(('c', c, map_args(c, it[2], argmap)))
            if stats is not None: stats['en_only'] += 1
            i += 1; continue
        gk = gj.get(jk)
        if gk is None:
            # DS-only insertion (J has it, G doesn't): drop
            if stats is not None: stats['dropped_ds_ins'] += 1
            i += 1; continue
        gi = g[gk]; ji = j[jk]
        if it[2] == ji[2]:
            out.append(('c', c, gi[2]))
        else:
            out.append(('c', c, map_args(c, it[2], argmap)))
            if stats is not None: stats['en_edit'] += 1
        i += 1
    if emap is not None: emap[len(e)] = len(out)
    return out

def items_to_words(items):
    ws = []
    for it in items:
        if it[0] == 't': ws.append(it[1])
        else: ws.append(it[1]); ws.extend(it[2])
    return ws

def run_mem(ctx):
    """Convert using data from a BuildContext; returns ({bank idx: bytes, 'common': bytes}, stats)."""
    from labels_en import menu_labels
    import banks as bk
    pairs = []
    parsed = {}
    for b in range(42):
        m = bk.main_bank_of(b)
        G = bk.parse_bank(ctx.gba_banks[b], ctx.gba_banks[m] if m != b else None)
        # the DS banks follow the GBA classification (DS-only 0x36 jumps target plain sections)
        J = bk.parse_bank(ctx.ds_banks[2 * b], ctx.ds_banks[2 * m] if m != b else None, labels=set(G['labels']))
        E = bk.parse_bank(ctx.ds_banks[2 * b + 1], ctx.ds_banks[2 * m + 1] if m != b else None, labels=set(G['labels']))
        assert G['n'] == J['n'] == E['n'] and G['present'] == J['present'] == E['present'], (b, G['n'], J['n'], E['n'])
        parsed[b] = (G, J, E)
        for s in G['present']:
            pairs.append((tok(words(G['sections'][s]), A), tok(words(J['sections'][s]), ADS)))
    Graw = bk.parse_bank(ctx.gba_common); Jraw = bk.parse_bank(ctx.ds_banks[84]); Eraw = bk.parse_bank(ctx.ds_banks[85])
    for s in Graw['present']:
        pairs.append((tok(words(Graw['sections'][s]), A), tok(words(Jraw['sections'][s]), ADS)))
    argmap = learn_argmap(pairs)
    stats = Counter()
    gba_menus = {}
    for b in range(42):
        G = parsed[b][0]
        for s in G['present']:
            tg = tok(words(G['sections'][s]), A)
            if any(it[0] == 'c' and it[1] == 0x07 for it in tg): gba_menus.setdefault(b, []).append(s)
    labels = menu_labels(ctx.arm9, gba_menus)
    out = {}
    for b in range(42):
        G, J, E = parsed[b]
        secs = {}; emaps = {}
        for s in G['present']:
            emap = {}
            conv = convert_section(tok(words(G['sections'][s]), A), tok(words(J['sections'][s]), ADS),
                                   tok(words(E['sections'][s]), ADS), argmap, labels=labels.get((b, s)), stats=stats, emap=emap)
            secs[s] = pack(items_to_words(conv)); emaps[s] = (conv, emap)
        # label entries (command 0x36 targets): E's byte offset -> E item index -> output item -> byte offset
        new_labels = {}
        for idx, (sec, off) in E['labels'].items():
            e_items = tok(words(E['sections'][sec]), ADS)
            pos = 0; e_index = len(e_items)
            for k, it in enumerate(e_items):
                if pos * 2 >= off: e_index = k; break
                pos += 1 + len(it[2])
            conv, emap = emaps[sec]
            o_index = emap[e_index]
            new_off = sum(1 + len(it[2]) for it in conv[:o_index]) * 2
            new_labels[idx] = (sec, new_off)
            stats['labels_0x36'] += 1
        # a partial bank's unused entries stay copies of its (already converted) main bank's
        m = bk.main_bank_of(b)
        stale = {i: bk.entries(out[m])[i] for i in G['stale']} if m != b and len(bk.entries(out[m])) == G['n'] else G['stale']
        out[b] = bk.build_bank(G['n'], secs, new_labels, stale)
    secs = {}
    for s in Graw['present']:   # keep the GBA section count (52); the DS has 54
        conv = convert_section(tok(words(Graw['sections'][s]), A), tok(words(Jraw['sections'][s]), ADS),
                               tok(words(Eraw['sections'][s]), ADS), argmap, stats=stats)
        secs[s] = pack(items_to_words(conv))
    out['common'] = bk.build_bank(Graw['n'], secs, Graw['labels'], Graw['stale'])
    return out, dict(stats)

def run(out_dir):
    """Development helper: convert from the extracted files and write extract/en/*."""
    import pipeline
    ctx = pipeline.BuildContext(os.path.join(ROOT, 'roms/gs3_jp.gba'), os.path.join(ROOT, 'roms/tt_us.nds'))
    out, stats = run_mem(ctx)
    os.makedirs(out_dir, exist_ok=True)
    sizes = {}
    for k, v in out.items():
        name = f'bank_{k:02d}.bin' if isinstance(k, int) else 'bank_raw.bin'
        open(os.path.join(out_dir, name), 'wb').write(v); sizes[k] = len(v)
    json.dump({'sizes': {str(k): v for k, v in sizes.items()}, 'stats': stats}, open(f'{out_dir}/report.json', 'w'), indent=1)
    return sizes, stats

if __name__ == '__main__':
    sizes, stats = run(os.path.join(ROOT, 'extract/en'))
    print('stats:', dict(stats))
    print('total bytes:', sum(sizes.values()), 'max bank:', max(sizes.values()))
