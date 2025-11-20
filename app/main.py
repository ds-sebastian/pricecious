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
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting smart scheduler (Heartbeat: 1 minute)")
    scheduler.add_job(scheduled_refresh, IntervalTrigger(minutes=1), id="refresh_job", replace_existing=True)
    scheduler.start()
    logger.info("Application started")
    yield
    logger.info("Shutting down scheduler...")
    scheduler.shutdown(wait=True)
    logger.info("Application shutdown complete")


app = FastAPI(title="Pricecious API", version="0.1.0", lifespan=lifespan)

# Rate Limiting & CORS
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.debug(f"Response: {response.status_code}")
    return response


# Static Files
if os.path.exists("static"):
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
os.makedirs("screenshots", exist_ok=True)
app.mount("/screenshots", StaticFiles(directory="screenshots"), name="screenshots")

# Routers
for router in [notifications.router, items.router, settings.router, jobs.router]:
    app.include_router(router, prefix="/api")


@app.get("/api/")
def read_root():
    return {"message": "Welcome to Pricecious API"}


# Frontend Serving
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith(("api", "screenshots", "assets")):
        return {"message": "Not found"}
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "Frontend not built or not found"}
