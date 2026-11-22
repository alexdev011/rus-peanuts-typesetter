"""Раскладка текста через Qt: Шрифт, ширина колонки, Жирность и автоподбор кегля.

Один и тот же `Typography.style()` используется и для измерения (при расстановке),
и для показа на холсте, поэтому размеры совпадают с тем, что видно на экране.
"""
from dataclasses import dataclass

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QGuiApplication, QPen, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QGraphicsTextItem

from .document import TextBlock
from .fonts import FontLibrary
from .hyphenation import SOFT_HYPHEN, hyphenate_text
from .translation import Line

REPLY_START_SIZE = 11.0
SOUND_START_SIZE = 28.0


@dataclass(frozen=True)
class SetLine:
    """Строка текста так, как её разложил Qt (координаты — относительно блока)."""
    text: str           # с дефисом на месте переноса, без мягких переносов
    center_x: float
    baseline_y: float
    width: float        # ширина набранной строки


@dataclass(frozen=True)
class SetText:
    """Разложенный текст блока: строки, кегль и интерлиньяж в пикселях стрипа."""
    lines: list
    size_px: float
    leading_px: float


class Typography:
    def __init__(self, fonts: FontLibrary):
        self.fonts = fonts

    # ------------------------------------------------------------------ стиль

    def font(self, block: TextBlock) -> QFont:
        f = QFont(self.fonts.family(block.font))
        f.setPointSizeF(max(5.0, block.size))
        f.setStretch(block.stretch)
        f.setItalic(block.italic)
        return f

    @staticmethod
    def bold_pen_width(block: TextBlock) -> float:
        if block.bold <= 0:
            return 0.0
        return block.bold * max(0.32, block.size * 0.032)

    def style(self, item: QGraphicsTextItem, block: TextBlock) -> None:
        """Применяет к текстовому элементу Qt шрифт и вид блока (текст не меняет)."""
        f = self.font(block)
        item.setFont(f)
        item.document().setDefaultFont(f)
        item.setDefaultTextColor(QColor("black"))
        if block.is_reply:
            item.setTextWidth(max(TextBlock.MIN_WIDTH, block.width))
            doc = item.document()
            opt = doc.defaultTextOption()
            opt.setAlignment(Qt.AlignmentFlag.AlignCenter)
            opt.setWrapMode(opt.WrapMode.WordWrap)
            doc.setDefaultTextOption(opt)
        else:
            item.setTextWidth(-1)
        self.apply_char_format(item, block)

    def apply_char_format(self, item: QGraphicsTextItem, block: TextBlock) -> None:
        """Шрифт всего текста без «залипания» старого стиля и плавная Жирность обводкой."""
        cursor = QTextCursor(item.document())
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        fmt.setFont(item.font())
        fmt.setForeground(QBrush(QColor("black")))
        if block.bold > 0:
            fmt.setTextOutline(QPen(QColor("black"), self.bold_pen_width(block), Qt.PenStyle.SolidLine,
                                    Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        else:
            fmt.setTextOutline(QPen(Qt.PenStyle.NoPen))
        cursor.setCharFormat(fmt)

    # -------------------------------------------------------------- измерение

    def bounds(self, block: TextBlock) -> QRectF:
        """Прямоугольник текста блока в его собственных координатах (без полей под Изгиб)."""
        probe = QGraphicsTextItem()
        probe.setPlainText(block.text)
        self.style(probe, block)
        return probe.boundingRect()

    def set_text(self, block: TextBlock) -> SetText:
        """Строки блока с точными переносами Qt — для экспорта в другие программы."""
        probe = QGraphicsTextItem()
        probe.setPlainText(block.text)
        self.style(probe, block)
        lines = []
        b = probe.document().begin()
        while b.isValid():
            layout, text, origin = b.layout(), b.text(), b.layout().position()
            for i in range(layout.lineCount()):
                ln = layout.lineAt(i)
                s = text[ln.textStart():ln.textStart() + ln.textLength()].rstrip(" ")
                if s.endswith(SOFT_HYPHEN):
                    s = s[:-1] + "-"
                lines.append(SetLine(
                    text=s.replace(SOFT_HYPHEN, ""),
                    center_x=origin.x() + ln.naturalTextRect().center().x(),
                    baseline_y=origin.y() + ln.y() + ln.ascent(),
                    width=ln.naturalTextWidth(),
                ))
            b = b.next()
        font = probe.font()
        screen = QGuiApplication.primaryScreen()
        dpi = screen.logicalDotsPerInchY() if screen else 96.0
        if len(lines) > 1:
            leading = lines[1].baseline_y - lines[0].baseline_y
        else:
            leading = QFontMetricsF(font).lineSpacing()
        return SetText(lines=lines, size_px=font.pointSizeF() * dpi / 72.0, leading_px=leading)

    def fit(self, line: Line, box) -> TextBlock:
        """Текстовый блок для строки Перевода, вписанный и отцентрованный в место на стрипе."""
        bx, by, bw, bh = box[0], box[1], box[2], box[3]
        text = hyphenate_text(line.text.upper()) if line.is_reply else line.text.upper()
        block = TextBlock(
            text=text, is_reply=line.is_reply, font=self.fonts.default,
            x=0.0, y=0.0, width=bw,
            size=REPLY_START_SIZE if line.is_reply else SOUND_START_SIZE,
            arch=getattr(box, "arch", 0),
        )
        probe = QGraphicsTextItem()
        probe.setPlainText(text)

        if line.is_reply:
            target_w, target_h = max(70, bw * 0.94), max(32, bh * 0.96)
            block.width = target_w
            sizes, best, slack_w, slack_h, lift = [s / 2.0 for s in range(44, 12, -1)], 6.5, 1.05, 1.06, 2
        else:
            target_w, target_h = bw, bh
            sizes, best, slack_w, slack_h, lift = [float(s) for s in range(58, 14, -1)], 20.0, 1.08, 1.15, 0

        for size in sizes:
            block.size = size
            self.style(probe, block)
            rect = probe.boundingRect()
            if rect.width() <= target_w * slack_w and rect.height() <= target_h * slack_h:
                best = size
                break
        block.size = best
        self.style(probe, block)
        rect = probe.boundingRect()
        block.x = bx + (bw - rect.width()) / 2
        block.y = by + (bh - rect.height()) / 2 - lift
        return block
