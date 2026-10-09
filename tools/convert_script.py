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
ADS = dict(A); ADS.update({0x74: 2, 0x75: 4, 0x76: 2, 0x77: 2, 0x78: 1})
TEXT_CMDS = {0x01, 0x02, 0x03, 0x0b, 0x0c, 0x2d, 0x2e, 0x45}   # emitted verbatim from E
DS_ONLY = {0x53, 0x74, 0x75, 0x76, 0x77, 0x78}                 # never emitted
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
            for pos, (ga, ja) in enumerate(zip(gi[2], ji[2])):
                mp[(gi[1], pos)][ja][ga] += 1
    out = {}
    for key, d in mp.items():
        m = {jv: c.most_common(1)[0][0] for jv, c in d.items()}
        gvals = set(m.values())
        if len(gvals) == 1: m['*'] = next(iter(gvals))   # G side constant for this slot
        out[key] = m
    return out

def map_args(cmd, args, argmap):
    res = []
    for p, a in enumerate(args):
        m = argmap.get((cmd, p))
        if m is None: res.append(a)
        elif a in m: res.append(m[a])
        elif '*' in m: res.append(m['*'])
        else: res.append(a)
    return tuple(res)

def convert_section(g, j, e, argmap, labels=None, stats=None):
    je = align(j, e, True)          # e index -> j index
    gj = align(g, j, False)         # j index -> g index
    out = []
    i = 0
    while i < len(e):
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
    pairs = []
    banks = {}
    for b in range(42):
        G = load_bank(ctx.gba_banks[b]); J = load_bank(ctx.ds_banks[2 * b]); E = load_bank(ctx.ds_banks[2 * b + 1])
        banks[b] = (G, J, E)
        for s in range(len(G)):
            pairs.append((tok(words(G[s]), A), tok(words(J[s]), ADS)))
    Graw = load_bank(ctx.gba_common); Jraw = load_bank(ctx.ds_banks[84]); Eraw = load_bank(ctx.ds_banks[85])
    for s in range(len(Graw)):
        pairs.append((tok(words(Graw[s]), A), tok(words(Jraw[s]), ADS)))
    argmap = learn_argmap(pairs)
    stats = Counter()
    gba_menus = {}
    for b in range(42):
        for s, sec in enumerate(banks[b][0]):
            tg = tok(words(sec), A)
            if any(it[0] == 'c' and it[1] == 0x07 for it in tg): gba_menus.setdefault(b, []).append(s)
    labels = menu_labels(ctx.arm9, gba_menus)
    out = {}
    for b in range(42):
        G, J, E = banks[b]
        secs = []
        for s in range(len(G)):
            conv = convert_section(tok(words(G[s]), A), tok(words(J[s]), ADS), tok(words(E[s]), ADS), argmap,
                                   labels=labels.get((b, s)), stats=stats)
            secs.append(pack(items_to_words(conv)))
        out[b] = save_bank(secs)
    secs = []
    for s in range(len(Graw)):   # keep the GBA section count (52); the DS has 54
        conv = convert_section(tok(words(Graw[s]), A), tok(words(Jraw[s]), ADS), tok(words(Eraw[s]), ADS), argmap, stats=stats)
        secs.append(pack(items_to_words(conv)))
    out['common'] = save_bank(secs)
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
