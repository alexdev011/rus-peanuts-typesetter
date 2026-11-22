"""Файл перевода (.txt): один или несколько Переводов, каждый под своей Датой стрипа.

    1963-04-08
    - Привет, Чарли Браун!
    - Как дела?
    Звуки:
    - БАЦ!

    1963-04-09
    -Пока!

Перевод — сначала Реплики, потом строка «Звуки:» и Звуки. Строки начинаются с тире;
пробелы вокруг тире и регистр «Звуки:» не важны. Строка, которая начинается с даты
YYYY-MM-DD, открывает Перевод этого стрипа (что после даты — не важно); строки до
первой даты пропускаются. В файле без дат весь файл — один Перевод.

Без строки «Звуки:» работает старое правило: Звуки — строки без тире в самом
конце Перевода, а строка без тире, после которой ещё идут Реплики, — тоже Реплика.
Сноски (`* ...`), комментарии в скобках и пустые строки пропускаются.
"""
import re
from dataclasses import dataclass, field

ENCODINGS = ("utf-8-sig", "windows-1251")
_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_DASH = re.compile(r"^(?:[-–—]\s*)+")  # Word сам меняет «-» на «–», поэтому годится любое тире
_SOUNDS = re.compile(r"^звуки\s*:?$", re.IGNORECASE)


@dataclass(frozen=True)
class Line:
    """Одна строка Перевода: текст Реплики или Звука."""
    text: str
    is_reply: bool
    dash: bool = True       # в файле строка начиналась с тире


@dataclass
class TranslationFile:
    """Файл перевода: Переводы по Датам стрипов, или один Перевод без даты."""
    by_date: dict = field(default_factory=dict)     # дата -> list[Line], в порядке файла
    undated: list | None = None                     # весь файл, если в нём нет ни одной даты
    duplicates: list = field(default_factory=list)  # даты, встретившиеся ещё раз (берётся первый Перевод)

    @property
    def dates(self) -> list[str]:
        return list(self.by_date)

    def for_date(self, date) -> list[Line] | None:
        return self.by_date.get(date)

    def only(self) -> list[Line] | None:
        """Перевод, если он в файле один (без даты или с одной датой); иначе None."""
        if self.undated is not None:
            return self.undated
        return next(iter(self.by_date.values())) if len(self.by_date) == 1 else None


def parse(text: str) -> list[Line]:
    """Один Перевод."""
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


def parse_file(text: str) -> TranslationFile:
    blocks = []             # (дата, строки)
    for line in text.split("\n"):
        m = _DATE.match(line.strip())
        if m:
            blocks.append((m.group(1), []))
        elif blocks:
            blocks[-1][1].append(line)
    if not blocks:
        return TranslationFile(undated=parse(text))
    result = TranslationFile()
    for date, lines in blocks:
        if date in result.by_date:
            result.duplicates.append(date)
        else:
            result.by_date[date] = parse("\n".join(lines))
    return result


def replies_without_dash(lines: list[Line]) -> list[Line]:
    """Реплики, записанные без тире (возможно, забыли строку «Звуки:»)."""
    return [ln for ln in lines if ln.is_reply and not ln.dash]


def read(path) -> TranslationFile | None:
    """Читает Файл перевода в UTF-8 (с BOM или без) или Windows-1251. None — не прочитать или он пустой."""
    for enc in ENCODINGS:
        try:
            with open(path, "r", encoding=enc) as f:
                text = f.read()
            break
        except (UnicodeDecodeError, LookupError, OSError):
            continue
    else:
        return None
    if not text:
        return None
    return parse_file(text)
