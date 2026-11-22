"""Текстовый блок на холсте окна: вид из BlockGraphic плюс рамка, маркеры и мышь."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsTextItem

from rus_peanuts.typesetting.document import TextBlock
from rus_peanuts.typesetting.graphics import BlockGraphic

HANDLE_SIZE = 10


class BlockItem(BlockGraphic):
    """`editor` — окно вёрстки: даёт `typography`, `checkpoint()` и `drop_checkpoint()`."""

    def __init__(self, block: TextBlock, editor):
        self.editor = editor
        self.drag_mode = None
        self.start_mouse_pos = QPointF()
        self.start_item_pos = QPointF()
        self.start_width = block.width
        self.start_size = block.size
        super().__init__(block, editor.typography)
        self.setFlags(
            QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsTextItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setAcceptHoverEvents(True)

    # ---------------------------------------------------------------- вид

    def width_handle_rect(self):
        r = self.text_rect()
        return QRectF(r.right() - HANDLE_SIZE, r.center().y() - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE)

    def scale_handle_rect(self):
        r = self.text_rect()
        return QRectF(r.right() - HANDLE_SIZE, r.bottom() - HANDLE_SIZE, HANDLE_SIZE, HANDLE_SIZE)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.save()
            painter.setPen(QPen(QColor("#00a8ff"), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.text_rect())
            painter.setPen(QPen(QColor("white"), 1))
            painter.setBrush(QBrush(QColor("#00a8ff")))
            painter.drawRect(self.width_handle_rect())
            painter.setBrush(QBrush(QColor("#00e676")))
            painter.drawRect(self.scale_handle_rect())
            painter.restore()

    # --------------------------------------------------------------- мышь

    def hoverMoveEvent(self, event):
        if self.isSelected():
            pos = event.pos()
            if self.scale_handle_rect().contains(pos):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                return
            if self.width_handle_rect().contains(pos):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                return
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.editor.checkpoint()
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.block.set_text(self.toPlainText())
        if self.toPlainText() != self.block.text:
            self.setPlainText(self.block.text)
        self.typography.apply_char_format(self, self.block)
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.editor.checkpoint()
            self.start_item_pos = self.pos()
            if self.isSelected():
                pos = event.pos()
                if self.scale_handle_rect().contains(pos):
                    self.drag_mode = "scale"
                elif self.width_handle_rect().contains(pos):
                    self.drag_mode = "width"
                if self.drag_mode:
                    self.start_mouse_pos = event.scenePos()
                    self.start_size = self.block.size
                    self.start_width = self.block.width
                    event.accept()
                    return
        self.drag_mode = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_mode == "width":
            dx = event.scenePos().x() - self.start_mouse_pos.x()
            self.block.width = max(TextBlock.MIN_WIDTH, self.start_width + dx)
            self.refresh()
            event.accept()
            return
        if self.drag_mode == "scale":
            d = event.scenePos() - self.start_mouse_pos
            self.block.size = max(TextBlock.MIN_SIZE, min(TextBlock.MAX_DRAG_SIZE, self.start_size + (d.x() + d.y()) * 0.08))
            self.refresh()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drag_mode:
            self.drag_mode = None
            if self.scene():
                self.scene().update()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.pos() == self.start_item_pos:
            self.editor.drop_checkpoint()  # просто клик: правки не было
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        # Qt двигает сразу все выделенные блоки — позицию каждого держим в его TextBlock
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.block.x, self.block.y = self.pos().x(), self.pos().y()
        return super().itemChange(change, value)
