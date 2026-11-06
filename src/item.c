/* The item shown in court and the effects that share its tiles (patches/icons.py, item_waits).
 *
 * The item shown in court (OAM 65; 72 or 0 in some modes) is run by 0x0801545c every frame (from
 * the vertical blank's updates, 0x08000430, and once from 0x0801db9c), its state in SYS+0x99:
 * state 3, set by script command 0x13, unpacks its picture and copies it to OBJ tiles ITEM_TILE
 * (0x1e0-0x21f in the English build; the original's 0x80-0xbf are the English page's third line);
 * state 4 shows it; state 5, the item put away while the Court Record is open, copies it again
 * once the Record has gone (SYS+8, the mode, back to 6 or under).  Animated effects copy their
 * pictures to OBJ tiles too, each frame of their animation (the table at 0x08046b30), and two
 * dozen of them have tiles among the item's: the shout bubbles (effects 1-9, 192 tiles from
 * 0x1e8), Franziska's whip (28-30, from 0x200) and others.  In the original, with the item in
 * 0x80-0xbf, none did.  A bubble or a whip while an item is up wrote its picture over the
 * item's, which then showed the bubble's letters in its own colours until it was put away
 * (0.16.95: Objection! over the crystal sphere in episode 5).
 *
 * Since 0.16.97 the item stays up over those effects, as in the original: while one of them runs
 * (FX_RANGES, from the build: the tiles each effect takes) the item's picture is in 64 other OBJ
 * tiles that no sprite on screen and no running effect uses, from the top of the characters'
 * (0x3c0, 0x3b8, ... 0x2c0), else 0x1a0 ... 0x180, and its sprite points there.  In 0x180-0x1df
 * what was there is kept at ITEM_BACKUP and put back after, unless something else has written
 * to those tiles meanwhile (their sum); the characters' and the effects' tiles are copied again
 * before they are shown, and nothing is kept for them.  The picture comes from ITEM_PIC, a copy
 * the update takes each time the game copies the item to its tiles (states 3 and 5), so it is
 * whole whenever it is needed (with no copy, as from a save state of an older build, it is
 * unpacked again).  Every frame the tiles are checked: if a running effect has tiles there or a
 * sprite on the screen (in OAM) uses them, the item moves to other free tiles, or, with none, is
 * hidden as from 0.16.95 to 0.16.96, looking for free tiles again every RETRY frames.
 * Animations write their tiles in the vertical blank, before this update (0x08018134, from
 * 0x0800041a), and a character growing into the tiles shows its sprites there in the same frame:
 * the check comes before the frame is drawn.  Two other places run that copy without this update
 * (0x080043ce and 0x08004dba, frames of a mode change), and check the tiles after it
 * (item_anim_copy).  Once no such effect runs and no other sprite on the screen uses the item's
 * own tiles, the picture goes back there.  The checks take a few scanlines a frame; the search
 * for tiles, which takes more, runs only as an effect starts and on the retries, so that the
 * game's own updates after this one (the life bar's tiles) still come before the screen is drawn.
 *
 * While one of those effects runs with its sprites at priority 0 (the slot's byte +0x43: the shout
 * bubbles 1-4, Objection! and the like; the rest are at 1-3, under the box), the item's sprite is
 * at priority 1 (since 0.16.98): the bubble covers the picture as it covers the box (BG1, priority
 * 1), as it did from 0.16.95 to 0.16.96 with the item hidden.  The original, its item at priority
 * 0 and before the bubble in OAM, drew the picture over the bubble and the box's border under it.
 * That is set in the OAM shadow once the animations have put the effects' sprites for the next
 * frame in it (after 0x080184ac, the last of the vertical blank's updates to write the shadow;
 * and in item_anim_copy), and for TAIL frames after.  With no item and no bubble it costs a few
 * cycles, at the end of the updates: the copies racing the screen in a busy scene come as before.
 *
 * States 3 and 5 wait (doing nothing that frame, the state staying) while such an effect is
 * running, or (since 0.16.89) while a sprite in the bubbles' palette uses the item's tiles, in the
 * OAM shadow or in OAM itself (a bubble stays a frame or two after its effect has gone): the item
 * comes up after it.  The script goes on as before (command 0x13 takes its 16 frames all the
 * same).  The waits end after MAX_WAIT frames whatever is there (an effect, MAX_EFFECT_WAIT).
 */
#include "gba.h"

