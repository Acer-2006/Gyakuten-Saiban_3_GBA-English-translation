"""English script: banks resident in ROM, loader + jump functions patched."""
import os, sys, json, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
from rom import compile_c
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOADER_CALLS = [0x0801ef04, 0x0801ef24, 0x0801ef44, 0x0801ef94, 0x0801efb0, 0x0801efd0, 0x0801fb0c]
CHAPTER_TABLE = 0x08049b38           # 25 pointers (first block of each chapter)
EXTRA_BLOCK_LITS = {                  # block index -> literal address (from the loader switch)
    2: 0x1ee9c, 4: 0x1eecc, 6: 0x1eea4, 8: 0x1eeb4, 9: 0x1eebc, 12: 0x1eed4, 14: 0x1eee4, 16: 0x1ef54,
    18: 0x1eef4, 19: 0x1eefc, 22: 0x1ef14, 24: 0x1ef34, 26: 0x1ef74, 29: 0x1ef6c, 33: 0x1ef84,
    35: 0x1ef9c, 37: 0x1efa8, 40: 0x1efc0, 41: 0x1eff0}
LOADER_POOLS = (0x1ee80, 0x1f000)   # the loader's literal pools (offsets)
COMMON_LITS = [(0x1ed64, 0), (0x1ed60, 4)]   # (literal address, offset from bank base)
JUMP_SECTION = 0x0801fcd8
JUMP_LABEL   = 0x0801fc9c

DIRECTORY = 0x08800000               # bank directory written for tools: 'GS3E', u32 1, u32 45, {u32 addr, u32 len} x 45
                                     # (banks 0..43 then the common bank; len 0 = LZ-compressed at addr)

def apply(rom, ctx):
    table = ctx.gba_table
    en = ctx.en_banks if ctx.en_banks is not None else ctx.convert()
    # 1. place English banks in the expansion area, after the bank directory
    dir_addr = rom.alloc(16 + 45 * 8, 'ext', 4)
    assert dir_addr == DIRECTORY, hex(dir_addr)
    bank_addr = {}
    for b in range(42):
        bank_addr[b] = rom.store(en[b], 'ext', 4, f'en bank {b}')
    common = rom.store(en['common'], 'ext', 4, 'en common bank')
    print(f"  English banks at {bank_addr[0]:#x}.., common at {common:#x}; ext used {rom.regions['ext'].used/1e6:.2f} MB")
    entries = []
    for b in range(44):
        if b in bank_addr: entries.append((bank_addr[b], len(en[b])))
        else: entries.append((0x08000000 + [t for t in table if t['idx'] == b][0]['rom_off'], 0))
    entries.append((common, len(en['common'])))
    rom.write(dir_addr, b'GS3E' + struct.pack('<II', 1, 45) + b''.join(struct.pack('<II', a, l) for a, l in entries), 'bank directory')

    # 2. compile script.c
    text_addr = 0x08000000 + ((rom.regions['font'].cur + 3) & ~3)
    binary, syms, bss = compile_c([os.path.join(ROOT, 'src/script.c')], text_addr, 0x02028100,
                                  os.path.join(ROOT, 'build/script'),
                                  defines=[f'COMMON_BANK_ADDR={common:#x}'], ld_defsyms={
                                      'f_801e210': 0x0801e211, 'f_801e4ac': 0x0801e4ad, 'f_801fb98': 0x0801fb99,
                                      'common_bank_addr': common})
    rom.store(binary, 'font', 4, 'script code')
    print(f"  script code at {text_addr:#x} ({len(binary)} bytes)")

    # 3. loader call sites -> script_load
    for site in LOADER_CALLS:
        assert rom.u16(site) & 0xf800 == 0xf000, hex(site)
        rom.thumb(site, f'bl #{syms["script_load"] & ~1:#x}', 'script_load')
    # 4. jump functions -> C versions
    for site, fn in ((JUMP_SECTION, 'jump_section'), (JUMP_LABEL, 'jump_label')):
        rom.thumb(site, f'ldr r1, [pc, #0]\n bx r1\n .word {syms[fn] | 1:#x}', fn)
    # 5. bank pointers
    chapter_first = {}   # block index -> table slot
    ptrs = [rom.u32(CHAPTER_TABLE + i * 4) for i in range(25)]
    by_addr = {0x08000000 + t['rom_off']: t['idx'] for t in table}
    for i, p in enumerate(ptrs):
        b = by_addr[p]
        if b in bank_addr: rom.w32(CHAPTER_TABLE + i * 4, bank_addr[b])
    for b, lit in EXTRA_BLOCK_LITS.items():
        assert by_addr[rom.u32(0x08000000 + lit)] == b, (b, hex(rom.u32(0x08000000 + lit)))
    # every bank pointer in the loader's literal pools: besides the 19 above, the loader's switch
    # also loads the first bank of seven chapters (3, 7, 13, 17, 28, 32, 34) from here, which is
    # the way in when an episode is started from the episode select or a save is continued
    redirected = 0
    for lit in range(LOADER_POOLS[0], LOADER_POOLS[1], 4):
        b = by_addr.get(rom.u32(0x08000000 + lit))
        if b is not None and b in bank_addr:
            rom.w32(0x08000000 + lit, bank_addr[b]); redirected += 1
    assert redirected == len(EXTRA_BLOCK_LITS) + 7, redirected
    for lit, off in COMMON_LITS:
        assert rom.u32(0x08000000 + lit) == 0x086e3578 + off
        rom.w32(0x08000000 + lit, common + off)
