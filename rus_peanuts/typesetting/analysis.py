"""Анализ стрипа: поиск Надписей на Оригинале, места Реплик и Звуков, Очистка.

Классическое компьютерное зрение без нейросетей, один проход для любых надписей —
от мелких букв реплик до крупных букв звуков:

1. Связные области тёмных пикселей. Кандидат в буквы — область размером с букву
   на светлом фоне; остальное крупное — «стенки»: рамки кадров, контуры Баблов, рисунок.
2. Буква подтверждается соседями той же высоты в той же строке.
3. Соседние буквы похожего размера, между которыми нет стенки, собираются в Надпись.
   В Надписи должны быть хотя бы три буквы подряд, как в слове.
4. Где стоит Надпись: из её центра пускаются лучи. Если почти все упираются в линию
   рядом — Надпись в Бабле (место Реплики), иначе — на рисунке (место Звука).
   Крупные буквы без общего контура вокруг — тоже Звук, даже если рядом тесно.
5. Не места: логотип PEANUTS (крупные буквы в прямоугольной рамке), подписи под
   стрипами (белое поле до края картинки), мелкие пометки рисунка — лица, трава,
   подпись SCHULZ, дата (их буквы заметно мельче обычных букв реплик).

Пороги в пикселях подобраны под сканы шириной ~2200 px.
"""
import math
from dataclasses import dataclass
from typing import NamedTuple

import cv2
import numpy as np

DARK, LIGHT = 200, 210          # тёмное — буквы и линии, светлое — фон
LETTER_H = (7, 140)             # высота буквы, px
SMALL_MAX = 42                  # до этой высоты — буквы реплик, выше — крупные буквы
SURROUND = 0.72                 # доля светлого вокруг кандидата в буквы
MIN_WORD = 3                    # букв подряд в Надписи
RAYS = 32
FAR_MARGIN = 2.5                # луч не встретил линию за столько высот букв — открытое место
FAR_SHARE = 0.2                 # столько лучей может уйти в открытое место у Надписи в Бабле
BIG_LETTERS = 1.25              # крупные буквы — во столько раз выше обычных букв реплик
LOOSE_HUG = 0.75                # у Бабла общий контур ловит хотя бы столько лучей
MIN_REL = 0.7                   # буквы мельче этой доли обычных — пометки рисунка
SOUND_MIN_REL = 0.75            # то же для Надписи на рисунке: там пометок больше (лица, трава)
WATERMARK = (28, 0.35)          # надпись группы вверху слева на готовых стрипах: высота, доля ширины
BUBBLE_PAD = (6, 5, 14, 5)      # поля места Реплики вокруг букв: слева, сверху, справа, снизу
SOUND_PAD = (8, 8, 16, 8)


class Box(NamedTuple):
    """Место Реплики на стрипе (область старого английского текста с полями)."""
    x: int
    y: int
    w: int
    h: int


class SoundBox(NamedTuple):
    """Место Звука на стрипе и его Изгиб (плюс — дуга вверх)."""
    x: int
    y: int
    w: int
    h: int
    arch: int


@dataclass
class StripAnalysis:
    original: np.ndarray        # BGR, как прочитан с диска
    bubbles: list[Box]          # в Порядке чтения
    sounds: list[SoundBox]      # в Порядке чтения
    cleaned: np.ndarray         # Оригинал после Очистки всех найденных мест


def load_image(path) -> np.ndarray | None:
    """Читает картинку в BGR (в том числе по путям с кириллицей). None — не картинка."""
    stream = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(stream, cv2.IMREAD_COLOR)


def analyze(img: np.ndarray) -> StripAnalysis:
    scan = _Scan(img)
    places = scan.lettering()
    bubbles = [p for p in places if p.kind == "bubble"]
    sounds = [p for p in places if p.kind == "sound"]
    H = img.shape[0]
    bubble_boxes = [Box(*p.padded(BUBBLE_PAD, scan.W, scan.H)) for p in bubbles]
    sound_boxes = [SoundBox(*p.padded(SOUND_PAD, scan.W, scan.H), scan.arch(p)) for p in sounds]
    erase_mask = scan.erase_mask(bubble_boxes + [b[:4] for b in sound_boxes])
    cleaned = _clean(img, erase_mask, bubble_boxes + sound_boxes)
    return StripAnalysis(
        original=img,
        bubbles=_sort_reading_order(bubble_boxes, H),
        sounds=_sort_reading_order(sound_boxes, H),
        cleaned=cleaned,
    )


