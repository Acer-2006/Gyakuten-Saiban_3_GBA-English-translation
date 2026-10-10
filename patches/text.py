"""Text engine: VWF renderer on a BG1 tile canvas, 3-line box, English font."""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
from rom import compile_c
import genfont, dsfont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Engine addresses
DRAW_CALL       = 0x0801f986   # bl 0x801f4c4 (cell draw) in the dispatcher
NEWLINE_HANDLER = 0x0802172d   # command 0x01 handler
CMD_TABLE       = 0x08163afc   # dispatch table (121 entries)
BSS_ADDR        = 0x02028000
FRAME_TEMPLATE  = 0x0803b844   # 32x32 byte map template of the normal text box
TAG_ROW14_LIT   = 0x08006678   # literal 0x3002400 (row 14) in the name-tag drawer
TAG_ROW12_LIT   = 0x0800667c   # literal 0x3002380 (row 12)
TAG_ERASE_FROM  = 0x0800658c   # movs r4, #0xc0 (<< 1: template entry 0x180, row 12) when there is no tag
# loops that clear map rows 12-19 (0x100 entries from 0x180): (start, the instruction after the
# loop, what the replaced instructions set up that is used after it)
BOX_CLEARS = [(0x08022166, 0x08022186, 'adds r4, r7, #0\n adds r4, #0x23'),   # command 0x1c
              (0x08021c8e, 0x08021caa, 'ldr r5, [pc, #0x4c]')]                # after a choice:
                                                                  # r5 = 0x03002080 (0x08021cdc)
TAG_ERASE_DST   = 0x08006596   # movs r5, #0xc0 (<< 2: map byte offset 0x300, row 12)
VRAMUPD_HOOK    = 0x08006686   # ldr r3,[pc,#0xc4]; ldr r2,[pc,#0xc4]  (after push {r4,lr})
RESTORE_TEXT    = 0x08020024   # redraws text sprites from the sprite records after a state restore
RESTORE_CALLS   = (0x0800bcc4, 0x08014464)   # 0x0800dcd4, continuing a save: patches/script.py

UI_PAL = [0x0000,0x0400,0x1ce7,0x4210,0x739c,0x3800,0x3cc5,0x5a0c,0x7fff,0x0c6c,0x3191,0x4656,0x631b,0x3def,0x028c,0x03ff]
TEXT_PAL = {13: 0x167f, 14: 0x7eed, 15: 0x2be7}

def call_hook(rom, site, target, displaced, note='', keep=('r0', 'r1', 'r2', 'r3')):
    """Replace the 4 bytes at `site` with a bl to a trampoline that calls C function `target`
    (preserving the `keep` registers and r12), then re-executes `displaced` (the instructions
    that were at `site`) and returns to site+4."""
    regs = ', '.join(keep)
    tramp = rom.thumb_code(f'''
        push {{{regs}, lr}}
        mov r0, r12
        push {{r0}}
        bl #{target & ~1:#x}
        pop {{r0}}
        mov r12, r0
        pop {{{regs}}}
        {displaced}
        pop {{pc}}
    ''', note=note + ' trampoline')
    rom.thumb(site, f'bl #{tramp & ~1:#x}', note + ' hook')

