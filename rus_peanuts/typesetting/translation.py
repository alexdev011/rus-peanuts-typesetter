"""Перевод (.txt): сначала Реплики, потом строка «Звуки:» и Звуки.

    - Привет, Чарли Браун!
    - Как дела?
    Звуки:
    - БАЦ!

Строки начинаются с тире; пробелы вокруг тире и регистр «Звуки:» не важны.
Без строки «Звуки:» работает старое правило: Звуки — строки без тире в самом
конце файла, а строка без тире, после которой ещё идут Реплики, — тоже Реплика.
Даты стрипов, Сноски (`* ...`), комментарии в скобках и пустые строки пропускаются.
"""
import re
from dataclasses import dataclass

ENCODINGS = ("utf-8-sig", "windows-1251")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_DASH = re.compile(r"^(?:[-–—]\s*)+")  # Word сам меняет «-» на «–», поэтому годится любое тире
_SOUNDS = re.compile(r"^звуки\s*:?$", re.IGNORECASE)


@dataclass(frozen=True)
class Line:
    """Одна строка Перевода: текст Реплики или Звука."""
    text: str
    is_reply: bool
    dash: bool = True       # в файле строка начиналась с тире


def parse(text: str) -> list[Line]:
    raw = []                # (текст, было ли тире)
    sounds_from = None      # номер первой строки после «Звуки:»
    for line in text.split("\n"):
        s = line.strip()
        if not s or _DATE.match(s) or s.startswith("(") or s.startswith("*"):
            continue
        if _SOUNDS.match(s):
            sounds_from = len(raw) if sounds_from is None else sounds_from
            continue
        dash = _DASH.match(s)
        body = s[dash.end():].strip() if dash else s
        if body:
            raw.append((body, bool(dash)))
    if sounds_from is None:  # старое правило: звуки — строки без тире в конце
        sounds_from = len(raw)
        while sounds_from > 0 and not raw[sounds_from - 1][1]:
            sounds_from -= 1
    return [Line(text, is_reply=k < sounds_from, dash=dash) for k, (text, dash) in enumerate(raw)]


def replies_without_dash(lines: list[Line]) -> list[Line]:
    """Реплики, записанные без тире (возможно, забыли строку «Звуки:»)."""
    return [ln for ln in lines if ln.is_reply and not ln.dash]


def read(path) -> list[Line] | None:
    """Читает Перевод в UTF-8 (с BOM или без) или Windows-1251. None — файл не прочитать или он пустой."""
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
