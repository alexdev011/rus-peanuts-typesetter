"""Текстовый блок на холсте: показывает TextBlock и переводит действия мыши в его правки."""
import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsTextItem, QStyle, QStyleOptionGraphicsItem

from rus_peanuts.typesetting.document import TextBlock

HANDLE_SIZE = 10


class BlockItem(QGraphicsTextItem):
    """`editor` — окно вёрстки: даёт `typography`, `checkpoint()` и `drop_checkpoint()`."""

    def __init__(self, block: TextBlock, editor):
        super().__init__()
        self.block = block
        self.editor = editor
        self.drag_mode = None
        self.start_mouse_pos = QPointF()
        self.start_item_pos = QPointF()
        self.start_width = block.width
        self.start_size = block.size

        self.setFlags(
            QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsTextItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setAcceptHoverEvents(True)
        self.setPlainText(block.text)
        self.refresh()
        self.setPos(block.x, block.y)

    # ---------------------------------------------------------------- вид

    def refresh(self) -> None:
        """Перерисовать после изменения блока (кроме позиции и текста)."""
        self.prepareGeometryChange()
        self.editor.typography.style(self, self.block)
        if self.scene():
            self.scene().update()
        else:
            self.update()

    def text_rect(self) -> QRectF:
        return super().boundingRect()

    def boundingRect(self):
        pad_y = abs(self.block.arch) + 18 if self.block.arch != 0 else 8
        pad_x = 18 if self.block.arch != 0 else 8
        return self.text_rect().adjusted(-pad_x, -pad_y, pad_x, pad_y)

    def width_handle_rect(self):
        r = self.text_rect()
        return QRectF(r.right() - HANDLE_SIZE, r.center().y() - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE)

    def scale_handle_rect(self):
        r = self.text_rect()
        return QRectF(r.right() - HANDLE_SIZE, r.bottom() - HANDLE_SIZE, HANDLE_SIZE, HANDLE_SIZE)

    def paint(self, painter, option, widget=None):
        opt = QStyleOptionGraphicsItem(option)
        opt.state &= ~QStyle.StateFlag.State_Selected
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        editing = self.textInteractionFlags() == Qt.TextInteractionFlag.TextEditorInteraction
        if self.block.arch != 0 and not editing:
            self._paint_arched(painter)
        else:
            super().paint(painter, opt, widget)

        if self.isSelected():
            r = self.text_rect()
            painter.save()
            painter.setPen(QPen(QColor("#00a8ff"), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)
            painter.setPen(QPen(QColor("white"), 1))
            painter.setBrush(QBrush(QColor("#00a8ff")))
            painter.drawRect(self.width_handle_rect())
            painter.setBrush(QBrush(QColor("#00e676")))
            painter.drawRect(self.scale_handle_rect())
            painter.restore()

    def _paint_arched(self, painter):
        """Каждая буква — на параболе, повёрнутая по касательной к ней."""
        arch = self.block.arch
        r = self.text_rect()
        lines = self.toPlainText().splitlines() or [""]
        fm = QFontMetrics(self.font())
        line_h = fm.lineSpacing()
        start_y = r.center().y() - line_h * len(lines) / 2.0 + fm.ascent()
        pen_w = self.editor.typography.bold_pen_width(self.block)

        painter.save()
        painter.setFont(self.font())
        painter.setPen(QColor("black"))
        for li, line in enumerate(lines):
            if not line:
                continue
            char_widths = [fm.horizontalAdvance(ch) for ch in line]
            total_w = sum(char_widths)
            if total_w <= 0:
                continue
            half_w = max(1.0, total_w / 2.0)
            cur_x = -half_w
            base_y = start_y + li * line_h
            cx_center = r.center().x()
            for ch, cw in zip(line, char_widths):
                char_mid_x = cur_x + cw / 2.0
                t = char_mid_x / half_w                       # [-1, 1]
                dy = arch * (t * t - 0.5)                     # при arch > 0 середина выше краёв
                angle_deg = math.degrees(math.atan((2.0 * arch * t) / half_w))
                painter.save()
                painter.translate(cx_center + char_mid_x, base_y + dy)
                painter.rotate(angle_deg)
                if self.block.bold > 0:
                    path = QPainterPath()
                    path.addText(QPointF(-cw / 2.0, 0), self.font(), ch)
                    painter.setPen(QPen(QColor("black"), pen_w, Qt.PenStyle.SolidLine,
                                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                    painter.setBrush(QBrush(QColor("black")))
                    painter.drawPath(path)
                else:
                    painter.drawText(QPointF(-cw / 2.0, 0), ch)
                painter.restore()
                cur_x += cw
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
        self.editor.typography.apply_char_format(self, self.block)
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
