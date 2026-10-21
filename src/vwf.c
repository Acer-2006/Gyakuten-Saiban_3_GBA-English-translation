/* Variable-width font renderer for the text engine.
 *
 * Main window: the original engine draws one 16x16 sprite per character cell.  The English
 * page is sprite text too, blitted at a pixel pen into 32x16 sprite cells (three lines of eight,
 * OAM 3-26, the engine's own sprite-text palette): the box behind it is the engine's own, the
 * text keeps its colours (the box blends with the scene; sprites do not), and it stays in view
 * under the Court Record as the original's does.
 * Choice menus: the page that asks the question is drawn on a 30x6-tile canvas in BG char
 * block 0 (tiles CV_TILE0..) mapped onto BG1 rows CV_MAPROW..+5 instead, so that when the box
 * grows to full screen the question can move to the top rows while the options take the sprite
 * cells.
 */
#include "gba.h"
#include "font.h"   /* generated: font_rows[], font_w[], expand_lut[], cmd_args[] */

#define CV_TILE0   0xe0
#define CV_COLS    30
#define CV_ROWS    6
#define CV_MAPROW  13         /* the box's first interior row: the box is BG1 rows 12-19 */
#define BOX_BOTTOM 19         /* its bottom edge row */
#define TEXT_Y0    102        /* the page's first line: 4 px below the box's top border, as the DS's */
#define LINE_H     16
#define MODE_RECORD 7         /* game mode (SYS+8): the Court Record */
#define MAX_LINES  3
/* The DS starts its lines 8 pixels inside the box (its box is 256 wide; the GBA's 240): the same
   margin here, with 230 pixels for the line.  Lines wider than that (under 1%, up to 246) get
   their letter spacing one pixel tighter; the DS's line breaks are kept. */
#define BOX_W      240
#define TEXT_X0    8          /* left padding inside the box */
#define TEXT_MAXW  230        /* usable width in pixels */
/* cross-examination statements: the engine's arrows to the previous and next statement are
   sprites over the box's edge columns at the second line (x 0-8 and 232-239), so the text keeps
   clear of them */
#define STMT_X0    10
#define STMT_MAXW  220

#define OAMBUF ((volatile u16*)0x03002ba0)

/* continue arrow sprite */
#define ARROW_OBJ   2
#define ARROW_TILE  0xf8
#define ARROW_X     229       /* at rest: the tip 2 pixels inside the box's right edge, as the DS's */
#define ARROW_Y     139       /* 10 px above the box's bottom border, as the DS's */

/* sprite text: 3 lines of 8 sprite cells (32x16, 8 tiles each) in OBJ tiles 0x00-0xbf.  The
   original's two lines take 0x00-0x7f and the item shown in court 0x80-0xbf: patches/icons.py
   moves that item to 0x1e0.  Effects that play over dialogue (the butterflies, 0xe0 on), the
   continue arrow (0xf8) and the choice cursor (0xfc, OAM 57) are above. */
#define LBL_X0     24
#define LBL_CELLS  8
#define LBL_CELLW  32
#define LBL_LINES  3
static u32 lbl_tile(int L, int cell);
/* OAM entries of each line's cells: 3-26, within the entries 2-33 the engine's own sprite text
   takes.  They must come before the scene's sprites (the defence bench is in 48-51, at
   priority 3): the hardware draws an earlier, lower-priority sprite that overlaps a later,
   higher-priority one with the latter's priority, so a line of text in entries after 48 lifted
   the bench above the box.  The Court Record draws its arrows in 0-1 and its panel in 34-47,
   the save screen its Yes / No in 40-41, and the choice cursor is 57. */
static const u8 lbl_obj0[LBL_LINES] = {3, 11, 19};
#define Q_MAPROW   2          /* question canvas rows in choice mode: its first line at y 17, as the
                                 original's question (row 1 put it against the box's top edge) */
#define Q_DROP     4          /* ... shown this much lower, clear of the penalty gauge (vwf_bgcnt) */
#define CAP_Y0     62         /* caption screen: first row y, 18 px pitch */
#define CAP_PITCH  18
#define SYS_Y0     56         /* system messages in the save / continue screen box: first row y */

struct vwf_state {
    s16 pen_x;
    u8 line;
    u8 squeeze;
    u8 mapped;      /* canvas map entries currently written */
    u8 arrow_on;
    s16 lbl_pen;
    s16 lbl_row0;
    u8 lbl_line;
    u8 lbl_width[LBL_LINES];
    u8 lbl_caption;     /* sprite text outside the box (command 0x42) rather than menu labels */
    u8 lbl_shown;       /* OAM entries lbl_obj0[].. currently carry sprite text */
    u8 lbl_used[LBL_LINES];   /* ... how many of each line's 8 entries (the others are left
                                 alone: the save screen puts its Yes / No in entries 40-41) */
    u8 lbl_align;       /* ... and how the engine places it, latched at its first character */
    u8 lbl_rows;
    u8 lbl_sys;
    u8 lbl_low;
    u8 lbl_free;        /* free-slot mode (TXT flags bit 2): placed at the command 0x48 offset */
    u8 lbl_fx, lbl_fy;
    u8 lbl_full[LBL_LINES];   /* width of each line of the page (measured ahead) */
    u8 lost;            /* the canvas tiles were overwritten while mapped (see canvas_check) */
    u8 csum_ok;
    u16 glog_n;
    u32 csum;
    u8 resume;          /* a continued save's page is to be drawn again (see vwf_resume) */
    u8 resume_colour, resume_align;
    u32 resume_page, resume_cur;
    u8 inset;           /* this page is a statement (STMT_X0) */
    s16 line_x0;        /* where the line starts: centred lines (command 0x5d 1) further in */
    u8 blip_n, blip_mode;     /* text blips (text_blip) */
    u8 q_noedge;        /* the canvas's bottom edge is taken out for the choice box (frame_bottom) */
    u8 mode;            /* the page being typed: 0 none yet, 1 on the canvas (it ends in a choice),
                           2 sprite text in the box (box_glyph) */
    u8 lbl_base;        /* a choice: the engine's row of the first option (see label_draw_char) */
    u8 arrow_y;         /* the engine's arrow bobs: its tile pair (0x20, 0x22, 0x24, 0x26) is a row down each */
    u8 arrow_t;         /* frames the DS-style arrow has been up (its slide) */
    u8 overlay;         /* the save screen is up over the game: nothing of the page is shown */
    volatile u32* ds_cell;   /* the data screen: tiles of the 16x16 sprite being drawn into */
    u8 l3_lent;         /* the Court Record has put its picture in line 3's tiles (record_borrows) */
};
static struct vwf_state vs;

/* Every glyph blitted onto the canvas since it was last cleared, so that the question can be
   drawn again: the Court Record's slide between items copies its panel into BG tiles
   0xa0-0x17f, which are the canvas's (BG char block 0 has no room for both). */
#define GLOG_MAX   192
static u32 glog[GLOG_MAX];          /* glyph | x << 9 | y << 17 | colour << 23 */

/* State added after 0.16.21, at a fixed address past the BSS (patches/text.py keeps the BSS
   below it): a save state made with an earlier build has zeros there, where fields appended to
   vs would shift glog and read the log's first entry as l3_tile.  New fields go at the end. */
struct vwf_ext {
    u8 lbl_trim[LBL_LINES];   /* leading space of each line dropped so that it fits (page_scan) */
    u16 l3_tile;        /* while the Court Record borrows 0x80-0xbf: line 3's stand-in tiles (0: none) */
    u8 lbl_dirty;       /* lines whose tiles are still to be cleared for this page (line_clean) */
    u8 q_bare;          /* the canvas tiles hold the letters alone (BG0 shows them over the box): set
                           by canvas_tiles, from q_want, so it always says how the tiles are drawn */
    u8 q_on;            /* the question is on BG0 this frame (q_frame) */
    u8 q_new;           /* ... from this frame: BG0's whole map is cleared first */
    u8 q_bg1;           /* the game DMAs BG1's map this frame: its canvas cells are patched after */
    u32 q_rows;         /* BG0 map rows (0-19) holding canvas entries */
    u32 q_rows_now;     /* ... this frame's */
    u16 q_save_disp, q_save_bld;   /* the game's shadow values around its IO register update */
    u32 q_save_win;
    u8 q_saved;
    u8 q_want;          /* BG0 is free: canvases are drawn bare (q_bare is how the tiles are now) */
    u8 cur_ahead;       /* the choice cursor is in OAM CURSOR_AHEAD (cursor_ahead) */
    u8 lo_rows;         /* box_leftovers: the pair of rows it looks at this frame (0-4) */
    u8 lbl_sq;          /* a choice's options: pixels taken out of every letter gap (line_done) */
};
#define vx (*(struct vwf_ext*)0x02028780)

/* Each line's eight 32x16 cells: OBJ tiles 0x00, 0x40 and 0x80 on, the third line elsewhere
   while the Court Record has its tiles (record_lend). */
static u32 lbl_tile(int L, int cell) {
    return (L == 2 && vs.l3_lent && vx.l3_tile ? vx.l3_tile : (u32)L * 0x40) + cell * 8;
}
#define BOX_TEMPLATE ((const u8*)0x0803b844)   /* the engine's box, 32x32 tile numbers */

/* The three text colours (commands 0x03 1-3): the Japanese game's, which the DS uses too.
   They live in BG palette 0 entries 13-15 only while the page is mapped; the UI palette's own
   values go back the moment it is not, because the Court Record's panel (on a background while
   it slides) names its items in entry 15. */
#define TEXT_ORANGE 0x1dde
#define TEXT_BLUE   0x7b0d
#define TEXT_GREEN  0x03c0
#define UI_13 0x3def
#define UI_14 0x028c
#define UI_15 0x03ff
static void text_colours(int on) {
    if (on) { BGPAL[13] = TEXT_ORANGE; BGPAL[14] = TEXT_BLUE; BGPAL[15] = TEXT_GREEN; }
    else    { BGPAL[13] = UI_13;       BGPAL[14] = UI_14;     BGPAL[15] = UI_15; }
}

/* Sprite text uses OBJ palette 0, as the engine's own does: the same in every scene, with white
   at 3 and the three text colours at 6, 9 and 12 (the BG text has them at 8 and 13-15). */
static u32 lbl_colour(u32 c) {
    return c == 13 ? 6 : c == 14 ? 9 : c == 15 ? 12 : 3;
}

static const u16 text_colors[16] = {
    /* colour index per text colour argument (command 0x03) */
    8, 13, 14, 15, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
};

