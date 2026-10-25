/* Script banks resident in ROM instead of decompressed into EWRAM.
 *
 * The original loader LZ77-decompresses a chapter bank to 0x2011fc0 and several
 * functions hard-code that address.  We keep a `bank_base` pointer: for English
 * banks (uncompressed, in the expanded ROM) it points into ROM; for untouched
 * Japanese banks it stays 0x2011fc0 and the data is still decompressed there.
 *
 * Saved games keep the script pointer as an address, which is only good for the build that
 * made the save; script_save / script_resume make saves carry over to other builds.
 */
#include "gba.h"
#include "font.h"                        /* cmd_args[] */

#define RAM_BANK   0x02011fc0u
#define COMMON_BANK 0x086e3578u          /* patched to the English common bank by the build */


u32 bank_base;

static inline void lz77_wram(u32 src, u32 dst) {
    register u32 r0 __asm__("r0") = src;
    register u32 r1 __asm__("r1") = dst;
    __asm__ volatile("swi 0x11" : : "r"(r0), "r"(r1) : "r2", "r3", "memory");
}

/* Bit 1 of TXT+0x1c lets the script run on while the screen fades (see "brightness fades"
 * below).  The game turns it on in two scenes only, and off again before each ends: episode 1's
 * opening (effect 1 of 0x69) and bank 22 section 0x8a (0x69 62 23d, then 23e), with no section
 * jump or bank load in between.  Builds up to 0.16.58 also turned it on by mistake at a date and
 * place card (the centring count, patches/text.py 5a), and a save or a savestate keeps it: a
 * section jump or a bank load turns such a stray bit off. */
static inline void fade_flag_off(void) { TXT_FLAGS &= ~2; }

/* Replaces `bl 0x803a048` at the 7 script-loader call sites. */
void script_load(u32 src, u32 dst) {
    fade_flag_off();
    if (src >= 0x08800000u) { bank_base = src; return; }
    bank_base = RAM_BANK;
    lz77_wram(src, dst);
}

/* ---- engine functions reimplemented ---- */
extern int f_801e210(void);           /* original helpers, called through thumb thunks */
extern void f_801e4ac(int);
extern void f_801fb98(int sec);

static inline u32 common_base(void) { return COMMON_BANK_ADDR; }

/* 0x0801fcd8: jump to section `sec` (sections >= 0x80 live in the chapter bank). */
void jump_section(u32 sec) {
    volatile u8* sys = SYS;
    fade_flag_off();
    if ((*(volatile u32*)(sys + 0x2d0) & 8) && sec > 0x7f && *(volatile u16*)(TXT + 0xc) > 0x7f)
        sec = *(volatile u16*)(TXT + 0xc) + 1;
    if ((sys[8] == 4 || sys[0xc] == 4) && sys[9] != 0xa) {
        if (!f_801e210()) f_801e4ac(2); else f_801e4ac(4);
    }
    f_801fb98(sec);
    u32 s = *(volatile u16*)(TXT + 0xc);
    u32 base, p;
    if (s > 0x7f) { base = bank_base; p = base + 4 + (s - 0x80) * 4; }
    else { base = common_base(); p = base + 4 + s * 4; }
    u32 addr = *(const u32*)p + base;
    *(volatile u32*)(TXT + 0) = addr;
    *(volatile u32*)(TXT + 4) = addr;
}

/* 0x0801fc9c: command 0x36 target (entry = u16 word offset, u16 section). */
void jump_label(u32 idx) {
    const u16* ent = (const u16*)(bank_base + 4 + idx * 4);
    u32 woff = ent[0] >> 1;
    u32 sec = ent[1];
    f_801fb98(sec + 0x80);
    u32 addr = *(const u32*)(bank_base + 4 + sec * 4) + bank_base;
    *(volatile u32*)(TXT + 4) = addr;
    *(volatile u32*)(TXT + 0) = addr + woff * 2;
}

