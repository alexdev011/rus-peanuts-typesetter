"""Анализ стрипа: поиск Баблов и Звуков на Оригинале и Очистка английского текста.

Классическое компьютерное зрение без нейросетей: связные области тёмных пикселей
делятся на «барьеры» (рамки, рисунок) и кандидаты в буквы; буквы, у которых есть
соседи того же размера, собираются в группы — места Реплик и Звуков.

Все пороги заданы в пикселях и подобраны под сканы определённого разрешения.
"""
from dataclasses import dataclass
from typing import NamedTuple

import cv2
import numpy as np


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
    erase_mask, bubbles, sounds = _detect(img)
    cleaned = _clean(img, erase_mask, list(bubbles) + list(sounds))
    return StripAnalysis(original=img, bubbles=bubbles, sounds=sounds, cleaned=cleaned)


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
    box_list.sort(key=lambda b: b[1])
    rows = []
    row_thresh = max(70, min(150, int(H * 0.18)))
    for b in box_list:
        placed = False
        for r in rows:
            avg_y = np.mean([item[1] for item in r])
            if abs(b[1] - avg_y) < row_thresh:
                r.append(b)
                placed = True
                break
        if not placed:
            rows.append([b])
    res = []
    for r in rows:
        r.sort(key=lambda b: b[0])
        res.extend(r)
    return res