/* Box frame tile patterns (4bpp rows) from the original UI tiles. */
static const u32 frame_tiles[7][8] = {
    {0x11111111, 0x11111111, 0x11111111, 0x11111111, 0x11111111, 0x11111111, 0x11111111, 0x11111111}, /* 0 interior */
    {0x11111123, 0x11111123, 0x11111123, 0x11111123, 0x11111123, 0x11111223, 0x22222231, 0x33333311}, /* 1 bottom-left */
    {0x32111111, 0x32111111, 0x32111111, 0x32111111, 0x32111111, 0x32211111, 0x13222222, 0x11333333}, /* 2 bottom-right */
    {0x11111123, 0x11111123, 0x11111123, 0x11111123, 0x11111123, 0x11111123, 0x11111123, 0x11111123}, /* 3 left */
    {0x32111111, 0x32111111, 0x32111111, 0x32111111, 0x32111111, 0x32111111, 0x32111111, 0x32111111}, /* 4 right */
    {0x33333333, 0x22222222, 0x11111111, 0x11111111, 0x11111111, 0x11111111, 0x11111111, 0x11111111}, /* 5 top */
    {0x11111111, 0x11111111, 0x11111111, 0x11111111, 0x11111111, 0x11111111, 0x22222222, 0x33333333}, /* 6 bottom */
};

/* A 32-bit DMA3 copy (or fill, the source fixed: it must then be in RAM, as a DMA from the
   cartridge always steps its source).  The game uses DMA3 too, never across our calls. */
static void dma32(const volatile void* src, volatile void* dst, u32 words, u32 fixed) {
    REG(0x040000d4) = (u32)src;
    REG(0x040000d8) = (u32)dst;
    REG(0x040000dc) = words | 0x84000000 | (fixed ? 0x01000000 : 0);
    (void)REG(0x040000dc);
}

/* ---------------------------------------------------------------- glyph blitting */
static int glyph_index(u32 code) {
    if (code >= 0x80 && code < 0x180) return code - 0x80;
    if (code >= 0x680 && code < 0x698) return 0x100 + (code - 0x680);
    return FONT_MISSING;
}

typedef volatile u32* (*rowptr_fn)(int tx, int ty, int r);

static volatile u32* canvas_rowptr(int tx, int ty, int r) {
    if (tx < 0 || tx >= CV_COLS || ty >= CV_ROWS) return 0;
    return (volatile u32*)(VRAM + (CV_TILE0 + ty * CV_COLS + tx) * 32 + r * 4);
}

static volatile u32* label_rowptr(int tx, int ty, int r) {
    if (tx < 0 || tx >= LBL_CELLS * 4 || ty >= LBL_LINES * 2) return 0;
    int tile = lbl_tile(ty >> 1, tx >> 2) + (ty & 1) * 4 + (tx & 3);   /* 1D mapping: a 32x16 sprite's tiles */
    return (volatile u32*)(0x06010000 + tile * 32 + r * 4);
}

/* Blit glyph gi at pixel (x, y) with colour index c onto a tiled surface. */
static void blit_to(int gi, int x, int y, u32 c, rowptr_fn rowptr) {
    const u16* rows = font_rows + gi * 16;
    int tx0 = x >> 3;
    for (int r = 0; r < 16; r++) {
        u32 bits = rows[r];
        if (!bits) continue;
        int yy = y + r;
        int ty = yy >> 3, rr = yy & 7;
        u32 win = bits << 16;
        for (int t = 0; t < 3; t++) {
            int tx = tx0 + t;
            int s = tx * 8 - x;                    /* glyph pixel index at the tile's left edge */
            u32 w = (s >= 0) ? (win << s) : (win >> (-s));
            u32 m8 = (w >> 24) & 0xff;
            if (!m8) continue;
            volatile u32* p = rowptr(tx, ty, rr);
            if (!p) continue;
            u32 v = *p;
            u32 em = expand_lut[m8];
            v = (v & ~(em * 0xf)) | (em * c);
            *p = v;
        }
    }
}

/* ---------------------------------------------------------------- main canvas */
static void fill_tile(int dst_tile, const u32* src) {
    volatile u32* d = (volatile u32*)(VRAM + dst_tile * 32);
    for (int i = 0; i < 8; i++) d[i] = src[i];
}

static void canvas_tiles(void) {
    vx.q_bare = vx.q_want;
    if (vx.q_bare) {
        volatile u32 zero = 0;
        dma32(&zero, VRAM + CV_TILE0 * 32, CV_ROWS * CV_COLS * 8, 1);
        vs.q_noedge = 0;
        vs.csum_ok = 0;
        return;
    }
    for (int ty = 0; ty < CV_ROWS; ty++) {
        for (int tx = 0; tx < CV_COLS; tx++) {
            int src;
            src = (tx == 0) ? 3 : (tx == CV_COLS - 1) ? 4 : 0;   /* the bottom edge is the template's row 19 */
            fill_tile(CV_TILE0 + ty * CV_COLS + tx, frame_tiles[src]);
        }
    }
    vs.q_noedge = 0;
    vs.csum_ok = 0;
}

/* The canvas's last row carries the box's bottom edge (the last two pixel rows of its tiles, three
   at the corners).  In the full-screen choice box the question canvas sits at the top, where that
   edge would draw a line across the screen: frame_bottom(0) turns it into plain interior and side
   edges, frame_bottom(1) puts it back.  Only frame pixels change (text has colours 8 and up). */
static void frame_bottom(int on) {
    if (vx.q_bare) { vs.q_noedge = !on; return; }   /* no frame in the tiles: BG1 has the box */
    for (int tx = 0; tx < CV_COLS; tx++) {
        int edge = (tx == 0) ? 1 : (tx == CV_COLS - 1) ? 2 : 6;
        int side = (tx == 0) ? 3 : (tx == CV_COLS - 1) ? 4 : 0;
        const u32* from = frame_tiles[on ? side : edge];
        const u32* to = frame_tiles[on ? edge : side];
        volatile u32* d = (volatile u32*)(VRAM + (CV_TILE0 + (CV_ROWS - 1) * CV_COLS + tx) * 32);
        for (int r = 5; r < 8; r++) {
            u32 v = d[r];
            for (int k = 0; k < 32; k += 4)
                if (((v >> k) & 15) == ((from[r] >> k) & 15))
                    v = (v & ~(15u << k)) | (to[r] & (15u << k));
            d[r] = v;
        }
    }
    vs.q_noedge = !on;
    vs.csum_ok = 0;
}

static void canvas_reset(void) {
    canvas_tiles();
    vs.glog_n = 0;
}

/* The DS's page arrow: a solid white triangle pointing right, 9 pixels wide and high, at the
   right of the third line; it slides a pixel at a time, three frames a step, from one pixel
   right of its rest to two pixels left and back (an 18-frame cycle).  The original's is a
   10x5 triangle pointing down in the box's bottom edge, bobbing.  A 16x16 sprite, tiles
   0xf8-0xfb, in the text's white: OBJ palette 0 entry 3, the engine's sprite-text palette, the
   same in every scene.  (Until 0.16.43 it was OBJ palette 2 entry 8, white too, but a
   Psyche-Lock sequence loads gradients into OBJ palettes 1-4 and leaves 2's entry 8 pale
   blue-violet, 0x7f18, after it.) */
/* Rows 1, 3, 5, 7, 9, 7, 5, 3, 1 pixels wide from the left, in colour 3; the engine rewrites
   its arrow cells every frame, so this is copied every frame the arrow is up (working the rows
   out each time took six scanlines of the vertical blank). */
static const u32 arrow_tiles[32] = {
    0x00000003, 0x00000333, 0x00033333, 0x03333333, 0x33333333, 0x03333333, 0x00033333, 0x00000333,
    0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000003, 0x00000000, 0x00000000, 0x00000000,
    0x00000003, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000,
};
static void arrow_load(void) {
    volatile u32* d = (volatile u32*)(0x06010000 + ARROW_TILE * 32);
    if (d[4] == arrow_tiles[4] && d[12] == arrow_tiles[12] && d[16] == arrow_tiles[16] && d[1] == arrow_tiles[1]) return;
    for (int i = 0; i < 32; i++) d[i] = arrow_tiles[i];
}

/* Choice menus grow the box to the whole screen: its top-left corner tile sits at row 0. */
static int fullscreen_box(void) {
    return (BG1MAP[0] & 0x3ff) == 0x06 && (BG1MAP[1] & 0x3ff) == 0x01;
}

/* Is the (3-line) text box frame currently drawn on BG1?  Top edge at row CV_MAPROW-1. */
static int box_open(void) {
    return (BG1MAP[(CV_MAPROW - 1) * 32 + 8] & 0x3ff) == 0x08 &&
           (BG1MAP[(CV_MAPROW + CV_ROWS - 1) * 32 + 8] & 0x3ff) != 0x00;
}

static int canvas_tile(u32 e) {
    u32 t = e & 0x3ff;
    return t >= CV_TILE0 && t < CV_TILE0 + CV_ROWS * CV_COLS;
}

static void canvas_map(void) {
    if (vs.q_noedge) frame_bottom(1);
    for (int ty = 0; ty < CV_ROWS; ty++)
        for (int tx = 0; tx < CV_COLS; tx++)
            BG1MAP[(CV_MAPROW + ty) * 32 + tx] = CV_TILE0 + ty * CV_COLS + tx;
    SYS_BGDIRTY |= 2;
    text_colours(1);
    arrow_load();
    vs.mapped = 1;
}

/* Put the engine's empty box back where the canvas was mapped. */
static void canvas_unmap(void) {
    for (int ty = 0; ty < CV_ROWS; ty++)
        for (int tx = 0; tx < CV_COLS; tx++)
            BG1MAP[(CV_MAPROW + ty) * 32 + tx] = BOX_TEMPLATE[(CV_MAPROW + ty) * 32 + tx];
    SYS_BGDIRTY |= 2;
    if (vs.mapped) text_colours(0);
    vs.mapped = 0;
}

/* A sample of the canvas tiles (every 16th byte). */
static u32 canvas_sum(void) {
    volatile u32* p = (volatile u32*)(VRAM + CV_TILE0 * 32);
    u32 h = 0;
    for (int i = 0; i < CV_ROWS * CV_COLS * 8; i += 4) h = (h << 1 | h >> 31) ^ p[i];
    return h;
}

