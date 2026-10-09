#!/usr/bin/env python3
"""ROM patching framework: allocation, code generation (assembly / C) with a prebuilt cache.

Code generation needs keystone (Thumb/ARM assembly) and clang/lld (C).  Every generated blob is
recorded in prebuilt/codegen.json, keyed by its inputs, so a plain Python install can rebuild the
ROM from the two game cartridges without any toolchain: the generated code is ours, the game
data is read from the user's own ROMs at build time.
"""
import os, struct, subprocess, json, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, 'prebuilt', 'codegen.json')

_cache = None
_cache_dirty = False
_ks = {}

def _load_cache():
    global _cache
    if _cache is None:
        _cache = json.load(open(CACHE_PATH)) if os.path.exists(CACHE_PATH) else {}
    return _cache

def save_cache():
    global _cache_dirty
    if _cache is not None and _cache_dirty:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        json.dump(_cache, open(CACHE_PATH, 'w'), indent=0, sort_keys=True)
        _cache_dirty = False

def have_toolchain():
    if os.environ.get('GS3_NO_TOOLCHAIN'): return False
    try:
        import keystone  # noqa
        return subprocess.run(['clang', '--version'], capture_output=True).returncode == 0
    except Exception:
        return False

def _assemble(mode, addr, src):
    """Assemble with keystone (dev machines) or fetch the prebuilt bytes."""
    global _cache_dirty
    key = f'{mode}:{addr:#x}:{src}'
    c = _load_cache()
    if key in c: return bytes.fromhex(c[key])
    try:
        if os.environ.get('GS3_NO_TOOLCHAIN'): raise ImportError
        from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB, KS_MODE_ARM
    except ImportError:
        raise RuntimeError('prebuilt code is out of date and keystone is not installed; '
                           'run the build once on a machine with the dev toolchain') from None
    if mode not in _ks:
        _ks[mode] = Ks(KS_ARCH_ARM, KS_MODE_THUMB if mode == 'thumb' else KS_MODE_ARM)
    enc, _ = _ks[mode].asm(src, addr)
    b = bytes(enc)
    c[key] = b.hex(); _cache_dirty = True
    return b

def off(addr):
    return addr - 0x08000000 if addr >= 0x08000000 else addr

class Region:
    def __init__(self, start, end, name):
        self.start, self.end, self.name, self.cur = start, end, name, start
    def alloc(self, size, align=4):
        a = (self.cur + align - 1) & ~(align - 1)
        if a + size > self.end:
            raise MemoryError(f'region {self.name} full: need {size:#x}, have {self.end - a:#x}')
        self.cur = a + size
        return a
    @property
    def used(self): return self.cur - self.start

class Rom:
    def __init__(self, data, size=0x1000000):
        self.d = bytearray(data)
        self.orig_size = len(self.d)
        self.d += b'\xff' * (size - len(self.d))
        self.regions = {}
        self.log = []
    def region(self, name, start, end):
        self.regions[name] = Region(start, end, name); return self.regions[name]
    def alloc(self, size, region='ext', align=4):
        return 0x08000000 + self.regions[region].alloc(size, align)
    # raw access
    def read(self, addr, n): o = off(addr); return bytes(self.d[o:o + n])
    def write(self, addr, data: bytes, note=''):
        o = off(addr); self.d[o:o + len(data)] = data
        self.log.append((addr, len(data), note))
    def u8(self, addr): return self.d[off(addr)]
    def u16(self, addr): return struct.unpack_from('<H', self.d, off(addr))[0]
    def u32(self, addr): return struct.unpack_from('<I', self.d, off(addr))[0]
    def w16(self, addr, v): self.write(addr, struct.pack('<H', v & 0xffff))
    def w32(self, addr, v): self.write(addr, struct.pack('<I', v & 0xffffffff))
    def store(self, data: bytes, region='ext', align=4, note=''):
        a = self.alloc(len(data), region, align); self.write(a, data, note); return a
    # assembly
    def asm_thumb(self, addr, src): return _assemble('thumb', addr & ~1, src)
    def asm_arm(self, addr, src): return _assemble('arm', addr & ~3, src)
    def thumb(self, addr, src, note=''):
        b = self.asm_thumb(addr, src); self.write(addr & ~1, b, note); return len(b)
    def arm(self, addr, src, note=''):
        b = self.asm_arm(addr, src); self.write(addr & ~3, b, note); return len(b)
    def hook_bl(self, at, target, note=''):
        """Overwrite the 4-byte Thumb instruction(s) at `at` with `bl target`."""
        self.thumb(at, f'bl #{target & ~1:#x}', note)
    def hook_b(self, at, target, note=''):
        self.thumb(at, f'b #{target & ~1:#x}', note)
    def thumb_code(self, src, region='font', note=''):
        """Assemble a Thumb routine into free space; returns its address (with Thumb bit)."""
        a = self.regions[region]
        addr = 0x08000000 + ((a.cur + 3) & ~3)
        b = self.asm_thumb(addr, src)
        addr = self.store(b, region, 4, note)
        return addr | 1
    def arm_code(self, src, region='font', note=''):
        a = self.regions[region]
        addr = 0x08000000 + ((a.cur + 3) & ~3)
        b = self.asm_arm(addr, src)
        return self.store(b, region, 4, note)
    def save(self, path):
        open(path, 'wb').write(self.d)