/* ---- saved games ----
 * The game saves 0x2c54 bytes of EWRAM (0x02000000, the state taken when the save screen
 * opened; the text state is at +0x35c) to SRAM 0x0e000000.  The text state holds the script
 * pointer and the start of its section as addresses.  Next to the game's save, at SRAM
 * RESUME_SRAM, the English build keeps the section number and the script words just before
 * the pointer; when the save is continued with a build whose script differs, the pointer is
 * found again in the same section by those words. */
extern int sram_write(const void* src, u32 dst, u32 n);     /* 0x0803a1ac, WriteSramEx */
extern void sram_read(u32 src, void* dst, u32 n);           /* 0x0803a074, ReadSram */

#define SAVE_IMAGE    0x02000000u
#define SAVE_TXT      (SAVE_IMAGE + 0x35c)
#define RESUME_SRAM   0x0e007f00u
#define RESUME_MAGIC  0x52334753u                          /* 'SG3R' */
#define ANCHOR        16                                   /* script words kept before the pointer */
#define SEARCH        0x4000                               /* bytes searched around the old offset */

struct resume_info {
    u32 magic;
    u32 ptr, start;                   /* the saved text state's pointer and section start */
    u16 sec;
    u16 n;                            /* words kept before the pointer (fewer at a section start) */
    u16 words[ANCHOR + 1];            /* ... and the word at the pointer */
    u16 pad;
};

static u32 section_start(u32 s) {
    u32 base = s > 0x7f ? bank_base : common_base();
    u32 i = s > 0x7f ? s - 0x80 : s;
    return base + *(const u32*)(base + 4 + i * 4);
}

/* Replaces the game's `bl WriteSramEx(0x02000000, 0x0e000000, 0x2c54)` (0x0800ac22). */
int script_save(const void* src, u32 dst, u32 size) {
    int r = sram_write(src, dst, size);
    struct resume_info b;
    u8* q = (u8*)&b;
    for (u32 i = 0; i < sizeof b; i++) q[i] = 0;
    const volatile u8* t = (const volatile u8*)SAVE_TXT;
    u32 ptr = *(const volatile u32*)t, start = *(const volatile u32*)(t + 4);
    u32 sec = *(const volatile u16*)(t + 0xc);
    /* only when the saved state belongs to this build's script (a save of the cleared parts
       writes back an older state) */
    if (!(ptr & 1) && !(start & 1) && ptr >= start && ptr - start < 0x40000 &&
        (sec > 0x7f || sec < 0x40) && section_start(sec) == start) {
        u32 n = (ptr - start) / 2;
        if (n > ANCHOR) n = ANCHOR;
        const u16* w = (const u16*)ptr - n;
        b.magic = RESUME_MAGIC; b.ptr = ptr; b.start = start; b.sec = sec; b.n = n;
        for (u32 i = 0; i <= n; i++) b.words[i] = w[i];
    }
    sram_write(&b, RESUME_SRAM, sizeof b);
    return r;
}

/* The place in this build's section at `start` that matches where the save stopped, `off`
   bytes into the section in the build that made it: the nearest one with the saved words before
   it (b), else (no record, or the words are gone) the nearest one with the command the game
   stopped on if that is a page end, a choice, a cross-examination statement's end (0x15) or the
   Court Record opened to present (0x21), else `off` itself if it is still on a token boundary.
   0 if none of these. */
static u32 resume_find(u32 start, u32 off, const struct resume_info* b, u32 cmd) {
    const u16* p = (const u16*)start;
    const u16* old = (const u16*)(start + off);
    const u16* lo = (const u16*)(start + (off > SEARCH ? off - SEARCH : 0));
    const u16* hi = (const u16*)(start + off + SEARCH);
    int stop = cmd == 0x02 || cmd == 0x2d || cmd == 0x08 || cmd == 0x09 || cmd == 0x0a ||
               cmd == 0x15 || cmd == 0x21;
    u32 words = 0, words_d = ~0u, same = 0, same_d = ~0u, here = 0;
    while (p <= hi) {
        if (p >= lo) {
            u32 d = p > old ? (u32)(p - old) : (u32)(old - p);
            if (b && (u32)(p - (const u16*)start) >= b->n && d < words_d) {
                const u16* w = p - b->n;
                u32 i = 0;
                while (i <= b->n && w[i] == b->words[i]) i++;
                if (i > b->n) { words_d = d; words = (u32)p; }
            }
            if (stop && *p == cmd && d < same_d) { same_d = d; same = (u32)p; }
            if (p == old) here = (u32)p;
        }
        u32 t = *p++;
        if (t < 0x80) p += cmd_args[t];
    }
    return words ? words : same ? same : here;
}