/* Does any background with char base 0 show canvas tiles (other than the canvas itself)? */
static int canvas_in_use(void) {
    u32 dispcnt = REG16(0x04000000);
    for (int bg = 0; bg < 3; bg++) {
        if (!(dispcnt & (0x100 << bg)) || (bg == 0 && vx.q_on)) continue;
        u32 cnt = REG16(0x04000008 + 2 * bg);
        if (cnt & 0x0c) continue;                        /* other char base */
        volatile u16* m = (volatile u16*)(VRAM + ((cnt >> 8) & 31) * 0x800);
        for (int i = 0; i < 32 * 20; i++)
            if (canvas_tile(m[i]) && !(bg == 1 && vs.mapped)) return 1;
    }
    return 0;
}

static void blit_to(int gi, int x, int y, u32 c, rowptr_fn rowptr);
static volatile u32* canvas_rowptr(int tx, int ty, int r);

static void canvas_redraw(void) {
    canvas_tiles();
    for (int i = 0; i < vs.glog_n; i++) {
        u32 g = glog[i];
        blit_to(g & 0x1ff, (g >> 9) & 0xff, (g >> 17) & 0x3f, g >> 23, canvas_rowptr);
    }
}

/* Per frame while the canvas is mapped: if its tiles changed behind our back, show the
   engine's empty box instead and draw the page again once nothing else uses the tiles. */
static void canvas_check(void) {
    u32 h = canvas_sum();
    if (!vs.csum_ok) { vs.csum = h; vs.csum_ok = 1; return; }
    if (h == vs.csum) return;
    canvas_unmap();
    vs.lost = 1;
}

/* Measure the rest of the current line (from the script pointer) in pixels. */
static int measure_line(const u16* p) {
    int w = 0;
    for (int n = 0; n < 512; n++) {
        u32 t = *p++;
        if (t >= 0x80) { w += font_w[glyph_index(t)]; continue; }
        if (t == 0x00 || t == 0x01 || t == 0x02 || t == 0x07 || t == 0x08 || t == 0x09 || t == 0x0a ||
            t == 0x0d || t == 0x2c || t == 0x2d || t == 0x2e || t == 0x35 || t == 0x36) break;
        p += cmd_args[t];
    }
    return w;
}

/* ---------------------------------------------------------------- choice labels */
/* A line's tiles are cleared when the page first puts a character on it, not all three when it
   starts: a line the page leaves empty keeps what is in its tiles.  On the screen that shows a
   newly added episode, the box (OBJ tiles 0x398-0x417) runs past the end of OBJ VRAM into tiles
   0-23, line 1's, as in the original, and the prompt under it is on lines 2 and 3. */
static void line_clean(int L) {
    if (!(vx.lbl_dirty & (1 << L))) return;
    vx.lbl_dirty &= ~(1 << L);
    volatile u32 zero = 0;          /* a line's eight cells are one run of 64 tiles */
    dma32(&zero, (volatile u32*)(0x06010000 + lbl_tile(L, 0) * 32), LBL_CELLS * 64, 1);
}

static void labels_reset(void) {
    vx.lbl_dirty = (1 << LBL_LINES) - 1;
    for (int i = 0; i < LBL_LINES; i++) vs.lbl_width[i] = 0;
    vs.lbl_pen = 0; vs.lbl_line = 0;
}

/* The rest of the page from the character being drawn (code at `row`, the script pointer just
   after it): the number of rows, and the width of each line (for centring before it is typed).
   A line the DS lays out with leading spaces (" ... THE END" under an episode's title at its end,
   right-aligned in the DS's narrower spaces) can come out wider than the screen in this font:
   as much of that leading space as it takes is dropped (lbl_trim), so it ends LBL_FIT px from
   its start, before the right edge as far as the text starts from the left. */
#define LBL_FIT 222
/* A choice's options start at x 24, after the engine's cursor, and the full-screen box's right
   border is at x 238: an option wider than OPT_FIT ran off the box (the DS's screen is wider).
   Like a page line that does not fit (box_glyph), its letters close up a pixel, two if one is not
   enough; every option of the menu takes the same spacing, so that they still look alike. */
#define OPT_FIT (236 - LBL_X0)
static void line_done(int L, int w, int lead, int n) {
    if (L < 0 || L >= LBL_LINES) return;
    int trim = 0;
    if (w > LBL_FIT) { trim = w - LBL_FIT; if (trim > lead) trim = lead; }
    w -= trim;
    vs.lbl_full[L] = w > 255 ? 255 : w;
    vx.lbl_trim[L] = trim > 255 ? 255 : trim;
    if (!vs.lbl_caption && n > 1) {
        int sq = 0;
        while (w - sq * (n - 1) > OPT_FIT && sq < 2) sq++;
        if (sq > vx.lbl_sq) vx.lbl_sq = sq;
    }
}

static int page_scan(const u16* p, u32 code, int row) {
    int L = row - vs.lbl_row0;
    int w = font_w[glyph_index(code)], g = 1;
    int lead = code == 0x17f ? w : 0, inlead = code == 0x17f;
    for (int n = 0; n < 1024; n++) {
        u32 t = *p++;
        if (t >= 0x80) {
            int gw = font_w[glyph_index(t)];
            w += gw; g++;
            if (inlead && t == 0x17f) lead += gw; else inlead = 0;
            continue;
        }
        if (t == 0x01) {
            line_done(L, w, lead, g);
            row++; L++; w = 0; g = 0; lead = 0; inlead = 1; continue;
        }
        if (t == 0x00 || t == 0x02 || t == 0x07 || t == 0x08 || t == 0x09 || t == 0x0a || t == 0x0d ||
            t == 0x2c || t == 0x2d || t == 0x2e || t == 0x35 || t == 0x36 || t == 0x42) break;
        p += cmd_args[t];
    }
    line_done(L, w, lead, g);
    return row + 1;
}

/* Sprite text (choice labels / text outside the box).  The engine hands us (col, row) cell
   positions; col 0 marks the start of a line.  Captions are re-dispatched every frame from
   the first character, so the surface is only cleared when the text state is reset. */
static void label_draw_char(u32 code, int col, int row) {
    if (vs.lbl_row0 < 0) {
        labels_reset();
        vs.lbl_caption = (SYS_CAPTION & 4) ? 1 : 0;
        vs.lbl_row0 = vs.lbl_caption ? 0 : row;
        /* a choice's options go on the rows the engine's cursor is placed on: its row counter
           (the question's lines) plus the blank row it adds, 18 px a row from y 18 */
        vs.lbl_base = TXT_ROW + 1;
        /* where the engine's sprite writer (0x0801fd6c) puts this text: see labels_oam */
        u32 sec = TXT_SECTION;
        vs.lbl_sys = (sec <= 1 || sec == 3 || sec == 4 || (sec >= 6 && sec <= 31));
        vs.lbl_align = TXT_ALIGN & 0xf;
        vs.lbl_free = (TXT_FLAGS & 4) ? 1 : 0;
        vs.lbl_fx = TXT_OFSX; vs.lbl_fy = TXT_OFSY;
        for (int i = 0; i < LBL_LINES; i++) { vs.lbl_full[i] = 0; vx.lbl_trim[i] = 0; }
        vx.lbl_sq = 0;
        vs.lbl_rows = page_scan((const u16*)TXT_PTR, code, row);
        /* alignment-2 lines sit at y 71 while TXT+0x1a is 0, which it is until the engine
           reaches the first new line: a one-line caption stays there, a longer one moves up
           to y 62 once its second line starts; the English text goes there from the start */
        vs.lbl_low = vs.lbl_rows - vs.lbl_row0 <= 1;
    }
    int L = row - vs.lbl_row0;
    if (L < 0 || L >= LBL_LINES) return;
    line_clean(L);
    if (col == 0 || L != vs.lbl_line) { vs.lbl_line = L; vs.lbl_pen = -vx.lbl_trim[L]; }
    int gi = glyph_index(code);
    u32 c = text_colors[TXT_COLOR & 0xf];
    if (vs.lbl_pen >= 0 && vs.lbl_pen + 16 <= LBL_CELLS * LBL_CELLW && code != 0x17f) blit_to(gi, vs.lbl_pen, L * 16, lbl_colour(c), label_rowptr);
    vs.lbl_pen += font_w[gi] - (vs.lbl_caption ? 0 : vx.lbl_sq);
    if (vs.lbl_pen > 255) vs.lbl_pen = 255;
    if (vs.lbl_pen > vs.lbl_width[L]) vs.lbl_width[L] = vs.lbl_pen;
}

static void labels_hide(void) {
    if (!vs.lbl_shown) return;
    for (int L = 0; L < LBL_LINES; L++) {
        for (int c = 0; c < vs.lbl_used[L]; c++) OAMBUF[(lbl_obj0[L] + c) * 4 + 0] = 0x0200;   /* disabled */
        vs.lbl_used[L] = 0;
    }
    vs.lbl_shown = 0;
}

/* The Court Record's picture (OAM 34, 64x64) goes to OBJ tile 0x280, or, with a large character
   on screen whose sprites start below 0x2c0 (0x08014dca: Armando's from 0x284), to 0x80
   (0x08014ddc, 0x08014e9a): in the original the spare tiles of the item shown in court, here the
   third line's.  While it is there the third line moves to 64 tiles in 0x100-0x17f that no sprite
   on screen uses (the defence bench's and the investigation tabs' tiles, whose pictures are kept
   at L3_BACKUP and put back when the Record closes), the page is drawn again into them, and when
   the Record has closed it is drawn again in its own tiles (vwf_resume).  With no such tiles the
   third line is not shown meanwhile. */
#define L3_BACKUP ((volatile u32*)0x0202a000)   /* 2 KB: free (the English build's chapter banks stay in ROM) */
#define L3_FROM   0x100
#define L3_TO     0x180
static int record_borrows(void) {
    if (SYS[8] != MODE_RECORD) return 0;
    /* the loader's own test (the first animation's state), true from the frame the picture is copied */
    if ((*(volatile u32*)0x03000850 & 0xffffff) == 0x800ff && (*(volatile u32*)0x03000844 & 0x10000000)) return 1;
    u32 a0 = OAMBUF[34 * 4], t = OAMBUF[34 * 4 + 2] & 0x3ff;
    return (a0 & 0x300) != 0x200 && t >= 0x80 && t < 0xc0;
}

static int obj_tiles(u32 a0, u32 a1) {
    static const u8 n[3][4] = {{1, 4, 16, 64}, {2, 4, 8, 32}, {2, 4, 8, 32}};
    u32 shape = a0 >> 14;
    if (shape > 2) return 0;
    return n[shape][a1 >> 14] << ((a0 >> 13) & 1);
}

