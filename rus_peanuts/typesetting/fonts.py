"""Набор шрифтов: шрифты, из которых для каждого Текстового блока выбирается свой.

Шрифты — файлы .ttf/.otf в папке `fonts` программы (и во встроенной в .exe).
Команда добавляет свои шрифты туда же — меню «Шрифты → Добавить шрифты…».

Шрифт блока хранится как PostScript-имя: по нему Фотошоп находит шрифт в PSD,
и оно же записывается в файл проекта. В Qt каждый файл регистрируется под
собственным уникальным именем семейства — иначе Qt путает начертания одного
семейства (например, MP Manga Bold и MP Manga Bold Shadow).
"""
import os
import shutil
import struct
import sys
from dataclasses import dataclass

from PyQt6.QtCore import QByteArray
from PyQt6.QtGui import QFontDatabase

# Шрифт реплик: им по умолчанию набирается каждый новый Текстовый блок
DEFAULT_FONT = "PeanutsRusbyme-Regular"
FALLBACK_FAMILY = "Comic Sans MS"  # если шрифта нет в Наборе
FONT_EXTENSIONS = (".ttf", ".otf")


@dataclass(frozen=True)
class FontFace:
    postscript: str     # ключ шрифта: в блоке, в проекте и в PSD
    name: str           # как показывать в списке
    family: str         # уникальное имя семейства в Qt


class FontLibrary:
    """Набор шрифтов. `folder` — куда «Добавить шрифты…» копирует новые файлы."""

    def __init__(self, folder: str | None = None):
        self.folder = folder
        self._faces: dict[str, FontFace] = {}

    @property
    def faces(self) -> list[FontFace]:
        return sorted(self._faces.values(), key=lambda f: f.name.lower())

    @property
    def default(self) -> str:
        return DEFAULT_FONT

    def get(self, postscript: str) -> FontFace | None:
        return self._faces.get(postscript)

    def family(self, postscript: str) -> str:
        """Семейство Qt для шрифта блока; неизвестный шрифт показывается Шрифтом реплик."""
        face = self._faces.get(postscript) or self._faces.get(DEFAULT_FONT)
        return face.family if face else FALLBACK_FAMILY

    def add_file(self, path) -> FontFace | None:
        """Регистрирует файл шрифта. None — файл не читается как шрифт."""
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError:
            return None
        stem = os.path.splitext(os.path.basename(path))[0]
        postscript = postscript_name(raw) or stem
        if postscript in self._faces:
            return self._faces[postscript]
        # Нейтральное имя семейства: без слов вроде Bold и без общего начала с другими. Иначе
        # Windows отрезает «-Bold» и сводит MP Manga Bold и MP Manga Bold Shadow в одно семейство.
        family = f"RusPeanutsFace{len(self._faces) + 1:03d}"
        fid = QFontDatabase.addApplicationFontFromData(QByteArray(rename_ttf_family(raw, family)))
        families = QFontDatabase.applicationFontFamilies(fid) if fid != -1 else []
        if not families:
            return None
        # Имена внутри шрифтов часто бестолковы (у MP Manga Shadow нет слова Shadow),
        # поэтому в списке шрифт называется как его файл — его легко переименовать.
        face = FontFace(postscript=postscript, name=stem.replace("_", " "), family=families[0])
        self._faces[postscript] = face
        return face

    def install(self, path) -> FontFace | None:
        """Копирует файл шрифта в папку Набора и регистрирует его.

        None — файл не шрифт (тогда он и не копируется). OSError — не удалось скопировать.
        """
        if not self.folder:
            return self.add_file(path)
        with open(path, "rb") as f:
            if postscript_name(f.read()) is None:
                return None
        os.makedirs(self.folder, exist_ok=True)
        target = os.path.join(self.folder, os.path.basename(path))
        if os.path.normcase(os.path.abspath(path)) != os.path.normcase(os.path.abspath(target)):
            shutil.copyfile(path, target)
        return self.add_file(target)


def program_dir() -> str:
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def default_search_dirs() -> list[str]:
    """Папки со шрифтами: встроенная в .exe, рядом с программой, в текущей папке."""
    dirs = []
    if hasattr(sys, "_MEIPASS"):
        dirs.append(os.path.join(sys._MEIPASS, "fonts"))
    dirs.append(os.path.join(program_dir(), "fonts"))
    dirs.append(os.path.abspath("fonts"))
    return dirs


def load_fonts(search_dirs=None, folder=None) -> FontLibrary:
    """Собирает Набор шрифтов из папок. Нужен уже созданный QApplication.

    `folder` — куда добавлять новые шрифты (по умолчанию `fonts` рядом с программой).
    """
    library = FontLibrary(folder if folder is not None else os.path.join(program_dir(), "fonts"))
    seen = set()
    for d in (search_dirs if search_dirs is not None else default_search_dirs()):
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            path = os.path.normcase(os.path.normpath(os.path.join(d, fname)))
            if fname.lower().endswith(FONT_EXTENSIONS) and path not in seen:
                seen.add(path)
                library.add_file(os.path.join(d, fname))
    return library


