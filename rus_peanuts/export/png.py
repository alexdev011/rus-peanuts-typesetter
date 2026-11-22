"""Экспорт Результата в PNG: очищенный стрип с наложенными Текстовыми блоками."""
from PyQt6.QtCore import QSize

from rus_peanuts.typesetting.document import Document
from rus_peanuts.typesetting.graphics import build_scene, render_scene


def export_png(doc: Document, typography, path) -> bool:
    """Сохраняет PNG. False — в Документе нет стрипа."""
    if doc.image is None:
        return False
    scene = build_scene(doc, typography)
    h, w = doc.image.shape[:2]
    return render_scene(scene, QSize(w, h)).save(str(path))