def _detect(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape

    _, dark_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    _, white_mask = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(dark_mask, connectivity=8)

    barrier_ids = []
    candidates = []
    sfx_candidates = []

    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]

        if y < 28 and x < W * 0.35:
            barrier_ids.append(i)
            continue

        if 30 <= h <= min(140, int(H * 0.25)) and 4 <= w <= h * 1.6 and area >= 35:
            pad = 5
            y1, y2 = max(0, y - pad), min(H, y + h + pad)
            x1, x2 = max(0, x - pad), min(W, x + w + pad)
            if np.mean(white_mask[y1:y2, x1:x2]) > 135:
                sfx_candidates.append((i, x, y, w, h))

        if w > 48 or h > 45 or area > 800:
            barrier_ids.append(i)
            continue

        if 7 <= h <= 42 and 2 <= w <= h * 3.0 and area >= 8:
            pad = 4
            y1, y2 = max(0, y - pad), min(H, y + h + pad)
            x1, x2 = max(0, x - pad), min(W, x + w + pad)
            if np.mean(white_mask[y1:y2, x1:x2]) > 160:
                candidates.append((i, x, y, w, h))

    barrier_lut = np.zeros(num_labels, dtype=np.uint8)
    barrier_lut[barrier_ids] = 255
    barrier_mask = barrier_lut[labels]

    verified_letters = []

    for (idx_i, x, y, w, h) in candidates:
        cy = y + h / 2.0
        neighbors = 0
        for (idx_j, nx, ny, nw, nh) in candidates:
            if idx_i == idx_j:
                continue
            ncy = ny + nh / 2.0
            if abs(cy - ncy) < h * 0.60 and abs(h - nh) <= max(4, h * 0.28):
                dist_x = max(0, max(x - (nx + nw), nx - (x + w)))
                if dist_x < h * 2.5:
                    mid_x = int(((x + w / 2) + (nx + nw / 2)) / 2)
                    mid_y = int((cy + ncy) / 2)
                    if barrier_mask[mid_y, mid_x] == 0:
                        neighbors += 1
        if neighbors >= 2:
            verified_letters.append((idx_i, x, y, w, h))

    med_h = float(np.median([b[4] for b in verified_letters])) if verified_letters else 15.0

    filtered_letters = []
    filtered_ids = []
    for b in verified_letters:
        if med_h * 0.65 <= b[4] <= med_h * 1.45:
            filtered_letters.append(b)
            filtered_ids.append(b[0])

    filtered_lut = np.zeros(num_labels, dtype=np.uint8)
    filtered_lut[filtered_ids] = 255
    filtered_mask = filtered_lut[labels]

    near_filtered = cv2.dilate(filtered_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (int(med_h * 2.2), int(med_h * 0.8))))
    for (idx_i, x, y, w, h) in candidates:
        if med_h * 0.55 <= h <= med_h * 1.45 and np.any(near_filtered[y:y + h, x:x + w] > 0):
            if not np.any(barrier_mask[y:y + h, max(0, x - 12):x + w] > 0):
                if (idx_i, x, y, w, h) not in filtered_letters:
                    filtered_letters.append((idx_i, x, y, w, h))
                    filtered_ids.append(idx_i)

    filtered_lut = np.zeros(num_labels, dtype=np.uint8)
    filtered_lut[filtered_ids] = 255
    filtered_mask = filtered_lut[labels]

    kw = max(16, int(med_h * 1.55))
    kh = max(11, int(med_h * 1.15))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
    grouped = cv2.dilate(filtered_mask, kernel, iterations=1)

    thick_barriers = cv2.dilate(barrier_mask, np.ones((3, 3), np.uint8), iterations=1)
    grouped[thick_barriers > 0] = 0

    contours, _ = cv2.findContours(grouped, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    valid_bubbles = []
    for cnt in contours:
        bx, by, bw, bh = cv2.boundingRect(cnt)
        in_box = [
            b for b in filtered_letters
            if bx <= b[1] and (b[1] + b[3]) <= (bx + bw) and by <= b[2] and (b[2] + b[4]) <= (by + bh)
        ]
        if len(in_box) < 6 or bw < med_h * 2.5:
            continue

        roi_white = white_mask[by:by + bh, bx:bx + bw]
        if np.mean(roi_white) < 170:
            continue

        min_x = min(b[1] for b in in_box)
        min_y = min(b[2] for b in in_box)
        max_x = max(b[1] + b[3] for b in in_box)
        max_y = max(b[2] + b[4] for b in in_box)

        pad_l, pad_r, pad_y = 6, 14, 5
        rx = max(0, min_x - pad_l)
        ry = max(0, min_y - pad_y)
        rw = min(W - rx, (max_x - min_x) + pad_l + pad_r)
        rh = min(H - ry, (max_y - min_y) + pad_y * 2)
        valid_bubbles.append((rx, ry, rw, rh))

    sfx_verified = []
    sfx_ids = []
    for (idx_i, x, y, w, h) in sfx_candidates:
        if y < H * 0.45 and x < W * 0.45:
            continue
        cy = y + h / 2.0
        neighbors = 0
        for (idx_j, nx, ny, nw, nh) in sfx_candidates:
            if idx_i == idx_j:
                continue
            ncy = ny + nh / 2.0
            if abs(cy - ncy) < h * 0.45 and abs(h - nh) <= h * 0.30:
                dist_x = max(0, max(x - (nx + nw), nx - (x + w)))
                if dist_x < h * 1.2:
                    neighbors += 1
        if neighbors >= 3:
            sfx_verified.append((idx_i, x, y, w, h))
            sfx_ids.append(idx_i)

    sfx_lut = np.zeros(num_labels, dtype=np.uint8)
    sfx_lut[sfx_ids] = 255
    sfx_mask = sfx_lut[labels]

    sfx_boxes = []
    if sfx_verified:
        sfx_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (35, 20))
        sfx_grouped = cv2.dilate(sfx_mask, sfx_kernel, iterations=1)
        sfx_cnts, _ = cv2.findContours(sfx_grouped, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in sfx_cnts:
            sx, sy, sw, sh = cv2.boundingRect(cnt)
            in_sfx = [b for b in sfx_verified if sx <= b[1] and (b[1] + b[3]) <= (sx + sw) and sy <= b[2] and (b[2] + b[4]) <= (sy + sh)]
            if len(in_sfx) >= 4 and sw > 90:
                sfx_boxes.append((max(0, sx - 6), max(0, sy - 6), min(W - sx, sw + 16), min(H - sy, sh + 14),
                                  _read_arch(in_sfx)))

    erase_ids = []

    for (bx, by, bw, bh) in valid_bubbles:
        for i in range(1, num_labels):
            if barrier_lut[i]:
                continue
            cx, cy, cw, ch, carea = stats[i]
            if (cx >= bx - 4 and (cx + cw) <= (bx + bw + 6) and
                    cy >= by - 4 and (cy + ch) <= (by + bh + 4)):
                center_x = bx + bw // 2
                center_y = by + bh // 2
                line_check = np.zeros_like(barrier_mask)
                cv2.line(line_check, (center_x, center_y), (cx + cw // 2, cy + ch // 2), 255, 1)
                if np.any((line_check > 0) & (barrier_mask > 0)):
                    continue
                if ch < 5:
                    p = 4
                    y1, y2 = max(0, cy - p), min(H, cy + ch + p)
                    x1, x2 = max(0, cx - p), min(W, cx + cw + p)
                    if np.mean(white_mask[y1:y2, x1:x2]) < 185:
                        continue
                erase_ids.append(i)

    for sfx_b in sfx_boxes:
        sx, sy, sw, sh = sfx_b[0], sfx_b[1], sfx_b[2], sfx_b[3]
        for i in range(1, num_labels):
            cx, cy, cw, ch, carea = stats[i]
            if cx >= sx and (cx + cw) <= (sx + sw) and cy >= sy and (cy + ch) <= (sy + sh):
                if ch <= sh * 0.98 and cw <= sw * 0.45:
                    erase_ids.append(i)

    erase_lut = np.zeros(num_labels, dtype=np.uint8)
    erase_lut[erase_ids] = 255
    erase_mask = erase_lut[labels]

    bubbles = [Box(*(int(v) for v in b)) for b in _sort_reading_order(valid_bubbles, H)]
    sounds = [SoundBox(*(int(v) for v in b)) for b in _sort_reading_order(sfx_boxes, H)]
    return erase_mask, bubbles, sounds


def _read_arch(letters) -> int:
    """Изгиб Звука по центрам букв: парабола через них, коэффициент при x² (в пикселях)."""
    try:
        pts_x = np.array([b[1] + b[3] / 2.0 for b in letters], dtype=np.float64)
        pts_y = np.array([b[2] + b[4] / 2.0 for b in letters], dtype=np.float64)
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
