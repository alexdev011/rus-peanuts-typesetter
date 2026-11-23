"""Значки инструментов, нарисованные кодом (без файлов картинок)."""
from qtpy.QtCore import QPointF, Qt
from qtpy.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


def cursor_icon(size: int = 20) -> QIcon:
    """Обычная стрелка мыши: чёрная с белой обводкой."""
    k = size / 20
    arrow = QPolygonF([QPointF(x * k, y * k) for x, y in
                       ((3, 1), (3, 16), (7, 12.5), (10, 19), (12.5, 18), (9.5, 11.5), (14.5, 11.5))])
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addPolygon(arrow)
    path.closeSubpath()
    p.setPen(QPen(QColor("white"), 2 * k))
    p.drawPath(path)
    p.fillPath(path, QColor("black"))
    p.end()
    return QIcon(pix)
