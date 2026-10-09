// Headless mGBA harness driven by stdin commands.
// run N | key MASK | shot FILE.ppm | rd ADDR LEN | wr ADDR HEX | save FILE | load FILE | pc | quit
#include <mgba/core/core.h>
#include <mgba/core/serialize.h>
#include <mgba/gba/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/arm/arm.h>
#include <mgba-util/vfs.h>
#include <mgba/core/log.h>
#include <mgba/debugger/debugger.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static struct mCore* core;
static uint32_t* fb;
static unsigned W, H;

static int verbose = 0;
static void nolog(struct mLogger* l, int cat, enum mLogLevel lv, const char* fmt, va_list args) {
    (void)l; (void)cat;
    if (verbose && lv <= mLOG_WARN) { vfprintf(stderr, fmt, args); fputc('\n', stderr); }
}
static struct mLogger logger = { .log = nolog };

// ---- tracepoints ----
static struct mDebugger dbg;
static int dbgAttached = 0;
static int tpCount = 0;
#define MAXTP 64
static uint32_t tpAddr[MAXTP];
static uint32_t tpMem[MAXTP];   // optional memory address to dump (u32) at hit, 0 = none
static FILE* tplog = NULL;
static long tpHits = 0;

static void tpEntered(struct mDebugger* d, enum mDebuggerEntryReason reason, struct mDebuggerEntryInfo* info) {
    (void)info;
    if (reason == DEBUGGER_ENTER_WATCHPOINT) {
        struct ARMCore* cpu = core->cpu;
        if (tplog) {
            fprintf(tplog, "WP %08x pc=%08x old=%08x new=%08x", info->address, cpu->gprs[ARM_PC] - 4, info->type.wp.oldValue, info->type.wp.newValue);
            for (int i = 0; i < 8; ++i) fprintf(tplog, " %08x", cpu->gprs[i]);
            fprintf(tplog, " lr=%08x\n", cpu->gprs[ARM_LR]);
        }
        ++tpHits;
    }
    if (reason == DEBUGGER_ENTER_BREAKPOINT) {
        struct ARMCore* cpu = core->cpu;
        uint32_t pc = info->address;
        if (tplog) {
            fprintf(tplog, "%08x", pc);
            for (int i = 0; i < 8; ++i) fprintf(tplog, " %08x", cpu->gprs[i]);
            fprintf(tplog, " sp=%08x lr=%08x", cpu->gprs[ARM_SP], cpu->gprs[ARM_LR]);
            for (int i = 0; i < tpCount; ++i) if (tpAddr[i] == pc && tpMem[i]) {
                fprintf(tplog, " m=%08x", core->busRead32(core, tpMem[i]));
            }
            fprintf(tplog, "\n");
        }
        ++tpHits;
    }
    d->state = DEBUGGER_RUNNING;
}

static void ensureDebugger(void) {
    if (dbgAttached) return;
    memset(&dbg, 0, sizeof dbg);
    dbg.entered = tpEntered;
    mDebuggerAttach(&dbg, core);
    dbg.state = DEBUGGER_RUNNING;
    dbgAttached = 1;
}

static void shot(const char* path) {
    FILE* f = fopen(path, "wb");
    if (!f) { printf("ERR open\n"); return; }
    fprintf(f, "P6\n%u %u\n255\n", W, H);
    for (unsigned i = 0; i < W * H; ++i) {
        uint32_t p = fb[i];
        unsigned char rgb[3] = { p & 0xFF, (p >> 8) & 0xFF, (p >> 16) & 0xFF };
        fwrite(rgb, 1, 3, f);
    }
    fclose(f);
}

