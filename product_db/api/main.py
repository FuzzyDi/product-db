from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from product_db.api.routes import intake, products, stats

app = FastAPI(title="Product DB", version="0.1.0")

API_PREFIX = "/api/v1"
app.include_router(intake.router, prefix=API_PREFIX)
app.include_router(products.router, prefix=API_PREFIX)
app.include_router(stats.router, prefix=API_PREFIX)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "data": None, "meta": {}, "error": str(exc)},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
