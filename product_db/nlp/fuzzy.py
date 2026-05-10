"""Нечёткий поиск через rapidfuzz."""
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
