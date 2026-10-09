/* Variable-width font renderer for the text engine.
 *
 * Main window: the original engine drew one 16x16 sprite per character cell.  We keep a
 * 30x6-tile canvas in BG char block 0 (tiles CV_TILE0..) mapped onto BG1 rows
 * CV_MAPROW..+5 (the inside of the text box) and blit 1bpp glyphs at a pixel pen.
 * Choice menus: the box grows to full screen; the question canvas is re-mapped to the top
 * rows and the option labels are rendered into 16x16 sprite cells in OBJ VRAM.
 */
#include "gba.h"
#include "font.h"   /* generated: font_rows[], font_w[], expand_lut[], cmd_args[] */

#define CV_TILE0   0xe0
#define CV_COLS    30
#define CV_ROWS    6
#define CV_MAPROW  14
#define LINE_H     16
#define MAX_LINES  3
#define TEXT_X0    2          /* left padding inside the box */
#define TEXT_MAXW  236        /* usable width in pixels */

#define OAMBUF ((volatile u16*)0x03002ba0)

/* continue arrow sprite */
#define ARROW_OBJ   2
#define ARROW_TILE  0xf8

/* choice-menu labels: 3 lines of 16 sprite cells (16x16) in OBJ tiles 0x00..0xbf */
#define LBL_X0     24
#define LBL_Y0     72
#define LBL_CELLS  16
#define LBL_LINES  3
#define LBL_OBJ0   3
#define Q_MAPROW   1          /* question canvas rows in choice mode */
#define CAP_Y0     62         /* caption screen: first row y, 18 px pitch */
#define CAP_PITCH  18

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
    u8 lbl_shown;       /* OAM entries LBL_OBJ0.. currently carry sprite text */
    u8 lbl_used[LBL_LINES];   /* ... how many of each line's 16 entries (the others are left
                                 alone: the save screen puts its Yes / No in entries 40-41) */
    u8 lbl_align;       /* ... and how the engine places it, latched at its first character */
    u8 lbl_rows;
    u8 lbl_sys;
    u8 lbl_low;
    u8 lbl_full[LBL_LINES];   /* width of each line of the page (measured ahead) */
};
static struct vwf_state vs;

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
static const u32 arrow_tiles[2][8] = {   /* original tiles 0x24/0x25, white (8) only */
    {0x00000000, 0x00000000, 0x88888000, 0x88880000, 0x88800000, 0x88000000, 0x80000000, 0x00000000},
    {0x00000000, 0x00000000, 0x00088888, 0x00008888, 0x00000888, 0x00000088, 0x00000008, 0x00000000},
};

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
    if (tx < 0 || tx >= LBL_CELLS * 2 || ty >= LBL_LINES * 2) return 0;
    int cell = (ty >> 1) * LBL_CELLS + (tx >> 1);
    int tile = cell * 4 + (ty & 1) * 2 + (tx & 1);
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

static void canvas_reset(void) {
    for (int ty = 0; ty < CV_ROWS; ty++) {
        for (int tx = 0; tx < CV_COLS; tx++) {
            int src;
            if (ty == CV_ROWS - 1) src = (tx == 0) ? 1 : (tx == CV_COLS - 1) ? 2 : 6;
            else src = (tx == 0) ? 3 : (tx == CV_COLS - 1) ? 4 : 0;
            fill_tile(CV_TILE0 + ty * CV_COLS + tx, frame_tiles[src]);
        }
    }
}

