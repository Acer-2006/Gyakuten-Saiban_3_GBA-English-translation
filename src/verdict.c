/* The verdict from the DS version: Not Guilty / Guilty in its letters (patches/verdict.py).
 *
 * The original shows its two words as OAM entries 49 and 50, affine with double size (matrices 0
 * and 1), which the verdict mode (mode 9, 0x0800f23c, state in SYS+9) zooms in one after the
 * other (states 0 and 2), then moves up while zooming out (state 4) and hides.  Here those two
 * entries stay as the code sets them but small and off the screen, and every letter is a 32x64
 * sprite in entries 51-59 that follows its word's entry: zooming about its own centre with the
 * word's matrix while the word comes in, as on the DS, and a plain sprite at the word's height
 * the rest of the time (nine affine sprites with double size would take more of a line's
 * sprite time than there is, and the judge behind them would go).
 */
#include "gba.h"

#define OAM_SH   ((volatile u16*)0x03002ba0)   /* OAM shadow, 4 halfwords per entry */
#define WORD0    49                            /* the original's two words */
#define FIRST    51                            /* the letters (the confetti, afterwards, uses 58-88) */
#define TILES    ((volatile u32*)0x06013400)   /* OBJ tile 0x1a0 */
#define TALL     0x8000                        /* attr0 shape: 32x64 with size 3 in attr1 */
#define SIZE3    0xc000
#define OFF      240                           /* x off the screen */

struct letter { u8 word, pad; s16 x; u16 attr2, pad2; };   /* x: of the double-size box */
struct verdict { u16 n, words; const u32* tiles; const struct letter* l; };
extern const struct verdict verdicts[2];      /* not guilty, guilty */

static u8 active;                             /* 0, or 1 + the verdict */

/* the end of the handler of command 0x44 (0x080209dc), after it has loaded its pictures */
void verdict_start(void) {
    u32 kind = ((const u16*)TXT_PTR)[-1] ? 1 : 0;   /* the command's argument */
    const struct verdict* v = &verdicts[kind];
    for (u32 i = 0; i < v->words; i++) TILES[i] = v->tiles[i];
    active = 1 + kind;
}

/* after each frame of the verdict mode */
void verdict_letters(void) {
    if (!active) return;
    const struct verdict* v = &verdicts[active - 1];
    u32 state = SYS[9];
    int shown = 0;
    for (int w = 0; w < 2; w++) {
        volatile u16* a = &OAM_SH[(WORD0 + w) * 4];
        u16 a0 = a[0];
        int zoom = state == (w ? 2u : 0u) || (w && state == 1);
        for (int i = 0; i < v->n; i++) {
            const struct letter* l = &v->l[i];
            if (l->word != w) continue;
            volatile u16* o = &OAM_SH[(FIRST + i) * 4];
            if ((a0 & 0x300) != 0x300) { o[0] = 0x200; continue; }   /* not shown (yet, or any more) */
            if (zoom) {
                o[0] = (a0 & 0x3fff) | TALL;                    /* the word's flags and height */
                o[1] = SIZE3 | w << 9 | (l->x & 0x1ff);          /* and its matrix */
            } else {
                o[0] = TALL | ((a0 + 32) & 0xff);                /* plain, where the box puts it */
                o[1] = SIZE3 | ((l->x + 16) & 0x1ff);
            }
            o[2] = l->attr2;
        }
        if ((a0 & 0x300) == 0x300) {
            shown = 1;
            a[1] = (a[1] & 0x3e00) | OFF;                       /* the word's entry: 8x8, off the screen */
        }
    }
    if (!shown && state >= 4) active = 0;                       /* gone after rising (then the confetti) */
}

void _start(void) {}