/* 64 tiles from L3_FROM up that no sprite shown (other than the page's own) uses, or 0. */
static u32 l3_block(void) {
    for (u32 base = L3_FROM; base + 64 <= L3_TO; base += 8) {
        int ok = 1;
        for (int k = 0; k < 128 && ok; k++) {
            if (k == ARROW_OBJ || (k >= 3 && k < 27)) continue;
            u32 a0 = OAMBUF[k * 4], a1 = OAMBUF[k * 4 + 1], t = OAMBUF[k * 4 + 2] & 0x3ff;
            if ((a0 & 0x300) == 0x200) continue;
            u32 n = obj_tiles(a0, a1);
            if (t < base + 64 && t + n > base) ok = 0;
        }
        if (ok) return base;
    }
    return 0;
}

void vwf_resume(void);

static void l3_give_back(void) {
    if (vx.l3_tile < L3_FROM || vx.l3_tile + 64 > L3_TO) { vx.l3_tile = 0; return; }
    volatile u32* v = (volatile u32*)(0x06010000 + vx.l3_tile * 32);
    dma32(L3_BACKUP, v, 64 * 8, 0);
    vx.l3_tile = 0;
}

static void record_lend(void) {
    if (record_borrows()) {
        if (vs.l3_lent || !vs.lbl_width[2]) return;
        vs.l3_lent = 1;
        u32 base = l3_block();
        if (!base) return;                           /* the third line waits, hidden */
        volatile u32* v = (volatile u32*)(0x06010000 + base * 32);
        dma32(v, L3_BACKUP, 64 * 8, 0);
        vx.l3_tile = base;
        vwf_resume();                                /* the page again, its third line there */
        return;
    }
    if (!vs.l3_lent || SYS[8] == MODE_RECORD) return;
    vs.l3_lent = 0;
    l3_give_back();
    vwf_resume();
}

static void labels_oam(void) {
    /* the engine's sprite-text writer shows nothing while SYS+0x19 is 0 (the episode select
       clears it as soon as an episode is picked, with its prompt still on the page) */
    if (!SYS[0x19] && !fullscreen_box()) { labels_hide(); return; }
    vs.lbl_shown = 1;
    for (int L = 0; L < LBL_LINES; L++) {
        int w = vs.lbl_width[L];
        int ncells = (w + LBL_CELLW - 1) / LBL_CELLW;
        /* a choice's options: the rows the engine's cursor is placed on, 18 px apart from
           y 18, after the question's lines and a blank row (lbl_row0 is the first option's) */
        int x = LBL_X0, y = 18 + 18 * (vs.lbl_base + L);
        if (vs.mode == 2) {
            /* the page in the box: the cells cover its text rows from the left edge */
            x = 0; y = TEXT_Y0 + L * LINE_H;
        } else if (vs.lbl_caption) {
            /* As the engine: the box rows (y 116 + 18 * row; with a third English line, the
               three-line box's 112 + 16 * row), 64 px higher for some common-bank sections;
               otherwise centred text is centred, and alignment 2 (captions) is drawn at
               y 62 + 18 * row (y 71 when TXT+0x1a is 0). */
            int fw = vs.lbl_full[L] > w ? vs.lbl_full[L] : w;
            x = 9;
            y = (vs.lbl_rows > 2) ? TEXT_Y0 + L * 16 : 116 + L * 18;
            if (vs.lbl_free) {
                /* free-slot mode (the staff roll): the records hold 14 + 14 * column + x offset,
                   36 + 18 * row + y offset, and the writer adds 9 to x */
                x = 23 + vs.lbl_fx;
                y = 36 + L * 18 + vs.lbl_fy;
                if (vs.lbl_sys) y -= 64;
            } else if (vs.lbl_sys) {
                /* the engine does not centre these (the Japanese pads them with spaces); the
                   English lines are centred, as on the DS, and a little lower and closer
                   together, clear of the DS header above them (patches/ui.py) */
                y = SYS_Y0 + L * LINE_H;
                x = (240 - fw) / 2;
            } else if (vs.lbl_align) {
                x = (240 - fw) / 2;
                if (vs.lbl_align == 2) y = (vs.lbl_low ? 71 : CAP_Y0) + L * CAP_PITCH;
            }
            if (x < 0) x = 0;
        }
        if (L == 2 && vs.l3_lent && !vx.l3_tile) ncells = 0;
        for (int c = 0; c < LBL_CELLS; c++) {
            int obj = lbl_obj0[L] + c;
            if (c >= ncells) { if (c < vs.lbl_used[L]) OAMBUF[obj * 4 + 0] = 0x0200; continue; }
            OAMBUF[obj * 4 + 0] = y | (1 << 14);                         /* wide: 32x16 */
            OAMBUF[obj * 4 + 1] = ((x + c * LBL_CELLW) & 0x1ff) | (2 << 14);
            /* priority 1 like the engine's own sprite text: under the Court Record's panel
               (BG2, priority 0), as a choice's options are in the original */
            OAMBUF[obj * 4 + 2] = lbl_tile(L, c) | (1 << 10) | (0 << 12);
        }
        vs.lbl_used[L] = ncells;
    }
}

/* question canvas lives at rows Q_MAPROW..+5; any canvas tiles copied elsewhere by the
   box-grow animation become plain interior. */
static void choice_frame(void) {
    int dirty = 0;
    if (!vs.q_noedge) frame_bottom(0);
    /* rows are written and copied whole: two columns tell a row that is already right (the full
       scan of every cell every frame was a good part of the vertical blank) */
    for (int row = 0; row < 20; row++) {
        volatile u16* m = BG1MAP + row * 32;
        int qrow = row - Q_MAPROW;
        if (qrow >= 0 && qrow < CV_ROWS) {
            u32 t0 = CV_TILE0 + qrow * CV_COLS;
            if (m[1] == t0 + 1 && m[CV_COLS - 2] == t0 + CV_COLS - 2 && m[0] == t0 && m[CV_COLS - 1] == t0 + CV_COLS - 1) continue;
            for (int tx = 0; tx < CV_COLS; tx++) m[tx] = t0 + tx;
            dirty = 1;
        } else if (canvas_tile(m[1]) || canvas_tile(m[CV_COLS - 2])) {
            for (int tx = 0; tx < CV_COLS; tx++) if (canvas_tile(m[tx])) m[tx] = 0x01;
            dirty = 1;
        }
    }
    if (dirty) SYS_BGDIRTY |= 2;
    labels_oam();
}

/* The engine's choice cursor, a 16x16 hand at OBJ tiles 0xfc-0xff, is OAM 57, after the defence
   bench (48-51, priority 3, from y 128).  The hardware draws an earlier, lower-priority sprite that
   overlaps a later, higher-priority one with the latter's priority: where the cursor (priority 1)
   met the bench, a square of the bench came up over the box.  A three-line question puts the
   options a row lower than the Japanese two-line ones, so the third option's cursor (y 126) does
   meet it.  The engine writes the cursor every frame; it is shown from OAM 33 instead (free while
   the full-screen box is up: the page's sprite text is 3-26), ahead of the bench. */
#define CURSOR_OBJ   57
#define CURSOR_TILE  0xfc
#define CURSOR_AHEAD 33
static void cursor_ahead(int on) {
    volatile u16* c = OAMBUF + CURSOR_OBJ * 4;
    volatile u16* d = OAMBUF + CURSOR_AHEAD * 4;
    if (on && (c[2] & 0x3ff) == CURSOR_TILE) {
        d[0] = c[0]; d[1] = c[1]; d[2] = c[2];
        c[0] = 0x0200;
        vx.cur_ahead = 1;
    } else if (vx.cur_ahead) {
        d[0] = 0x0200;
        vx.cur_ahead = 0;
    }
}

/* Before a choice the box grows (and after it shrinks) a few rows a frame, the engine copying map
   rows upward (or downward): rows with the canvas in them would show copies of the text in every
   row.  A copied canvas row keeps each tile in its column. */
static int canvas_row_at(int row) {
    u32 a = BG1MAP[row * 32 + 1] & 0x3ff, b = BG1MAP[row * 32 + CV_COLS - 2] & 0x3ff;
    if (!canvas_tile(a) || !canvas_tile(b)) return -1;
    a -= CV_TILE0; b -= CV_TILE0;
    if (a % CV_COLS != 1 || b % CV_COLS != CV_COLS - 2 || a / CV_COLS != b / CV_COLS) return -1;
    return a / CV_COLS;
}

/* While the box moves: the engine's own tiles wherever canvas rows are, as the original hides
   the text then (the canvas keeps the page; it is shown again at the top for a choice, or where
   it was if the box comes back).  1 if the box is moving. */
static int box_moving(void) {
    int moving = 0;
    for (int row = 0; row < CV_MAPROW; row++)
        if (canvas_row_at(row) >= 0) { moving = 1; break; }
    if (!moving) return 0;
    for (int row = 0; row < 20; row++) {
        int ty = canvas_row_at(row);
        if (ty < 0) continue;
        for (int tx = 0; tx < CV_COLS; tx++) {
            u32 e = BG1MAP[row * 32 + tx] & 0x3ff;
            if (canvas_tile(e) && (e - CV_TILE0) % CV_COLS == (u32)tx)
                BG1MAP[row * 32 + tx] = BOX_TEMPLATE[(CV_MAPROW + (e - CV_TILE0) / CV_COLS) * 32 + tx];
        }
    }
    SYS_BGDIRTY |= 2;
    return 1;
}

/* ---------------------------------------------------------------- hooks */

static void canvas_glyph(u32 code, u32 col, int blit);

static int page_has_choice(const u16* p);
static void box_glyph(u32 code, u32 col);

/* The common bank's system messages (the save and continue screens' prompts, the chapter
   names): the engine places their sprite text 64 pixels up, for the box of those screens.
   Dispatched with no such screen up (the load screen's chapter name, when a suspended game is
   continued from its save point, was drawn over the first statement of Dahlia's testimony),
   they must not land on the page in the box. */
static int sys_text(void) {
    u32 sec = TXT_SECTION;
    return sec <= 1 || sec == 3 || sec == 4 || (sec >= 6 && sec <= 31);
}

/* Replaces the engine's cell draw: r0 = code-0x80, r1 = col, r2 = row. */
void vwf_draw_char(u32 code80, u32 col, u32 row) {
    u32 code = code80 + 0x80;
    if ((vs.lbl_row0 >= 0 && vs.lbl_caption) || (SYS_CAPTION & 4) || fullscreen_box()) {
        label_draw_char(code, col, row); return;
    }
    if (sys_text()) return;
    /* the engine's own cell counters start a page over at (0, 0): a page started again with no
       clear in between (its text in the original's records is replaced too) starts ours over */
    if (col == 0 && row == 0 && (vs.pen_x || vs.line)) {
        vs.pen_x = 0; vs.line = 0; vs.squeeze = 0; vs.inset = 0; vs.mode = 0;
        canvas_reset();
    }
    if (!vs.mode) {
        vs.mode = page_has_choice((const u16*)TXT_PTR) ? 1 : 2;
        if (vs.mode == 2) labels_reset();
    }
    if (vs.mode == 2) { box_glyph(code, col); return; }
    if (!vs.mapped) {
        if (vs.lost) { canvas_redraw(); vs.lost = 0; }
        else canvas_reset();
        canvas_map();
    }
    else if ((BG1MAP[CV_MAPROW * 32 + 1] & 0x3ff) != CV_TILE0 + 1) canvas_map();
    canvas_glyph(code, col, 1);
}

