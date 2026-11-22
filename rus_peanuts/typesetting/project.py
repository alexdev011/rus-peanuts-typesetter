"""Файл проекта (.rpeanuts): Документ целиком, чтобы вернуться к вёрстке позже.

Это ZIP-архив:
  project.json  — версия формата, Текстовые блоки, Перевод, найденные места;
  original.png  — Оригинал;
  cleaned.png   — Оригинал после Очистки (нужен, чтобы заново расставить Перевод);
  image.png     — очищенный стрип с правками Ластиком (то, что видно под текстом).
История отмены в файл не попадает.
"""
import json
import zipfile
from dataclasses import asdict, fields

import cv2
import numpy as np

from .analysis import Box, SoundBox, StripAnalysis
from .document import Document, TextBlock
from .translation import Line

EXTENSION = ".rpeanuts"
FORMAT = "rus-peanuts-project"
VERSION = 1


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
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json", json.dumps(meta, ensure_ascii=False, indent=1))
        z.writestr("original.png", _png(doc.analysis.original))
        z.writestr("cleaned.png", _png(doc.analysis.cleaned))
        z.writestr("image.png", _png(doc.image))


def load(path, typography) -> Document:
    try:
        with zipfile.ZipFile(path) as z:
            meta = json.loads(z.read("project.json").decode("utf-8"))
            if meta.get("format") != FORMAT:
                raise ProjectError("это не проект RUS PEANUTS")
            if meta.get("version", 0) > VERSION:
                raise ProjectError("проект сохранён более новой версией программы")
            original = _unpng(z.read("original.png"))
            cleaned = _unpng(z.read("cleaned.png"))
            image = _unpng(z.read("image.png"))
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ProjectError(f"файл повреждён: {e}") from e

    doc = Document(typography)
    doc.analysis = StripAnalysis(
        original=original,
        bubbles=[Box(*b) for b in meta["bubbles"]],
        sounds=[SoundBox(*s) for s in meta["sounds"]],
        cleaned=cleaned,
    )
    doc.image = image
    known = {f.name for f in fields(TextBlock)}
    doc.blocks = [TextBlock(**{k: v for k, v in b.items() if k in known}) for b in meta["blocks"]]
    doc.lines = None if meta["lines"] is None else [Line(**ln) for ln in meta["lines"]]
    return doc


def _png(bgr: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", bgr)
    if not ok:
        raise ProjectError("не удалось закодировать картинку")
    return buf.tobytes()


def _unpng(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ProjectError("картинка в проекте повреждена")
    return img
