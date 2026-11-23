"""0rb1t brand assets: wordmark, tagline and the orbit "comet" spinner.

The wordmark is authored as a 6px-tall pixel font and compiled to three rows of
half-blocks (``▀ ▄ █``).  Keeping the source as pixels means the logo stays
editable as data and is verifiable in tests, instead of being a fragile blob of
hand-aligned block characters.

The zero carries a "nucleus" (the 2px bar in its centre): an orbit with
something at the middle.  That is the one distinctive mark in the identity.
"""

from __future__ import annotations

# 6 rows per glyph.  "#" = lit pixel.
GLYPHS: dict[str, tuple[str, ...]] = {
    "0": (".###.", "#...#", "#.#.#", "#.#.#", "#...#", ".###."),
    "r": ("....", "....", "#.##", "##..", "#...", "#..."),
    "b": ("#...", "#...", "###.", "#..#", "#..#", "###."),
    "1": (".#.", "##.", ".#.", ".#.", ".#.", "###"),
    "t": (".#..", ".#..", "####", ".#..", ".#..", "..##"),
}

_HALF = {(True, True): "█", (True, False): "▀", (False, True): "▄", (False, False): " "}


def compile_wordmark(word: str, gap: int = 1) -> tuple[str, ...]:
    """Compile ``word`` from :data:`GLYPHS` into half-block rows."""
    glyphs = [GLYPHS[c] for c in word]
    px = [("." * gap).join(g[r] for g in glyphs) for r in range(6)]
    rows = []
    for i in range(0, 6, 2):
        rows.append("".join(_HALF[(a == "#", b == "#")] for a, b in zip(px[i], px[i + 1])))
    return tuple(rows)


NAME = "0rb1t"
LOGO: tuple[str, ...] = compile_wordmark(NAME)
LOGO_WIDTH: int = len(LOGO[0])
TAGLINE = "terminal intelligence environment"

# One braille dot orbiting the perimeter of a cell, with a two-dot tail.
COMET = "⠉⠘⠰⢠⣀⡄⠆⠃"