def compile_c(sources, text_addr, bss_addr, out_dir, extra_cflags=(), defines=(), ld_defsyms=None):
    """Compile C sources to a flat Thumb binary placed at text_addr; returns (binary, symbols, bss_size).
    Cached in prebuilt/codegen.json by a hash of the sources and parameters."""
    global _cache_dirty
    h = hashlib.sha256()
    for s in sources:
        h.update(os.path.basename(s).encode()); h.update(open(s, 'rb').read())
    for inc in sorted(os.listdir(os.path.dirname(sources[0]))):
        if inc.endswith('.h'):
            p = os.path.join(os.path.dirname(sources[0]), inc)
            h.update(inc.encode()); h.update(open(p, 'rb').read())
    h.update(json.dumps([text_addr, bss_addr, list(extra_cflags), list(defines), sorted((ld_defsyms or {}).items())]).encode())
    key = 'c:' + h.hexdigest()
    c = _load_cache()
    if key in c:
        e = c[key]
        return bytes.fromhex(e['bin']), {k: int(v) for k, v in e['syms'].items()}, e['bss']
    if not have_toolchain():
        raise RuntimeError('prebuilt code is out of date and clang/keystone are not installed; '
                           'run the build once on a machine with the dev toolchain')
    os.makedirs(out_dir, exist_ok=True)
    objs = []
    cflags = ['--target=arm-none-eabi', '-mthumb', '-mcpu=arm7tdmi', '-O2', '-ffreestanding', '-fno-builtin',
              '-nostdlib', '-fno-stack-protector', '-fomit-frame-pointer', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
              '-Wall', '-mno-unaligned-access', '-fno-pic', '-fshort-enums'] + list(extra_cflags) + [f'-D{d}' for d in defines]
    for s in sources:
        o = os.path.join(out_dir, os.path.basename(s) + '.o')
        subprocess.check_call(['clang'] + cflags + ['-c', s, '-o', o])
        objs.append(o)
    ld = os.path.join(out_dir, 'link.ld')
    open(ld, 'w').write(f'''
ENTRY(_start)
SECTIONS {{
  /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment) }}
  . = {text_addr:#x};
  .text : {{ *(.text.start) *(.text*) *(.rodata*) *(.data*) }}
  . = {bss_addr:#x};
  .bss (NOLOAD) : {{ *(.bss*) *(COMMON) }}
}}
''')
    elf = os.path.join(out_dir, 'out.elf'); binp = os.path.join(out_dir, 'out.bin')
    defs = [f'--defsym={k}={v:#x}' for k, v in (ld_defsyms or {}).items()]
    subprocess.check_call(['ld.lld', '-T', ld, '-o', elf] + defs + objs)
    subprocess.check_call(['llvm-objcopy', '-O', 'binary', '--only-section=.text', elf, binp])
    syms = {}
    for line in subprocess.check_output(['llvm-nm', elf]).decode().splitlines():
        parts = line.split()
        if len(parts) == 3: syms[parts[2]] = int(parts[0], 16)
    assert syms['_start'] >= text_addr
    for line in subprocess.check_output(['llvm-readelf', '-S', elf]).decode().splitlines():
        if '.text' in line and 'PROGBITS' in line:
            assert int(line.split('PROGBITS')[1].split()[0], 16) == text_addr, line
    bss_size = 0
    for line in subprocess.check_output(['llvm-size', '-A', elf]).decode().splitlines():
        p = line.split()
        if p and p[0] == '.bss': bss_size = int(p[1])
    binary = open(binp, 'rb').read()
    c[key] = {'bin': binary.hex(), 'syms': {k: v for k, v in syms.items() if not k.startswith('$')}, 'bss': bss_size}
    _cache_dirty = True
    return binary, syms, bss_size
