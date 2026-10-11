/* The save screen's header from the DS version: SAVE, and LOAD on the continue screen.
 *
 * The GBA's header 記録 was 32 tiles of the UI sheet, which stays in BG VRAM: the save screen
 * opened during the game loads no BG tiles of its own.  The DS lettering takes 14x4 tiles, which
 * are put in BG tiles HDR_TILE.. when a screen with the header opens.  During the game a scene's
 * graphics may be there, so the save screen opened with START keeps them and puts them back when
 * it closes (patches/ui.py has the hooks).
 */
#include "gba.h"

#define HDR_TILE   0x1c4
#define HDR_WORDS  (56 * 8)

extern const u32 hdr_save[HDR_WORDS], hdr_load[HDR_WORDS];   /* the tiles, in ROM */
static u32 keep[HDR_WORDS];
static u8 kept;

static volatile u32* hdr_vram(void) { return (volatile u32*)(VRAM + HDR_TILE * 32); }

static void put(const u32* src) {
    volatile u32* v = hdr_vram();
    for (int i = 0; i < HDR_WORDS; i++) v[i] = src[i];
}

/* The save screen, opened with START during the game (and at the end of a part). */
void hdr_game(void) {
    volatile u32* v = hdr_vram();
    int shown = 1;
    for (int i = 0; i < HDR_WORDS && shown; i++) shown = v[i] == hdr_save[i];
    if (!shown) {                       /* (not when the screen loads its graphics again) */
        for (int i = 0; i < HDR_WORDS; i++) keep[i] = v[i];
        kept = 1;
    }
    put(hdr_save);
}

/* The erase-all-data screen (from the title): the title loads its own graphics afterwards. */
void hdr_erase(void) { kept = 0; put(hdr_save); }

/* The continue screen (Continue on the title). */
void hdr_continue(void) { kept = 0; put(hdr_load); }

/* The save screen closes: the game state has just been put back (0x0800bcc4). */
void hdr_close(void) {
    if (!kept) return;
    volatile u32* v = hdr_vram();
    for (int i = 0; i < HDR_WORDS; i++) v[i] = keep[i];
    kept = 0;
}

/* The Testimony label (OAM 57, a 64x32 sprite at the top left during a testimony): the DS
   lettering fills its sprite edge to edge, where the Japanese 証言中 had a margin, so the
   sprite sits 3 pixels in from the corner.  Called where the game places it (0x0800e97c,
   after it has stored attribute 0; the hook stores attribute 1 with the x). */
void label_pos(void) {
    volatile u16* oam = (volatile u16*)0x03002ba0;
    oam[57 * 4 + 0] = 0x4000 | 2;
}

void _start(void) {}
