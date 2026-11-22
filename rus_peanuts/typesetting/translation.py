"""Перевод (.txt): строки с тире — Реплики, без тире — Звуки.

Даты стрипов, Сноски (`* ...`), комментарии в скобках и пустые строки пропускаются.
"""
import re
from dataclasses import dataclass

ENCODINGS = ("utf-8", "windows-1251", "cp1251")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Line:
    """Одна строка Перевода: текст Реплики или Звука."""
    text: str
    is_reply: bool


def parse(text: str) -> list[Line]:
    lines = []
    for raw in text.split("\n"):
        s = raw.strip()
        if not s or _DATE.match(s) or s.startswith("(") or s.startswith("*"):
            continue
        if s.startswith("-"):
            lines.append(Line(s.lstrip("- ").strip(), is_reply=True))
        else:
            lines.append(Line(s, is_reply=False))
    return lines


def read(path) -> list[Line] | None:
    """Читает Перевод в UTF-8 или Windows-1251. None — файл не прочитать или он пустой."""
    for enc in ENCODINGS:
        try:
            with open(path, "r", encoding=enc) as f:
                text = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        return None
    if not text:
        return None
    return parse(text)
