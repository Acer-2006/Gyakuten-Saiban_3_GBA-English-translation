#!/usr/bin/env python3
"""Python driver for the gbarun harness (see build.sh and ../docs/tools.md).

    from emu import Emu
    e = Emu('game.gba'); e.run(300); e.press('START'); e.shot('title.png')
    e.rd32(0x03007200)                     # read memory
    e.tplog('trace.txt'); e.tp(0x0801f4c4, 0x03007200); e.run(60); print(e.tpflush())
"""
import subprocess, os
try:
    from PIL import Image
except ImportError:
    Image = None

KEY = dict(A=1, B=2, SELECT=4, START=8, RIGHT=0x10, LEFT=0x20, UP=0x40, DOWN=0x80, R=0x100, L=0x200)
HERE = os.path.dirname(os.path.abspath(__file__))

class Emu:
    def __init__(self, rom):
        self.p = subprocess.Popen([os.path.join(HERE, 'gbarun'), rom], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, bufsize=1)
    def cmd(self, s):
        self.p.stdin.write(s + '\n'); self.p.stdin.flush()
        return self.p.stdout.readline().strip()
    def run(self, n=1): return self.cmd(f'run {n}')
    def key(self, mask=0): return self.cmd(f'key {mask}')
    def press(self, name, hold=2, release=2):
        self.key(KEY[name]); self.run(hold); self.key(0); self.run(release)
    def shot(self, path):
        """Screenshot; .png needs Pillow, otherwise the file is written as .ppm."""
        if Image is None or path.endswith('.ppm'):
            if not path.endswith('.ppm'): path += '.ppm'
            self.cmd(f'shot {path}'); return path
        ppm = path + '.ppm'
        self.cmd(f'shot {ppm}')
        Image.open(ppm).save(path); os.remove(ppm)
        return path
    def rd(self, addr, n):
        return bytes.fromhex(self.cmd(f'rd {addr:#x} {n}'))
    def rd16(self, addr): return int.from_bytes(self.rd(addr, 2), 'little')
    def rd32(self, addr): return int.from_bytes(self.rd(addr, 4), 'little')
    def wr(self, addr, data: bytes): return self.cmd(f'wr {addr:#x} {data.hex()}')
    def save(self, path): return self.cmd(f'save {path}')
    def load(self, path): return self.cmd(f'load {path}')
    def pc(self): return int(self.cmd('pc'), 16)
    def close(self):
        try: self.cmd('quit')
        except Exception: pass
        self.p.wait()

    # tracing: tp = breakpoint that logs registers (and optionally a memory word) and continues
    def tp(self, addr, mem=0): return self.cmd(f'tp {addr:#x} {mem:#x}')
    def wp(self, addr, kind='w'): return self.cmd(f'wp {addr:#x} {kind}')     # r, w, rw, c (change)
    def tplog(self, path): return self.cmd(f'tplog {path}')
    def tpflush(self):
        """Flush the trace log; returns the number of hits so far."""
        return int(self.cmd('tpflush'))
    def crashtrace(self, max_steps=200000):
        """Single-step until PC leaves ROM/RAM; returns the harness's report line."""
        return self.cmd(f'crashtrace {max_steps}')
    def reset(self): return self.cmd('reset')
    def alive(self):
        """True if the game looks alive: PC in ROM/RAM, or in the BIOS with the IRQ vector intact."""
        pc = self.pc()
        if 0x8000000 <= pc < 0x9000000 or 0x2000000 <= pc < 0x3008000: return True
        return pc < 0x4000 and self.rd32(0x3007ffc) == 0x080000f0

if __name__ == '__main__':
    import sys
    e = Emu(sys.argv[1])
    e.run(300)
    print(e.shot(sys.argv[2] if len(sys.argv) > 2 else 'shot.png'))
    e.close()
