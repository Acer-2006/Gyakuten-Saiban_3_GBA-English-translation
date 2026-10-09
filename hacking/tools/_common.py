"""Shared helpers for the gs3_* command-line tools (import path, ROM loading, argument parsing)."""
import os, sys, struct, signal

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)     # `tool ... | head` without a traceback
except (AttributeError, ValueError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))            # repository root
LIB = os.path.join(ROOT, 'tools')                        # the build tool's library
DATA = os.path.join(ROOT, 'data')
if LIB not in sys.path:
    sys.path.insert(0, LIB)

ROM_BASE = 0x08000000

def num(s):
    """Parse a number: decimal, 0x.., or a ROM address (0x08xxxxxx is accepted everywhere)."""
    return int(s, 0)

def rom_off(v):
    """ROM address or offset -> offset."""
    return v - ROM_BASE if v >= ROM_BASE else v

def rom_addr(v):
    return v + ROM_BASE if v < ROM_BASE else v

def load_rom(path):
    d = open(path, 'rb').read()
    if len(d) < 0xc0 or d[0xb2] != 0x96:
        sys.exit(f'{path}: not a GBA ROM')
    return d

def is_gs3(d):
    return d[0xac:0xb0] == b'A3JJ'

def warn_not_gs3(d):
    if not is_gs3(d):
        print('warning: game code is not A3JJ; the built-in addresses are for Gyakuten Saiban 3 (Japan)', file=sys.stderr)

def used_end(rom):
    """First 4-aligned offset after the last byte that is not 0xff padding."""
    e = len(rom)
    while e > 0 and rom[e - 1] == 0xff: e -= 1
    return (e + 3) & ~3

def place(rom, data, at=None, align=4, note=''):
    """Put `data` into the ROM (a bytearray) at `at`, or after the last used byte, growing the
    ROM to the next power of two (32 MB at most) when needed.  Returns the ROM address."""
    at = used_end(rom) if at is None else rom_off(at)
    at = (at + align - 1) & ~(align - 1)
    new_size = at + len(data)
    if new_size > len(rom):
        size = 0x400000
        while size < new_size: size *= 2
        if size > 0x2000000:
            sys.exit('ROM would exceed 32 MB')
        rom += b'\xff' * (size - len(rom))
        print(f'ROM expanded to {size // 0x100000} MB')
    rom[at:at + len(data)] = data
    print(f'{note or "data"}: {len(data)} bytes written at {rom_addr(at):#x}')
    return rom_addr(at)

def repoint(rom, old_addr, new_addr, extra_offsets=(0,)):
    """Replace every aligned u32 equal to old_addr(+k) with new_addr(+k); returns the count."""
    n = 0
    for k in extra_offsets:
        old = struct.pack('<I', old_addr + k); new = struct.pack('<I', new_addr + k)
        i = 0
        while True:
            i = rom.find(old, i)
            if i < 0: break
            if i % 4 == 0:
                rom[i:i + 4] = new; n += 1
            i += 1
    return n

def save_rom(rom, path):
    open(path, 'wb').write(rom)
    print(f'wrote {path} ({len(rom) // 0x100000} MB)')
