"""Холст со стрипом: стрип вписывается в окно, Ctrl+колесо — масштаб, правая кнопка мыши — Ластик."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QGraphicsView

ZOOM_STEP = 1.15
MIN_SCALE, MAX_SCALE = 0.05, 8.0


class StripCanvasView(QGraphicsView):
    """`editor` — окно вёрстки: даёт `can_erase`, `checkpoint()` и `erase_at(x, y)`."""

    def __init__(self, scene, editor):
        super().__init__(scene)
        self.editor = editor
        self.erasing = False
        self.fit_mode = True  # стрип вписан в окно и следует за размером окна
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

    def zoom(self, factor: float) -> None:
        self.fit_mode = False
        factor = max(MIN_SCALE / self.zoom_level, min(MAX_SCALE / self.zoom_level, factor))
        self.scale(factor, factor)

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

    # --------------------------------------------------------------- Ластик

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
