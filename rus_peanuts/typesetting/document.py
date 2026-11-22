"""Документ вёрстки: стрип, Перевод, Текстовые блоки и история отмены.

Документ — единственный источник правды о том, что стоит на стрипе. Интерфейс
только показывает его и вызывает его операции; каждая правка, которую можно
отменить, начинается с `checkpoint()`.
"""
import copy
from dataclasses import dataclass

import cv2
import numpy as np

from . import analysis as _analysis
from .analysis import Box, SoundBox, StripAnalysis
from .hyphenation import hyphenate_text
from .translation import Line

HISTORY_LIMIT = 40
ERASER_RADIUS = 12

# Запасной ряд мест вверху стрипа для строк, которым не нашлось места
FALLBACK_X, FALLBACK_STEP, FALLBACK_Y, FALLBACK_W, FALLBACK_H = 80, 180, 45, 160, 70


@dataclass
class TextBlock:
    """Русский текст одной Реплики или одного Звука на стрипе."""
    text: str               # как показывается, с мягкими переносами
    is_reply: bool
    shadow: bool            # начертание Shadow (имеет смысл для Звука)
    x: float                # левый верхний угол текста
    y: float
    width: float            # ширина колонки Реплики
    size: float             # кегль
    stretch: int = 100      # растяжение шрифта, %
    italic: bool = False
    bold: int = 0           # Жирность 0..10
    arch: int = 0           # Изгиб: плюс — дуга вверх

    MIN_SIZE = 5.0
    MAX_DRAG_SIZE = 72.0
    MIN_WIDTH = 45

    def grow(self, delta: float) -> None:
        self.size = max(self.MIN_SIZE, self.size + delta)

    def widen(self, delta: float) -> None:
        if self.is_reply:
            self.width = max(self.MIN_WIDTH, self.width + delta)

    def toggle_italic(self) -> None:
        self.italic = not self.italic

    def stretch_by(self, delta: int) -> None:
        self.stretch = max(50, min(400, self.stretch + delta))

    def thicken(self, delta: int) -> None:
        self.bold = max(0, min(10, self.bold + (1 if delta > 0 else -1)))

    def toggle_shadow(self) -> None:
        """Кнопка «Shadow / Обычный»: у Реплики — Жирность 0 <-> 2, у Звука — Shadow <-> сплошной."""
        if self.is_reply:
            self.bold = 2 if self.bold == 0 else 0
            self.shadow = False
        else:
            self.shadow = not self.shadow

    def set_arch(self, value) -> None:
        self.arch = max(-150, min(150, int(value)))

    def set_text(self, text: str) -> None:
        self.text = hyphenate_text(text) if self.is_reply else text


def assign_places(lines: list[Line], bubbles: list[Box], sounds: list[SoundBox]):
    """Сопоставляет строки Перевода местам на стрипе по Порядку чтения.

    N-я Реплика идёт в N-й Бабл, N-й Звук — в N-е место Звука; строкам без места
    достаётся запасной ряд вверху стрипа. Известная особенность (вероятно, баг):
    лишняя Реплика тоже сдвигает счётчик Звуков.
    """
    bubble_idx = sound_idx = 0
    for line in lines:
        if line.is_reply and bubble_idx < len(bubbles):
            box = bubbles[bubble_idx]
            bubble_idx += 1
        elif not line.is_reply and sound_idx < len(sounds):
            box = sounds[sound_idx]
            sound_idx += 1
        else:
            box = Box(FALLBACK_X + sound_idx * FALLBACK_STEP, FALLBACK_Y, FALLBACK_W, FALLBACK_H)
            sound_idx += 1
        yield line, box


class Document:
    def __init__(self, typography):
        self.typography = typography
        self.analysis: StripAnalysis | None = None
        self.lines: list[Line] | None = None
        self.image: np.ndarray | None = None      # очищенный стрип с правками Ластиком
        self.blocks: list[TextBlock] = []
        self._history: list = []

    # ------------------------------------------------------------ состояние

    @property
    def original(self) -> np.ndarray | None:
        return self.analysis.original if self.analysis else None

    @property
    def bubbles(self) -> list[Box]:
        return self.analysis.bubbles if self.analysis else []

    @property
    def sounds(self) -> list[SoundBox]:
        return self.analysis.sounds if self.analysis else []

    # -------------------------------------------------------- стрип и Перевод

    def open_strip(self, image: np.ndarray, lines: list[Line] | None = None) -> None:
        """Новый стрип: анализ, Очистка и расстановка Перевода. История начинается заново."""
        self.analysis = _analysis.analyze(image)
        if lines is not None:
            self.lines = lines
        self._history.clear()
        self._place()

    def set_translation(self, lines: list[Line]) -> None:
        """Новый Перевод: Текстовые блоки расставляются заново (это можно отменить)."""
        if self.image is not None:
            self.checkpoint()
        self.lines = lines
        self._place()

    def _place(self) -> None:
        if self.analysis is not None:
            self.image = self.analysis.cleaned.copy()  # правки Ластиком сбрасываются
        self.blocks = [self.typography.fit(line, box)
                       for line, box in assign_places(self.lines or [], self.bubbles, self.sounds)]

    # ---------------------------------------------------------------- правки

    def remove(self, blocks) -> None:
        ids = {id(b) for b in blocks}
        self.blocks = [b for b in self.blocks if id(b) not in ids]

    def erase_spot(self, x: int, y: int, radius: int = ERASER_RADIUS) -> bool:
        """Ластик: белое пятно на стрипе. False — точка вне картинки."""
        if self.image is None:
            return False
        h, w = self.image.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return False
        cv2.circle(self.image, (x, y), radius, (255, 255, 255), -1)
        return True

    # --------------------------------------------------------------- отмена

    def checkpoint(self, selected=()) -> None:
        """Запоминает состояние перед правкой. `selected` — индексы выделенных блоков."""
        if self.image is None:
            return
        self._history.append((self.image.copy(), copy.deepcopy(self.blocks), tuple(selected)))
        if len(self._history) > HISTORY_LIMIT:
            self._history.pop(0)

    def drop_checkpoint(self) -> None:
        """Отменяет последний checkpoint, если правка в итоге ничего не изменила."""
        if self._history:
            self._history.pop()

    @property
    def can_undo(self) -> bool:
        return bool(self._history)

    @property
    def history_size(self) -> int:
        return len(self._history)

    def undo(self):
        """Возвращает предыдущее состояние. Результат — индексы блоков, которые были
        выделены, или None, если отменять нечего."""
        if not self._history:
            return None
        self.image, self.blocks, selected = self._history.pop()
        return list(selected)
