"""Step 3: нормализация текста, определение языка, транслитерация."""
import re
import unicodedata

from .context import PipelineContext

# Узбекский кириллица → латиница (базовая таблица)
_CYRL_LATN: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sh", "ъ": "'", "ь": "", "э": "e",
    "ю": "yu", "я": "ya",
    # Узбекские специфичные
    "ғ": "g'", "қ": "q", "ҳ": "h", "ў": "o'",
}

# Паттерн для узбекской кириллицы (chars not in Russian)
_UZ_CYRL_CHARS = re.compile(r"[ғқҳў]")
# Паттерн русского текста
_RU_CHARS = re.compile(r"[а-яёА-ЯЁ]")


def _detect_language(text: str) -> str:
    if _UZ_CYRL_CHARS.search(text):
        return "uz-cyrl"
    if _RU_CHARS.search(text):
        return "ru"
    if re.search(r"[a-zA-Z]", text):
        return "uz-latn"
    return "unknown"


def _uz_cyrl_to_latn(text: str) -> str:
    result = []
    for ch in text:
        lower = ch.lower()
        if lower in _CYRL_LATN:
            mapped = _CYRL_LATN[lower]
            result.append(mapped.upper() if ch.isupper() else mapped)
        else:
            result.append(ch)
    return "".join(result)


def _normalize_text(text: str) -> str:
    # Убираем лишние пробелы, нормализуем unicode
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[\s,;/\-–—]+", text.lower()) if t]


def run(ctx: PipelineContext) -> PipelineContext:
    text = _normalize_text(ctx.name_raw)
    lang = _detect_language(text)
    ctx.language = lang

    if lang == "uz-cyrl":
        text = _uz_cyrl_to_latn(text)
        ctx.language = "uz-latn"

    ctx.name_normalized = text.lower()
    ctx.tokens = tokenize(text)
    return ctx
