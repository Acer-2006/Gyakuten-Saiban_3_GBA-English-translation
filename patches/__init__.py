"""All patches, applied in order."""
def apply_all(rom, ctx):
    from . import text, script, graphics, voices
    text.apply(rom, ctx)
    script.apply(rom, ctx)
    graphics.apply(rom, ctx)
    voices.apply(rom, ctx)
