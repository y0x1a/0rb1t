import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

_POS = re.compile(r"\x1b\[(\d+);1H")
_SGR = re.compile(r"\x1b\[[0-9;]*m")


def split_rows(frame: str) -> list[str]:
    """Split a frame into the text painted on each absolute-positioned row."""
    parts = _POS.split(frame)
    # parts: [prefix, rownum, text, rownum, text, ...]
    return [parts[i + 1] for i in range(1, len(parts), 2)]


def plain(line: str) -> str:
    return _SGR.sub("", line)
