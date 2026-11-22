"""Нарезка Страниц, Квадрат и формат Acomics.

Координаты ищутся «прогулкой» по негативу картинки от фиксированных точек
до первого пикселя рамки — так же, как это делал старый Multi tool.
"""
from .raster import Picture, crop, is_dark, level, paste, resize, white_canvas

START_X, START_Y = 400, 250        # откуда начинаем искать левый верхний угол кадров
ACOMICS_WIDTH = 1024
ACOMICS_DAILY_HEIGHT = 223
ACOMICS_SUNDAY_HEIGHT = 705
SUNDAY_MIN_HEIGHT = 1000           # выше — считаем стрип Воскресным


def contrast(picture: Picture) -> Picture:
    return level(picture, 60 / 255, 232 / 255)


def negative(picture: Picture) -> Picture:
    """Пороговый негатив: светлое становится тёмным, рамки и линии — белыми."""
    return level(picture, 0.6, 0.5)


def _px(neg: Picture, x: int, y: int):
    return neg.pixels[y, x]


def _upper_left(neg: Picture, mark_x: int, mark_y: int, x: int = 0, y: int = 0):
    while is_dark(_px(neg, x, mark_y)):
        x += 2
    while is_dark(_px(neg, mark_x, y)):
        y += 2
    return x, y


def _frame_size(neg: Picture, x: int, y: int, sunday: bool = False):
    marker = neg.width - 2
    while is_dark(_px(neg, marker, y + 10)):
        marker -= 2
    w = marker - x
    if not sunday:
        h = int((neg.height - 3 * y) / 3)
        marker = h + y + 10
        while is_dark(_px(neg, x + 15, marker)):
            marker -= 2
        h = marker - y
    else:
        marker = neg.height
        while is_dark(_px(neg, x + 20, marker - 1), inclusive=True) and marker > 0:
            marker -= 3
        h = marker - y
    return w + 30, h + 40


def slice_daily_page(page: Picture) -> list[Picture]:
    """Три Ежедневных стрипа со Страницы, сверху вниз."""
    neg = negative(page)
    mark_x, mark_y = START_X, START_Y
    x, y = _upper_left(neg, mark_x, mark_y)
    space = y
    w, h = _frame_size(neg, x, y)
    strips = []
    for i in range(3):
        if i != 0:
            x, y = _upper_left(neg, mark_x, mark_y, y=y)
        x -= 15
        y -= 20
        strips.append(crop(page, x, y, w, h))
        if i == 0:
            mark_y = 2 * space + h
            y = space + h
        elif i == 1:
            mark_y = int(page.height - space - 0.7 * h)
            y = page.height - space - h
    return strips


def slice_sunday_page(page: Picture) -> Picture:
    """Воскресный стрип, занимающий всю Страницу."""
    neg = negative(page)
    x, y = _upper_left(neg, START_X, START_Y)
    w, h = _frame_size(neg, x, y, sunday=True)
    return crop(page, x - 15, y - 20, w, h)


def square(strip: Picture) -> Picture:
    """Квадрат: левая половина Ежедневного стрипа сверху, правая — под ней."""
    w = int(strip.width / 2)
    h = strip.height
    x, _ = _upper_left(negative(strip), START_X, START_Y)
    left = crop(strip, x, 0, w, h)
    right = crop(strip, w, 0, w, h)
    x, y = _upper_left(negative(right), START_X, START_Y)
    right = crop(right, x, y, w, h)
    canvas = white_canvas(min(left.width, right.width) + 5, left.height + right.height, strip)
    paste(canvas, right, 5, h)
    paste(canvas, left, 5, 0)
    return canvas


def fit_acomics(strip: Picture) -> Picture:
    height = ACOMICS_DAILY_HEIGHT if strip.height < SUNDAY_MIN_HEIGHT else ACOMICS_SUNDAY_HEIGHT
    return resize(strip, ACOMICS_WIDTH, height)