def _tables(ttf_bytes: bytes) -> dict:
    if len(ttf_bytes) < 12:
        return {}
    num_tables = struct.unpack(">H", ttf_bytes[4:6])[0]
    tables = {}
    for i in range(num_tables):
        pos = 12 + 16 * i
        tag = ttf_bytes[pos:pos + 4].decode("latin1")
        offset, length = struct.unpack(">II", ttf_bytes[pos + 8:pos + 16])
        tables[tag] = ttf_bytes[offset:offset + length]
    return tables


def postscript_name(ttf_bytes: bytes):
    """PostScript-имя шрифта (запись 6 таблицы 'name') или None."""
    try:
        name = _tables(ttf_bytes).get("name")
        if not name:
            return None
        count, string_offset = struct.unpack(">HH", name[2:6])
        for r in range(count):
            pid, eid, lid, nid, length, offset = struct.unpack(">HHHHHH", name[6 + 12 * r:18 + 12 * r])
            if nid == 6:
                raw = name[string_offset + offset:string_offset + offset + length]
                text = raw.decode("utf-16-be", "ignore") if pid in (0, 3) else raw.decode("latin1")
                if text:
                    return text
    except struct.error:
        pass
    return None


def rename_ttf_family(ttf_bytes: bytes, new_family: str) -> bytes:
    """Переименовывает family/subfamily в таблице 'name' TTF-файла в памяти."""
    if len(ttf_bytes) < 12:
        return ttf_bytes
    sfnt_version, num_tables, search_range, entry_selector, range_shift = struct.unpack(">IHHHH", ttf_bytes[:12])
    if sfnt_version not in (0x00010000, 0x4F54544F):
        return ttf_bytes

    tables = {}
    table_order = []
    pos = 12
    for _ in range(num_tables):
        tag = ttf_bytes[pos:pos + 4].decode("latin1")
        checksum, offset, length = struct.unpack(">III", ttf_bytes[pos + 4:pos + 16])
        tables[tag] = ttf_bytes[offset:offset + length]
        table_order.append(tag)
        pos += 16

    if "name" not in tables:
        return ttf_bytes

    ps_name = "".join(ch for ch in new_family if ch.isalnum() or ch in "-_")
    entries_spec = [
        (1, new_family),
        (2, "Regular"),
        (4, new_family),
        (6, ps_name),
        (16, new_family),
        (17, "Regular"),
    ]

    records = []
    str_data = bytearray()
    for nid, text in entries_spec:
        enc = text.encode("ascii", errors="ignore")
        records.append((1, 0, 0, nid, len(enc), len(str_data)))
        str_data.extend(enc)
    for nid, text in entries_spec:
        enc = text.encode("utf-16-be")
        records.append((3, 1, 0x0409, nid, len(enc), len(str_data)))
        str_data.extend(enc)

    records.sort(key=lambda r: (r[0], r[1], r[2], r[3]))
    string_offset = 6 + len(records) * 12
    new_name = bytearray(struct.pack(">HHH", 0, len(records), string_offset))
    for r in records:
        new_name.extend(struct.pack(">HHHHHH", *r))
    new_name.extend(str_data)
    tables["name"] = bytes(new_name)

    def calc_checksum(data: bytes) -> int:
        pad = (4 - (len(data) % 4)) % 4
        padded = data + b"\x00" * pad
        total = 0
        for i in range(0, len(padded), 4):
            total = (total + struct.unpack(">I", padded[i:i + 4])[0]) & 0xFFFFFFFF
        return total

    if "head" in tables and len(tables["head"]) >= 12:
        head_ba = bytearray(tables["head"])
        head_ba[8:12] = b"\x00\x00\x00\x00"
        tables["head"] = bytes(head_ba)

    out = bytearray(struct.pack(">IHHHH", sfnt_version, num_tables, search_range, entry_selector, range_shift))
    dir_pos = len(out)
    out.extend(b"\x00" * (num_tables * 16))

    head_file_offset = None
    for idx, tag in enumerate(table_order):
        data = tables[tag]
        offset = len(out)
        if tag == "head":
            head_file_offset = offset
        csum = calc_checksum(data)
        entry = tag.encode("latin1") + struct.pack(">III", csum, offset, len(data))
        out[dir_pos + idx * 16: dir_pos + (idx + 1) * 16] = entry
        out.extend(data)
        pad = (4 - (len(data) % 4)) % 4
        if pad:
            out.extend(b"\x00" * pad)

    if head_file_offset is not None:
        whole_csum = calc_checksum(bytes(out))
        adj = (0xB1B0AFBA - whole_csum) & 0xFFFFFFFF
        out[head_file_offset + 8: head_file_offset + 12] = struct.pack(">I", adj)

    return bytes(out)
