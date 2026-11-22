"""Файл проекта (.rpeanuts): Документ целиком, чтобы вернуться к вёрстке позже.

Это ZIP-архив:
  project.json    — версия формата, Текстовые блоки, Перевод, найденные места, стёртые Звуки;
  original.png    — Оригинал;
  cleaned.png     — Оригинал после Очистки Баблов;
  sound_erase.png — какие пиксели стираются вместе с каждым Звуком;
  pencil.png      — слой Карандаша (0 — нет, 1 — белый, 2 — чёрный);
  image.png       — то, что видно под текстом (для просмотра архива; при открытии собирается заново).
История отмены в файл не попадает.

Версии формата: 1 — у блока флаг Shadow вместо Шрифта; 2 — у блока свой Шрифт;
3 — Карандаш и стёртые Звуки хранятся отдельными слоями.
"""
import json
import zipfile
from dataclasses import asdict, fields

import cv2
import numpy as np

from .analysis import Box, SoundBox, StripAnalysis
from .document import Document, TextBlock
from .fonts import DEFAULT_FONT
from .translation import Line

EXTENSION = ".rpeanuts"
FORMAT = "rus-peanuts-project"
VERSION = 3

# Версия 1: Реплики — Шрифтом реплик, Звуки — MP Manga, Shadow или сплошным
_V1_SOUND_FONTS = {True: "MPMangaFontBold", False: "MPMangaFontBold-Bold"}


class ProjectError(Exception):
    """Файл не является проектом RUS PEANUTS или повреждён."""


def save(doc: Document, path) -> None:
    if doc.analysis is None:
        raise ProjectError("в Документе нет стрипа — сохранять нечего")
    meta = {
        "format": FORMAT,
        "version": VERSION,
        "blocks": [asdict(b) for b in doc.blocks],
        "lines": None if doc.lines is None else [asdict(ln) for ln in doc.lines],
        "bubbles": [list(b) for b in doc.bubbles],
        "sounds": [list(s) for s in doc.sounds],
        "erased_sounds": list(doc.erased_sounds),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json", json.dumps(meta, ensure_ascii=False, indent=1))
        z.writestr("original.png", _png(doc.analysis.original))
        z.writestr("cleaned.png", _png(doc.analysis.cleaned))
        z.writestr("sound_erase.png", _png(doc.analysis.sound_erase))
        z.writestr("pencil.png", _png(doc.pencil))
        z.writestr("image.png", _png(doc.image))


def load(path, typography) -> Document:
    try:
        with zipfile.ZipFile(path) as z:
            meta = json.loads(z.read("project.json").decode("utf-8"))
            if meta.get("format") != FORMAT:
                raise ProjectError("это не проект RUS PEANUTS")
            version = meta.get("version", 0)
            if version > VERSION:
                raise ProjectError("проект сохранён более новой версией программы")
            original = _unpng(z.read("original.png"))
            cleaned = _unpng(z.read("cleaned.png"))
            if version >= 3:
                sound_erase = _unpng(z.read("sound_erase.png"), gray=True)
                pencil = _unpng(z.read("pencil.png"), gray=True)
            else:
                # раньше Звуки стирались сразу (они уже в cleaned), а Карандаш — прямо по картинке
                sound_erase = np.zeros(original.shape[:2], np.uint8)
                pencil = _pencil_from(_unpng(z.read("image.png")), cleaned)
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ProjectError(f"файл повреждён: {e}") from e

    doc = Document(typography)
    doc.analysis = StripAnalysis(
        original=original,
        bubbles=[Box(*b) for b in meta["bubbles"]],
        sounds=[SoundBox(*s) for s in meta["sounds"]],
        cleaned=cleaned,
        sound_erase=sound_erase,
    )
    doc.pencil = pencil
    doc.erased_sounds = tuple(meta.get("erased_sounds", ()))
    known = {f.name for f in fields(TextBlock)}
    doc.blocks = [TextBlock(**{k: v for k, v in _upgrade(b).items() if k in known}) for b in meta["blocks"]]
    doc.lines = None if meta["lines"] is None else [Line(**ln) for ln in meta["lines"]]
    doc._render()
    return doc


def _upgrade(block: dict) -> dict:
    """Блок из проекта версии 1: флаг Shadow превращается в Шрифт."""
    if "font" in block:
        return block
    font = DEFAULT_FONT if block.get("is_reply", True) else _V1_SOUND_FONTS[bool(block.get("shadow"))]
    return {**block, "font": font}


def _pencil_from(image: np.ndarray, cleaned: np.ndarray) -> np.ndarray:
    """Слой Карандаша из старого проекта: где картинка отличается от Очистки."""
    pencil = np.zeros(image.shape[:2], np.uint8)
    changed = (image != cleaned).any(axis=2)
    pencil[changed & (image == 255).all(axis=2)] = 1
    pencil[changed & (image == 0).all(axis=2)] = 2
    return pencil


def _png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ProjectError("не удалось закодировать картинку")
    return buf.tobytes()


def _unpng(data: bytes, gray: bool = False) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_GRAYSCALE if gray else cv2.IMREAD_COLOR)
    if img is None:
        raise ProjectError("картинка в проекте повреждена")
    return img
