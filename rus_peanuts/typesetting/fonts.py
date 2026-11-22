"""Шрифты вёрстки: Шрифт реплик и Шрифт звуков (Shadow и сплошное начертание).

Файлы шрифтов ищутся рядом с программой и в системных папках Windows.
Перед регистрацией в Qt семейство каждого шрифта переименовывается прямо
в памяти, чтобы Qt не путал Shadow и обычный Bold одного семейства.
"""
import os
import struct
import sys
from dataclasses import dataclass

from PyQt6.QtCore import QByteArray
from PyQt6.QtGui import QFontDatabase

_UNIQUE_FAMILIES = {
    "reply": "RusPeanuts_Dialogue",
    "sound": "RusPeanuts_MangaSolid",
    "sound_shadow": "RusPeanuts_MangaShadow",
}


@dataclass(frozen=True)
class Fonts:
    """Имена семейств Qt для каждого шрифта вёрстки."""
    reply: str = "Comic Sans MS"
    sound: str = "Arial Black"
    sound_shadow: str = "Arial Black"

    def family(self, is_reply: bool, shadow: bool) -> str:
        if is_reply:
            return self.reply
        return self.sound_shadow if shadow else self.sound


def default_search_dirs() -> list[str]:
    dirs = []
    if hasattr(sys, "_MEIPASS"):
        dirs.append(os.path.join(sys._MEIPASS, "fonts"))
        dirs.append(sys._MEIPASS)
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    dirs.extend([
        os.path.join(exe_dir, "fonts"),
        exe_dir,
        os.path.abspath("fonts"),
        os.path.abspath("."),
    ])
    if os.name == "nt":
        local_app = os.environ.get("LOCALAPPDATA", "")
        win_dir = os.environ.get("WINDIR", "C:\\Windows")
        if local_app:
            dirs.append(os.path.join(local_app, "Microsoft", "Windows", "Fonts"))
        dirs.append(os.path.join(win_dir, "Fonts"))
    return dirs


def load_fonts(search_dirs=None) -> Fonts:
    """Находит и регистрирует шрифты в Qt. Нужен уже созданный QApplication."""
    found = {}

    def register(key, filepath):
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            fid = QFontDatabase.addApplicationFontFromData(QByteArray(rename_ttf_family(raw, _UNIQUE_FAMILIES[key])))
            if fid != -1:
                fams = QFontDatabase.applicationFontFamilies(fid)
                if fams:
                    found[key] = fams[0]
                    return
        except Exception:
            pass
        fid = QFontDatabase.addApplicationFont(filepath)  # запасной вариант без переименования
        if fid != -1:
            fams = QFontDatabase.applicationFontFamilies(fid)
            if fams:
                found[key] = fams[0]

    seen = set()
    font_files = []
    for d in (search_dirs if search_dirs is not None else default_search_dirs()):
        if os.path.isdir(d):
            try:
                for fname in sorted(os.listdir(d)):
                    low = fname.lower()
                    if low.endswith((".ttf", ".otf")):
                        full_p = os.path.normpath(os.path.join(d, fname))
                        if full_p not in seen:
                            seen.add(full_p)
                            font_files.append((low, full_p))
            except Exception:
                pass

    rules = [
        ("reply", lambda low: "peanuts" in low),
        ("sound", lambda low: "manga" in low and "shadow" not in low),
        ("sound_shadow", lambda low: "shadow" in low and ("manga" in low or "mp" in low)),
    ]
    for key, matches in rules:
        for low, full_p in font_files:
            if key not in found and matches(low):
                register(key, full_p)

    # запасной поиск среди уже установленных семейств
    all_fams = QFontDatabase.families()
    for key, matches in rules:
        if key not in found:
            for fam in all_fams:
                if matches(fam.lower()):
                    found[key] = fam
                    break

    defaults = Fonts()
    sound = found.get("sound", defaults.sound)
    return Fonts(
        reply=found.get("reply", defaults.reply),
        sound=sound,
        sound_shadow=found.get("sound_shadow", sound),
    )


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
