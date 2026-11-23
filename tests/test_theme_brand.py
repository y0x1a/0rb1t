from orb1t import brand, theme, ui
from orb1t.theme import THEMES, get_theme


def _lum(hex_color):
    def c(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = theme.hex_rgb(hex_color)
    return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_every_theme_the_command_offers_exists_in_the_tui():
    # /theme lists ui.theme_names(); a name the TUI can't draw silently fell back to purple.
    assert set(ui.theme_names()) <= set(THEMES)
    for n in ui.theme_names():
        assert get_theme(n).name == n


def test_primary_identity_values():
    t = get_theme("purple")
    assert t.ACCENT == "#6D28D9" and t.BG == "#0B0B10"


def test_unknown_theme_and_name_fallbacks():
    assert get_theme("nope").name == "purple"
    assert get_theme("purple", "").APP_NAME == "0rb1t"
    assert get_theme("PURPLE ", "Nova").APP_NAME == "Nova"


def test_accent_text_is_readable_in_every_theme():
    for name in THEMES:
        t = get_theme(name)
        for surface in (t.BG, t.PANEL):
            assert contrast(t.ACCENT_SOFT, surface) >= 4.5, (name, surface)
            assert contrast(t.LAVENDER, surface) >= 4.5, (name, surface)


def test_text_tiers_are_readable_on_both_surfaces():
    t = get_theme("purple")
    for surface in (t.BG, t.PANEL):
        assert contrast(t.TEXT_BRIGHT, surface) >= 12
        assert contrast(t.TEXT, surface) >= 9
        assert contrast(t.MUTED, surface) >= 6
        assert contrast(t.DIM, surface) >= 3.5          # tertiary (hints)
        assert contrast(t.ACCENT_SOFT, surface) >= 4.5  # accent *text*
    assert contrast(t.PANEL, t.BG) > 1.0                # surfaces are distinguishable


def test_style_wraps_and_resets():
    t = get_theme("purple")
    assert t.style("x") == "x"
    s = t.style("x", fg="#010203", bg="#040506", bold=True)
    assert s.startswith("\x1b[1m") and "38;2;1;2;3" in s and "48;2;4;5;6" in s and s.endswith("\x1b[0m")


def test_wordmark_is_compiled_from_pixels():
    assert len(brand.LOGO) == 3 and len({len(r) for r in brand.LOGO}) == 1
    assert brand.LOGO_WIDTH == len(brand.LOGO[0]) <= 30
    assert set("".join(brand.LOGO)) <= set(" ▀▄█")
    assert brand.compile_wordmark("0")[1] == "█ █ █"          # the nucleus
    assert brand.LOGO == brand.compile_wordmark("0rb1t")
    assert ui.LOGO.splitlines() == list(brand.LOGO)            # legacy ui shares the one logo


def test_comet_is_one_braille_cell_per_frame():
    assert len(brand.COMET) == 8 and len(set(brand.COMET)) == 8
    assert all(0x2800 <= ord(c) <= 0x28FF for c in brand.COMET)