int main(int argc, char** argv) {
    if (argc < 2) { fprintf(stderr, "usage: gbarun rom.gba\n"); return 1; }
    verbose = getenv("GBARUN_VERBOSE") != NULL;
    mLogSetDefaultLogger(&logger);
    core = GBACoreCreate();
    core->init(core);
    mCoreInitConfig(core, NULL);
    mCoreConfigSetValue(&core->config, "idleOptimization", "remove");
    core->desiredVideoDimensions(core, &W, &H);
    fb = malloc(W * H * 4);
    core->setVideoBuffer(core, fb, W);
    if (!mCoreLoadFile(core, argv[1])) { fprintf(stderr, "load failed\n"); return 1; }
    core->reset(core);
    char line[4096];
    setvbuf(stdout, NULL, _IOLBF, 0);
    while (fgets(line, sizeof line, stdin)) {
        char cmd[32]; char a1[2048]; char a2[2048];
        int n = sscanf(line, "%31s %2047s %2047s", cmd, a1, a2);
        if (n < 1) continue;
        if (!strcmp(cmd, "run")) {
            int k = atoi(a1);
            if (dbgAttached && tpCount) { for (int i = 0; i < k; ++i) mDebuggerRunFrame(&dbg); }
            else { for (int i = 0; i < k; ++i) core->runFrame(core); }
            printf("ok\n");
        } else if (!strcmp(cmd, "tp")) {   // tp ADDR [MEMADDR]
            ensureDebugger();
            struct mBreakpoint bp = { .address = strtoul(a1, NULL, 0) & ~1u, .segment = -1, .type = BREAKPOINT_HARDWARE, .condition = NULL };
            dbg.platform->setBreakpoint(dbg.platform, &bp);
            tpAddr[tpCount] = bp.address; tpMem[tpCount] = (n > 2) ? strtoul(a2, NULL, 0) : 0; ++tpCount;
            printf("ok\n");
        } else if (!strcmp(cmd, "wp")) {   // wp ADDR [r|w|rw|c]
            ensureDebugger();
            enum mWatchpointType t = WATCHPOINT_WRITE;
            if (n > 2) { if (!strcmp(a2, "r")) t = WATCHPOINT_READ; else if (!strcmp(a2, "rw")) t = WATCHPOINT_RW; else if (!strcmp(a2, "c")) t = WATCHPOINT_WRITE_CHANGE; }
            struct mWatchpoint wp = { .address = strtoul(a1, NULL, 0), .segment = -1, .type = t, .condition = NULL };
            dbg.platform->setWatchpoint(dbg.platform, &wp);
            ++tpCount;  // force debugger stepping mode
            printf("ok\n");
        } else if (!strcmp(cmd, "crashtrace")) {   // crashtrace MAXSTEPS : step until PC leaves ROM/RAM, print last 64 PCs
            long maxs = atol(a1); uint32_t ring[64]; int ri = 0; long steps = 0;
            struct ARMCore* cpu = core->cpu;
            while (steps < maxs) {
                uint32_t pc = cpu->gprs[ARM_PC] - (cpu->executionMode == MODE_THUMB ? 4 : 8);
                ring[ri++ & 63] = pc;
                if (!((pc >= 0x08000000 && pc < 0x0a000000) || (pc >= 0x02000000 && pc < 0x02040000) || (pc >= 0x03000000 && pc < 0x03008000) || pc < 0x4000)) break;
                core->step(core); ++steps;
            }
            printf("steps=%ld pc=%08x r0=%08x r1=%08x r2=%08x r3=%08x r4=%08x r5=%08x r6=%08x r7=%08x sp=%08x lr=%08x |", steps,
                   cpu->gprs[ARM_PC], cpu->gprs[0], cpu->gprs[1], cpu->gprs[2], cpu->gprs[3], cpu->gprs[4], cpu->gprs[5], cpu->gprs[6], cpu->gprs[7], cpu->gprs[ARM_SP], cpu->gprs[ARM_LR]);
            for (int i = 0; i < 64; ++i) printf(" %08x", ring[(ri + i) & 63]);
            printf("\n");
        } else if (!strcmp(cmd, "tplog")) {  // tplog FILE  (start logging to file)
            if (tplog) fclose(tplog);
            tplog = fopen(a1, "w"); tpHits = 0; printf("ok\n");
        } else if (!strcmp(cmd, "tpflush")) {
            if (tplog) fflush(tplog);
            printf("%ld\n", tpHits);
        } else if (!strcmp(cmd, "key")) {
            core->setKeys(core, strtoul(a1, NULL, 0));
            printf("ok\n");
        } else if (!strcmp(cmd, "shot")) {
            shot(a1); printf("ok\n");
        } else if (!strcmp(cmd, "rd")) {
            uint32_t addr = strtoul(a1, NULL, 0); int len = atoi(a2);
            for (int i = 0; i < len; ++i) printf("%02x", core->busRead8(core, addr + i));
            printf("\n");
        } else if (!strcmp(cmd, "wr")) {
            uint32_t addr = strtoul(a1, NULL, 0);
            size_t l = strlen(a2) / 2;
            for (size_t i = 0; i < l; ++i) {
                unsigned v; sscanf(a2 + 2 * i, "%2x", &v);
                core->busWrite8(core, addr + i, v);
            }
            printf("ok\n");
        } else if (!strcmp(cmd, "save")) {
            struct VFile* vf = VFileOpen(a1, O_RDWR | O_CREAT | O_TRUNC);
            mCoreSaveStateNamed(core, vf, SAVESTATE_SAVEDATA);
            vf->close(vf); printf("ok\n");
        } else if (!strcmp(cmd, "load")) {
            struct VFile* vf = VFileOpen(a1, O_RDONLY);
            if (!vf) { printf("ERR\n"); continue; }
            bool ok = mCoreLoadStateNamed(core, vf, SAVESTATE_SAVEDATA);
            vf->close(vf); printf(ok ? "ok\n" : "ERR load\n");
        } else if (!strcmp(cmd, "pc")) {
            struct ARMCore* cpu = core->cpu;
            printf("%08x\n", cpu->gprs[ARM_PC]);
        } else if (!strcmp(cmd, "reset")) {
            core->reset(core); printf("ok\n");
        } else if (!strcmp(cmd, "quit")) {
            break;
        } else {
            printf("ERR unknown\n");
        }
    }
    core->deinit(core);
    return 0;
}