/* Does the page lead to a choice (command 0x07) before it ends?  Its question is drawn on the
   canvas, which can move to the top of the full-screen box. */
static int page_has_choice(const u16* p) {
    for (int n = 0; n < 1024; n++) {
        u32 t = *p++;
        if (t >= 0x80) continue;
        if (t == 0x07) return 1;
        if (t == 0x00 || t == 0x02 || t == 0x08 || t == 0x09 || t == 0x0a || t == 0x0d ||
            t == 0x2c || t == 0x2d || t == 0x2e || t == 0x35 || t == 0x36) return 0;
        p += cmd_args[t];
    }
    return 0;
}

/* Does the page end in command 0x15 (the text stays up while the game waits: a cross-examination
   statement) rather than in a page end? */
static int page_is_statement(const u16* p) {
    for (int n = 0; n < 1024; n++) {
        u32 t = *p++;
        if (t >= 0x80) continue;
        if (t == 0x15) return 1;
        if (t == 0x00 || t == 0x02 || t == 0x07 || t == 0x08 || t == 0x09 || t == 0x0a || t == 0x0d ||
            t == 0x2c || t == 0x2d || t == 0x2e || t == 0x35 || t == 0x36) return 0;
        p += cmd_args[t];
    }
    return 0;
}

/* One character onto the canvas at the pen (the script pointer is just after it); with `blit`
   0 only into the glyph log. */
static void canvas_glyph(u32 code, u32 col, int blit) {
    int gi = glyph_index(code);
    if (vs.pen_x == 0) {
        if (vs.line == 0) vs.inset = page_is_statement((const u16*)TXT_PTR);
        /* start of a line: decide on squeeze */
        int w = font_w[gi] + measure_line((const u16*)TXT_PTR);
        int maxw = vs.inset ? STMT_MAXW : TEXT_MAXW;
        vs.squeeze = 0;
        if (w > maxw) vs.squeeze = 1;
        if (w - 24 > maxw) vs.squeeze = 2;
        /* command 0x5d 1 (the date and place cards, the testimony titles): the line centred, as
           the DS centres it (0x02023840) */
        vs.line_x0 = (TXT_ALIGN & 1) && w < maxw ? (BOX_W - w) / 2 - (vs.inset ? STMT_X0 : TEXT_X0) : 0;
    }
    int L = vs.line;
    if (L >= MAX_LINES) L = MAX_LINES - 1;
    int x = (vs.inset ? STMT_X0 : TEXT_X0) + vs.line_x0 + vs.pen_x;
    if (x > 240 - 4) return;
    u32 c = text_colors[TXT_COLOR & 0xf];
    int draw = code != 0x17f;
    if (TXT_ALIGN & 0x20) {
        /* command 0x5d 5: the line trails off (Ron's mumbling).  The engine greys the text out by
           column and leaves out everything from a last column on; these are the DS English
           version's columns, in characters, and the nearest greys of the UI palette (no choice's
           question trails off: the page's own lines are sprite text, box_glyph) */
        static const u8 fade_end[5] = {8, 16, 22, 28, 32};
        static const u8 fade_col[5] = {0, 4, 3, 3, 2};
        int k = 0;
        while (k < 5 && col >= fade_end[k]) k++;
        if (k == 5) draw = 0;
        else if (k) c = fade_col[k];
    }
    if (draw) {
        if (blit) blit_to(gi, x, L * LINE_H, c, canvas_rowptr);
        if (vs.glog_n < GLOG_MAX) glog[vs.glog_n++] = gi | x << 9 | (L * LINE_H) << 17 | c << 23;
        vs.csum_ok = 0;
    }
    int adv = font_w[gi] - vs.squeeze;
    if (adv < 1) adv = 1;
    vs.pen_x += adv;
}

/* The same character as sprite text in the box (the page is not a choice's question): the
   engine's sprite-text palette, white 3 and the colours at 6, 9 and 12, greys 13, 2, 14 and 1
   for a line trailing off (the DS's text palette is the same, entry for entry). */
static void box_glyph(u32 code, u32 col) {
    int gi = glyph_index(code);
    if (vs.pen_x == 0) {
        if (vs.line == 0) vs.inset = page_is_statement((const u16*)TXT_PTR);
        int w = font_w[gi] + measure_line((const u16*)TXT_PTR);
        int maxw = vs.inset ? STMT_MAXW : TEXT_MAXW;
        vs.squeeze = 0;
        if (w > maxw) vs.squeeze = 1;
        if (w - 24 > maxw) vs.squeeze = 2;
        vs.line_x0 = (TXT_ALIGN & 1) && w < maxw ? (BOX_W - w) / 2 - (vs.inset ? STMT_X0 : TEXT_X0) : 0;
    }
    int L = vs.line;
    if (L >= MAX_LINES) L = MAX_LINES - 1;
    line_clean(L);
    int x = (vs.inset ? STMT_X0 : TEXT_X0) + vs.line_x0 + vs.pen_x;
    if (x > 240 - 4) return;
    u32 c = lbl_colour(text_colors[TXT_COLOR & 0xf]);
    int draw = code != 0x17f;
    if (TXT_ALIGN & 0x20) {
        /* command 0x5d 5: the DS English version's columns (characters) and its greys, the same
           entries of the same palette (its glyph draw, 0x020239bc, recolours a character with
           the table at 0x020a1cc8: 13, 2, 14, 1 from the first step on); before 0.16.45 this
           took 2, 14, 14, 1, the second step darker than the DS's and the same as the third */
        static const u8 fade_end[5] = {8, 16, 22, 28, 32};
        static const u8 fade_col[5] = {0, 13, 2, 14, 1};
        int k = 0;
        while (k < 5 && col >= fade_end[k]) k++;
        if (k == 5) draw = 0;
        else if (k) c = fade_col[k];
    }
    if (draw) {
        blit_to(gi, x, L * LINE_H, c, label_rowptr);
        int right = x + font_w[gi];
        if (right > 255) right = 255;
        if (right > vs.lbl_width[L]) vs.lbl_width[L] = right;
    }
    int adv = font_w[gi] - vs.squeeze;
    if (adv < 1) adv = 1;
    vs.pen_x += adv;
}

/* ---------------------------------------------------------------- pace and text blips */
/* The DS's English text runs faster than its Japanese: the speed of command 0x0b (frames a
   character) goes through a table first (0x020ac050), and the speaker's blip comes on every
   other letter, every third at the fastest speeds, never on a space (0x0202370c).  The engine
   (0x0801f7f8) waits the speed itself and blips every other letter, on the first two rows of
   its two-line box only; these replace its reload of the wait and its blip. */
#define PLAY_SE(n)   ((void (*)(u32))0x08015bc9)(n)
#define TXT_SPEED    (TXT[0x26])
#define TXT_BLIPS    (*(volatile u16*)0x03007216)   /* 0: the typewriter (command 0x30 2) */
#define TXT_SPEAKER  (TXT[0x24])
#define SPEAKER_BLIP ((const u8*)0x08049af2)        /* per speaker: 0 the low blip, 1 the high */
#define SE_TYPE      0x44
#define SE_HIGH      0x2e
#define SE_LOW       0x2d
static const u8 en_pace[16] = { 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8 };

/* frames to the next character (0x0801f960) */
u32 text_pace(u32 speed) { return speed < 16 ? en_pace[speed] : speed; }

/* after a character other than a space, the text not instant (0x0801f9b0): `n` is the number of
   blips played this frame, returned with this one's */
u32 text_blip(u32 n) {
    u32 pace = text_pace(TXT_SPEED), mode = TXT_BLIPS;
    if (vs.blip_n > 2 || (!mode && vs.blip_mode)) vs.blip_n = 0;   /* (the typewriter starts with a blip) */
    vs.blip_mode = mode != 0;
    if (vs.blip_n && !(pace >= 2 && vs.blip_n <= 1)) { vs.blip_n--; return n; }
    vs.blip_n = 2;
    /* as the engine: none in the system messages, in caption mode or twice in a frame */
    if (TXT_SECTION <= 0x1c || n || (SYS_CAPTION & 4)) return n;
    if (!mode) PLAY_SE(SE_TYPE);
    else if (SPEAKER_BLIP[TXT_SPEAKER] == 1) PLAY_SE(SE_HIGH);
    else if (SPEAKER_BLIP[TXT_SPEAKER] == 0) PLAY_SE(SE_LOW);
    return n + 1;
}

void vwf_newline(void) {
    if (sys_text() && !(SYS_CAPTION & 4) && !fullscreen_box()) return;   /* see vwf_draw_char */
    vs.pen_x = 0;
    if (vs.line < 255) vs.line++;
}

void vwf_clear(void) {
    vs.overlay = 0;
    vs.pen_x = 0;
    vs.line = 0;
    vs.squeeze = 0;
    vs.lbl_row0 = -1;
    for (int i = 0; i < LBL_LINES; i++) vs.lbl_width[i] = 0;
    canvas_reset();
    vs.lost = 0;
    vs.resume = 0;
    vs.inset = 0;
    vs.mode = 0;
    l3_give_back();
    vs.l3_lent = 0;
}

/* ---------------------------------------------------------------- continuing a saved game */
/* The save keeps the engine's sprite records, which hold the original's text, and the game
   draws them again when a save is continued; the English text is on the canvas (and the choice
   labels in OBJ VRAM), which the save does not keep.  When the game stopped on a page waiting
   for the button or on a choice, vwf_resume finds that page in the script (from the last page
   end before the script pointer) and resume_frame draws it again once the box is up. */

/* Command 0x5d on the layout byte (TXT+0x22). */
static u32 align_cmd(u32 a, u32 v) {
    switch (v) {
    case 0: return a & 0xf0;
    case 1: case 2: return (a & 0xf0) | v;
    case 3: return a | 0x10;
    case 4: return a & 0x0f;
    case 5: return a | 0x20;
    }
    return a;
}

static int page_end(u32 t) { return t == 0x02 || t == 0x2d || t == 0x2e; }

