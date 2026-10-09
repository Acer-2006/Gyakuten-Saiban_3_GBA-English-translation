/* Script banks resident in ROM instead of decompressed into EWRAM.
 *
 * The original loader LZ77-decompresses a chapter bank to 0x2011fc0 and several
 * functions hard-code that address.  We keep a `bank_base` pointer: for English
 * banks (uncompressed, in the expanded ROM) it points into ROM; for untouched
 * Japanese banks it stays 0x2011fc0 and the data is still decompressed there.
 */
#include "gba.h"

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

void _start(void) {}
