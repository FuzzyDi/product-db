import logging
import time

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from starlette.middleware.base import BaseHTTPMiddleware

from product_db.api.routes import intake, mxik, products, refs, review, stats
from product_db.config import settings
from product_db.core.auth import require_api_key
from product_db.core.logging_config import setup_logging
from product_db.core.ratelimit import limiter

# Логирование
setup_logging()
logger = logging.getLogger(__name__)

# Sentry (если настроен)
if settings.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.05,
        environment="production",
    )
    logger.info("Sentry инициализирован")


# ---------------------------------------------------------------------------
# HTTP logging middleware
# ---------------------------------------------------------------------------
class _RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed = round((time.perf_counter() - t0) * 1000)
        logger.info(
            "%s %s %d %dms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
API_PREFIX = "/api/v1"

app = FastAPI(
    title="Product DB",
    version="0.3.0",
    dependencies=[Depends(require_api_key)],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(_RequestLogMiddleware)

app.include_router(intake.router,   prefix=API_PREFIX)
app.include_router(products.router, prefix=API_PREFIX)
app.include_router(review.router,   prefix=API_PREFIX)
app.include_router(mxik.router,     prefix=API_PREFIX)
app.include_router(refs.router,     prefix=API_PREFIX)
app.include_router(stats.router,    prefix=API_PREFIX)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"success": False, "data": None, "meta": {}, "error": str(exc)},
    )


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "version": app.version}
