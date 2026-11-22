"""Переносы в Репликах: мягкий перенос (U+00AD) между слогами длинных русских слов."""
import re

SOFT_HYPHEN = "­"
_VOWELS = set("АЕЁИОУЫЭЮЯаеёиоуыэюя")
_NO_SPLIT_BEFORE = "ЬЪЙьъй"
_MIN_LENGTH = 7


def hyphenate_word(word: str) -> str:
    """Расставляет мягкие переносы в слове длиной от 7 букв (упрощённые правила по гласным)."""
    if len(word) < _MIN_LENGTH:
        return word
    v_indices = [i for i, ch in enumerate(word) if ch in _VOWELS]
    if len(v_indices) < 2:
        return word

    parts = []
    last_idx = 0
    for k in range(len(v_indices) - 1):
        v1 = v_indices[k]
        v2 = v_indices[k + 1]
        cut = v1 + 1 if (v2 - v1) <= 2 else v1 + 2
        while cut < v2 and word[cut] in _NO_SPLIT_BEFORE:
            cut += 1
        if cut >= 2 and (len(word) - cut) >= 2 and cut > last_idx:
            parts.append(word[last_idx:cut])
            last_idx = cut

    parts.append(word[last_idx:])
    return SOFT_HYPHEN.join(parts)


def hyphenate_text(text: str) -> str:
    """Переносы во всех длинных кириллических словах текста; остальное не трогается."""
    return re.sub(r"[А-ЯЁа-яё]{7,}", lambda m: hyphenate_word(m.group(0)), text)
