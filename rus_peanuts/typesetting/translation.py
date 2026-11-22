"""Перевод (.txt): сначала Реплики (с тире), в конце — Звуки (без тире).

Звуки — строки без тире в самом конце файла. Строка без тире, после которой
ещё есть Реплики, — тоже Реплика (например, крик в Бабле, записанный без тире).
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
    dash: bool = True       # в файле строка начиналась с тире


def parse(text: str) -> list[Line]:
    raw = []
    for line in text.split("\n"):
        s = line.strip()
        if not s or _DATE.match(s) or s.startswith("(") or s.startswith("*"):
            continue
        if s.startswith("-"):
            raw.append((s.lstrip("- ").strip(), True))
        else:
            raw.append((s, False))
    sounds_from = len(raw)
    while sounds_from > 0 and not raw[sounds_from - 1][1]:
        sounds_from -= 1
    return [Line(text, is_reply=k < sounds_from, dash=dash) for k, (text, dash) in enumerate(raw)]


def replies_without_dash(lines: list[Line]) -> list[Line]:
    """Строки без тире не в конце Перевода: по правилу они стали Репликами."""
    return [ln for ln in lines if ln.is_reply and not ln.dash]


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