def _clean(orig_img, erase_mask, boxes):
    cleaned = orig_img.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    for b in boxes:
        x, y, w, h = b[0], b[1], b[2], b[3]
        roi = erase_mask[y:y + h, x:x + w]
        dilated = cv2.dilate(roi, kernel, iterations=1)
        cleaned[y:y + h, x:x + w][dilated > 0] = [255, 255, 255]
    return cleaned


def _sort_reading_order(box_list, H):
    box_list = sorted(box_list, key=lambda b: b[1])
    rows = []
    row_thresh = max(70, min(150, int(H * 0.18)))
    for b in box_list:
        for r in rows:
            if abs(b[1] - np.mean([item[1] for item in r])) < row_thresh:
                r.append(b)
                break
        else:
            rows.append([b])
    res = []
    for r in rows:
        res.extend(sorted(r, key=lambda b: b[0]))
    return res


@dataclass
class _Lettering:
    """Надпись: буквы (номера связных областей) и где она стоит."""
    members: list
    height: float                 # высота букв самого длинного слова
    letters: tuple                # x0, y0, x1, y1 — границы букв
    kind: str = ""                # bubble, sound, logo, margin, tiny
    far: float = 0.0              # доля лучей, ушедших в открытое место
    hug: float = 0.0              # доля лучей, упёршихся в общий контур вокруг Надписи
    rel: float = 0.0              # высота букв относительно обычных букв реплик
    region: int = 0               # белая область вокруг Надписи

    def padded(self, pad, W, H):
        x0, y0, x1, y1 = self.letters
        left, top, right, bottom = pad
        x, y = max(0, x0 - left), max(0, y0 - top)
        return int(x), int(y), int(min(W - x, x1 - x0 + left + right)), int(min(H - y, y1 - y0 + top + bottom))


