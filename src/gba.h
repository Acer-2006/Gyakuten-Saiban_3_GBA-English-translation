#pragma once
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef signed char s8;
typedef short s16;
typedef int s32;

#define REG(a) (*(volatile u32*)(a))
#define REG16(a) (*(volatile u16*)(a))

/* ---- engine addresses (GBA Gyakuten Saiban 3, A3JJ) ---- */
#define TXT ((volatile u8*)0x03007200)      /* text engine state struct */
#define TXT_PTR (*(volatile u32*)0x03007200) /* current script pointer */
#define TXT_FLAGS (*(volatile u16*)0x0300721c)
#define TXT_COLOR (*(volatile u8*)0x03007225)
#define TXT_COL (*(volatile u8*)0x03007228)
#define TXT_ROW (*(volatile u8*)0x03007229)
#define SYS ((volatile u8*)0x030037b0)
#define SYS_BGDIRTY (*(volatile u8*)0x030037ca)  /* bit0 BG0 map, bit1 BG1 map */
#define BG1MAP ((volatile u16*)0x03002080)        /* 32x32 map shadow -> 0x600e800 */
#define BG0MAP ((volatile u16*)0x03002fa0)
#define OAMSH ((volatile u8*)0x03003e50)          /* 12-byte sprite shadow entries */
#define BGPAL ((volatile u16*)0x05000000)
#define OBJPAL ((volatile u16*)0x05000200)
#define SYS_CAPTION (*(volatile u8*)0x03003a0c)   /* bit2: caption text mode (command 0x42) */
#define TXT_ALIGN (*(volatile u8*)0x03007222)     /* low nibble: 1 = centred (command 0x5d) */
#define TXT_SECTION (*(volatile u16*)0x0300720c)  /* current section (< 0x80: common bank) */
#define TXT_1A (*(volatile u16*)0x0300721a)       /* 0: alignment-2 text sits at y 71 */
#define VRAM ((volatile u8*)0x06000000)
#define OBJVRAM ((volatile u16*)0x06010000)
