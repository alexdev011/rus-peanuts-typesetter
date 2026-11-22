"""Растровые примитивы подготовки к публикации на numpy/Pillow.

Раньше эти операции делал Wand/ImageMagick (Q8). Здесь они повторены так,
чтобы результат совпадал с ним: уровни и обрезка — бит в бит, масштабирование —
тем же алгоритмом ImageMagick (разделимый фильтр, промежуточное округление
до 8 бит), а сохранение — в оттенках серого, если картинка серая.
"""
from dataclasses import dataclass

import numpy as np
from PIL import Image

_EPSILON = 1.0e-12  # MagickEpsilon


@dataclass
class Picture:
    """Картинка в памяти: uint8, (h, w) для серой или (h, w, 3) для цветной.

    `indexed` повторяет то, как ImageMagick помечает серые и палитровые файлы:
    для них он масштабирует фильтром Mitchell, для полноцветных — Lanczos.
    """
    pixels: np.ndarray
    indexed: bool = False

    @property
    def width(self) -> int:
        return self.pixels.shape[1]

    @property
    def height(self) -> int:
        return self.pixels.shape[0]

    def copy(self) -> "Picture":
        return Picture(self.pixels.copy(), self.indexed)


# ------------------------------------------------------------------ файлы

def load(path) -> Picture:
    with Image.open(path) as im:
        im.load()
        indexed = im.mode in ("1", "L", "LA", "P", "PA")
        if "A" in im.getbands() or im.mode in ("P", "PA"):
            im = _flatten_on_white(im)
        if im.mode == "1":
            im = im.convert("L")
        elif im.mode.startswith("I"):
            im = Image.fromarray((np.asarray(im, dtype=np.float64) / 257.0 + 0.5).clip(0, 255).astype(np.uint8))
        elif im.mode not in ("L", "RGB"):
            im = im.convert("RGB")
        return Picture(np.array(im), indexed)


def _flatten_on_white(im: Image.Image) -> Image.Image:
    rgba = im.convert("RGBA")
    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    bg.alpha_composite(rgba)
    gray = all(b == "L" for b in im.getbands() if b != "A") or im.mode in ("LA",)
    return bg.convert("L" if gray else "RGB")


def save(picture: Picture, path) -> None:
    px = picture.pixels
    if px.ndim == 3 and (px[..., 0] == px[..., 1]).all() and (px[..., 1] == px[..., 2]).all():
        px = px[..., 0]
    Image.fromarray(np.ascontiguousarray(px)).save(path, format="PNG")


# --------------------------------------------------------------- пиксели

def level(picture: Picture, black: float, white: float) -> Picture:
    """Уровни как MagickLevelImage: black/white — доли от 255, гамма 1.

    Если black > white, получается инверсия с порогом (так строится «негатив»
    для поиска рамок кадров).
    """
    bp, wp = black * 255.0, white * 255.0
    v = picture.pixels.astype(np.float64)
    out = np.floor(255.0 * (v - bp) / (wp - bp) + 0.5)
    return Picture(np.clip(out, 0, 255).astype(np.uint8), picture.indexed)


def crop(picture: Picture, left: int, top: int, width: int, height: int) -> Picture:
    """Обрезка как в Wand: отрицательный отступ считается от правого/нижнего края,
    а выход за границы картинки просто обрезается."""
    if left < 0:
        left += picture.width
    if top < 0:
        top += picture.height
    if left >= picture.width or top >= picture.height or width <= 0 or height <= 0:
        raise ValueError("область обрезки вне картинки")
    px = picture.pixels[top:min(top + height, picture.height), left:min(left + width, picture.width)]
    return Picture(px.copy(), picture.indexed)


def white_canvas(width: int, height: int, like: Picture) -> Picture:
    shape = (height, width) + like.pixels.shape[2:]
    return Picture(np.full(shape, 255, dtype=np.uint8), indexed=False)


def paste(canvas: Picture, picture: Picture, left: int, top: int) -> None:
    """Кладёт непрозрачную картинку на холст; всё, что вылезает, отрезается."""
    h = min(picture.height, canvas.height - top)
    w = min(picture.width, canvas.width - left)
    if h > 0 and w > 0:
        canvas.pixels[top:top + h, left:left + w] = _match_channels(picture.pixels[:h, :w], canvas.pixels)


