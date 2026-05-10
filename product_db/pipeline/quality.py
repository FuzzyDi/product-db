"""Step 8: скоринг качества и флаги для ревью.

Confidence:  сколько атрибутов определено с уверенностью
Completeness: насколько заполнена карточка
"""
from .context import PipelineContext

# Критические: блокируют авто-подтверждение
CRITICAL_ISSUES = {"BARCODE_CONFLICT", "INTERNAL_BC_AS_GLOBAL", "BRAND_TYPE_MISMATCH"}

# Штрафы за completeness
_COMPLETENESS_PENALTIES = {
    "MISSING_BRAND":        0.15,
    "MISSING_PRODUCT_TYPE": 0.20,
    "MISSING_QUANTITY":     0.10,
    "MISSING_MXIK":         0.10,
    "MISSING_BARCODE":      0.05,
}

# Штрафы за confidence
_CONFIDENCE_PENALTIES = {
    "MISSING_BRAND":        0.15,
    "MISSING_PRODUCT_TYPE": 0.20,
    "MISSING_QUANTITY":     0.10,
    "MISSING_MXIK":         0.10,
    "MXIK_GROUP_CODE":      0.10,  # нашли только групповой код
    "INTERNAL_BC_AS_GLOBAL": 0.30,
}


def run(ctx: PipelineContext) -> PipelineContext:
    issues = list(ctx.issues)  # уже могут быть из предыдущих шагов

    if not ctx.brand_id:
        issues.append("MISSING_BRAND")
    if not ctx.product_type_id:
        issues.append("MISSING_PRODUCT_TYPE")
    if ctx.quantity_value is None:
        issues.append("MISSING_QUANTITY")
    if not ctx.mxik_code:
        issues.append("MISSING_MXIK")
    if not ctx.barcode:
        issues.append("MISSING_BARCODE")

    ctx.issues = issues

    # Completeness: штрафуем за отсутствующие поля
    completeness = 1.0
    for issue in issues:
        completeness -= _COMPLETENESS_PENALTIES.get(issue, 0)
    ctx.completeness_score = max(0.0, round(completeness, 3))

    # Confidence: штрафуем за неуверенность
    confidence = 1.0
    for issue in issues:
        confidence -= _CONFIDENCE_PENALTIES.get(issue, 0)
    ctx.confidence_score = max(0.0, round(confidence, 3))

    # Флаги для ревью
    critical = [i for i in issues if i in CRITICAL_ISSUES]
    if critical:
        ctx.review_required = True
        ctx.review_reasons.extend(critical)

    return ctx
