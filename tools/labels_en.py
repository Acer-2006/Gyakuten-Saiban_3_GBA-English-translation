#!/usr/bin/env python3
"""English choice-menu labels.

The DS build stores the option labels as pre-rendered button textures (a pack of LZ images in
data.bin) and selects them through two arm9 tables: a menu table of (chapter, section|0x80) and a
per-language table of three texture indices per menu.  The tables are read from the DS ROM at
build time; the texts below are the transcription of the English textures (index -> text).
"""
import struct

DS_MENU_TABLE = 0x20ad128     # 90 x {u8 chapter, u8, u16 section|0x80, u8, u8}
DS_MENU_COUNT = 90
DS_INDEX_PTRS = 0x20ad120     # u32[2]: per-language u16[90*3] texture indices (0xffff = none)
DS_CHAPTER_IDX = 0x20a1c44    # u32[]: DS chapter -> script bank pair index (bank = 2*idx + lang)
DS_ARM9_BASE = 0x2000000

LABELS = {
    0: "Asphyxiation", 1: "Electrocution", 2: "Hypothermia", 3: "I can handle it myself.",
    4: "I need some help.", 5: "About timing of the meeting", 6: "About Pharmacology Dept.",
    7: "Forget about it", 8: "Establish murder method", 9: "Can't right now",
    10: "Ask for more details", 11: "Leave it alone", 12: "Of course it's important!",
    13: "Of course it's not important!", 14: "Show contradiction", 15: "Press for more details",
    16: "She didn't hear anything.", 17: "She was listening to music.", 18: "There was lightning.",
    19: "Wait and see", 20: "Keep pressing", 21: "Press further", 22: "Back off",
    23: "she's madly in love with you.", 24: "because of that necklace.", 25: "to keep you quiet.",
    26: "Take his case", 27: "Refuse his case", 28: "fast asleep.", 29: "using the bathroom.",
    30: "unconscious.", 31: "Press harder", 32: "Leave it", 33: "That's enough",
    34: "About the sensor", 35: "About the computer", 36: "\"You were blinded?\"",
    37: "\"Atmey Fighting Style?\"", 38: "It was a waste of time.", 39: "It was very important.",
    40: "Mr. Atmey is no Ace Detective!", 41: "this Mr. Atmey is a fake!",
    42: "Mr. Atmey is Mask☆DeMasque!", 43: "is right here!", 44: "has yet to be found!",
    45: "I've got all I need.", 46: "I don't have a thing.", 47: "Testify about what I saw",
    48: "Show fingerprints on the urn", 49: "I can't prove anything yet", 50: "Name another person",
    51: "Think it over again", 52: "No, I have no evidence.", 53: "Yes, I have evidence.",
    54: "Life after being fired", 55: "Why he was fired", 56: "Don't say anything",
    57: "Not especially.", 58: "Yes, he would.", 59: "I can prove it alright.",
    60: "I'm not ready yet.", 61: "They didn't mean to.", 62: "To call the security guard.",
    63: "To find out what it did.", 64: "Name the accomplice", 65: "Give it up",
    66: "You bet there is.", 67: "Not that I can see.", 68: "an Ace Detective.",
    69: "Mask☆DeMasque.", 70: "a blackmailer.", 71: "can prove it.", 72: "can't prove it.",
    73: "Prove with evidence", 74: "Can't prove it", 75: "Ask about the prescription bag",
    76: "Ask about his health insurance", 77: "Push the medication issue", 78: "Ask about the straps",
    79: "Ask about the waitress's back", 80: "Cut in", 81: "Suck it up", 82: "Mr. Kudo made a mistake.",
    83: "The ear doctor made a mistake.", 84: "The victim was a phony.", 85: "Don't ask anything.",
    86: "How many minutes after?", 87: "What time was it?", 88: "Outside Trés Bien",
    89: "Inside Trés Bien", 90: "Start over", 91: "Present more evidence",
    92: "Pick another location", 93: "Ask about what Maggey did", 94: "Ask how things would've been",
    95: "Have it amended", 96: "Mr. Armstrong's oils.", 97: "the victim's ear medicine.",
    98: "potassium cyanide.", 99: "witness's photo.", 100: "body in the trunk.",
    101: "witness's testimony.", 102: "I'll buy it.", 103: "It doesn't work.",
    104: "she happened to be passing by.", 105: "she put the corpse in herself.",
    106: "she is the owner of the car.", 107: "Press her harder", 108: "Have it added to the testimony",
    109: "It's not important", 110: "It's important", 111: "Stop here", 112: "It's flawless.",
    113: "There is a contradiction.", 114: "Not right now.", 115: "Why didn't you call anyone?",
    116: "Why did you go to the bridge?", 117: "Look at the sketch", 118: "Yes, I can.",
    119: "No, it is impossible.", 120: "You were at Hazakura Temple.", 121: "You were at the Inner Temple.",
    122: "There were two of you.", 123: "Play forensics expert", 124: "Save it for later",
    125: "No problem", 126: "There is one thing...", 127: "Forget it", 128: "About the snowmobile",
    129: "About the tracks", 130: "It's very important.", 131: "It's not important.",
    132: "evidence of nothing.", 133: "a complete contradiction.", 134: "exactly what happened.",
    135: "Rethink things", 136: "Point to something else", 137: "Present another piece",
    138: "Not a chance", 139: "There was one...", 140: "in the Inner Temple.",
    141: "in Hazakura Temple.", 142: "in this very courtroom.", 143: "Leave her alone",
    144: "What did she scream?", 145: "\"My last hope\"", 146: "Wait and see",
    147: "The killer wrote it.", 148: "To pin the crime on Maya.", 149: "The killer didn't notice it.",
    150: "Cheering Pearls up", 151: "Godot's investigation", 152: "There's a contradiction.",
    153: "That sounds about right.",
}