/* A line's trailing off (command 0x5d 5, bit 0x20 of TXT+0x22) is the engine's for that line
   alone: the new line (0x0802172c), the page ends (0x080217d8 for 0x02 / 0x07 / 0x0a / 0x2d,
   0x0802258c for 0x2e) and a jump (0x2c) clear it. */
static int ends_trail(u32 t) {
    return t == 0x01 || t == 0x02 || t == 0x07 || t == 0x0a || t == 0x2c || t == 0x2d || t == 0x2e;
}

/* Called when a saved game is continued, after script_resume has put the script pointer back. */
void vwf_resume(void) {
    vs.resume = 0;
    const u16* cur = (const u16*)TXT_PTR;
    u32 t = *cur;
    /* the engine stopped on a command: a page end, a choice, a statement (0x15), the Court
       Record opened to present (0x21), the wait before a choice's question ({0c 1}), ... */
    if (t >= 0x80) return;
    const u16* p = (const u16*)TXT_START;
    const u16* page = p;
    u32 c = 0, a = 0, pc = 0, pa = 0, caption = 0;
    while (p < cur) {
        u32 w = *p++;
        if (w >= 0x80) continue;
        if (w == 0x03) c = *p & 0xf;
        else if (w == 0x5d) a = align_cmd(a, *p);
        else if (w == 0x42) caption = *p == 0;
        else if (ends_trail(w)) a &= ~0x20;
        p += cmd_args[w];
        if (page_end(w)) { page = p; pc = c; pa = a; }
    }
    /* a caption (command 0x42) is dispatched again every frame by the engine itself */
    if (p != cur || caption) return;
    vs.resume_page = (u32)page; vs.resume_cur = (u32)cur;
    vs.resume_colour = pc; vs.resume_align = pa;
    vs.resume = 1;
}

/* Lay the page out again as the engine typed it: the text into the glyph log (drawn on the canvas
   as a lost page is, once no other background uses the canvas tiles: the Court Record may be
   open), and for a choice the question on the canvas and the options as labels. */
static void resume_replay(int choice) {
    const u16* p = (const u16*)vs.resume_page;
    const u16* cur = (const u16*)vs.resume_cur;
    u32 ptr = TXT_PTR;
    u8 colour = TXT_COLOR, align = TXT_ALIGN;
    vs.pen_x = 0; vs.line = 0; vs.squeeze = 0; vs.inset = 0;
    vs.lbl_row0 = -1; vs.mode = 0;
    for (int i = 0; i < LBL_LINES; i++) vs.lbl_width[i] = 0;
    vs.glog_n = 0; vs.lost = 0;
    if (choice) canvas_tiles();
    else labels_reset();    /* the save screen's prompt was sprite text in the same tiles */
    TXT_COLOR = (colour & 0xf0) | vs.resume_colour;
    TXT_ALIGN = vs.resume_align;
    int labels = 0, caption = 0, col = 0, row = 0, qrows = 1;
    while (p < cur) {
        u32 t = *p++;
        if (t >= 0x80) {
            if (caption) continue;
            TXT_PTR = (u32)p;
            if (labels) label_draw_char(t, col, row);
            else if (choice) canvas_glyph(t, col, 1);
            else box_glyph(t, col);
            col++;
            continue;
        }
        if (ends_trail(t)) TXT_ALIGN &= ~0x20;
        if (t == 0x01) { if (caption) {} else if (labels) row++; else { vwf_newline(); qrows++; } col = 0; }
        else if (t == 0x03) TXT_COLOR = (TXT_COLOR & 0xf0) | (*p & 0xf);
        else if (t == 0x5d) TXT_ALIGN = align_cmd(TXT_ALIGN, *p);
        else if (t == 0x42) caption = *p == 0;
        else if (t == 0x07) { labels = choice; col = 0; row = 0; }
        p += cmd_args[t];
    }
    TXT_PTR = ptr; TXT_COLOR = colour; TXT_ALIGN = align;
    if (choice) {
        vs.mode = 1; vs.mapped = 1;     /* choice_frame shows the question at the top */
        /* the options sit under the question and a blank row, where the engine's cursor is: its
           row counter, which label_draw_char read, has moved on to the last option by now */
        vs.lbl_base = qrows + 1;
        text_colours(1);                /* the question's colours: set while the page is typed */
    }
    else vs.mode = 2;
}

/* A save carries the box's map rows, and one made by a build with the 56-pixel box (before
   0.16.8) puts the box back a row lower than this build's (top edge at row 13, name tag at
   11-12): box_open never saw it, and the page was never drawn again.  Move it up. */
static void box_rows_fix(void) {
    if ((BG1MAP[13 * 32 + 8] & 0x3ff) != 0x08 || (BG1MAP[12 * 32 + 8] & 0x3ff) == 0x08) return;
    for (int r = 10; r < 12; r++)
        for (int tx = 0; tx < 32; tx++) BG1MAP[r * 32 + tx] = BG1MAP[(r + 1) * 32 + tx];
    for (int r = 12; r < 20; r++)
        for (int tx = 0; tx < 32; tx++) BG1MAP[r * 32 + tx] = BOX_TEMPLATE[r * 32 + tx];
    SYS_BGDIRTY |= 2;
}

static void resume_frame(void) {
    u32 p = TXT_PTR;
    if ((p != vs.resume_cur && p != vs.resume_cur + 2) || (SYS_CAPTION & 4)) { vs.resume = 0; return; }
    int full = fullscreen_box();
    if (!full) box_rows_fix();
    if (!full && !box_open()) return;
    vs.resume = 0;
    /* A page that leads to a choice goes on the canvas, as when it is typed (vwf_draw_char): the
       box has grown for the options if the save was made at them, but not if it was made while
       the question waited at its 0x07 for the A Button, or before the question was finished.
       Before 0.16.47 that question came back as sprite text in the box, which the options then
       took the place of: the question was gone and the box with it. */
    resume_replay(full || page_has_choice((const u16*)vs.resume_page));
}

/* Per frame (before the BG map / OAM DMA). */
/* The item box's frame (BG1 tiles 0x30-0x38) left on rows 0-9 with no item box open: before
   0.16.17 the end of the box's closing animation left its top corners on row 0, and a save made
   then carries them (the save keeps the map's rows).  Only the item box puts those tiles there,
   in the game's modes with a box (dialogue 3, investigation 4, cross-examination 6, the Court
   Record 7).  Clear them. */
/* The episode select's box is the original's short one (the box routine's mode 2, 0x080055f0:
   top edge on row 16, two interior rows, bottom on 19; patches/text.py) for its one-line prompts.
   An English prompt of two lines (a newly added episode) is set on the three-line box's second
   and third rows (y 118, 134, labels_oam): the box grows two rows for it, top edge on row 14, and
   goes back for a one-line page.  A box left by 0.16.22-0.16.23 (top edge on row 15, row 16
   empty) is put right too. */
#define MODE_NEW_EPISODE 0x0b
#define MODE_SELECT      0x0c
static void select_box(int tall) {
    if (SYS[8] != MODE_NEW_EPISODE && SYS[8] != MODE_SELECT) return;
    volatile u16* m = BG1MAP;
    if ((m[13 * 32 + 8] & 0x3ff) || (m[17 * 32] & 0x3ff) != 0x06 || (m[18 * 32] & 0x3ff) != 0x06 ||
        (m[19 * 32] & 0x3ff) != 0x04) return;
    int at = 0;
    for (int r = 14; r <= 16; r++) if ((m[r * 32 + 8] & 0x3ff) == 0x08) { at = r; break; }
    int edge = tall ? 14 : 16;
    if (!at || (at == edge && (m[16 * 32] & 0x3ff) == (tall ? 0x06 : 0x02))) return;
    for (int r = 14; r <= 16; r++)
        for (int tx = 0; tx < 32; tx++)
            m[r * 32 + tx] = r < edge ? 0 : BOX_TEMPLATE[(r == edge ? 12 : 13) * 32 + tx];
    SYS_BGDIRTY |= 2;
}

static void box_leftovers(void) {
    u32 m = SYS[8];
    if (SYS[0x99] != 0 || (m != 3 && m != 4 && m != 6 && m != MODE_RECORD)) return;
    /* two rows a frame, two cells a read: the whole ten rows cell by cell took eight scanlines of
       the vertical blank, every frame, and pushed the game's own updates past it on busy frames.
       A leftover is a safety net for saves made before 0.16.17; it goes within five frames. */
    u32 r = vx.lo_rows < 5 ? vx.lo_rows : 0;
    vx.lo_rows = r == 4 ? 0 : r + 1;
    volatile u32* w = (volatile u32*)BG1MAP;
    int dirty = 0;
    for (int i = r * 32; i < r * 32 + 32; i++) {
        u32 v = w[i];
        if ((v & 0x3ff) - 0x30 <= 8 || (v >> 16 & 0x3ff) - 0x30 <= 8) {
            volatile u16* h = BG1MAP + 2 * i;
            if ((h[0] & 0x3ff) - 0x30 <= 8) h[0] = 0;
            if ((h[1] & 0x3ff) - 0x30 <= 8) h[1] = 0;
            dirty = 1;
        }
    }
    if (dirty) SYS_BGDIRTY |= 2;
}

static void q_frame(void);
static void frame_body(void);
static void cursor_ahead(int on);
void vwf_frame(void) {
    frame_body();
    cursor_ahead(fullscreen_box() && !vs.overlay);
    q_frame();
}

