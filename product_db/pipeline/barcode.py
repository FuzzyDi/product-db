"""Step 2: определение типа штрихкода."""
import re

from .context import PipelineContext

# Порядок важен: более специфичные — первыми
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("internal_weight", re.compile(r"^2[278]\d{11}$")),
    ("internal_price",  re.compile(r"^29\d{11}$")),
    ("internal_unit",   re.compile(r"^2[0-6]\d{11}$")),
    ("gs1_128",         re.compile(r"^\(01\)\d+")),
    ("ean8",            re.compile(r"^\d{8}$")),
    ("upc_a",           re.compile(r"^\d{12}$")),
    ("ean13",           re.compile(r"^\d{13}$")),
]

GLOBAL_TYPES = {"ean13", "ean8", "upc_a", "gs1_128"}


def detect_barcode_type(barcode: str) -> str | None:
    for btype, pattern in _PATTERNS:
        if pattern.match(barcode):
            return btype
    return None


def run(ctx: PipelineContext) -> PipelineContext:
    if not ctx.barcode:
        return ctx
    bc = ctx.barcode.strip()
    ctx.barcode_type = detect_barcode_type(bc)
    if ctx.barcode_type and ctx.barcode_type not in GLOBAL_TYPES:
        ctx.issues.append("INTERNAL_BC_AS_GLOBAL")
    return ctx