#define OAM_SH      ((volatile u16*)0x03002ba0)   /* OAM shadow, 4 halfwords per entry */
#define OAM         ((volatile u16*)0x07000000)
#define BUBBLE_PAL  11                             /* the bubbles' OBJ palette */
#define ITEM_PAL    1
#define ITEM_TILES  64
#define ITEM_WORDS  (ITEM_TILES * 8)
#define MAX_WAIT    60
#define MAX_EFFECT_WAIT 240
#define RETRY       32                             /* frames between looks for free tiles while hidden */
#define ITEM_STATE  0x99                           /* SYS+0x99 */
#define ITEM_NUM    0x98                           /* SYS+0x98: the item shown */
#define MODE        8                              /* SYS+8: 7 while the Court Record is up */
#define ITEM_FRAME(s) ((void (*)(volatile u8*))0x0801545d)(s)
#define ITEM_COPY(s)  ((void (*)(volatile u8*))0x080157e1)(s)   /* unpack and copy the picture */
#define ANIM_COPY(r)  ((void (*)(u32))0x08018135)(r)            /* animations' tiles to VRAM */
#define ANIM_UPDATE(r) ((void (*)(u32))0x080184ad)(r)           /* animations' sprites to the shadow */
#define LZ77_WRAM(s, d) ((void (*)(u32, u32))0x0803a049)(s, d)
#define EFFECT_SLOT(k) ((volatile u32*)(0x0300103c - (k) * 0x44))   /* 32 slots, +0 bit 28 running */
#define EFFECT_NUM(k)  (*(volatile u16*)(0x0300103c - (k) * 0x44 + 0xc))   /* 0xff: a character */
#define TILES(t)    ((volatile u32*)(0x06010000 + (t) * 32))
#define PIC         ((volatile u32*)ITEM_PIC)      /* 2 KB: the item's picture */
#define BACKUP      ((volatile u32*)ITEM_BACKUP)   /* 2 KB: what was in the tiles it borrows */
#define PIC_MAGIC   0x9c17
#define TAIL        2                              /* frames the item stays under a bubble after it */

/* At ITEM_BSS; the first three as up to 0.16.96, so that save states carry over. */
struct item_st {
    u8 waited;              /* frames state 3 or 5 has waited */
    u8 spoiled;             /* the item is hidden for an effect */
    u16 shown_attr0;        /* its sprite's attr0 from before that */
    u16 pic;                /* PIC_MAGIC: PIC holds the picture of item pic_item */
    u16 win;                /* the tiles the item is in, 0: its own */
    u32 sum;                /* PIC's sum, while it is in tiles whose contents are kept */
    u8 pic_item;
    u8 tick;
    u8 idle;                /* frames with no such effect running while the item is away */
    u8 behind;              /* frames left with the item at priority 1, under a bubble */
};
_Static_assert(sizeof(struct item_st) <= 0x10, "item.c's state runs past its 16 bytes");
#define ST (*(volatile struct item_st*)ITEM_BSS)

static const u32 fx_range[256] = FX_RANGES;   /* effect n: tiles lo | hi << 16 ([lo, hi)), 0 none */
static const u16 windows[] = {
    0x3c0, 0x3b8, 0x3b0, 0x3a8, 0x3a0, 0x398, 0x390, 0x388, 0x380, 0x378, 0x370, 0x368, 0x360,
    0x358, 0x350, 0x348, 0x340, 0x338, 0x330, 0x328, 0x320, 0x318, 0x310, 0x308, 0x300, 0x2f8,
    0x2f0, 0x2e8, 0x2e0, 0x2d8, 0x2d0, 0x2c8, 0x2c0, 0x1a0, 0x198, 0x190, 0x188, 0x180,
};
#define NWIN (sizeof(windows) / sizeof(windows[0]))

/* tiles a sprite takes, by attr0 shape and attr1 size (twice as many for 256 colours) */
static const u8 tiles[3][4] = { { 1, 4, 16, 64 }, { 2, 4, 8, 32 }, { 2, 4, 8, 32 } };
static u32 obj_tiles(u32 a0, u32 a1) { return tiles[a0 >> 14][a1 >> 14] << ((a0 >> 13) & 1); }

static void dma32(const volatile void* src, volatile void* dst, u32 words) {
    REG(0x040000d4) = (u32)src;
    REG(0x040000d8) = (u32)dst;
    REG(0x040000dc) = words | 0x84000000;
    (void)REG(0x040000dc);
}