static void frame_body(void) {
    box_leftovers();
    if (vs.lbl_shown && vs.lbl_caption) select_box(vs.lbl_rows > 2);
    if (vs.overlay) { labels_hide(); return; }
    record_lend();
    if (vs.resume) resume_frame();
    if (vs.lbl_row0 >= 0 && vs.lbl_caption) { labels_oam(); return; }
    if (fullscreen_box()) {
        if (vs.mapped) choice_frame();
        return;
    }
    /* the question canvas's colours, kept in BG palette 0 against the scene's palette loads */
    if (vs.mapped) text_colours(1);
    /* the page in the box is sprite text: shown while the box is (under the Court Record's
       panel too, as the original keeps it), gone with it */
    if (vs.mode == 2 && box_open()) labels_oam();
    else labels_hide();
    vs.lbl_row0 = -1;
    if (vs.mapped && box_moving()) return;
    if (vs.lost) {
        /* the box is still there (its top edge) and nothing shows the canvas tiles any more */
        if ((BG1MAP[(CV_MAPROW - 1) * 32 + 8] & 0x3ff) == 0x08 && !canvas_in_use()) {
            canvas_redraw(); canvas_map(); vs.lost = 0;
        }
        return;
    }
    if (!box_open()) {
        vs.arrow_on = 0;
        /* The engine writes its arrow cells (row 19, columns 14-15: tile 0x24/0x25 = arrow,
           0x09 = plain bottom edge) even after the box has been cleared; with the box gone
           they would stay on screen as a 16x8 scrap of frame.  Remove them when they are the
           only thing left on that row. */
        volatile u16* r = &BG1MAP[BOX_BOTTOM * 32];
        u32 e = r[14] & 0x3ff;
        if ((e == 0x09 || e == 0x24) && (r[8] & 0x3ff) == 0 && (r[12] & 0x3ff) == 0 &&
            (r[13] & 0x3ff) == 0 && (r[16] & 0x3ff) == 0) {
            r[14] = 0; r[15] = 0;
            SYS_BGDIRTY |= 2;
        }
        return;
    }
    if (!vs.mapped && vs.mode != 2) return;
    /* the engine's arrow is BG tiles in row 19, columns 14-15, bobbing through the tile pairs
       0x20/0x21 .. 0x26/0x27 (each a row lower; 0x09 is the plain bottom edge): ours is a sprite
       at the right that bobs with it, and those cells show the box's bottom edge */
    u32 e = BG1MAP[BOX_BOTTOM * 32 + 14] & 0x3ff;
    if (e >= 0x20 && e <= 0x27) { vs.arrow_on = 1; vs.arrow_y = (e - 0x20) >> 1; }
    else if (e == 0x09 || e == 0x00) vs.arrow_on = 0;
    if (vs.mapped && (BG1MAP[CV_MAPROW * 32 + 1] & 0x3ff) != CV_TILE0 + 1) canvas_map();
    if (e >= 0x20 && e <= 0x27) {
        BG1MAP[BOX_BOTTOM * 32 + 14] = BOX_TEMPLATE[BOX_BOTTOM * 32 + 14];
        BG1MAP[BOX_BOTTOM * 32 + 15] = BOX_TEMPLATE[BOX_BOTTOM * 32 + 15];
        SYS_BGDIRTY |= 2;
        arrow_load();
    }
    if (vs.arrow_on) {
        static const s8 slide[6] = {0, 1, 0, -1, -2, -1};
        int x = ARROW_X + slide[(vs.arrow_t / 3) % 6];
        vs.arrow_t++;
        OAMBUF[ARROW_OBJ * 4 + 0] = ARROW_Y | (0 << 14);      /* y, square shape, 4bpp */
        OAMBUF[ARROW_OBJ * 4 + 1] = (x & 0x1ff) | (1 << 14);  /* x, size 1 -> 16x16 */
        OAMBUF[ARROW_OBJ * 4 + 2] = ARROW_TILE | (0 << 10) | (0 << 12);   /* palette 0 */
    } else vs.arrow_t = 0;
    if (vs.mapped) canvas_check();
}

/* ---------------------------------------------------------------- the question on BG0 */
/* The question canvas is on BG1, the box's layer, which the game blends with the scene (the box
   lets 7/16 of it through): its letters took the colour of what was behind them, a blue line
   paler over a bright wall than over a dark suit (white, at full brightness, does not show it).
   The page text is sprites and keeps its colours, as the original's and the DS's do.  While the
   game has BG0 off (every choice page seen), the letters go there instead: the canvas tiles hold
   them alone (vx.q_bare), BG0 maps them where BG1's map has the canvas, at BG1's priority (BG0 is
   drawn over BG1 at the same priority) and scroll, and BG1 shows the box's own tiles in their
   place.  BG0 is not a blending target, so the letters keep their colours over the box, which
   blends as before.  BG1's map shadow keeps the canvas entries (everything above works on it):
   only VRAM differs.  Everything is written where the game writes its own, so that nothing
   lands later in the frame than the game's (a first try that did it all after the game's
   updates tore the screen while the box slid): q_frame, before the map DMAs (0x08006684), takes
   BG0 off the game's DMA; vwf_bgcnt, called in place of the BG0CNT / BG1CNT store right after
   them, patches the maps in VRAM and gives the BG0 control and scroll; vwf_io_pre / vwf_io_post,
   around the IO register update (0x080009bc), add BG0 to DISPCNT (and to a fade's targets, and
   to the windows that show BG1) in the game's shadow and put the shadow back.  The game's BG0
   map and scroll go back (its DMA) the frame the question goes. */
#define SH_DISPCNT   (*(volatile u16*)0x03003ada)
#define SH_BLDCNT    (*(volatile u16*)0x03003ad8)
#define SH_WIN       (*(volatile u32*)0x03003ad0)   /* WININ | WINOUT << 16 */
#define SH_BG1SCROLL (*(volatile u32*)0x03003a9c)
#define BG0VRAM ((volatile u16*)0x0600e000)
#define BG1VRAM ((volatile u16*)0x0600e800)

static void q_frame(void) {
    u32 disp = SH_DISPCNT;
    int bg0_free = !(disp & 0x100) && (disp & 0x200) && (disp & 7) <= 1;
    /* the canvas's tiles follow, drawn again from the glyph log, while the page is mapped (a lost
       page is drawn again later, as q_want says).  The full-screen choice box skips canvas_check,
       so its checksum is not to be relied on; nothing else has the tiles while the page is mapped
       and not lost.  q_bare changes only with the tiles, so BG0 never shows framed ones (a page
       left framed by a save state from 0.16.30 or before showed the box opaque behind the
       question) and BG1 never bare ones. */
    vx.q_want = bg0_free;
    if (vx.q_want != vx.q_bare && vs.mapped && !vs.lost) {
        canvas_redraw();
    }
    /* canvas rows are whole rows (canvas_map, choice_frame; the engine copies rows whole) */
    u32 rows = 0;
    if (vx.q_bare && vx.q_want && vs.mapped && !vs.lost && !vs.overlay)
        for (int row = 0; row < 20; row++)
            if (canvas_tile(BG1MAP[row * 32 + 1])) rows |= 1u << row;
    if (!rows) {
        if (vx.q_on) {
            vx.q_on = 0; vx.q_rows = 0;
            SYS_BGDIRTY |= 3;       /* the game's BG0 map and scroll, and BG1's map as it is */
        }
        return;
    }
    if (!vx.q_on) { vx.q_new = 1; SYS_BGDIRTY |= 2; }
    vx.q_on = 1;
    SYS_BGDIRTY &= ~1;              /* BG0's map in VRAM is ours until the question goes */
    vx.q_bg1 = (SYS_BGDIRTY & 2) != 0;
    vx.q_rows_now = rows;
}

/* In place of the store of BG0CNT | BG1CNT << 16 (0x0800673a), after the game's map DMAs.  This
   runs in the vertical blank, ahead of the game's own updates (the OAM DMA, the characters'
   tiles): only what changed is written, a row at a time by DMA (doing all twenty rows every frame,
   with the canvas scan, took 23 scanlines and pushed the game's updates past the blank, and the top
   of the screen showed a character half updated). */
static const u16 box_row[CV_COLS] = {
    0x06, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
    0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x07,
};
u32 vwf_bgcnt(u32 v) {
    if (!vx.q_on) return v;
    /* the fill's zero is on the stack: a DMA from the cartridge always steps its source, fixed or
       not, so a zero in ROM filled the map with whatever follows it */
    volatile u32 zero_word = 0;
    u32 rows = vx.q_rows_now, old = vx.q_rows;
    if (vx.q_new) { dma32(&zero_word, BG0VRAM, 32 * 32 / 2, 1); old = 0; }
    for (int row = 0; row < 20; row++) {
        u32 bit = 1u << row;
        if (rows & bit) {
            if (!(old & bit) || BG0VRAM[row * 32 + 1] != BG1MAP[row * 32 + 1])
                dma32(BG1MAP + row * 32, BG0VRAM + row * 32, 16, 0);
            if (vx.q_bg1 || vx.q_new) dma32(box_row, BG1VRAM + row * 32, CV_COLS / 2, 0);   /* the box's own */
        } else if (old & bit)
            dma32(&zero_word, BG0VRAM + row * 32, 16, 1);
    }
    vx.q_rows = rows;
    vx.q_new = 0;
    /* At the top of the full-screen choice box the question is drawn Q_DROP pixels lower than
       the original's (its first line at y 21, not 17): an English first line runs on under the
       penalty gauge at the top right (y 4-16, x 156-235), and touched its bottom edge.  The
       options keep their rows; the question's last line still ends well above the first. */
    u32 scroll = SH_BG1SCROLL;
    if ((rows >> Q_MAPROW & 1) && fullscreen_box()) scroll -= Q_DROP << 16;
    REG(0x04000010) = scroll;
    return (v & 0xffff0000) | 0x1c00 | (v >> 16 & 3);     /* char block 0, map 0x600e000 */
}

void vwf_io_pre(void) {
    vx.q_saved = 0;
    if (!vx.q_on) return;
    vx.q_save_disp = SH_DISPCNT; vx.q_save_bld = SH_BLDCNT; vx.q_save_win = SH_WIN;
    vx.q_saved = 1;
    SH_DISPCNT = vx.q_save_disp | 0x100;
    u32 bld = vx.q_save_bld;
    if ((bld >> 6 & 3) >= 2 && (bld & 2)) SH_BLDCNT = bld | 1;     /* a fade takes BG0 with the box */
    if (vx.q_save_disp & 0xe000) {
        u32 w = vx.q_save_win;
        for (int k = 0; k < 32; k += 8) if (w >> k & 2) w |= 1u << k;
        SH_WIN = w;
    }
}

void vwf_io_post(void) {
    if (!vx.q_saved) return;
    SH_DISPCNT = vx.q_save_disp; SH_BLDCNT = vx.q_save_bld; SH_WIN = vx.q_save_win;
    vx.q_saved = 0;
}

/* The save screen opens over the game (START; patches/ui.py, with hdr_game): the page's sprite
   text goes until the state is put back (vwf_restore), a page starts (vwf_clear) or the box is
   cleared.  On a choice its options were drawn over the save screen. */
void vwf_overlay(void) {
    vs.overlay = 1;
    labels_hide();
}

/* Called before 0x08020024, which redraws the text sprites from the saved sprite records when
   an overlay screen (the save screen, for one) closes and the game state is restored: the
   overlay's own sprite text goes with it. */
void vwf_restore(void) {
    vs.overlay = 0;
    labels_hide();
    vs.lbl_row0 = -1;
    vs.lbl_caption = 0;
}