/* Called when a saved game is continued (0x0800dcd4): the text state has just been put back from
   the save and the chapter bank loaded. */
void script_resume(void) {
    u32 sec = TXT_SECTION, ptr = TXT_PTR, start = TXT_START, cmd = TXT_CMD;
    u32 nstart = section_start(sec);
    u32 off = ptr - start;
    struct resume_info b;
    sram_read(RESUME_SRAM, &b, sizeof b);
    int rec = b.magic == RESUME_MAGIC && b.ptr == ptr && b.start == start && b.sec == sec && b.n <= ANCHOR;
    u32 target = (!(off & 1) && off < 0x40000) ? resume_find(nstart, off, rec ? &b : 0, cmd) : 0;
    TXT_START = nstart;
    TXT_PTR = target ? target : nstart;     /* nothing matches: the section starts again */
}

/* ---- the end of a Psyche-Lock conversation ----
 * Command 0x64 (0x0802393c) starts the unlock sequence (SYS+8 = 0x40a04): the game's main loop
 * runs it (the chains break, the background goes back to the room, "Unlock Successful") and the
 * script is not run meanwhile.  Every other 0x64 of the Japanese GBA script and the DS's is
 * followed by a wait (0x0c, after a 0x26 or a sound when there is one), which ends the script's
 * run for that frame, so the commands after it (the location's lock flag, 0x37; the room's
 * background, 0x1b) come once the sequence is over.  The DS's English script lost that wait once
 * (bank 8 section 0xbb, Larry's locks): 0x37 and 0x1b ran under the sequence, and it broke up a
 * grey copy of the room instead of the Psyche-Lock's background.  Putting the wait back in the
 * script would move the rest of the bank, and a savestate in it with it: the run stops here
 * instead, after a 0x26 that comes next as in the Japanese script. */
extern u32 f_802393c(void);           /* 0x64 */
extern u32 f_802239c(void);           /* 0x26 */

u32 psyche_end(void) {
    u32 r = f_802393c();
    const u16* q = (const u16*)TXT_PTR;
    if (*q == 0x26) q += 2;
    while (*q == 0x05 || *q == 0x06) q += 1 + cmd_args[*q];
    if (r || *q == 0x0c) return r;
    if (*(const u16*)TXT_PTR == 0x26) { TXT_PTR += 2; f_802239c(); }
    TXT_PTR += 2;                     /* the dispatcher steps back over a command that waits */
    return 1;
}