def apply(rom, ctx):
    genfont.gen()
    # font tables (from the DS ROM) first, at fixed positions in the old font area
    rows, widths = dsfont.tables(ctx.data, ctx.arm9)
    rows_addr = rom.store(rows, 'font', 4, 'font rows')
    w_addr = rom.store(widths, 'font', 4, 'font widths')
    text_addr = 0x08000000 + ((rom.regions['font'].cur + 3) & ~3)
    binary, syms, bss = compile_c([os.path.join(ROOT, 'src/vwf.c')], text_addr, BSS_ADDR,
                                  os.path.join(ROOT, 'build/vwf'),
                                  ld_defsyms={'font_rows': rows_addr, 'font_w': w_addr})
    code_addr = rom.store(binary, 'font', 4, 'vwf code')
    assert code_addr == text_addr
    assert bss <= 0x800, bss                 # script.c's state follows at 0x02028800
    print(f"  vwf code at {code_addr:#x} ({len(binary)} bytes), bss {bss} bytes")
    rom.syms = syms

    # 1. character draw -> vwf_draw_char (args r0=code-0x80, r1=col, r2=row)
    rom.thumb(DRAW_CALL, f'bl #{syms["vwf_draw_char"] & ~1:#x}', 'char draw hook')

    # 2. newline: dispatch table entry 0x01 -> trampoline
    tramp_nl = rom.thumb_code(f'''
        push {{r4, lr}}
        bl #{syms["vwf_newline"] & ~1:#x}
        pop {{r4}}
        pop {{r0}}
        mov lr, r0
        ldr r0, [pc, #0]
        bx r0
        .word {NEWLINE_HANDLER:#x}
    ''', note='newline trampoline')
    rom.w32(CMD_TABLE + 1 * 4, tramp_nl)

    # 3. page clears / text state resets -> vwf_clear
    call_hook(rom, 0x08021ab0, syms['vwf_clear'], 'movs r0, #0\n strb r0, [r3]', 'page clear (wait)', keep=('r1', 'r2', 'r3'))
    call_hook(rom, 0x08022622, syms['vwf_clear'], 'movs r0, #0\n strb r0, [r4]', 'page clear (0x2e)', keep=('r1', 'r2', 'r3'))
    call_hook(rom, 0x0801fc00, syms['vwf_clear'], 'mov r2, r8\n strb r2, [r6]', 'section init')
    call_hook(rom, 0x0801fa6c, syms['vwf_clear'], 'movs r1, #0\n strb r1, [r0]', 'text reset', keep=('r0', 'r2', 'r3'))

    # 4. per-frame canvas remap, hooked before the BG map DMA
    tramp_fr = rom.thumb_code(f'''
        push {{lr}}
        mov r0, r12
        push {{r0}}
        bl #{syms["vwf_frame"] & ~1:#x}
        pop {{r0}}
        mov r12, r0
        ldr r3, [pc, #4]
        ldr r2, [pc, #4]
        pop {{pc}}
        .word 0x030037b0
        .word 0x03003a90
    ''', note='frame trampoline')
    assert rom.u32(0x0800674c) == 0x030037b0, hex(rom.u32(0x0800674c))
    assert rom.u32(0x08006750) == 0x03003a90, hex(rom.u32(0x08006750))
    rom.thumb(VRAMUPD_HOOK, f'bl #{tramp_fr & ~1:#x}', 'frame hook')

    # 4b. overlay screens (save screen, ...) restore the game state on exit and call 0x08020024
    # to redraw the text sprites from the restored records: drop the overlay's sprite text first
    tramp_rs = rom.thumb_code(f'''
        push {{lr}}
        bl #{syms["vwf_restore"] & ~1:#x}
        bl #{RESTORE_TEXT:#x}
        pop {{pc}}
    ''', note='restore trampoline')
    for site in RESTORE_CALLS:
        assert rom.asm_thumb(site, f'bl #{RESTORE_TEXT:#x}') == rom.read(site, 4), hex(site)
        rom.thumb(site, f'bl #{tramp_rs & ~1:#x}', 'restore hook')
    rom.restore_tramp = tramp_rs             # patches/ui.py adds the save screen header to the first

    # 5. taller text box: frame rows 13..19 (top edge, 5 interior rows, bottom)
    t = bytearray(rom.read(FRAME_TEMPLATE, 1024))
    rows = [bytes(t[r * 32:(r + 1) * 32]) for r in range(32)]
    assert rows[14][0] == 0x02 and rows[15][0] == 0x06 and rows[19][0] == 0x04, [r[:2].hex() for r in rows[12:20]]
    new = rows[:13] + [rows[14]] + [rows[15]] * 5 + [rows[19]] + rows[20:]
    rom.write(FRAME_TEMPLATE, b''.join(new), 'frame template 3 lines')
    # partial frame redraw starts at row 13 instead of 14
    assert rom.u16(0x0800577a) == 0x21e0 and rom.u16(0x08005784) == 0x25e0
    rom.w16(0x0800577a, 0x21d0); rom.w16(0x08005784, 0x25d0)
    # name tag one row up (rows 11-12, joint at row 13)
    assert rom.u32(TAG_ROW14_LIT) == 0x03002400 and rom.u32(TAG_ROW12_LIT) == 0x03002380
    rom.w32(TAG_ROW14_LIT, 0x030023c0); rom.w32(TAG_ROW12_LIT, 0x03002340)
    # ... and a line with no name tag puts the box template back from row 11 instead of 12 (the
    # loop at 0x0800659c copies template entries 0x180-0x1df to the map from row 12)
    assert rom.u16(TAG_ERASE_FROM) == 0x24c0 and rom.u16(TAG_ERASE_DST) == 0x25c0
    rom.w16(TAG_ERASE_FROM, 0x24b0); rom.w16(TAG_ERASE_DST, 0x25b0)
    # box clear loops (rows 12-19 -> rows 11-19): replace each loop with a call.  Command 0x1c
    # (hide the box): the code after the loop sets TXT+0x23 = 1 through r4 = r7 + 0x23, which the
    # loop's first instructions set up
    assert rom.u32(0x08021cdc) == 0x03002080
    for site, after, setup in BOX_CLEARS:
        assert rom.u16(after) == 0x2001, hex(after)          # movs r0, #1
        rom.thumb(site, f'{setup}\n bl #{syms["vwf_boxclear"] & ~1:#x}\n b #{after:#x}', 'box clear')

    # 6. UI palette: add text colours to every embedded copy of bank 0
    pal = b''.join(struct.pack('<H', v) for v in UI_PAL)
    newpal = list(UI_PAL)
    for k, v in TEXT_PAL.items(): newpal[k] = v
    newb = b''.join(struct.pack('<H', v) for v in newpal)
    d = bytes(rom.d[:rom.orig_size]); i = 0; n = 0
    while True:
        i = d.find(pal, i)
        if i < 0: break
        rom.write(0x08000000 + i, newb, 'ui palette'); n += 1; i += 32
    print(f"  patched {n} UI palette copies")
