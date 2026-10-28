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
VWF_SIZE        = 17424        # bytes kept for src/vwf.c's code (its size in 0.16.67)
FRAME_TEMPLATE  = 0x0803b844   # 32x32 byte map template of the normal text box
# loops that clear map rows 12-19 (0x100 entries from 0x180): (start, the instruction after the
# loop, what the replaced instructions set up that is used after it)
BOX_CLEARS = [(0x08022166, 0x08022186, 'adds r4, r7, #0\n adds r4, #0x23'),   # command 0x1c
              (0x08021c8e, 0x08021caa, 'ldr r5, [pc, #0x4c]')]                # after a choice:
                                                                  # r5 = 0x03002080 (0x08021cdc)
STMT_ARROW_Y    = (0x0800ebc8, 0x0800ebfe)   # movs r0, #0x80: the statement arrows' y (0x0800ebb0)
VRAMUPD_HOOK    = 0x08006686   # ldr r3,[pc,#0xc4]; ldr r2,[pc,#0xc4]  (after push {r4,lr})
IOREG_CALL      = 0x08000422   # bl IOREG_UPDATE, in the main loop's per-frame updates
BGCNT_STORE     = 0x0800673a   # ldr r0,[r2]; str r0,[r1]: BG0CNT | BG1CNT << 16 from the shadow, after the map DMAs
IOREG_UPDATE    = 0x080009bc   # DISPCNT, DISPSTAT, windows, blending from the shadow at 0x03003a90
RESTORE_TEXT    = 0x08020024   # redraws text sprites from the sprite records after a state restore
RESTORE_CALLS   = (0x0800bcc4, 0x08014464)   # 0x0800dcd4, continuing a save: patches/script.py
SAVE_BACK       = 0x0800bd54   # bl 0x080201e4: the save screen's last call once the game state is back
SAVE_BACK_CALL  = 0x080201e4
PACE_RELOAD     = 0x0801f960   # ldrb r2, [r2]; adds r0, r2, r0  (wait = TXT+0x26, the speed)
BLIP_AT         = 0x0801f9b0   # ldrb r6, [r6]; cmp r6, #1; bls (the blip); b 0x0801f858 (no blip)
TEXT_LOOP       = 0x0801f858
CENTRE_ROWS     = 0x0801f024   # cmp r1, #2: the rows the centring count (0x0801f014) keeps a value for
RECORD_REDRAW   = 0x0802187c   # bl 0x080214ac: the page waits' redraw of the sprite records' glyphs

