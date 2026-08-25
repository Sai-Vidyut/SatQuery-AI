from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import analysis, health, imagery, query
from app.core.config import get_settings
from app.core.errors import SatQueryError

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(imagery.router, prefix=settings.api_prefix)
app.include_router(query.router, prefix=settings.api_prefix)
app.include_router(analysis.router, prefix=settings.api_prefix)


@app.exception_handler(SatQueryError)
async def satquery_error_handler(_request: Request, exc: SatQueryError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_response())
