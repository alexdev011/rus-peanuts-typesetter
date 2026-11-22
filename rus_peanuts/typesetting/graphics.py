"""Как Документ выглядит на картинке: Текстовый блок как графический элемент Qt и сцена стрипа.

Этим пользуются и холст окна (с мышью поверх), и экспорт в PNG — поэтому
сохранённый файл выглядит ровно так же, как стрип на экране.
"""
import math

import cv2
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFontMetrics, QImage, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsTextItem, QStyle, QStyleOptionGraphicsItem

from .document import Document, TextBlock


def to_qpixmap(bgr) -> QPixmap:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    return QPixmap.fromImage(QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy())


class BlockGraphic(QGraphicsTextItem):
    """Текстовый блок на сцене: шрифт и вид из Typography, Изгиб — побуквенной отрисовкой."""

    def __init__(self, block: TextBlock, typography):
        super().__init__()
        self.block = block
        self.typography = typography
        self.setPlainText(block.text)
        self.refresh()
        self.setPos(block.x, block.y)

    def refresh(self) -> None:
        """Перерисовать после изменения блока (кроме позиции и текста)."""
        self.prepareGeometryChange()
        self.typography.style(self, self.block)
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

    def is_editing(self) -> bool:
        return self.textInteractionFlags() == Qt.TextInteractionFlag.TextEditorInteraction

    def paint(self, painter, option, widget=None):
        opt = QStyleOptionGraphicsItem(option)
        opt.state &= ~QStyle.StateFlag.State_Selected
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        if self.block.arch != 0 and not self.is_editing():
            self._paint_arched(painter)
        else:
            super().paint(painter, opt, widget)

    def _paint_arched(self, painter):
        """Каждая буква — на параболе, повёрнутая по касательной к ней."""
        arch = self.block.arch
        r = self.text_rect()
        lines = self.toPlainText().splitlines() or [""]
        fm = QFontMetrics(self.font())
        line_h = fm.lineSpacing()
        start_y = r.center().y() - line_h * len(lines) / 2.0 + fm.ascent()
        pen_w = self.typography.bold_pen_width(self.block)

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


def build_scene(doc: Document, typography) -> QGraphicsScene:
    """Сцена с очищенным стрипом и всеми Текстовыми блоками Документа (без интерактива)."""
    scene = QGraphicsScene()
    if doc.image is not None:
        pixmap = to_qpixmap(doc.image)
        scene.addPixmap(pixmap)
        scene.setSceneRect(QRectF(pixmap.rect()))
    for block in doc.blocks:
        scene.addItem(BlockGraphic(block, typography))
    return scene


def render_scene(scene: QGraphicsScene, size) -> QImage:
    """Сцена в картинку: белый фон, сглаживание текста — как кнопка «Сохранить (PNG)»."""
    img = QImage(size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    scene.render(painter)
    painter.end()
    return img