def _match_channels(src, dst):
    if src.ndim == dst.ndim:
        return src
    if src.ndim == 2:
        return np.repeat(src[..., None], dst.shape[2], axis=2)
    return src[..., 0]


def is_dark(pixel, inclusive: bool = False) -> bool:
    """Предикат «ещё не белое», которым Multi tool ищет рамки кадров.

    Wand сравнивал цвет пикселя КАК СТРОКУ: 'srgb(r,g,b)' < 'srgb(250,250,250)'.
    Это не числовое сравнение: 30..99 считаются «белыми», а 100..249 — нет.
    Поведение сохранено, чтобы Нарезка резала ровно там же, где раньше.
    """
    values = np.atleast_1d(pixel)
    if values.size == 1:
        values = np.repeat(values, 3)
    s = "srgb({},{},{})".format(*(int(v) for v in values[:3]))
    return s < "srgb(250,250,250)" or (inclusive and s == "srgb(250,250,250)")


# ---------------------------------------------------------- масштабирование

def _mitchell(x):
    b = c = 1.0 / 3.0
    x = np.abs(x)
    near = ((12 - 9 * b - 6 * c) * x ** 3 + (-18 + 12 * b + 6 * c) * x ** 2 + (6 - 2 * b)) / 6
    far = ((-b - 6 * c) * x ** 3 + (6 * b + 30 * c) * x ** 2 + (-12 * b - 48 * c) * x + (8 * b + 24 * c)) / 6
    return np.where(x < 1, near, np.where(x < 2, far, 0.0))


def _lanczos(x):
    x = np.abs(x)
    return np.where(x < 3, np.sinc(x) * np.sinc(x / 3.0), 0.0)


_FILTERS = {"mitchell": (_mitchell, 2.0), "lanczos": (_lanczos, 3.0)}


def _weights(n_in: int, n_out: int, kind: str) -> np.ndarray:
    """Матрица весов (n_out, n_in) — как HorizontalFilter/VerticalFilter в resize.c."""
    func, filter_support = _FILTERS[kind]
    factor = n_out / n_in
    scale = max(1.0 / factor + _EPSILON, 1.0)
    support = scale * filter_support
    scale = 1.0 / scale
    m = np.zeros((n_out, n_in))
    for i in range(n_out):
        bisect = (i + 0.5) / factor + _EPSILON
        start = int(max(bisect - support + 0.5, 0.0))
        stop = int(min(bisect + support + 0.5, float(n_in)))
        j = np.arange(start, stop)
        w = func(scale * (j - bisect + 0.5))
        density = w.sum()
        if density != 0.0 and density != 1.0:
            w = w / density
        m[i, start:stop] = w
    return m


def _quantize(a: np.ndarray) -> np.ndarray:
    return np.clip(np.floor(a + 0.5), 0, 255).astype(np.uint8)


def resize(picture: Picture, width: int, height: int) -> Picture:
    """Масштабирование алгоритмом ImageMagick с тем же выбором фильтра."""
    src = picture.pixels
    in_h, in_w = src.shape[:2]
    if (width, height) == (in_w, in_h):
        return picture.copy()
    enlarging = width * height > in_w * in_h
    kind = "mitchell" if picture.indexed or enlarging else "lanczos"
    wx = _weights(in_w, width, kind)
    wy = _weights(in_h, height, kind)

    a = src.astype(np.float64)
    if a.ndim == 2:
        a = a[..., None]
    horizontal_first = width * (in_h + height) > height * (in_w + width)
    if horizontal_first:
        a = _quantize(np.einsum("ox,yxc->yoc", wx, a)).astype(np.float64)
        a = _quantize(np.einsum("oy,yxc->oxc", wy, a))
    else:
        a = _quantize(np.einsum("oy,yxc->oxc", wy, a)).astype(np.float64)
        a = _quantize(np.einsum("ox,yxc->yoc", wx, a))
    if src.ndim == 2:
        a = a[..., 0]
    return Picture(a, picture.indexed)
