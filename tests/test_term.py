from orb1t.term import _strip_control_sequences


def test_strip_csi_arrows_and_mouse():
    assert _strip_control_sequences("\x1b[A\x1b[B\x1b[C\x1b[D") == ""
    assert _strip_control_sequences("\x1b[<64;10;5M\x1b[<65;10;5M") == ""


def test_strip_keeps_text():
    assert _strip_control_sequences("hello\x1b[A world") == "hello world"
    assert _strip_control_sequences("plain") == "plain"


def test_strip_osc_and_ss3():
    assert _strip_control_sequences("\x1b]0;title\x07abc") == "abc"
    assert _strip_control_sequences("\x1bOA") == ""
