"""Холст со стрипом: правая кнопка мыши — Ластик."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGraphicsView


class StripCanvasView(QGraphicsView):
    """`editor` — окно вёрстки: даёт `can_erase`, `checkpoint()` и `erase_at(x, y)`."""

    def __init__(self, scene, editor):
        super().__init__(scene)
        self.editor = editor
        self.erasing = False
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self.editor.can_erase:
            self.editor.checkpoint()
            self.erasing = True
            self._erase(event.pos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.erasing and self.editor.can_erase:
            self._erase(event.pos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self.erasing:
            self.erasing = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _erase(self, view_pos):
        pt = self.mapToScene(view_pos)
        self.editor.erase_at(int(pt.x()), int(pt.y()))
