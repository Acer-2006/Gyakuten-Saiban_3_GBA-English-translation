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
CMD_TABLE = 0x08163afc                # the script's dispatch table (121 entries)
PSYCHE_END_HANDLER = 0x0802393c       # command 0x64
FADE_START = 0x08000b40               # start a brightness fade (mode, frames per step, step, layers)
FADE_START_BYTES = bytes.fromhex('30b5094ca44688340025238063468a33188060468e30017001300270'
                                 '0338058030bc01bc0047')
# the step of a fade in the main loop: BLDY - step (modes 1, 3) or + step (modes 2, 4), stored
FADE_STEPS = ((0x08000c26, '081a1080', 'down'), (0x08000dfc, '081a1080', 'down'),
              (0x08000d98, '28181080', 'up'), (0x08000e70, '28181080', 'up'))
JUMP_SECTION = 0x0801fcd8
JUMP_LABEL   = 0x0801fc9c

SCRIPT_BSS = 0x02028800               # after the renderer's state (patches/text.py)
SAVE_WRITE = 0x0800ac22               # bl WriteSramEx(0x02000000, 0x0e000000, 0x2c54): the game's save
CONTINUE_REDRAW = 0x0800dcd4          # bl 0x08020024 after a saved game's state is put back
RESTORE_TEXT = 0x08020024
SRAM_SYMS = {'sram_write': 0x0803a1ad, 'sram_read': 0x0803a075}   # WriteSramEx, ReadSram
DIRECTORY = 0x08800000               # bank directory written for tools: 'GS3E', u32 1, u32 45, {u32 addr, u32 len} x 45
                                     # (banks 0..43 then the common bank; len 0 = LZ-compressed at addr)
# Every English bank sits in a slot of a fixed size (data/bank_slots.json: its length when the slots
# were set, plus a sixteenth and 1 KB), so that a script fix that changes one bank's length moves
# no other: a save state holds absolute script addresses (the text pointer, script.c's bank_base),
# and one made with an earlier build then still finds its script.  A bank that outgrows its slot
# stops the build; raising the slot moves every bank after it (and breaks save states once).
SLOTS = os.path.join(ROOT, 'data', 'bank_slots.json')

def place(rom, data, size, note):
    if len(data) > size:
        raise SystemExit(f'script: {note} is {len(data)} bytes, more than its slot of {size} '
                         f'(raise it in data/bank_slots.json; every bank after it moves)')
    a = rom.alloc(size, 'ext', 4)
    rom.write(a, data, note)
    return a

def apply(rom, ctx):
    table = ctx.gba_table
    en = ctx.en_banks if ctx.en_banks is not None else ctx.convert()
    # 1. place English banks in the expansion area, after the bank directory
    dir_addr = rom.alloc(16 + 45 * 8, 'ext', 4)
    assert dir_addr == DIRECTORY, hex(dir_addr)
    bank_addr = {}
    slots = json.load(open(SLOTS))
    for b in range(42):
        bank_addr[b] = place(rom, en[b], slots[str(b)], f'en bank {b}')
    common = place(rom, en['common'], slots['common'], 'en common bank')
    print(f"  English banks at {bank_addr[0]:#x}.., common at {common:#x}; ext used {rom.regions['ext'].used/1e6:.2f} MB")
    entries = []
    for b in range(44):
        if b in bank_addr: entries.append((bank_addr[b], len(en[b])))
        else: entries.append((0x08000000 + [t for t in table if t['idx'] == b][0]['rom_off'], 0))
    entries.append((common, len(en['common'])))
    rom.write(dir_addr, b'GS3E' + struct.pack('<II', 1, 45) + b''.join(struct.pack('<II', a, l) for a, l in entries), 'bank directory')

    # 2. compile script.c
    text_addr = 0x08000000 + ((rom.regions['font'].cur + 3) & ~3)
    binary, syms, bss = compile_c([os.path.join(ROOT, 'src/script.c')], text_addr, SCRIPT_BSS,
                                  os.path.join(ROOT, 'build/script'),
                                  defines=[f'COMMON_BANK_ADDR={common:#x}'], ld_defsyms={
                                      'f_801e210': 0x0801e211, 'f_801e4ac': 0x0801e4ad, 'f_801fb98': 0x0801fb99,
                                      'f_802393c': PSYCHE_END_HANDLER | 1, 'f_802239c': 0x0802239d,
                                      'common_bank_addr': common, **SRAM_SYMS})
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

    # 5b. command 0x64 (a Psyche-Lock conversation ends) -> psyche_end (src/script.c): the script
    # stops for the frame after it, as it does on the wait that follows it everywhere but once
    assert rom.u32(CMD_TABLE + 0x64 * 4) == PSYCHE_END_HANDLER | 1
    rom.w32(CMD_TABLE + 0x64 * 4, syms['psyche_end'] | 1)

    # 5c. the start of a brightness fade (0x08000b40: command 0x12 and the engine's own) ->
    # fade_start (src/script.c), which first finishes a fade under way that the new one could not
    # end from (a strobe in Ron's "night of the crime"); the function keeps its push and pop
    assert rom.read(FADE_START, 0x26) == FADE_START_BYTES, rom.read(FADE_START, 0x26).hex()
    rom.thumb(FADE_START + 2, f'bl #{syms["fade_start"] & ~1:#x}\n b #{FADE_START + 0x20:#x}', 'fade_start')
    # ... and a fade under way that still cannot land (one in a savestate, or a level the engine set
    # itself) stops on its target where its step would take it past: down from above 0 (modes 1
    # and 3: r1 the level, r0 the step) or up from below 16 (modes 2 and 4: r5 the level).  From
    # the target itself it goes round as before (a flash).  Only r0 and the flags change.
    down = rom.thumb_code('''
        subs r0, r1, r0
        bpl store
        cmp r1, #0
        beq store
        movs r0, #0
    store:
        strh r0, [r2]
        bx lr
    ''', note='fade step down')
    up = rom.thumb_code('''
        adds r0, r5, r0
        cmp r5, #16
        bhs store
        cmp r0, #16
        bls store
        movs r0, #16
    store:
        strh r0, [r2]
        bx lr
    ''', note='fade step up')
    for site, old, fn in FADE_STEPS:
        assert rom.read(site, 4) == bytes.fromhex(old), hex(site)
        rom.hook_bl(site, down if fn == 'down' else up, 'fade step')

    # 6. saved games (src/script.c): the save also records where the script stopped, and continuing
    # a save finds that place in this build's script, then draws the page again (src/vwf.c)
    assert rom.read(SAVE_WRITE, 4) == rom.asm_thumb(SAVE_WRITE, f'bl #{SRAM_SYMS["sram_write"] & ~1:#x}')
    rom.thumb(SAVE_WRITE, f'bl #{syms["script_save"] & ~1:#x}', 'save hook')
    assert rom.read(CONTINUE_REDRAW, 4) == rom.asm_thumb(CONTINUE_REDRAW, f'bl #{RESTORE_TEXT:#x}')
    tramp = rom.thumb_code(f'''
        push {{lr}}
        bl #{syms["script_resume"] & ~1:#x}
        bl #{rom.syms["vwf_restore"] & ~1:#x}
        bl #{RESTORE_TEXT:#x}
        bl #{rom.syms["vwf_resume"] & ~1:#x}
        pop {{pc}}
    ''', note='continue trampoline')
    rom.thumb(CONTINUE_REDRAW, f'bl #{tramp & ~1:#x}', 'continue hook')
