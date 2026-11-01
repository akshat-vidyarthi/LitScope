import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.rate_limiter import RateLimitMiddleware
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.papers import router as papers_router
from app.api.discovery import router as discovery_router
from app.api.matrix import router as matrix_router
from app.api.gaps import router as gaps_router
from app.api.reviews import router as reviews_router

logger = logging.getLogger("litscope")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from app.core.migration_runner import run_database_migrations
        run_database_migrations()
    except Exception:
        pass
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Research Paper Intelligence Platform Backend API",
    version="0.1.0",
    lifespan=lifespan
)

# Enforce rate limiting before expensive endpoints
app.add_middleware(RateLimitMiddleware)

# Configure CORS for local development and cloud production (Render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global unhandled exception handler to sanitize 500 errors and protect internal details
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."}
    )

# Register routes under /api/v1
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(projects_router, prefix=settings.API_V1_STR)
app.include_router(papers_router, prefix=settings.API_V1_STR)
app.include_router(discovery_router, prefix=settings.API_V1_STR)
app.include_router(matrix_router, prefix=settings.API_V1_STR)
app.include_router(gaps_router, prefix=settings.API_V1_STR)
app.include_router(reviews_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "app": settings.PROJECT_NAME,
        "version": "0.1.0",
        "docs_url": "/docs"
    }