class _Scan:
    def __init__(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        self.H, self.W = gray.shape
        _, self.dark = cv2.threshold(gray, DARK, 255, cv2.THRESH_BINARY_INV)
        _, light = cv2.threshold(gray, LIGHT, 1, cv2.THRESH_BINARY)
        self.light = cv2.integral(light)
        self.n, self.labels, self.stats, _ = cv2.connectedComponentsWithStats(self.dark, connectivity=8)

    # -------------------------------------------------------------- помощники

    def light_share(self, x0, y0, x1, y1, own=0) -> float:
        """Доля светлых пикселей в прямоугольнике (без `own` пикселей самой области)."""
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(self.W, x1), min(self.H, y1)
        L = self.light
        count = int(L[y1, x1] - L[y0, x1] - L[y1, x0] + L[y0, x0])
        return count / max(1, (x1 - x0) * (y1 - y0) - own)

    def region_at(self, x0, y0, x1, y1) -> int:
        """Белая область (между стенками), которая занимает прямоугольник больше всех."""
        sub = self.regions[y0:y1, x0:x1]
        vals = sub[sub > 0]
        return int(np.bincount(vals).argmax()) if len(vals) else 0

    def crosses(self, mask, x0, y0, x1, y1) -> bool:
        steps = int(max(abs(x1 - x0), abs(y1 - y0)) / 2) + 2
        xs = np.clip(np.linspace(x0, x1, steps).astype(int), 0, self.W - 1)
        ys = np.clip(np.linspace(y0, y1, steps).astype(int), 0, self.H - 1)
        return bool(mask[ys, xs].any())

    # ------------------------------------------------------------ поиск букв

    def lettering(self) -> list[_Lettering]:
        stats, n = self.stats, self.n
        x, y, w, h, area = (stats[:, k] for k in range(5))
        watermark = (y < WATERMARK[0]) & (x < self.W * WATERMARK[1])
        watermark[0] = False
        big = (w > 48) | (h > 45) | (area > 800)
        small = h <= SMALL_MAX
        h_max = min(LETTER_H[1], int(self.H * 0.25))
        shape_ok = ((h >= LETTER_H[0]) & (h <= h_max) & (w >= 2) & (w <= h * np.where(small, 5.0, 3.0))
                    & (area >= np.where(small, 8, 35)) & ~watermark)
        shape_ok[0] = False
        cand = np.zeros(n, bool)
        for i in np.nonzero(shape_ok)[0]:
            pad = 4 if small[i] else 5
            if self.light_share(x[i] - pad, y[i] - pad, x[i] + w[i] + pad, y[i] + h[i] + pad, area[i]) > SURROUND:
                cand[i] = True

        barrier = watermark | (big & ~cand)
        barrier[0] = False
        self.barrier = barrier
        barrier_mask = barrier.astype(np.uint8)[self.labels]

        verified = self._verify(np.nonzero(cand)[0], barrier_mask)
        small_h = [h[i] for i in verified if small[i]]
        med_small = float(np.median(small_h)) if small_h else 25.0

        # крупное, что не подтвердилось как буква, — рисунок, то есть стенка
        barrier |= big & cand & ~np.isin(np.arange(n), list(verified))
        self.barrier = barrier
        self.barrier_mask = barrier.astype(np.uint8)[self.labels]
        self.thick = cv2.dilate(self.barrier_mask, np.ones((3, 3), np.uint8))

        letters = self._with_neighbours(verified, np.nonzero(cand & ~big)[0])
        places = [p for p in (self._place(g) for g in self._group(letters)) if p]
        self._classify(places, med_small)
        return [p for p in places if p.kind != "merged"]

    def _verify(self, ids, barrier_mask) -> set:
        """Буквы, у которых есть хотя бы два соседа той же высоты в той же строке."""
        st = self.stats[ids].astype(float)
        bx, by, bw, bh = st[:, 0], st[:, 1], st[:, 2], st[:, 3]
        cy = by + bh / 2
        verified = set()
        for a in range(len(ids)):
            ha = bh[a]
            gap = np.maximum(0, np.maximum(bx - (bx[a] + bw[a]), bx[a] - (bx + bw)))
            near = ((np.abs(cy - cy[a]) < 0.6 * ha) & (np.abs(bh - ha) <= max(4, 0.3 * ha))
                    & (gap < ha * (2.5 if ha <= SMALL_MAX else 1.5)))
            near[a] = False
            js = np.nonzero(near)[0]
            if len(js) < 2:
                continue
            mx = ((bx[a] + bw[a] / 2 + bx[js] + bw[js] / 2) / 2).astype(int)
            my = ((cy[a] + cy[js]) / 2).astype(int)
            if np.count_nonzero(barrier_mask[my, mx] == 0) >= 2:
                verified.add(int(ids[a]))
        return verified

    def _with_neighbours(self, verified, small_ids) -> set:
        """Добавляет буквы без двух соседей (I, ?, !), стоящие вплотную к подтверждённым."""
        stats = self.stats
        near = np.zeros((self.H, self.W), np.uint8)
        for i in verified:
            x, y, w, h = stats[i, :4]
            cv2.rectangle(near, (int(x - 1.1 * h), int(y - 0.4 * h)), (int(x + w + 1.1 * h), int(y + 1.4 * h)), 1, -1)
        letters = set(verified)
        for i in small_ids:
            if i in letters:
                continue
            x, y, w, h = stats[i, :4]
            if near[y:y + h, x:x + w].any() and not self.barrier_mask[y:y + h, max(0, x - 12):x + w].any():
                letters.add(int(i))
        return letters

    def _group(self, letters) -> list[list]:
        """Надписи: соседние буквы похожего размера, между которыми нет стенки."""
        order = np.array(sorted(letters), dtype=int)
        if not len(order):
            return []
        parent = list(range(len(order)))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        lx, ly, lw, lh = (self.stats[order, k].astype(float) for k in range(4))
        for a in range(len(order)):
            gap_x = np.maximum(0, np.maximum(lx - (lx[a] + lw[a]), lx[a] - (lx + lw)))
            gap_y = np.maximum(0, np.maximum(ly - (ly[a] + lh[a]), ly[a] - (ly + lh)))
            near = ((gap_x <= 0.78 * (lh + lh[a])) & (gap_y <= 0.58 * (lh + lh[a]))
                    & (np.maximum(lh, lh[a]) <= 2.2 * np.minimum(lh, lh[a])))
            near[:a + 1] = False
            for b in np.nonzero(near)[0]:
                if find(a) == find(b):
                    continue
                if not self.crosses(self.thick, lx[a] + lw[a] / 2, ly[a] + lh[a] / 2, lx[b] + lw[b] / 2, ly[b] + lh[b] / 2):
                    parent[find(a)] = find(b)
        groups = {}
        for k, i in enumerate(order):
            groups.setdefault(find(k), []).append(int(i))
        return list(groups.values())

    def _word(self, members) -> list:
        """Самая длинная цепочка букв подряд в одной строке: соседние, одной высоты, на одной линии."""
        stats = self.stats
        order = sorted(members, key=lambda i: stats[i, 0])
        best = {i: [i] for i in order}
        for a in order:
            xa, ya, wa, ha = stats[a, :4]
            for b in order:
                xb, yb, wb, hb = stats[b, :4]
                if xb <= xa:
                    continue
                hh = max(ha, hb)
                gap = xb - (xa + wa)
                if (-0.3 * hh <= gap < 0.9 * hh and abs(ha - hb) <= 0.3 * hh
                        and abs((ya + ha) - (yb + hb)) <= 0.4 * hh and abs((ya + ha / 2) - (yb + hb / 2)) < 0.5 * hh
                        and len(best[a]) + 1 > len(best[b])):
                    best[b] = best[a] + [b]
        return max(best.values(), key=len)

    def _place(self, members) -> _Lettering | None:
        stats = self.stats
        if len(members) < MIN_WORD:
            return None
        word = self._word(members)
        if len(word) < MIN_WORD:
            return None
        height = float(np.median([stats[i, 3] for i in word]))
        x0 = min(stats[i, 0] for i in members)
        y0 = min(stats[i, 1] for i in members)
        x1 = max(stats[i, 0] + stats[i, 2] for i in members)
        y1 = max(stats[i, 1] + stats[i, 3] for i in members)
        if x1 - x0 < height * 2.5:
            return None
        return _Lettering(members=list(members), height=height, letters=(x0, y0, x1, y1))

    # ------------------------------------------------------------ где стоит

    def _rays(self, place, walls) -> None:
        """Лучи из центра Надписи: сколько уходит в открытое место и сколько ловит общий контур."""
        x0, y0, x1, y1 = place.letters
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        half_w, half_h = max(1.0, (x1 - x0) / 2 + 6), max(1.0, (y1 - y0) / 2 + 5)
        far = hug = 0
        for k in range(RAYS):
            t = 2 * math.pi * k / RAYS
            dx, dy = math.cos(t), math.sin(t)
            d = min(half_w / abs(dx) if abs(dx) > 1e-9 else 1e9, half_h / abs(dy) if abs(dy) > 1e-9 else 1e9)
            limit = d + FAR_MARGIN * place.height
            hit = None
            while d <= limit:
                px, py = int(cx + dx * d), int(cy + dy * d)
                if not (0 <= px < self.W and 0 <= py < self.H):
                    break
                if walls[py, px]:
                    hit = (px, py)
                    break
                d += 1.5
            if hit is None:
                far += 1
                continue
            px, py = hit
            win = self.labels[max(0, py - 2):py + 3, max(0, px - 2):px + 3]
            found = win[self.barrier[win]]
            if len(found):
                lx, ly, lw, lh = self.stats[int(np.bincount(found).argmax()), :4]
                if lx <= cx <= lx + lw and ly <= cy <= ly + lh:
                    hug += 1
        place.far, place.hug = far / RAYS, hug / RAYS

    def _classify(self, places, med_small) -> None:
        walls = self.thick
        for p in places:
            self._rays(p, walls)
        sure = [p.height for p in places if p.far <= FAR_SHARE and len(p.members) >= 6]
        ref_h = float(np.median(sure)) if sure else med_small
        free = (walls == 0).astype(np.uint8)
        _, self.regions, rstats, _ = cv2.connectedComponentsWithStats(free, connectivity=4)
        for p in places:
            p.rel = p.height / ref_h
            p.region = self.region_at(*p.letters)

        # логотип PEANUTS: крупные буквы в прямоугольной рамке в первом кадре
        def top_left(p):
            return p.letters[1] < self.H * 0.45 and p.letters[0] < self.W * 0.45

        logo = set()
        for p in places:
            if top_left(p) and p.region and sum(self.stats[i, 3] > 2.2 * ref_h for i in p.members) >= 3:
                rx, ry, rw, rh, rarea = rstats[p.region]
                if rarea / float(rw * rh) > 0.85:
                    logo.add(p.region)

        for p in places:
            enclosed = p.far <= FAR_SHARE and not (p.rel > BIG_LETTERS and p.hug < LOOSE_HUG)
            rx, ry, rw, rh, _ = rstats[p.region]
            if top_left(p) and p.region in logo:
                p.kind = "logo"
            elif p.rel < MIN_REL:
                p.kind = "tiny"
            elif enclosed:
                p.kind = "bubble"
            elif not p.region or rx == 0 or ry == 0 or rx + rw >= self.W or ry + rh >= self.H:
                p.kind = "margin"
            elif (p.rel < SOUND_MIN_REL or len(p.members) < 4
                  or sum(self.stats[i, 2] >= 0.35 * self.stats[i, 3] for i in p.members) < 3):
                p.kind = "tiny"
            else:
                p.kind = "sound"
        self._merge_bubble_pieces(places)

    def _merge_bubble_pieces(self, places) -> None:
        """Куски одного Бабла (буквы посередине слиплись с контуром): одна область, одна строка."""
        bubbles = [p for p in places if p.kind == "bubble"]
        merged = True
        while merged:
            merged = False
            for a in bubbles:
                for b in bubbles:
                    if a is b or a.kind != "bubble" or b.kind != "bubble" or a.region != b.region:
                        continue
                    ax0, ay0, ax1, ay1 = a.letters
                    bx0, by0, bx1, by1 = b.letters
                    overlap = min(ay1, by1) - max(ay0, by0)
                    gap = max(bx0 - ax1, ax0 - bx1)
                    if overlap > 0.5 * min(ay1 - ay0, by1 - by0) and gap < 6 * max(a.height, b.height):
                        a.letters = (min(ax0, bx0), min(ay0, by0), max(ax1, bx1), max(ay1, by1))
                        a.members = a.members + b.members
                        b.kind = "merged"
                        merged = True

    # --------------------------------------------------------------- Очистка

    def erase_mask(self, boxes) -> np.ndarray:
        """Что стереть: всё, кроме стенок, внутри мест и в той же белой области, что и место
        (так за контуром Бабла ничего не стирается, даже если поле места за него заходит)."""
        stats = self.stats
        x, y, w, h = (stats[:, k] for k in range(4))
        erase = np.zeros(self.n, bool)
        for bx, by, bw, bh in boxes:
            region = self.region_at(bx, by, bx + bw, by + bh)
            inside = (~self.barrier & (x >= bx - 4) & (x + w <= bx + bw + 6) & (y >= by - 4) & (y + h <= by + bh + 4))
            inside[0] = False
            for i in np.nonzero(inside)[0]:
                if self.region_at(x[i] - 2, y[i] - 2, x[i] + w[i] + 2, y[i] + h[i] + 2) != region:
                    continue
                if h[i] < 5 and self.light_share(x[i] - 4, y[i] - 4, x[i] + w[i] + 4, y[i] + h[i] + 4) < 185 / 255:
                    continue  # точка в тёмном месте — скорее штриховка, чем знак препинания
                erase[i] = True
        return erase.astype(np.uint8)[self.labels] * 255

    def arch(self, place) -> int:
        return _read_arch([self.stats[i, :4] for i in place.members])


def _read_arch(letters) -> int:
    """Изгиб Звука по центрам букв: парабола через них, коэффициент при x² (в пикселях)."""
    try:
        pts_x = np.array([b[0] + b[2] / 2.0 for b in letters], dtype=np.float64)
        pts_y = np.array([b[1] + b[3] / 2.0 for b in letters], dtype=np.float64)
        if len(pts_x) >= 3 and (pts_x.max() - pts_x.min()) > 30:
            mid_x = (pts_x.max() + pts_x.min()) / 2.0
            half_w = (pts_x.max() - pts_x.min()) / 2.0
            nx = (pts_x - mid_x) / half_w  # [-1, 1]
            coeffs = np.polyfit(nx, pts_y, 2)
            if abs(coeffs[0]) >= 5.0:  # coeffs[0] > 0: края ниже середины
                return int(max(-120, min(120, round(coeffs[0]))))
    except Exception:
        pass
    return 0