/* a sum of the 512 words of 64 tiles (in VRAM or EWRAM), to tell whether they have changed */
static __attribute__((noinline)) u32 sum(volatile u32* v) {
    const u32* p = (const u32*)v;
    u32 s = 0, t = 0;
    for (int k = 0; k < ITEM_WORDS; k += 4, p += 4) {
        s += p[0] + p[2];
        t ^= p[1] + p[3];
        t = t << 3 | t >> 29;
    }
    return s ^ t;
}

static int win_valid(u32 w) {
    return !(w & 7) && ((w >= 0x2c0 && w <= 0x3c0) || (w >= 0x180 && w <= 0x1a0));
}

static int item_entry(int i, volatile u16* oam, u32 tile) {
    return (oam[i * 4 + 2] & 0x3ff) == tile && oam[i * 4 + 2] >> 12 == ITEM_PAL;
}

/* a sprite in the bubbles' palette (other than the item) on the item's own tiles */
static int over_item(volatile u16* oam) {
    for (int i = 0; i < 128; i++) {
        u32 a0 = oam[i * 4], a1 = oam[i * 4 + 1], a2 = oam[i * 4 + 2];
        if (item_entry(i, oam, ITEM_TILE) || (a0 & 0x300) == 0x200 || a0 >> 14 == 3 || a2 >> 12 != BUBBLE_PAL) continue;
        u32 t0 = a2 & 0x3ff, t1 = t0 + obj_tiles(a0, a1);
        if (t0 < ITEM_TILE + ITEM_TILES && t1 > ITEM_TILE) return 1;
    }
    return 0;
}

/* tiles a sprite takes, by attr0 bits 13-15 (256 colours, shape) and attr1 bits 14-15 (size) */
static const u8 obj_n[32] = {
    1, 4, 16, 64,  2, 8, 32, 128,  2, 4, 8, 32,  4, 8, 16, 64,
    2, 4, 8, 32,   4, 8, 16, 64,   0, 0, 0, 0,   0, 0, 0, 0,
};

/* a sprite parked off the screen (the Court Record's text sprites wait at x 326-422 during the
   game, on the item's own tiles): wholly right of x 239 (x is 9 bits, wrapping at 512) or below
   y 159 (8 bits, wrapping at 256); its size by shape and size, twice that double-sized */
static const u8 obj_w[12] = { 8, 16, 32, 64,  16, 32, 32, 64,  8, 8, 16, 32 };
static const u8 obj_h[12] = { 8, 16, 32, 64,  8, 8, 16, 32,  16, 32, 32, 64 };
static int off_screen(u32 a) {
    u32 k = (a >> 12 & 0xc) | a >> 30, dbl = (a & 0x300) == 0x300;
    u32 x = a >> 16 & 0x1ff, y = a & 0xff;
    return (x >= 240 && x + (obj_w[k] << dbl) <= 512) || (y >= 160 && y + (obj_h[k] << dbl) <= 256);
}

/* a sprite on the screen, other than entry `skip`, with tiles among [lo, hi) (every frame while
   the item is in other tiles: most entries are hidden, and are passed over four at a time) */
static __attribute__((noinline)) int sprite_in(volatile u16* oam, u32 lo, u32 hi, int skip) {
    volatile u32* end = (volatile u32*)oam + 128 * 2;
    volatile u32* own = (volatile u32*)oam + skip * 2;
    for (volatile u32* q = (volatile u32*)oam; q != end; q += 8) {
        if (!(((q[0] ^ 0x200) | (q[2] ^ 0x200) | (q[4] ^ 0x200) | (q[6] ^ 0x200)) & 0x300)) continue;
        for (volatile u32* p = q; p != q + 8; p += 2) {
            u32 a = p[0];                                   /* attr0 | attr1 << 16 */
            if ((a & 0x300) == 0x200 || p == own) continue;
            u32 t0 = p[1] & 0x3ff;
            if (t0 >= hi || t0 + 128 <= lo || off_screen(a)) continue;   /* 128: the most a sprite takes */
            u32 n = obj_n[(a >> 11 & 0x1c) | a >> 30];        /* 0: shape 3, not shown */
            if (n && t0 + n > lo) return 1;
        }
    }
    return 0;
}

static int sprites_in(u32 lo, u32 hi, int skip) {
    return sprite_in(OAM_SH, lo, hi, skip) || sprite_in(OAM, lo, hi, skip);
}

