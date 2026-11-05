"""AtlasOps task service. One Uvicorn process per container for correct metrics."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
import hmac
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import time
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, delete, insert, select, text, update
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Title must contain text")
        return value


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    done: bool


def database_url():
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    password = Path(os.getenv("DB_PASSWORD_FILE", "/run/secrets/db_password")).read_text().strip()
    return URL.create("postgresql+psycopg", username="atlas", password=password,
                      host=os.getenv("DB_HOST", "db"), port=5432, database="atlasops")


def create_app(db_url=None, key_file=None, log_file=None):
    key_path = Path(key_file or os.getenv("API_KEY_FILE", "/run/atlasops/api-key"))
    resolved_url = db_url or database_url()
    engine = create_engine(resolved_url, pool_pre_ping=True,
                           connect_args={"connect_timeout": 3} if "postgresql" in str(resolved_url) else {})
    metadata = MetaData()
    tasks = Table("tasks", metadata, Column("id", String(36), primary_key=True),
                  Column("title", String(120), nullable=False),
                  Column("done", Integer, nullable=False, default=0),
                  Column("created_at", String(40), nullable=False))
    registry = CollectorRegistry()
    requests = Counter("atlasops_http_requests_total", "Completed HTTP requests",
                       ["method", "route", "status"], registry=registry)
    duration = Histogram("atlasops_http_request_duration_seconds", "HTTP request latency",
                         ["method", "route"], registry=registry,
                         buckets=(.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5))
    logger = logging.getLogger("atlasops." + uuid.uuid4().hex)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream)
    logfile = log_file or os.getenv("LOG_FILE")
    if logfile:
        Path(logfile).parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(logfile, maxBytes=2_000_000, backupCount=3)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    @asynccontextmanager
    async def lifespan(app):
        # Retries are deliberately bounded: a bad configuration must fail visibly.
        for attempt in range(30):
            try:
                metadata.create_all(engine)
                break
            except SQLAlchemyError:
                if attempt == 29:
                    raise
                time.sleep(2)
        yield
        engine.dispose()
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    app = FastAPI(title="AtlasOps", version=os.getenv("APP_VERSION", "local"),
                  lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.engine = engine

    def read_key():
        try:
            key = key_path.read_text().strip()
        except OSError:
            raise HTTPException(503, "Secret is unavailable")
        if len(key) < 32:
            raise HTTPException(503, "Secret is unavailable")
        return key

    def authenticate(x_api_key: Annotated[str | None, Header()] = None):
        expected = read_key()  # Re-read the Agent's atomic file on every request.
        if x_api_key is None or not hmac.compare_digest(x_api_key.encode(), expected.encode()):
            raise HTTPException(401, "Invalid API key")

    @app.middleware("http")
    async def observe(request: Request, call_next):
        started = time.perf_counter()
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if re.fullmatch(r"[a-zA-Z0-9-]{1,64}", incoming) else uuid.uuid4().hex
        response = await call_next(request)
        route_object = request.scope.get("route")
        route = getattr(route_object, "path", "unmatched")
        method = request.method if request.method in {"GET", "POST", "PATCH", "DELETE", "HEAD", "OPTIONS"} else "OTHER"
        elapsed = time.perf_counter() - started
        if route != "/metrics":
            requests.labels(method, route, str(response.status_code)).inc()
            duration.labels(method, route).observe(elapsed)
        response.headers["X-Request-ID"] = request_id
        if route not in {"/metrics", "/health/live", "/health/ready"}:
            logger.info(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                                    "service": "atlasops-api", "request_id": request_id,
                                    "method": method, "route": route, "status": response.status_code,
                                    "duration_ms": round(elapsed * 1000, 2)}, separators=(",", ":")))
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request, _error):
        # Never serialize a DSN, query parameters, credentials, or exception text.
        return JSONResponse(status_code=503, content={"detail": "Database is unavailable"})

    @app.get("/health/live")
    def live():
        return {"status": "alive", "version": app.version}

    @app.get("/health/ready")
    def ready():
        read_key()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.get("/api/tasks", dependencies=[Depends(authenticate)])
    def list_tasks(limit: int = Query(50, ge=1, le=100)):
        with engine.connect() as connection:
            rows = connection.execute(select(tasks).order_by(tasks.c.created_at, tasks.c.id).limit(limit)).mappings()
            return [dict(row) | {"done": bool(row["done"])} for row in rows]

    @app.post("/api/tasks", status_code=201, dependencies=[Depends(authenticate)])
    def add_task(payload: TaskInput):
        task = {"id": str(uuid.uuid4()), "title": payload.title, "done": 0,
                "created_at": datetime.now(timezone.utc).isoformat()}
        with engine.begin() as connection:
            connection.execute(insert(tasks).values(**task))
        return task | {"done": False}

    @app.patch("/api/tasks/{task_id}", dependencies=[Depends(authenticate)])
    def update_task(task_id: uuid.UUID, payload: TaskUpdate):
        with engine.begin() as connection:
            result = connection.execute(update(tasks).where(tasks.c.id == str(task_id)).values(done=int(payload.done)))
            if result.rowcount == 0:
                raise HTTPException(404, "Task not found")
        return {"id": str(task_id), "done": payload.done}

    @app.delete("/api/tasks/{task_id}", status_code=204, dependencies=[Depends(authenticate)])
    def delete_task(task_id: uuid.UUID):
        with engine.begin() as connection:
            result = connection.execute(delete(tasks).where(tasks.c.id == str(task_id)))
            if result.rowcount == 0:
                raise HTTPException(404, "Task not found")
        return Response(status_code=204)

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def home():
        return FileResponse(static / "index.html")

    return app
