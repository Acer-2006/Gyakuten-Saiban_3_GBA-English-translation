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

/* Replaces `bl 0x803a048` at the 7 script-loader call sites. */
void script_load(u32 src, u32 dst) {
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
   stopped on if that is a page end or a choice, else `off` itself if it is still on a token
   boundary.  0 if none of these. */
static u32 resume_find(u32 start, u32 off, const struct resume_info* b, u32 cmd) {
    const u16* p = (const u16*)start;
    const u16* old = (const u16*)(start + off);
    const u16* lo = (const u16*)(start + (off > SEARCH ? off - SEARCH : 0));
    const u16* hi = (const u16*)(start + off + SEARCH);
    int stop = cmd == 0x02 || cmd == 0x2d || cmd == 0x08 || cmd == 0x09 || cmd == 0x0a;
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

void _start(void) {}
