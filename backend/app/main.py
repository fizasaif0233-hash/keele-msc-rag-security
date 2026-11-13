import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.router import api_router
from app.config import settings
from app.database import get_session_factory
from app.exceptions import AppError
from app.models import Experiment

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ragsec")


def reconcile_interrupted_experiments() -> None:
    if not settings.database_url:
        logger.warning("DATABASE_URL is not configured. Persistence is unavailable.")
        return
    try:
        session = get_session_factory()()
    except Exception:
        logger.exception("Database connection was not available during startup.")
        return
    try:
        running = session.scalars(select(Experiment).where(Experiment.status == "running")).all()
        for experiment in running:
            experiment.status = "failed"
            experiment.error_message = (
                "The run was interrupted by an application restart. Partial trial rows were kept."
            )
            experiment.completed_at = datetime.now(timezone.utc)
        session.commit()
        if running:
            logger.info("Marked %s interrupted experiment(s) as failed.", len(running))
    except Exception:
        session.rollback()
        logger.exception("Could not reconcile interrupted experiments. Apply the SQL migration if tables are missing.")
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    reconcile_interrupted_experiments()
    yield


app = FastAPI(
    title="RAG Security Evaluation Platform",
    summary="Controlled comparison of baseline and secured retrieval-augmented generation.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.exception_handler(AppError)
async def handle_app_error(_: object, exc: AppError) -> JSONResponse:
    if exc.internal:
        logger.warning("%s %s", exc.code, exc.internal)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})
