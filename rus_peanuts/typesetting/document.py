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

# Цвета Карандаша (BGR, как картинка стрипа) и как они хранятся в слое Карандаша
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
_PENCIL_CODE = {WHITE: 1, BLACK: 2}

# Запасной ряд мест вверху стрипа для строк, которым не нашлось места
FALLBACK_X, FALLBACK_STEP, FALLBACK_Y, FALLBACK_W, FALLBACK_H = 80, 180, 45, 160, 70


@dataclass
class TextBlock:
    """Русский текст одной Реплики или одного Звука на стрипе."""
    text: str               # как показывается, с мягкими переносами
    is_reply: bool          # Реплика переносится по колонке, Звук стоит одной строкой
    font: str               # Шрифт: PostScript-имя из Набора шрифтов
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

    def set_stretch(self, value) -> None:
        self.stretch = max(50, min(400, int(value)))

    def set_bold(self, value) -> None:
        self.bold = max(0, min(10, int(value)))

    def set_italic(self, on) -> None:
        self.italic = bool(on)

    def set_font(self, postscript) -> None:
        self.font = str(postscript)

    def set_arch(self, value) -> None:
        self.arch = max(-150, min(150, int(value)))

    def set_text(self, text: str) -> None:
        self.text = hyphenate_text(text) if self.is_reply else text


def assign_places(lines: list[Line], bubbles: list[Box], sounds: list[SoundBox], width: int | None = None):
    """Сопоставляет строки Перевода местам на стрипе по Порядку чтения.

    N-я Реплика идёт в N-й Бабл, N-й Звук — в N-е место Звука. Строки без места
    встают в запасной ряд вверху стрипа и не сдвигают остальные; если ряд не влезает
    в ширину стрипа `width`, он продолжается ниже.
    """
    per_row = max(1, (width - FALLBACK_X) // FALLBACK_STEP) if width else 10 ** 6
    bubble_idx = sound_idx = spare = 0
    for line in lines:
        if line.is_reply and bubble_idx < len(bubbles):
            box = bubbles[bubble_idx]
            bubble_idx += 1
        elif not line.is_reply and sound_idx < len(sounds):
            box = sounds[sound_idx]
            sound_idx += 1
        else:
            col, row = spare % per_row, spare // per_row
            box = Box(FALLBACK_X + col * FALLBACK_STEP, FALLBACK_Y + row * (FALLBACK_H + 20), FALLBACK_W, FALLBACK_H)
            spare += 1
        yield line, box


class Document:
    """Картинка под текстом (`image`) собирается из трёх слоёв: Оригинал с Очисткой Баблов,
    стёртые Звуки, на которые встал Перевод, и слой Карандаша поверх. Поэтому новый
    Перевод не стирает работу Карандашом."""

    def __init__(self, typography):
        self.typography = typography
        self.analysis: StripAnalysis | None = None
        self.lines: list[Line] | None = None
        self.image: np.ndarray | None = None      # то, что видно под текстом
        self.pencil: np.ndarray | None = None     # слой Карандаша: 0 — нет, 1 — белый, 2 — чёрный
        self.erased_sounds: tuple = ()            # номера Звуков, стёртых под строками Перевода
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
        self.pencil = np.zeros(image.shape[:2], np.uint8)
        if lines is not None:
            self.lines = lines
        self._history.clear()
        self._place()

    def set_translation(self, lines: list[Line]) -> None:
        """Новый Перевод: Текстовые блоки расставляются заново (это можно отменить).
        Работа Карандашом остаётся."""
        if self.image is not None:
            self.checkpoint()
        self.lines = lines
        self._place()

    def _place(self) -> None:
        width = self.analysis.original.shape[1] if self.analysis is not None else None
        placed = list(assign_places(self.lines or [], self.bubbles, self.sounds, width))
        self.blocks = [self.typography.fit(line, box) for line, box in placed]
        self.erased_sounds = tuple(k for k, s in enumerate(self.sounds) if any(box is s for _, box in placed))
        self._render()

    def _render(self) -> None:
        """Собирает картинку под текстом: Очистка, стёртые Звуки, Карандаш."""
        if self.analysis is None:
            self.image = None
            return
        self.image = self.analysis.cleaned_with(self.erased_sounds)
        if self.pencil is not None:
            self.image[self.pencil == 1] = WHITE
            self.image[self.pencil == 2] = BLACK

    # ---------------------------------------------------------------- правки

    def remove(self, blocks) -> None:
        ids = {id(b) for b in blocks}
        self.blocks = [b for b in self.blocks if id(b) not in ids]

    def paint(self, x0: int, y0: int, x1: int, y1: int, radius: int, color) -> bool:
        """Карандаш: закрашивает стрип линией от (x0, y0) до (x1, y1) круглой кистью.

        Цвет — WHITE или BLACK. Края без сглаживания, как у карандаша Фотошопа.
        False — стрипа нет или кисть не достаёт до картинки.
        """
        if self.image is None or self.pencil is None:
            return False
        h, w = self.image.shape[:2]
        r = max(0, int(radius))
        if max(x0, x1) < -r or min(x0, x1) >= w + r or max(y0, y1) < -r or min(y0, y1) >= h + r:
            return False
        color = tuple(int(c) for c in color)
        for layer, value in ((self.image, color), (self.pencil, _PENCIL_CODE[color])):
            cv2.circle(layer, (x0, y0), r, value, -1)
            if (x0, y0) != (x1, y1):
                cv2.line(layer, (x0, y0), (x1, y1), value, 2 * r + 1)
                cv2.circle(layer, (x1, y1), r, value, -1)
        return True

    # --------------------------------------------------------------- отмена

    def checkpoint(self, selected=()) -> None:
        """Запоминает состояние перед правкой. `selected` — индексы выделенных блоков."""
        if self.image is None:
            return
        self._history.append((self.pencil.copy(), copy.deepcopy(self.blocks), self.lines, self.erased_sounds,
                              tuple(selected)))
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
        self.pencil, self.blocks, self.lines, self.erased_sounds, selected = self._history.pop()
        self._render()
        return list(selected)
