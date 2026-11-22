"""Холст со стрипом: стрип вписывается в окно, Ctrl+колесо — масштаб, Карандаш.

Карандаш закрашивает стрип белым или чёрным. Пока он включён, левая кнопка мыши
рисует выбранным цветом, а блоки не выделяются и не двигаются. Правая кнопка
мыши всегда рисует белым — быстрый ластик и без включённого Карандаша.
"""
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsView

from rus_peanuts.typesetting.document import WHITE

ZOOM_STEP = 1.15
MIN_SCALE, MAX_SCALE = 0.05, 8.0
DEFAULT_BRUSH = 24          # толщина Карандаша в пикселях стрипа
MAX_CURSOR = 256            # больше этого курсор-кружок не рисуется


class StripCanvasView(QGraphicsView):
    """`editor` — окно вёрстки: даёт `can_paint`, `checkpoint()` и `paint(x0, y0, x1, y1, radius, color)`."""

    def __init__(self, scene, editor):
        super().__init__(scene)
        self.editor = editor
        self.fit_mode = True  # стрип вписан в окно и следует за размером окна
        self.pencil = False
        self.pencil_color = WHITE
        self.brush_size = DEFAULT_BRUSH
        self._stroke = None   # (кнопка мыши, цвет, последняя точка) — пока ведётся штрих
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    # -------------------------------------------------------------- масштаб

    @property
    def zoom_level(self) -> float:
        return self.transform().m11()

    def fit(self) -> None:
        """Вписать стрип в окно целиком (но не увеличивать больше 100 %)."""
        self.fit_mode = True
        rect = self.scene().sceneRect() if self.scene() else None
        if rect is None or rect.isEmpty():
            return
        self.resetTransform()
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        if self.zoom_level > 1.0:
            self.resetTransform()
        self._update_cursor()

    def zoom(self, factor: float) -> None:
        self.fit_mode = False
        factor = max(MIN_SCALE / self.zoom_level, min(MAX_SCALE / self.zoom_level, factor))
        self.scale(factor, factor)
        self._update_cursor()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(ZOOM_STEP if event.angleDelta().y() > 0 else 1 / ZOOM_STEP)
            event.accept()
            return
        super().wheelEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_mode:
            self.fit()

    # ------------------------------------------------------------- Карандаш

    def set_pencil(self, on: bool) -> None:
        """Включить или выключить Карандаш: пока он включён, блоки не трогаются мышью."""
        self.pencil = bool(on)
        self.setInteractive(not self.pencil)
        self._update_cursor()

    def set_brush(self, color=None, size=None) -> None:
        if color is not None:
            self.pencil_color = tuple(color)
        if size is not None:
            self.brush_size = max(1, int(size))
        self._update_cursor()

    @property
    def brush_radius(self) -> int:
        return self.brush_size // 2

    def _update_cursor(self) -> None:
        """Курсор Карандаша — кружок толщины кисти в текущем масштабе."""
        if not self.pencil:
            self.viewport().unsetCursor()
            return
        d = max(4, min(MAX_CURSOR, round(self.brush_size * self.zoom_level)))
        pix = QPixmap(d + 3, d + 3)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor("white"), 3))
        p.drawEllipse(QPointF((d + 3) / 2, (d + 3) / 2), d / 2, d / 2)
        p.setPen(QPen(QColor("black"), 1))
        p.drawEllipse(QPointF((d + 3) / 2, (d + 3) / 2), d / 2, d / 2)
        p.end()
        self.viewport().setCursor(QCursor(pix, (d + 3) // 2, (d + 3) // 2))

    def _paint_to(self, view_pos) -> None:
        button, color, last = self._stroke
        pt = self.mapToScene(view_pos)
        x, y = int(pt.x()), int(pt.y())
        x0, y0 = last if last is not None else (x, y)
        self.editor.paint(x0, y0, x, y, self.brush_radius, color)
        self._stroke = (button, color, (x, y))

    def mousePressEvent(self, event):
        color = None
        if self._stroke is None and self.editor.can_paint:
            if event.button() == Qt.MouseButton.RightButton:
                color = WHITE
            elif event.button() == Qt.MouseButton.LeftButton and self.pencil:
                color = self.pencil_color
        if color is not None:
            self.editor.checkpoint()        # каждый штрих — один шаг отмены
            self._stroke = (event.button(), color, None)
            self._paint_to(event.pos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._stroke is not None:
            if self.editor.can_paint:
                self._paint_to(event.pos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._stroke is not None and event.button() == self._stroke[0]:
            self._stroke = None
            event.accept()
            return
        super().mouseReleaseEvent(event)
