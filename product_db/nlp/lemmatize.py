"""Лемматизация русского текста через pymorphy3."""
import re

import pymorphy3

_morph = pymorphy3.MorphAnalyzer()
_word_re = re.compile(r"[а-яёА-ЯЁa-zA-Z]+")


def lemmatize_ru(text: str) -> str:
    """Возвращает строку нормальных форм (lowercase)."""
    words = _word_re.findall(text)
    return " ".join(_morph.parse(w.lower())[0].normal_form for w in words)


def lemmatize_tokens(tokens: list[str]) -> list[str]:
    return [_morph.parse(t)[0].normal_form for t in tokens if _word_re.match(t)]
