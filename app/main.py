import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app import checks, scraper
from app.api import router

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(os.getenv("STATIC_DIR", "static"))


def trusted_origins() -> set[str]:
    origins = {o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()}
    if "*" in origins:
        logger.warning("Ignoring wildcard in CORS_ORIGINS; list trusted origins explicitly")
        origins.discard("*")
    return origins


TRUSTED_ORIGINS = trusted_origins()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await checks.release_all_claims()
    try:
        await scraper.start()
    except scraper.ScrapeError as exc:
        logger.warning(f"{exc}. Will retry on the first check.")
    checks.spawn(checks.run_scheduler())
    yield
    await checks.shutdown()
    await scraper.stop()


app = FastAPI(title="Pricecious", lifespan=lifespan)

if TRUSTED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(TRUSTED_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _own_origin(request: Request) -> str:
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{scheme}://{host.split(',')[0].strip()}"


@app.middleware("http")
async def reject_cross_origin_writes(request: Request, call_next):
    """There is no login, so stop other websites from making a visitor's browser change anything."""
    if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin", "").rstrip("/")
        if origin:
            allowed = origin in TRUSTED_ORIGINS or origin == _own_origin(request)
        else:
            allowed = request.headers.get("sec-fetch-site") != "cross-site"
        if not allowed:
            return JSONResponse({"detail": "Cross-origin requests are not allowed"}, status_code=403)
    return await call_next(request)


class MethodOverride:
    """Let the web UI send PUT and DELETE as POST ?_method=...: some reverse-proxy firewalls only let GET and POST
    through (the OWASP Core Rule Set does by default). The REST routes themselves are unchanged."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"].startswith("/api/"):
            query = parse_qsl(scope["query_string"].decode("latin-1"), keep_blank_values=True)
            method = next((value.upper() for key, value in query if key == "_method"), None)
            if method in {"PUT", "DELETE"}:
                rest = urlencode([(key, value) for key, value in query if key != "_method"])
                scope = dict(scope, method=method, query_string=rest.encode("latin-1"))
        await self.app(scope, receive, send)


app.add_middleware(MethodOverride)  # outermost, so everything after it sees the real method


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(router)


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
def api_not_found(path: str):
    raise HTTPException(404, "Not found")


checks.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=checks.SCREENSHOT_DIR), name="screenshots")


class SPAStaticFiles(StaticFiles):
    """Serve the built frontend, falling back to index.html for client-side routes."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


if STATIC_DIR.is_dir():
    app.mount("/", SPAStaticFiles(directory=STATIC_DIR, html=True), name="frontend")