/* a running effect with tiles among [lo, hi) */
static __attribute__((noinline)) int effect_in(u32 lo, u32 hi) {
    volatile u32* slot = EFFECT_SLOT(0);
    for (int k = 0; k < 32; k++, slot -= 0x44 / 4) {
        if (!(slot[0] & (1u << 28))) continue;
        u32 n = ((volatile u16*)slot)[6];
        if (n >= 256) continue;
        u32 r = fx_range[n];
        if (r && (r & 0xffff) < hi && (r >> 16) > lo) return 1;
    }
    return 0;
}

/* the shadow entry the item's update uses, as it picks it (0x08015662): 0 with TXT+0x2c 3, 72
   while 0x0801e210 says so (with the life bar up), else 65; -1 if it does not show the item.  (Up
   to 0.16.96 the first of 65, 72 and 0 with the item's tiles: with the bar up, a stale 65, hidden,
   was hidden again, and 72 showed the effect's picture in the item's colours.) */
static int item_sprite(void) {
    int i = TXT[0x2c] == 3 ? 0 : ((int (*)(void))0x0801e211)() ? 72 : 65;
    return item_entry(i, OAM_SH, ITEM_TILE) || (ST.win && item_entry(i, OAM_SH, ST.win)) ? i : -1;
}

static void set_tile(int i, u32 t) {
    OAM_SH[i * 4 + 2] = (OAM_SH[i * 4 + 2] & ~0x3ff) | t;
    OAM[i * 4 + 2] = OAM_SH[i * 4 + 2];
}

/* granules g0..g1-1 (8 tiles each) marked in a 128-bit map */
static void mark(u32* used, u32 g0, u32 g1) {
    if (g1 > 128) g1 = 128;
    while (g0 < g1) {
        u32 n = 32 - (g0 & 31);
        if (n > g1 - g0) n = g1 - g0;
        used[g0 >> 5] |= (n == 32 ? ~0u : ((1u << n) - 1)) << (g0 & 31);
        g0 += n;
    }
}

/* 64 tiles from `windows` that no sprite in `oam` (other than the item's) and no running effect
   uses, or 0: the 8-tile blocks in use, then the first window clear of them */
static __attribute__((noinline)) u32 find_window(volatile u16* oam, int skip) {
    u32 used[4] = { 0, 0, 0, 0 };
    volatile u32* end = (volatile u32*)oam + 128 * 2;
    volatile u32* own = (volatile u32*)oam + skip * 2;
    for (volatile u32* q = (volatile u32*)oam; q != end; q += 8) {
        if (!(((q[0] ^ 0x200) | (q[2] ^ 0x200) | (q[4] ^ 0x200) | (q[6] ^ 0x200)) & 0x300)) continue;
        for (volatile u32* p = q; p != q + 8; p += 2) {
            u32 a = p[0];
            if ((a & 0x300) == 0x200 || p == own) continue;
            u32 t0 = p[1] & 0x3ff, n = obj_n[(a >> 11 & 0x1c) | a >> 30];
            if (n) mark(used, t0 >> 3, (t0 + n + 7) >> 3);
        }
    }
    volatile u32* slot = EFFECT_SLOT(0);
    for (int k = 0; k < 32; k++, slot -= 0x44 / 4) {
        if (!(slot[0] & (1u << 28))) continue;
        u32 n = ((volatile u16*)slot)[6];
        u32 r = n < 256 ? fx_range[n] : 0;
        if (r) mark(used, (r & 0xffff) >> 3, ((r >> 16) + 7) >> 3);
    }
    for (u32 j = 0; j < NWIN; j++) {
        u32 g = windows[j] >> 3, lo = used[g >> 5] >> (g & 31);
        if ((g & 31) > 24) lo |= used[(g >> 5) + 1] << (32 - (g & 31));
        if (!(lo & 0xff)) return windows[j];
    }
    return 0;
}

/* PIC: the picture of the item shown, from its tiles just after the game has copied it there */
static void snapshot(volatile u8* sys) {
    dma32(TILES(ITEM_TILE), PIC, ITEM_WORDS);
    ST.pic_item = sys[ITEM_NUM];
    ST.pic = PIC_MAGIC;
}

/* PIC holds the item's picture; unpacked again if not (the loader's own tables, 0x080157e0) */
static int pic_ready(volatile u8* sys) {
    if (ST.pic == PIC_MAGIC && ST.pic_item == sys[ITEM_NUM]) return 1;
    u32 pics = *(volatile u32*)0x08015854, items = *(volatile u32*)0x08015858;
    u32 src = *(volatile u32*)(pics + 4 * *(volatile u16*)(items + 8 * sys[ITEM_NUM] + 4));
    if (src < 0x08000000 || src >= 0x0a000000) return 0;
    LZ77_WRAM(src, ITEM_PIC - 0x20);                 /* the palette (32 bytes), then the tiles */
    ST.pic_item = sys[ITEM_NUM];
    ST.pic = PIC_MAGIC;
    return 1;
}

