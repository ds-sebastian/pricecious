import logging
import os
from contextlib import asynccontextmanager

from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.limiter import limiter
from app.routers import items, jobs, notifications, settings
from app.services.scheduler_service import scheduled_refresh, scheduler

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting smart scheduler (Heartbeat: 1 minute)")
    scheduler.add_job(scheduled_refresh, IntervalTrigger(minutes=1), id="refresh_job", replace_existing=True)
    scheduler.start()
    logger.info("Application started")

    yield

    # Shutdown
    logger.info("Shutting down scheduler...")
    scheduler.shutdown(wait=True)
    logger.info("Application shutdown complete")


app = FastAPI(title="Pricecious API", version=VERSION, lifespan=lifespan)

# Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware for logging requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.debug(f"Response: {response.status_code}")
    return response


# Mount static files
if os.path.exists("static"):
    logger.info("Mounting static files from static")
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
else:
    logger.warning("Static files directory static not found")

# Mount screenshots
os.makedirs("screenshots", exist_ok=True)
app.mount("/screenshots", StaticFiles(directory="screenshots"), name="screenshots")


# Include Routers
app.include_router(notifications.router, prefix="/api")
app.include_router(items.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")


@app.get("/api/")
def read_root():
    return {"message": "Welcome to Pricecious API"}


# Serve index.html at root
@app.get("/")
async def serve_index():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "Frontend not built or not found"}


# Catch-all for SPA
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api") or full_path.startswith("screenshots") or full_path.startswith("assets"):
        return {"message": "Not found"}

    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "Frontend not built or not found"}
