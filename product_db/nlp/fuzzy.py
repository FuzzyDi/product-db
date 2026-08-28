"""Нечёткий поиск через rapidfuzz."""
import re

from rapidfuzz import fuzz, process

BRAND_THRESHOLD = 82     # минимальный score для бренда
PRODUCT_THRESHOLD = 75   # минимальный score для товара


def find_best_brand(
    text: str,
    aliases: list[tuple[str, int, str]],  # (alias, brand_id, canonical_name)
) -> tuple[int | None, str | None, float]:
    """Возвращает (brand_id, canonical_name, score) или (None, None, 0)."""
    if not aliases:
        return None, None, 0.0

    text_norm = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", " ", text).strip().lower()
    best_substring: tuple[int, str] | None = None
    best_len = 0
    for alias, brand_id, canonical in aliases:
        alias_norm = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", " ", alias).strip().lower()
        if len(alias_norm.replace(" ", "")) < 3:
            continue
        if f" {alias_norm} " in f" {text_norm} ":
            if len(alias_norm) > best_len:
                best_substring = (brand_id, canonical)
                best_len = len(alias_norm)

    if best_substring:
        brand_id, canonical = best_substring
        return brand_id, canonical, 100.0

    alias_texts = [a[0] for a in aliases]
    result = process.extractOne(
        text,
        alias_texts,
        scorer=fuzz.token_set_ratio,
        score_cutoff=BRAND_THRESHOLD,
    )
    if result is None:
        return None, None, 0.0

    matched_alias, score, idx = result
    _, brand_id, canonical = aliases[idx]
    return brand_id, canonical, float(score)


def score_names(a: str, b: str) -> float:
    """Token sort ratio между двумя названиями (0-100)."""
    return fuzz.token_sort_ratio(a, b)