/* the tiles the item was in given back: in 0x180-0x1df what was there put back, unless something
   else has written to them since (the characters' tiles, 0x2c0 on, are copied again before they
   are shown, as are the effects': nothing is kept for them) */
#define KEEPS(w) ((w) < 0x2c0)
static void leave_window(void) {
    u32 w = ST.win;
    ST.win = 0;
    if (win_valid(w) && KEEPS(w) && sum(TILES(w)) == ST.sum) dma32(BACKUP, TILES(w), ITEM_WORDS);
}

static void move_to(int i, u32 w) {
    if (KEEPS(w)) { dma32(TILES(w), BACKUP, ITEM_WORDS); ST.sum = sum(PIC); }
    dma32(PIC, TILES(w), ITEM_WORDS);
    ST.win = w;
    set_tile(i, w);
}

static void hide(int i) {
    if (!ST.spoiled) { ST.shown_attr0 = OAM_SH[i * 4]; ST.spoiled = 1; }
    OAM_SH[i * 4] = (OAM_SH[i * 4] & ~0x300) | 0x200;
    OAM[i * 4] = OAM_SH[i * 4];
}

static void unhide(int i) {
    if ((OAM_SH[i * 4] & 0x300) == 0x200) OAM_SH[i * 4] = ST.shown_attr0;
    ST.spoiled = 0;
}

/* the item's own tiles are free: no effect over them runs and no other sprite shows them (or
   none has run for MAX_WAIT frames, whatever is there) */
static int home_free(int busy, int i) {
    return !busy && (ST.idle >= MAX_WAIT || !sprites_in(ITEM_TILE, ITEM_TILE + ITEM_TILES, i));
}

static void go_home(int i) {
    dma32(PIC, TILES(ITEM_TILE), ITEM_WORDS);
    set_tile(i, ITEM_TILE);
    leave_window();
}

/* the tiles the item is in are no longer its own: to its own if they are free, to other free
   tiles, or hidden */
static void window_lost(int i, int busy, volatile u16* oam) {
    set_tile(i, ITEM_TILE);
    leave_window();
    if (home_free(busy, i)) { dma32(PIC, TILES(ITEM_TILE), ITEM_WORDS); return; }
    u32 w = find_window(oam, i);
    if (w) move_to(i, w);
    else hide(i);
}

/* the tiles the item is in are still its own: no running effect has them and no other sprite
   shows them in `oam` (OAM in the item's update, just copied from the shadow at 0x08006780; the
   shadow after the animations' copy, which comes before that) */
static int window_ok(int i, volatile u16* oam) {
    u32 w = ST.win;
    return win_valid(w) && !effect_in(w, w + ITEM_TILES) && !sprite_in(oam, w, w + ITEM_TILES, i);
}

/* every frame with the item up (state 4, or 3 while a new one waits: start = 0) and the Court
   Record away */
static void keep(volatile u8* sys, int busy, int start) {
    int i = item_sprite();
    if (i < 0) { if (ST.win) leave_window(); ST.spoiled = 0; return; }
    if (busy) ST.idle = 0;
    else if (ST.idle < 255) ST.idle++;
    if (ST.win) {
        if (!window_ok(i, OAM)) window_lost(i, busy, OAM);
        else if (home_free(busy, i)) go_home(i);
        else set_tile(i, ST.win);
        return;
    }
    if (!start) return;
    if (ST.spoiled) {
        /* hidden for an effect (as up to 0.16.96): back once it is over and no other sprite is on
           its tiles (0.16.96 looked only for the bubbles' palette: the episode's title card,
           effect 16, showed the item's picture for a frame as it went), or into free tiles */
        if (home_free(busy, i)) {
            if (pic_ready(sys)) dma32(PIC, TILES(ITEM_TILE), ITEM_WORDS);
            else ITEM_COPY(sys);
            unhide(i);
            return;
        }
        if (busy && !(++ST.tick % RETRY) && pic_ready(sys)) {
            u32 w = find_window(OAM, i);
            if (w) { move_to(i, w); unhide(i); return; }
        }
        hide(i);
        return;
    }
    if (busy) {
        u32 w = pic_ready(sys) ? find_window(OAM, i) : 0;
        if (w) move_to(i, w);
        else hide(i);
    }
}