static void arrow_load(void) {
    volatile u32* d = (volatile u32*)(0x06010000 + ARROW_TILE * 32);
    for (int i = 0; i < 8; i++) { d[i] = arrow_tiles[0][i]; d[8 + i] = arrow_tiles[1][i]; }
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

static void canvas_map(void) {
    for (int ty = 0; ty < CV_ROWS; ty++)
        for (int tx = 0; tx < CV_COLS; tx++)
            BG1MAP[(CV_MAPROW + ty) * 32 + tx] = CV_TILE0 + ty * CV_COLS + tx;
    SYS_BGDIRTY |= 2;
    BGPAL[13] = 0x167f; BGPAL[14] = 0x7eed; BGPAL[15] = 0x2be7;
    arrow_load();
    vs.mapped = 1;
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
static void labels_reset(void) {
    volatile u32* p = (volatile u32*)0x06010000;
    for (int i = 0; i < LBL_LINES * LBL_CELLS * 32; i++) p[i] = 0;
    for (int i = 0; i < LBL_LINES; i++) vs.lbl_width[i] = 0;
    vs.lbl_pen = 0; vs.lbl_line = 0;
}

/* The rest of the page from the character being drawn (code at `row`, the script pointer just
   after it): the number of rows, and the width of each line (for centring before it is typed). */
static int page_scan(const u16* p, u32 code, int row) {
    int L = row - vs.lbl_row0;
    int w = font_w[glyph_index(code)];
    for (int n = 0; n < 1024; n++) {
        u32 t = *p++;
        if (t >= 0x80) { w += font_w[glyph_index(t)]; continue; }
        if (t == 0x01) {
            if (L >= 0 && L < LBL_LINES) vs.lbl_full[L] = w > 255 ? 255 : w;
            row++; L++; w = 0; continue;
        }
        if (t == 0x00 || t == 0x02 || t == 0x07 || t == 0x08 || t == 0x09 || t == 0x0a || t == 0x0d ||
            t == 0x2c || t == 0x2d || t == 0x2e || t == 0x35 || t == 0x36 || t == 0x42) break;
        p += cmd_args[t];
    }
    if (L >= 0 && L < LBL_LINES) vs.lbl_full[L] = w > 255 ? 255 : w;
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
        /* where the engine's sprite writer (0x0801fd6c) puts this text: see labels_oam */
        u32 sec = TXT_SECTION;
        vs.lbl_sys = (sec <= 1 || sec == 3 || sec == 4 || (sec >= 6 && sec <= 31));
        vs.lbl_align = TXT_ALIGN & 0xf;
        vs.lbl_low = TXT_1A == 0;
        for (int i = 0; i < LBL_LINES; i++) vs.lbl_full[i] = 0;
        vs.lbl_rows = page_scan((const u16*)TXT_PTR, code, row);
    }
    int L = row - vs.lbl_row0;
    if (L < 0 || L >= LBL_LINES) return;
    if (col == 0 || L != vs.lbl_line) { vs.lbl_line = L; vs.lbl_pen = 0; }
    int gi = glyph_index(code);
    u32 c = text_colors[TXT_COLOR & 0xf];
    if (vs.lbl_pen + 16 <= LBL_CELLS * 16 && code != 0x17f) blit_to(gi, vs.lbl_pen, L * 16, c, label_rowptr);
    vs.lbl_pen += font_w[gi];
    if (vs.lbl_pen > 255) vs.lbl_pen = 255;
    if (vs.lbl_pen > vs.lbl_width[L]) vs.lbl_width[L] = vs.lbl_pen;
}

static void labels_hide(void) {
    if (!vs.lbl_shown) return;
    for (int L = 0; L < LBL_LINES; L++) {
        for (int c = 0; c < vs.lbl_used[L]; c++) OAMBUF[(LBL_OBJ0 + L * LBL_CELLS + c) * 4 + 0] = 0x0200;   /* disabled */
        vs.lbl_used[L] = 0;
    }
    vs.lbl_shown = 0;
}

static void labels_oam(void) {
    OBJPAL[2 * 16 + 13] = 0x167f; OBJPAL[2 * 16 + 14] = 0x7eed; OBJPAL[2 * 16 + 15] = 0x2be7;
    /* white (index 8) is the UI palette's; screens that load their own palette 2 (the episode
       select) leave it black */
    if (!(OBJPAL[2 * 16 + 8] & 0x7fff)) OBJPAL[2 * 16 + 8] = 0x7fff;
    vs.lbl_shown = 1;
    for (int L = 0; L < LBL_LINES; L++) {
        int w = vs.lbl_width[L];
        int ncells = (w + 15) >> 4;
        int x = LBL_X0, y = LBL_Y0 + L * 16;
        if (vs.lbl_caption) {
            /* As the engine: the box rows (y 116 + 18 * row; with a third English line, the
               three-line box's 112 + 16 * row), 64 px higher for some common-bank sections;
               otherwise centred text is centred, and alignment 2 (captions) is drawn at
               y 62 + 18 * row (y 71 when TXT+0x1a is 0). */
            int fw = vs.lbl_full[L] > w ? vs.lbl_full[L] : w;
            x = 9;
            y = (vs.lbl_rows > 2) ? 112 + L * 16 : 116 + L * 18;
            if (vs.lbl_sys) {
                /* the engine does not centre these (the Japanese pads them with spaces); the
                   English lines are centred, as on the DS */
                y = 52 + L * CAP_PITCH;
                x = (240 - fw) / 2;
            } else if (vs.lbl_align) {
                x = (240 - fw) / 2;
                if (vs.lbl_align == 2) y = (vs.lbl_low ? 71 : CAP_Y0) + L * CAP_PITCH;
            }
            if (x < 0) x = 0;
        }
        for (int c = 0; c < LBL_CELLS; c++) {
            int obj = LBL_OBJ0 + L * LBL_CELLS + c;
            if (c >= ncells) { if (c < vs.lbl_used[L]) OAMBUF[obj * 4 + 0] = 0x0200; continue; }
            OAMBUF[obj * 4 + 0] = y | (0 << 14);
            OAMBUF[obj * 4 + 1] = ((x + c * 16) & 0x1ff) | (1 << 14);
            OAMBUF[obj * 4 + 2] = (L * LBL_CELLS + c) * 4 | (0 << 10) | (2 << 12);
        }
        vs.lbl_used[L] = ncells;
    }
}

/* question canvas lives at rows Q_MAPROW..+5; any canvas tiles copied elsewhere by the
   box-grow animation become plain interior. */
static void choice_frame(void) {
    int dirty = 0;
    for (int row = 0; row < 20; row++) {
        int qrow = row - Q_MAPROW;
        for (int tx = 0; tx < CV_COLS; tx++) {
            u32 e = BG1MAP[row * 32 + tx] & 0x3ff;
            u32 want;
            if (qrow >= 0 && qrow < CV_ROWS) want = CV_TILE0 + qrow * CV_COLS + tx;
            else if (e >= CV_TILE0 && e < CV_TILE0 + CV_ROWS * CV_COLS) want = 0x01;
            else continue;
            if (e != want) { BG1MAP[row * 32 + tx] = want; dirty = 1; }
        }
    }
    if (dirty) SYS_BGDIRTY |= 2;
    labels_oam();
}

/* ---------------------------------------------------------------- hooks */

/* Replaces the engine's cell draw: r0 = code-0x80, r1 = col, r2 = row. */
void vwf_draw_char(u32 code80, u32 col, u32 row) {
    u32 code = code80 + 0x80;
    int gi = glyph_index(code);
    if ((vs.lbl_row0 >= 0 && vs.lbl_caption) || (SYS_CAPTION & 4) || fullscreen_box()) {
        label_draw_char(code, col, row); return;
    }
    if (!vs.mapped) { canvas_reset(); canvas_map(); }
    else if ((BG1MAP[CV_MAPROW * 32 + 1] & 0x3ff) != CV_TILE0 + 1) canvas_map();
    if (vs.pen_x == 0) {
        /* start of a line: decide on squeeze */
        int w = font_w[gi] + measure_line((const u16*)TXT_PTR);
        vs.squeeze = 0;
        if (w > TEXT_MAXW) vs.squeeze = 1;
        if (w - 24 > TEXT_MAXW) vs.squeeze = 2;
    }
    int L = vs.line;
    if (L >= MAX_LINES) L = MAX_LINES - 1;
    int x = TEXT_X0 + vs.pen_x;
    if (x > 240 - 4) return;
    u32 c = text_colors[TXT_COLOR & 0xf];
    if (code != 0x17f) blit_to(gi, x, L * LINE_H, c, canvas_rowptr);
    int adv = font_w[gi] - vs.squeeze;
    if (adv < 1) adv = 1;
    vs.pen_x += adv;
}

void vwf_newline(void) {
    vs.pen_x = 0;
    if (vs.line < 255) vs.line++;
}

void vwf_clear(void) {
    vs.pen_x = 0;
    vs.line = 0;
    vs.squeeze = 0;
    vs.lbl_row0 = -1;
    for (int i = 0; i < LBL_LINES; i++) vs.lbl_width[i] = 0;
    canvas_reset();
}

/* Per frame (before the BG map / OAM DMA). */
void vwf_frame(void) {
    if (vs.lbl_row0 >= 0 && vs.lbl_caption) { labels_oam(); return; }
    if (fullscreen_box()) {
        if (vs.mapped) choice_frame();
        return;
    }
    labels_hide();
    vs.lbl_row0 = -1;
    if (!box_open()) {
        vs.arrow_on = 0;
        /* The engine writes its arrow cells (row 19, columns 14-15: tile 0x24/0x25 = arrow,
           0x09 = plain bottom edge) even after the box has been cleared; with the box gone
           they would stay on screen as a 16x8 scrap of frame.  Remove them when they are the
           only thing left on that row. */
        volatile u16* r = &BG1MAP[(CV_MAPROW + 5) * 32];
        u32 e = r[14] & 0x3ff;
        if ((e == 0x09 || e == 0x24) && (r[8] & 0x3ff) == 0 && (r[12] & 0x3ff) == 0 &&
            (r[13] & 0x3ff) == 0 && (r[16] & 0x3ff) == 0) {
            r[14] = 0; r[15] = 0;
            SYS_BGDIRTY |= 2;
        }
        return;
    }
    if (!vs.mapped) return;
    u32 e = BG1MAP[(CV_MAPROW + 5) * 32 + 14] & 0x3ff;
    if (e == 0x24) vs.arrow_on = 1;
    else if (e == 0x09 || e == 0x00) vs.arrow_on = 0;
    if ((BG1MAP[CV_MAPROW * 32 + 1] & 0x3ff) != CV_TILE0 + 1) canvas_map();
    else if (e != (u32)(CV_TILE0 + 5 * CV_COLS + 14)) {
        BG1MAP[(CV_MAPROW + 5) * 32 + 14] = CV_TILE0 + 5 * CV_COLS + 14;
        BG1MAP[(CV_MAPROW + 5) * 32 + 15] = CV_TILE0 + 5 * CV_COLS + 15;
        SYS_BGDIRTY |= 2;
    }
    if (vs.arrow_on) {
        OAMBUF[ARROW_OBJ * 4 + 0] = 150 | (1 << 14);          /* y, wide shape, 4bpp */
        OAMBUF[ARROW_OBJ * 4 + 1] = 222 | (0 << 14);          /* x, size 0 -> 16x8 */
        OAMBUF[ARROW_OBJ * 4 + 2] = ARROW_TILE | (0 << 10) | (2 << 12);
    }
}

/* Called before 0x08020024, which redraws the text sprites from the saved sprite records when
   an overlay screen (the save screen, for one) closes and the game state is restored: the
   overlay's own sprite text goes with it. */
void vwf_restore(void) {
    labels_hide();
    vs.lbl_row0 = -1;
    vs.lbl_caption = 0;
}

/* Replaces the engine's "clear box rows" loop: rows 11..19 of the BG1 map. */
void vwf_boxclear(void) {
    for (int i = 11 * 32; i < 20 * 32; i++) BG1MAP[i] = 0;
    vs.mapped = 0;
}

void _start(void) {}
