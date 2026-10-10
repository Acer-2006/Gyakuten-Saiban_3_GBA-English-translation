#!/usr/bin/env python3
"""Build context: reads the two game ROMs and prepares everything the patches need.

All game data (script, font, graphics, voices) is taken from the user's own cartridge images
each time the ROM is built.  The exceptions, typed in by hand: the English choice-menu options
(tools/labels_en.py; the DS has them only as pictures), the words on the buttons the build draws
itself (Press, Present, OK, Back, the investigation tabs) and the save screen's note, and the DS
lines reworded for the GBA's buttons (convert_script.GBA_WORDING).
"""
import os, sys, struct, zlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz, nitrofs
from mes import load_bank

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GBA_CRC = 0x51b6cf22          # Gyakuten Saiban 3 (Japan)  A3JJ
NDS_CODE = b'YG3E'            # Phoenix Wright: Ace Attorney - Trials and Tribulations (USA)
GBA_COMMON_BANK = 0x6e3578    # uncompressed common script bank in the GBA ROM
GBA_COMMON_SIZE = 0x264c      # ends where chapter bank 0 begins

class BuildContext:
    def __init__(self, gba_path, nds_path, verbose=True):
        self.log = print if verbose else (lambda *a, **k: None)
        self.gba = open(gba_path, 'rb').read()
        if len(self.gba) != 0x800000 or zlib.crc32(self.gba) & 0xffffffff != GBA_CRC:
            raise SystemExit(f'{gba_path}: not the expected Gyakuten Saiban 3 (Japan) ROM '
                             f'(size {len(self.gba)}, CRC32 {zlib.crc32(self.gba) & 0xffffffff:#010x})')
        nds = open(nds_path, 'rb').read()
        if nds[0xc:0x10] != NDS_CODE:
            raise SystemExit(f'{nds_path}: not the expected Trials and Tribulations (USA) ROM (game code {nds[0xc:0x10]!r})')
        self.log('reading the DS ROM...')
        self.ds = nitrofs.files(nds)          # name -> bytes (data.bin, mes_all.bin, sound_data.sdat, ...)
        a9o, _, _, a9s = struct.unpack_from('<IIII', nds, 0x20)
        self.arm9 = nds[a9o:a9o + a9s]
        self.data = self.ds['data.bin']
        self.sdat = self.ds['sound_data.sdat']
        # DS script banks (86: JP/EN pairs for 42 chapters, then JP/EN common)
        m = self.ds['mes_all.bin']
        n = struct.unpack_from('<I', m, 0)[0]
        ents = [struct.unpack_from('<II', m, 4 + i * 8) for i in range(n)]     # (offset, size)
        self.ds_banks = [lz.decompress(m, o)[0] for o, sz in ents]
        assert len(self.ds_banks) == 86, len(self.ds_banks)
        # GBA script banks (44 LZ-compressed chapter banks) + the raw common bank
        self.log('decompressing the GBA script...')
        table = json.load(open(os.path.join(ROOT, 'data/gba_mes_table.json')))
        self.gba_table = table
        self.gba_banks = {}
        for t in table:
            dec, used = lz.decompress(self.gba, t['rom_off'])
            assert len(dec) == t['dec_size'], (t, len(dec))
            self.gba_banks[t['idx']] = dec
        self.gba_common = self.gba[GBA_COMMON_BANK:GBA_COMMON_BANK + GBA_COMMON_SIZE]
        self.en_banks = None      # filled by convert()

    def convert(self):
        """Three-way script merge -> English banks (dict idx -> bytes, 'common' -> bytes)."""
        import convert_script
        self.log('converting the script (this takes a minute)...')
        self.en_banks, stats = convert_script.run_mem(self)
        self.log('  ' + ', '.join(f'{k} {v}' for k, v in sorted(stats.items())))
        return self.en_banks