/* entry i of `oam` is on and shows tiles from t */
static int shows(volatile u16* oam, int i, u32 t) {
    return (oam[i * 4] & 0x300) != 0x200 && (oam[i * 4 + 2] & 0x3ff) == t;
}

/* in place of 0x0801545c at both its calls */
void item_frame(volatile u8* sys) {
    u32 s = sys[ITEM_STATE];
    int busy = effect_in(ITEM_TILE, ITEM_TILE + ITEM_TILES);
    if ((s == 3 || (s == 5 && sys[MODE] <= 6)) &&
        ((busy && ST.waited < MAX_EFFECT_WAIT) || (ST.waited < MAX_WAIT && (over_item(OAM_SH) || over_item(OAM))))) {
        ST.waited++;
        if (s == 3 && sys[MODE] <= 6) keep(sys, busy, 0);
        return;
    }
    ST.waited = 0;
    ITEM_FRAME(sys);
    u32 now = sys[ITEM_STATE];
    if (now == 4 && s != 4) {
        /* the picture has just been copied to the item's tiles, and its sprite pointed there */
        if (ST.win) leave_window();
        ST.spoiled = 0;
        snapshot(sys);
    }
    if (now != 4 || sys[MODE] > 6) {
        /* put away: the game hides the sprite (states 1 and 5), or the screen goes on showing it
           for a few frames (a change of scene sets state 0 and hides it in the shadow, which is
           not copied to OAM meanwhile: bank 31 section 0x46): while OAM or the shadow still shows
           the picture from other tiles it stays there, or goes back once its own are free */
        if (ST.win) {
            int i = item_sprite();
            if (i >= 0 && (shows(OAM_SH, i, ST.win) || shows(OAM, i, ST.win))) {
                if (busy) ST.idle = 0;
                else if (ST.idle < 255) ST.idle++;
                if (!window_ok(i, OAM)) {
                    set_tile(i, ITEM_TILE);
                    OAM_SH[i * 4] = (OAM_SH[i * 4] & ~0x300) | 0x200;
                    OAM[i * 4] = OAM_SH[i * 4];
                    leave_window();
                } else if (home_free(busy, i)) go_home(i);
            } else leave_window();
        }
        ST.spoiled = 0;
        return;
    }
    keep(sys, busy, 1);
}

/* a running effect with tiles among the item's and its sprites at priority 0 (slot byte +0x43) */
static int bubble_up(void) {
    volatile u32* slot = EFFECT_SLOT(0);
    for (int k = 0; k < 32; k++, slot -= 0x44 / 4) {
        if (!(slot[0] & (1u << 28)) || ((volatile u8*)slot)[0x43]) continue;
        u32 n = ((volatile u16*)slot)[6];
        if (n >= 256) continue;
        u32 r = fx_range[n];
        if (r && (r & 0xffff) < ITEM_TILE + ITEM_TILES && (r >> 16) > ITEM_TILE) return 1;
    }
    return 0;
}

/* the item's sprite (whichever of 0, 65 and 72 shows its tiles) at priority 1 while such a bubble
   is up and TAIL frames after, else 0 as the game sets it; in the shadow, just before it goes to OAM */
static void item_prio(void) {
    static const u8 entries[3] = { 0, 65, 72 };
    if (!ST.behind && !SYS[ITEM_STATE]) return;   /* no item: nothing to do */
    if (bubble_up()) ST.behind = TAIL + 1;
    else if (!ST.behind) return;
    else ST.behind--;
    u32 p = ST.behind ? 0x400 : 0;
    for (int k = 0; k < 3; k++) {
        int i = entries[k];
        if (item_entry(i, OAM_SH, ITEM_TILE) || (ST.win && item_entry(i, OAM_SH, ST.win)))
            OAM_SH[i * 4 + 2] = (OAM_SH[i * 4 + 2] & ~0xc00) | p;
    }
}

/* in place of the animations' copy (0x08018134) where it runs without the item's update */
void item_anim_copy(void) {
    ANIM_COPY(0);
    if (ST.win) {
        int i = item_sprite();
        if (i >= 0 && !window_ok(i, OAM_SH)) window_lost(i, effect_in(ITEM_TILE, ITEM_TILE + ITEM_TILES), OAM_SH);
    }
    item_prio();
}

/* in place of the animations' update in the vertical blank's updates (0x0800043c), after the
   item's: the shadow as the next frame's copy to OAM (0x08006780) will take it */
void item_anim_update(u32 r0) {
    ANIM_UPDATE(r0);
    item_prio();
}

void _start(void) {}
