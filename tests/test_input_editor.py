from orb1t.input_editor import InputBuffer, KeyParser


def test_input_buffer_basic_edit():
    b = InputBuffer()
    b.insert('hello')
    assert b.text == 'hello'
    b.backspace()
    assert b.text == 'hell'
    b.left(); b.left(); b.insert('X')
    assert b.text == 'heXll'
    b.home(); b.insert('>')
    assert b.text == '>heXll'
    b.end(); b.insert('!')
    assert b.text == '>heXll!'


def test_input_buffer_multiline():
    b = InputBuffer()
    b.insert('hello')
    b.newline()
    b.insert('world')
    assert b.text == 'hello\nworld'
    assert b.row == 1 and b.col == 5
    b.home(); b.backspace()
    assert b.text == 'helloworld'
    assert b.row == 0


def test_keyparser_shift_enter_variants():
    p = KeyParser()
    assert [e.kind for e in p.feed(b'\x1b[13;2u')] == ['shift_enter']
    p = KeyParser()
    assert [e.kind for e in p.feed(b'\x1b\r')] == ['shift_enter']
    p = KeyParser()
    assert [e.kind for e in p.feed(b'\x1b[27;2;13~')] == ['shift_enter']


def test_keyparser_arrows_and_delete():
    p = KeyParser()
    ev = p.feed(b'\x1b[A\x1b[B\x1b[C\x1b[D\x1b[3~')
    assert [e.kind for e in ev] == ['up','down','right','left','delete']


def test_keyparser_mouse_wheel():
    p = KeyParser()
    ev = p.feed(b'\x1b[<64;10;5M\x1b[<65;10;5M')
    assert [e.kind for e in ev] == ['scroll_up', 'scroll_down']


def test_keyparser_ignores_unknown_csi():
    p = KeyParser()
    ev = p.feed(b'\x1b[?1000hhello')
    # unknown CSI ignored, text remains
    kinds = [e.kind for e in ev]
    assert 'char' in kinds
    assert ''.join(e.value for e in ev if e.kind=='char') == 'hello'
