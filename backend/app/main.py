"""ResolveAI API."""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from backend.app.config import settings
from backend.app import database
from backend.app.database import database_label, init_db
from backend.app.ml import embeddings
from backend.app.ml.index import index
from backend.app.ml.inference import intelligence
from backend.app.models import Ticket
from backend.app.routers import search, system, tickets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("resolveai")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    loaded = intelligence.load()
    logger.info("Models loaded." if loaded else "Models are not trained yet.")
    db = database.SessionLocal()
    try:
        rows = db.execute(select(Ticket.id, Ticket.embedding).where(Ticket.embedding.is_not(None))).all()
    finally:
        db.close()
    index.rebuild(rows)
    logger.info("Indexed %s ticket embeddings.", int(index.ids.size))
    threading.Thread(target=embeddings.warm, name="embedder-warm", daemon=True).start()
    yield


app = FastAPI(
    title="ResolveAI",
    summary="Support ticket routing, review, and response drafts.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tickets.router)
app.include_router(search.router)
app.include_router(system.router)


@app.get("/")
def root():
    return {"name": "ResolveAI", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "models_loaded": intelligence.ready,
        "embedder": embeddings.current_name(),
        "database": database_label(),
        "tickets_indexed": int(index.ids.size),
    }