# The text colours of commands {03 1}, {03 2} and {03 3} (orange, light blue, green) are the
# values the Japanese sprite text keeps in OBJ palette 0 (entries 6, 9 and 12), which the DS uses
# too.  The box text, drawn on BG1 with BG palette 0 (the UI palette: 0000 0400 1ce7 4210 739c
# 3800 3cc5 5a0c 7fff 0c6c 3191 4656 631b 3def 028c 03ff), has them in entries 13-15: src/vwf.c
# writes them there every frame a page is mapped and puts the UI values back when it is not (the
# Court Record's panel names its items in entry 15 while it slides).  The ROM's copies of the UI
# palette stay as they are: the same copies are loaded into OBJ palette 2, where sprites do use
# 13-15 (the Court Record's item names are 15).

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
    rows, widths = dsfont.tables(ctx.data, ctx.arm9, clear_top=True)
    rows_addr = rom.store(rows, 'font', 4, 'font rows')
    w_addr = rom.store(widths, 'font', 4, 'font widths')
    text_addr = 0x08000000 + ((rom.regions['font'].cur + 3) & ~3)
    binary, syms, bss = compile_c([os.path.join(ROOT, 'src/vwf.c')], text_addr, BSS_ADDR,
                                  os.path.join(ROOT, 'build/vwf'),
                                  ld_defsyms={'font_rows': rows_addr, 'font_w': w_addr})
    # The code after the renderer (the hooks' trampolines, src/script.c, ...) stays where it was
    # in earlier builds: a save state can hold a return address into it.  The renderer is padded
    # to the size it had in 0.16.67; one that has grown past it has to make room elsewhere.
    if len(binary) > VWF_SIZE:
        raise SystemExit(f'text: the renderer is {len(binary)} bytes, more than the {VWF_SIZE} kept for it')
    binary += bytes(VWF_SIZE - len(binary))
    code_addr = rom.store(binary, 'font', 4, 'vwf code')
    assert code_addr == text_addr
    assert bss <= 0x780, bss                 # vwf.c's fixed state (vx) at 0x02028780, script.c's at 0x02028800
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

    # 4a. the choice question on BG0 over the box (src/vwf.c, "the question on BG0"): BG0's
    # control register in place of the store of BG0CNT | BG1CNT << 16 right after the map DMAs,
    # and the game's shadow of DISPCNT, blending and windows around its IO register update
    assert rom.read(BGCNT_STORE, 4) == rom.asm_thumb(BGCNT_STORE, 'ldr r0, [r2]\n str r0, [r1]')
    tramp_bc = rom.thumb_code(f'''
        push {{r1, r2, r3, lr}}
        mov r0, r12
        push {{r0}}
        ldr r0, [r2]
        bl #{syms["vwf_bgcnt"] & ~1:#x}
        pop {{r3}}
        mov r12, r3
        pop {{r1, r2, r3}}
        str r0, [r1]
        pop {{pc}}
    ''', note='BG control trampoline')
    rom.thumb(BGCNT_STORE, f'bl #{tramp_bc & ~1:#x}', 'BG control hook')
    assert rom.read(IOREG_CALL, 4) == rom.asm_thumb(IOREG_CALL, f'bl #{IOREG_UPDATE:#x}')
    tramp_io = rom.thumb_code(f'''
        push {{lr}}
        mov r0, r12
        push {{r0}}
        bl #{syms["vwf_io_pre"] & ~1:#x}
        bl #{IOREG_UPDATE:#x}
        bl #{syms["vwf_io_post"] & ~1:#x}
        pop {{r0}}
        mov r12, r0
        pop {{pc}}
    ''', note='IO register trampoline')
    rom.thumb(IOREG_CALL, f'bl #{tramp_io & ~1:#x}', 'IO register hook')

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
    # The records hold the original's cells, not the English page, and the save screen (START,
    # "No") put the text state back only after that redraw: once it has (0x0800bd54, the last
    # call of its restore), the page is found in the script and drawn again, as a continued
    # save's is (vwf_resume).  Without this the box came back empty.
    assert rom.asm_thumb(SAVE_BACK, f'bl #{SAVE_BACK_CALL:#x}') == rom.read(SAVE_BACK, 4), hex(SAVE_BACK)
    tramp_sb = rom.thumb_code(f'''
        push {{lr}}
        bl #{SAVE_BACK_CALL:#x}
        bl #{syms["vwf_resume"] & ~1:#x}
        pop {{pc}}
    ''', note='save screen back trampoline')
    rom.thumb(SAVE_BACK, f'bl #{tramp_sb & ~1:#x}', 'save screen back hook')

    # 5. the text box is the original's, BG1 rows 14-19 (48 pixels; src/vwf.c, BOX_TOP): its
    # template, the name tag on rows 12-13, the item box's window, the episode select's short box
    # and the box's partial redraw stay as they are.  (0.16.8-0.16.67 drew a 64-pixel box from row
    # 12, with the tag two rows up and the routines that know those rows moved with it.)  The
    # cross-examination's arrows to the previous and next statement (OAM 0 and 1, 16x16 at the
    # box's edge columns) sit on the second line, y 129 instead of 128 (the original's second
    # line; src/vwf.c TEXT_Y0 + BOX_PITCH)
    t = rom.read(FRAME_TEMPLATE, 1024)
    assert t[14 * 32] == 0x02 and t[15 * 32] == 0x06 and t[19 * 32] == 0x04 and t[14 * 32 + 8] == 0x08, 'box template'
    for addr in STMT_ARROW_Y:
        assert rom.u16(addr) == 0x2080, hex(addr)       # movs r0, #0x80
        rom.w16(addr, 0x2000 | 129)
    # box clear loops (rows 12-19): replaced each with a call (vwf_boxclear).  Command 0x1c
    # (hide the box): the code after the loop sets TXT+0x23 = 1 through r4 = r7 + 0x23, which the
    # loop's first instructions set up
    assert rom.u32(0x08021cdc) == 0x03002080
    for site, after, setup in BOX_CLEARS:
        assert rom.u16(after) == 0x2001, hex(after)          # movs r0, #1
        rom.thumb(site, f'{setup}\n bl #{syms["vwf_boxclear"] & ~1:#x}\n b #{after:#x}', 'box clear')

    # 5a. the centring count (0x0801f014): at command 0x5d, and at newlines and page ends while the
    # text is centred, the engine counts the characters left on the row and keeps 16 less that
    # many at TXT+0x18 + 2 * row, rows 0 to 2, for its sprite cells.  There is room for two: row
    # 2's lands on TXT+0x1c, the text flags.  The Japanese box has two rows; the English box has
    # three, and a date and place card (0x5d 1) after a page that ended on its third row, or the
    # card's own third line, had the count go over the flags, turning on bit 1 (the script runs
    # on while the screen fades) and others.  The English build does not draw those cells: row 2
    # is left out.
    assert rom.read(CENTRE_ROWS, 2) == rom.asm_thumb(CENTRE_ROWS, 'cmp r1, #2'), 'centring count'
    rom.thumb(CENTRE_ROWS, 'cmp r1, #1', 'centring count: rows 0 and 1')

    # 5a'. the page waits (0x02, 0x07, 0x0a, 0x2d: 0x080217d8) redraw every sprite record's glyph
    # (0x080214ac) when bit 15 of TXT+0x12 is set and A is pressed.  The glyphs come from the
    # Japanese font area, which our code fills now, and the English build keeps no text in the
    # records: records 32-63 hold other data there, which this would turn into tiles.  Nothing
    # sets that bit in the scripts or in play (0.16.63); the call is taken out all the same.
    assert rom.read(RECORD_REDRAW, 4) == bytes.fromhex('fff716fe'), 'record redraw'
    rom.write(RECORD_REDRAW, bytes.fromhex('c046c046'), 'record redraw off (nop, nop)')

    # 5b. the DS English version's pace and text blips (see text_pace and text_blip): the wait
    # before each character, and the blip after it on every row of the box
    if rom.read(PACE_RELOAD, 4) != rom.asm_thumb(PACE_RELOAD, 'ldrb r2, [r2]\n adds r0, r2, r0') or \
            rom.read(BLIP_AT, 8) != rom.asm_thumb(BLIP_AT, f'ldrb r6, [r6]\n cmp r6, #1\n bls #{BLIP_AT + 8:#x}\n b #{TEXT_LOOP:#x}'):
        raise SystemExit('text: unexpected code in the text loop')
    tramp = rom.thumb_code(f'''
        push {{r0, r3, lr}}
        mov r0, r12
        push {{r0}}
        ldrb r0, [r2]
        bl #{syms["text_pace"] & ~1:#x}
        adds r2, r0, #0
        pop {{r0}}
        mov r12, r0
        pop {{r0, r3}}
        adds r0, r2, r0
        pop {{pc}}
    ''', note='text pace trampoline')
    rom.thumb(PACE_RELOAD, f'bl #{tramp & ~1:#x}', 'text pace hook')
    tramp = rom.thumb_code(f'''
        push {{lr}}
        mov r0, r12
        push {{r0}}
        adds r0, r7, #0
        bl #{syms["text_blip"] & ~1:#x}
        pop {{r1}}
        mov r12, r1
        pop {{pc}}
    ''', note='text blip trampoline')
    rom.thumb(BLIP_AT, f'bl #{tramp & ~1:#x}\n adds r7, r0, #0', 'text blip hook')

