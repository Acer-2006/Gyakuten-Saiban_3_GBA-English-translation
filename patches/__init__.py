"""All patches, applied in order."""
def apply_all(rom, ctx):
    from . import text, script, graphics, court_record, voices
    text.apply(rom, ctx)
    script.apply(rom, ctx)
    graphics.apply(rom, ctx)
    court_record.apply(rom, ctx)
    voices.apply(rom, ctx)