/* ---- brightness fades ----
 * 0x08000b40 (command 0x12, and the engine's own fades) starts a fade of the screen's brightness
 * (BLDY, IO shadow +0x4e): SYS+0x8a the mode (1 darker down to 0, 2 darker up to 16, 3 brighter
 * down to 0, 4 brighter up to 16), +0x8e frames per step, +0x8f the step, +0x88 the layers, +0x8c
 * the frame counter.  The main loop (0x08000b6c) moves BLDY by the step, keeps its low 5 bits and
 * stops when it lands on the target; a flash is a fade that starts on its target and goes once
 * round (12 301 8 1f: 0, 24, 16, 8, 0).  The script waits while a fade runs unless bit 1 of
 * TXT+0x1c is set (in two scenes, see fade_flag_off; the save keeps it), and then a fade can
 * start while another is under way, from a level its step never lands on the target from: the
 * screen strobes every four frames until the next fade (Ron's "night of the crime": a fade in
 * from white of 32 frames under a wait of 15, then a flash from 9; the Japanese game does the
 * same with the bit set, which in Ron's scene only the English build's centring count had set).
 *
 * The English build plays such a place as the game does with the bit clear.  fade_hold, asked by
 * the dispatcher before each command while a fade runs, looks past the sounds, name tag, box and
 * at most one wait (0x05, 0x06, 0x0e, 0x1c, 0x0c) that come next: when they lead to a fade that
 * could not land from the level the fade under way will be at by then, it clears the bit and the
 * script waits for the fade, the wait and the flash coming after it as they would with the bit
 * clear.  It never stops a fade that lands, so the places that set the bit on purpose (episode 1's
 * opening, 0x69 62 23d) play as before.  Should a fade that cannot land start all the same (text in
 * between), fade_start first finishes the one under way (or, with none, starts from the level
 * below that it can land from); and a fade already going round (in a savestate) is stopped by the
 * step in the main loop (patches/script.py). */

/* The level the fade under way is at after n more frames of the main loop (0x08000b6c, with the
 * English build's step, which stops on the target). */
static u32 fade_level_after(u32 n) {
    volatile u8* sys = SYS;
    u32 mode = *(volatile u16*)(sys + 0x8a), per = sys[0x8e], step = sys[0x8f];
    u32 cnt = *(volatile u16*)(sys + 0x8c), lv = *(volatile u16*)0x03003ade & 0x1f;
    u32 target = mode & 1 ? 0 : 16;
    for (; n; n--) {
        if ((u16)++cnt < per) continue;
        cnt = 0;
        if (!step) return target;
        if (mode & 1) lv = lv && lv < step ? 0 : (lv - step) & 0x1f;
        else lv = lv < 16 && lv + step > 16 ? 16 : (lv + step) & 0x1f;
        if (lv == target) return target;
    }
    return lv;
}

/* Returns TXT+0x1c for the dispatcher to go on, or -1 for it to stop until the fade is over. */
s32 fade_hold(void) {
    u32 f = TXT_FLAGS;
    if (!(f & 2)) return -1;              /* the game's own rule */
    const u16* p = (const u16*)TXT_PTR;
    u32 n = 0, waited = 0;
    for (int k = 0; k < 8; k++) {
        u32 c = *p;
        if (c == 0x0c && !waited) {      /* under way: TXT+0xa is 0x0c, frames left in TXT+0x12 */
            u32 left = TXT[0x12];
            n = *(volatile u16*)(TXT + 0xa) == 0x0c && left ? left - 1 : p[1] & 0xff;
            waited = 1;
        } else if (c != 0x05 && c != 0x06 && c != 0x0e && c != 0x1c) break;
        p += 1 + cmd_args[c];
    }
    if (*p != 0x12) return f;
    u32 mode = p[1] >> 8, g = p[2] & 0xff;
    g &= -g;
    if (mode - 1 >= 4 || !g || g >= 32 || !(fade_level_after(n) & (g - 1))) return f;
    TXT_FLAGS = f & ~2;
    return -1;
}

void fade_start(u32 mode, u32 period, u32 step, u32 layers) {
    volatile u8* sys = SYS;
    volatile u16* bldy = (volatile u16*)0x03003ade;
    u32 g = step & 0xff;
    g &= -g;                          /* BLDY moves in multiples of this, modulo 32 */
    if ((u32)(u16)mode - 1 < 4 && g && g < 32 && (*bldy & (g - 1))) {
        u32 run = *(volatile u16*)(sys + 0x8a);
        *bldy = run - 1 < 4 ? (run & 1 ? 0 : 16) : (*bldy & 0x1f & ~(g - 1));
    }
    *(volatile u16*)(sys + 0x88) = layers;
    *(volatile u16*)(sys + 0x8a) = mode;
    sys[0x8e] = period;
    sys[0x8f] = step;
    *(volatile u16*)(sys + 0x8c) = 0;
}

void _start(void) {}