/* Replaces the engine's "clear box rows" loop: rows 10..19 of the BG1 map (the name tag's two
   rows and the box's eight).  A page of sprite text keeps its lines: command 0x1c can hide the
   box in the middle of a page (14 pages, the same in the Japanese GBA script and the DS's: the
   box goes for an animation, a point or a desk slam, and comes back with the page's text, which
   goes on where it was; the Japanese even goes on in the same line), and the original keeps its
   sprite text through it.  Starting the page over here lost the lines typed before the hide.
   A page that ends, or a new one typed from the first cell, starts over anyway. */
void vwf_boxclear(void) {
    for (int i = 10 * 32; i < 20 * 32; i++) BG1MAP[i] = 0;
    if (vs.mapped) text_colours(0);
    vs.mapped = 0;
    if (vs.mode != 2) vs.mode = 0;
    vs.overlay = 0;
}

/* ---------------------------------------------------------------- the data screen (episode 4) */
/* The escaped convict's data screen types two pages, common sections 0x31 and 0x32, with
   0x0801ecd4 (called from 0x0802afd0 and 0x0802b50e as (section, OBJ VRAM, x, y, shadow,
   OAM records, timing list)): one 16x16 sprite per character, 14 px apart and 18 px a line,
   its glyph from the Japanese font, which the English build has filled with code.  It fills the
   sprites' OAM records (from OAM 37, hidden: 0x0802b288 shows them one at a time, the cursor,
   OAM 36, moving to the next one's place) and the timing list the screen works through: per
   sprite its frames (the current {0b} speed), 0x8000 | n for a pause ({0c n}), 0x4000 | n to show
   picture n ({20 n}), 0xffff at the end ({45}, after one more record, blank, where the cursor
   stops); it returns the list's length, which the screen also takes as the number of OAM entries
   to hide from 34 on.  The English pages have three times the characters (68 and 135 against 24
   and 58): one sprite each ran the reveal past OAM 127 into the game's state (the mode at
   SYS+8 among it) and the screen went black for good, and the glyphs were garbage.
   This draws them in the variable-width font, packed into 16x16 sprites placed edge to edge (two
   or three letters each; a pause or a picture change starts a new one), in the original's dark
   grey with its light shadow (OBJ palette 13, colours 2 and 1).  Each sprite's time is the speed
   times its letters, so the page types at the original's pace.  The DS's text is used as it is
   and reflowed (see ds_layout); lines beside the photo end before it, and the line pitch shrinks
   from 16 (then the letters close up a pixel) until the page fits above the screen's bottom. */
#define DS_LIST_MAX   0x50       /* the timing list's room (the caller clears 0x50 entries) */
#define DS_TILE_END   0x300      /* OBJ tiles from the caller's up to here (the PICTURE tab is at 0x302) */
#define DS_OAM_LAST   126        /* OAM 37 + sprites, and the end record, stay below 127 */
#define DS_PHOTO_Y0   48         /* the photo: x 160-223, y 48-111 */
#define DS_PHOTO_Y1   112
#define DS_NARROW     154        /* lines beside the photo end before it, */
#define DS_WIDE       230        /* the others before the DATA tabs (x 232) */
#define DS_BOTTOM     158
#define DS_SPACE      0x17f
#define COMMON_TAB    (*(const u32* const*)0x0801ed60)   /* the common bank: its offset table, */
#define COMMON_BASE   (*(const u8* const*)0x0801ed64)    /* and its base (patches/script.py) */

static volatile u32* ds_rowptr(int tx, int ty, int r) {
    if (tx < 0 || tx > 1 || ty < 0 || ty > 1) return 0;
    return vs.ds_cell + (ty * 2 + tx) * 8 + r;
}

struct ds_out {
    u32 vram;                    /* OBJ VRAM of sprite 0 */
    volatile u16* rec;           /* its OAM record */
    volatile u16* list;
    int shadow;
    int cells, n;                /* sprites made, timing list length */
    int open, cx, cy, chars;     /* the sprite being filled: its place, letters begun in it */
    int lgi, lgx, lgy;           /* the last glyph drawn (it may run into the next sprite) */
    int full;
};

static void ds_glyph(struct ds_out* o, int gi, int x) {
    vs.ds_cell = (volatile u32*)(o->vram + (o->cells - 1) * 128);
    if (o->shadow) blit_to(gi, x + 1, 1, 1, ds_rowptr);
    blit_to(gi, x, 0, 2, ds_rowptr);
}

static int ds_new_cell(struct ds_out* o, int x, int y) {
    int tile = ((o->vram - 0x06010000) >> 5) + o->cells * 4;
    if (o->full || tile + 8 > DS_TILE_END || 37 + o->cells + 1 > DS_OAM_LAST || o->n + 3 > DS_LIST_MAX) {
        o->full = 1; return 0;
    }
    volatile u32* d = (volatile u32*)(o->vram + o->cells * 128);
    for (int i = 0; i < 32; i++) d[i] = 0;
    if (o->rec) {
        volatile u16* r = o->rec + o->cells * 4;
        r[0] = (y & 0xff) | 0x200;              /* hidden, 16x16 */
        r[1] = (x & 0x1ff) | 0x4000;
        r[2] = tile | 0xd400;                   /* palette 13, priority 1 */
    }
    o->cells++;
    o->open = 1; o->cx = x; o->cy = y; o->chars = 0;
    return 1;
}

/* Close the sprite being filled: its time goes on the list; a glyph running past its right edge
   gets one more sprite for its tail unless the next sprite is about to be placed there. */
static void ds_close(struct ds_out* o, int speed, int adjacent) {
    if (!o->open) return;
    o->open = 0;
    int t = speed * (o->chars ? o->chars : 1);
    o->list[o->n++] = t > 0x3fff ? 0x3fff : t;
    if (!adjacent && o->lgi >= 0 && o->lgy == o->cy && o->lgx + font_w[o->lgi] + 1 > o->cx + 16) {
        if (ds_new_cell(o, o->cx + 16, o->cy)) {
            ds_glyph(o, o->lgi, o->lgx - o->cx);
            o->open = 0;
            o->list[o->n++] = speed;
        }
    }
}

static int ds_word_width(const u16* p, int sq) {
    int w = 0;
    for (;; p++) {
        u32 t = *p;
        if (t >= 0x80) { if (t == DS_SPACE) break; w += font_w[glyph_index(t)] - sq; continue; }
        if (t == 0x0b || t == 0x0c || t == 0x20) { p++; continue; }
        if (t == 0x2d || t == 0x00) continue;
        break;
    }
    return w;
}

static int ds_limit(int y) {
    return (y < DS_PHOTO_Y1 && y + 14 > DS_PHOTO_Y0) ? DS_NARROW : DS_WIDE;
}

static int ds_lower(u32 t) { return t >= 0xa4 && t < 0xa4 + 26; }

/* Lay the section out (o == 0: only measure; returns the last line's y), or draw it.  A single
   line break ({2e}) is the DS's own wrapping: here a space, and the text wraps again at the
   width it has; two or more end the line and leave a blank one (`gap` px) each after the first,
   unless the text goes on in lower case (the DS breaking a sentence round its picture). */
static int ds_layout(const u16* p, int x0, int y0, int pitch, int gap, int sq, struct ds_out* o) {
    int x = x0, y = y0, speed = 8, start = 1, nl = 0, wb = 0;
    int space = font_w[glyph_index(DS_SPACE)] - sq;
    for (; *p != 0x45; p++) {
        u32 t = *p;
        if (t >= 0x80) {
            if (nl) {
                if (nl == 1 || ds_lower(t)) { if (!start) { x += space; wb = 1; } }
                else {
                    x = x0; y += pitch + (nl - 1) * gap; start = 1; wb = 0;
                    if (o) ds_close(o, speed, 0);
                }
                nl = 0;
            }
            if (t == DS_SPACE) { if (!start) { x += space; wb = 1; } continue; }
            if (wb && x + ds_word_width(p, sq) > ds_limit(y)) {
                x = x0; y += pitch; start = 1;
                if (o) ds_close(o, speed, 0);
            }
            wb = 0;
            int gi = glyph_index(t);
            if (o) {
                if (!o->open || y != o->cy || x >= o->cx + 16) {
                    int adj = o->open && y == o->cy && x < o->cx + 32;
                    int nx = adj ? o->cx + 16 : x;
                    ds_close(o, speed, adj);
                    if (ds_new_cell(o, nx, y) && o->lgi >= 0 && o->lgy == y && o->lgx + font_w[o->lgi] + 1 > nx)
                        ds_glyph(o, o->lgi, o->lgx - nx);
                }
                if (o->open) {
                    ds_glyph(o, gi, x - o->cx);
                    o->chars++;
                    o->lgi = gi; o->lgx = x; o->lgy = y;
                }
            }
            x += font_w[gi] - sq; start = 0;
            continue;
        }
        switch (t) {
        case 0x2e: nl++; break;
        case 0x0b: speed = *++p; break;
        case 0x0c:
        case 0x20:
            p++;
            if (o) {
                ds_close(o, speed, 0);
                if (o->n + 2 <= DS_LIST_MAX) o->list[o->n++] = (t == 0x0c ? 0x8000 : 0x4000) + *p;
                o->lgi = -1;
            }
            break;
        default:
            p += cmd_args[t];
        }
    }
    if (!o) return y;
    ds_close(o, speed, 0);
    /* the end: one more record, blank, where the cursor stops */
    if (ds_new_cell(o, x, y)) o->cells--;     /* its record and blank tiles, not counted */
    o->open = 0;
    o->list[o->n++] = 0xffff;
    return o->n;
}

u32 vwf_data_text(u32 sec, u32 vram, u32 x0, u32 y0, u32 shadow, volatile u16* rec, volatile u16* list) {
    const u16* src = (const u16*)(COMMON_BASE + COMMON_TAB[sec]);
    /* line pitch, blank line, letters squeezed by: the first that fits */
    static const u8 fits[][3] = {{16, 8, 0}, {15, 7, 0}, {14, 6, 0}, {16, 8, 1}, {15, 7, 1}, {14, 6, 1}, {13, 5, 1}};
    int k = 0;
    while (k < 6 && ds_layout(src, x0, y0, fits[k][0], fits[k][1], fits[k][2], 0) + 14 > DS_BOTTOM) k++;
    struct ds_out o;
    o.vram = vram; o.rec = rec; o.list = list; o.shadow = shadow;
    o.cells = o.n = o.open = o.cx = o.cy = o.chars = o.lgx = o.lgy = o.full = 0;
    o.lgi = -1;
    return ds_layout(src, x0, y0, fits[k][0], fits[k][1], fits[k][2], &o);
}

void _start(void) {}
