"""All patches, applied in order."""
def apply_all(rom, ctx):
    from . import text, script, graphics, court_record, ui, banners, shouts, topics, episodes, verdict, pictures, datascreen, voices
    text.apply(rom, ctx)
    script.apply(rom, ctx)
    graphics.apply(rom, ctx)
    court_record.apply(rom, ctx)
    ui.apply(rom, ctx)
    banners.apply(rom, ctx)
    shouts.apply(rom, ctx)
    topics.apply(rom, ctx)
    episodes.apply(rom, ctx)
    verdict.apply(rom, ctx)
    pictures.apply(rom, ctx)
    datascreen.apply(rom, ctx)
    voices.apply(rom, ctx)