# text -> script character codes (same encoding as the dialogue text)
def encode(text):
    out = []
    quote_open = True
    for ch in text:
        if '0' <= ch <= '9': out.append(0x80 + ord(ch) - 48)
        elif 'A' <= ch <= 'Z': out.append(0x8a + ord(ch) - 65)
        elif 'a' <= ch <= 'z': out.append(0xa4 + ord(ch) - 97)
        elif ch == ' ': out.append(0x17f)
        elif ch == '.': out.append(0x161)
        elif ch == ',': out.append(0x16f)
        elif ch == "'": out.append(0x173)
        elif ch == '?': out.append(0xbf)
        elif ch == '!': out.append(0xbe)
        elif ch == '"': out.append(0x165 if quote_open else 0x166); quote_open = not quote_open
        elif ch == '☆': out.append(0x17d)
        elif ch == 'é': out.append(0x68b)
        else: raise ValueError('no code for %r' % ch)
    return out

def menu_labels(arm9, gba_menus):
    """Returns {(bank, section): [label codes, ...]} for the GBA script.

    gba_menus: {bank: [section, ...]} (choice menus per chapter bank, in script order).
    A DS 'chapter' covers the banks chap[c] .. chap[c+1]-1; its menu entries are listed in the
    same order as the banks' menus, so entries are matched sequentially by section number."""
    B = DS_ARM9_BASE
    ptr = struct.unpack_from('<2I', arm9, DS_INDEX_PTRS - B)
    idx = struct.unpack_from('<%dH' % (DS_MENU_COUNT * 3), arm9, ptr[1] - B)
    chap = list(struct.unpack_from('<24I', arm9, DS_CHAPTER_IDX - B))
    ents = []
    for k in range(DS_MENU_COUNT):
        e = arm9[DS_MENU_TABLE - B + k * 6: DS_MENU_TABLE - B + k * 6 + 6]
        labels = [encode(LABELS[idx[k * 3 + o]]) for o in range(3) if idx[k * 3 + o] != 0xffff]
        ents.append((e[0], struct.unpack_from('<H', e, 2)[0] - 0x80, labels))
    res = {}
    for c in range(23):
        banks = range(chap[c], chap[c + 1] if c + 1 < 23 else 42)
        ds = [(sec, labels) for (cc, sec, labels) in ents if cc == c]
        want = [(b, s) for b in banks for s in gba_menus.get(b, [])]
        i = 0
        for (b, s) in want:
            if i < len(ds) and ds[i][0] == s:
                res[(b, s)] = ds[i][1]; i += 1
        if i != len(ds): raise ValueError('DS chapter %d: unmatched label entries' % c)
    return res

if __name__ == '__main__':
    import sys
    a9 = open(sys.argv[1], 'rb').read()
    print(len(LABELS), 'labels')
