"""Parse OP.GG MCP tool output.

Most tools reply in a custom "class definitions + positional constructor calls"
text format instead of JSON. Example:

    class LolGetChampionAnalysis: champion,data
    class Data: core_items,boots

    LolGetChampionAnalysis("ANNIE",Data(CoreItems(["a","b"],1026,0.19),...))

Constructor arguments are positional and map 1:1 (zip) onto the fields declared
in the matching class line. Some tools (e.g. esports schedules) reply with
plain JSON, so JSON is tried first.
"""

from __future__ import annotations

import json
import re

_CLASS_RE = re.compile(r"class\s+([A-Za-z_]\w*)\s*:\s*(.*)$")
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_NUM_RE = re.compile(
    r"[-+]?(?:\d+\.\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?|\d+[eE][-+]?\d+|\d+)"
)
_WS = " \t\r\n"
_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


class ParseError(ValueError):
    pass


class _Parser:
    def __init__(self, text: str, classes: dict[str, list[str]]):
        self.s = text
        self.i = 0
        self.classes = classes

    def parse(self):
        self._skip_ws()
        value = self._value()
        self._skip_ws()
        if self.i < len(self.s):
            raise ParseError(f"trailing input at offset {self.i}")
        return value

    def _skip_ws(self) -> None:
        while self.i < len(self.s) and self.s[self.i] in _WS:
            self.i += 1

    def _value(self):
        self._skip_ws()
        if self.i >= len(self.s):
            raise ParseError("unexpected end of input")
        c = self.s[self.i]
        if c == '"':
            return self._string()
        if c == "[":
            return self._list()
        if c == "{":
            return self._object()
        if c.isdigit() or c in "-+":
            return self._number()
        m = _IDENT_RE.match(self.s, self.i)
        if not m:
            raise ParseError(f"unexpected character {c!r} at offset {self.i}")
        word = m.group(0)
        j = self.i + len(word)
        k = j
        while k < len(self.s) and self.s[k] in _WS:
            k += 1
        if k < len(self.s) and self.s[k] == "(":
            return self._call(word, k)
        self.i = j
        if word == "null":
            return None
        if word == "true":
            return True
        if word == "false":
            return False
        return word

    def _call(self, name: str, paren_pos: int) -> dict:
        self.i = paren_pos + 1
        args = []
        self._skip_ws()
        if self.i < len(self.s) and self.s[self.i] == ")":
            self.i += 1
        else:
            while True:
                args.append(self._value())
                self._skip_ws()
                if self.i >= len(self.s):
                    raise ParseError(f"unterminated call to {name}")
                c = self.s[self.i]
                self.i += 1
                if c == ",":
                    continue
                if c == ")":
                    break
                raise ParseError(f"expected ',' or ')' at offset {self.i - 1} in {name}")
        fields = self.classes.get(name)
        if fields is None:
            return {"_class": name, "args": args}
        # Positional zip: extra args are ignored, missing fields become null.
        result: dict = {"_class": name}
        for idx, field in enumerate(fields):
            result[field] = args[idx] if idx < len(args) else None
        return result

    def _list(self) -> list:
        self.i += 1
        items = []
        self._skip_ws()
        if self.i < len(self.s) and self.s[self.i] == "]":
            self.i += 1
            return items
        while True:
            items.append(self._value())
            self._skip_ws()
            if self.i >= len(self.s):
                raise ParseError("unterminated list")
            c = self.s[self.i]
            self.i += 1
            if c == ",":
                continue
            if c == "]":
                return items
            raise ParseError(f"expected ',' or ']' at offset {self.i - 1}")

    def _object(self) -> dict:
        self.i += 1
        obj = {}
        self._skip_ws()
        if self.i < len(self.s) and self.s[self.i] == "}":
            self.i += 1
            return obj
        while True:
            self._skip_ws()
            if self.i >= len(self.s) or self.s[self.i] != '"':
                raise ParseError(f"expected string key at offset {self.i}")
            key = self._string()
            self._skip_ws()
            if self.i >= len(self.s) or self.s[self.i] != ":":
                raise ParseError(f"expected ':' at offset {self.i}")
            self.i += 1
            obj[key] = self._value()
            self._skip_ws()
            if self.i >= len(self.s):
                raise ParseError("unterminated object")
            c = self.s[self.i]
            self.i += 1
            if c == ",":
                continue
            if c == "}":
                return obj
            raise ParseError(f"expected ',' or '}}' at offset {self.i - 1}")

    def _number(self):
        m = _NUM_RE.match(self.s, self.i)
        if not m:
            raise ParseError(f"invalid number at offset {self.i}")
        token = m.group(0)
        self.i = m.end()
        if any(ch in token for ch in ".eE"):
            return float(token)
        return int(token)

    def _string(self) -> str:
        self.i += 1  # opening quote
        out: list[str] = []
        while True:
            if self.i >= len(self.s):
                raise ParseError("unterminated string")
            c = self.s[self.i]
            if c == '"':
                self.i += 1
                return "".join(out)
            if c == "\\":
                self.i += 1
                if self.i >= len(self.s):
                    raise ParseError("unterminated escape")
                e = self.s[self.i]
                if e == "u":
                    cp = int(self.s[self.i + 1 : self.i + 5], 16)
                    self.i += 5
                    if 0xD800 <= cp <= 0xDBFF and self.s[self.i : self.i + 2] == "\\u":
                        low = int(self.s[self.i + 2 : self.i + 6], 16)
                        if 0xDC00 <= low <= 0xDFFF:
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (low - 0xDC00)
                            self.i += 6
                    out.append(chr(cp))
                else:
                    out.append(_ESCAPES.get(e, e))
                    self.i += 1
            else:
                out.append(c)
                self.i += 1


def _split_sections(text: str) -> tuple[dict[str, list[str]], str]:
    classes: dict[str, list[str]] = {}
    instance_start = None
    for idx, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        m = _CLASS_RE.match(stripped)
        if m:
            classes[m.group(1)] = [f.strip() for f in m.group(2).split(",") if f.strip()]
        else:
            instance_start = idx
            break
    if instance_start is None:
        raise ParseError("no instance section found")
    instance_text = "".join(line.strip() for line in text.splitlines()[instance_start:])
    return classes, instance_text


def parse_response(text: str):
    """Parse an MCP tool text response into a dict/list of plain Python values."""
    stripped = (text or "").strip()
    if not stripped:
        raise ParseError("empty response")
    try:
        return json.loads(stripped)
    except ValueError:
        pass
    classes, instance_text = _split_sections(stripped)
    return _Parser(instance_text, classes).parse()
