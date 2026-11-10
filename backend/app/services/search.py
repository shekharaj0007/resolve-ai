"""Semantic search over stored ticket embeddings."""

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from backend.app.errors import AppError
from backend.app.ml import embeddings
from backend.app.ml.index import DimensionMismatch, index, to_bytes
from backend.app.ml.text import ticket_text
from backend.app.models import Ticket, TicketMessage
from backend.app.serialize import clip, department_dict


def _vector_for(ticket: Ticket):
    raw = to_bytes(ticket.embedding)
    if raw and len(raw) % 4 == 0:
        return np.frombuffer(raw, dtype=np.float32).copy()
    return embeddings.encode([ticket_text(ticket.subject, ticket.body)])[0]


def _hydrate(db, hits, limit: int) -> list[dict]:
    if not hits:
        return []
    ids = [ticket_id for ticket_id, _score in hits[:limit]]
    tickets = db.scalars(
        select(Ticket)
        .options(joinedload(Ticket.predicted_department), joinedload(Ticket.final_department))
        .where(Ticket.id.in_(ids))
    ).unique().all()
    by_id = {ticket.id: ticket for ticket in tickets}
    messages = db.scalars(
        select(TicketMessage).where(
            TicketMessage.ticket_id.in_(ids),
            TicketMessage.author_type == "agent",
        )
    ).all()
    latest: dict[int, TicketMessage] = {}
    for message in messages:
        current = latest.get(message.ticket_id)
        if current is None or (message.created_at and current.created_at and message.created_at > current.created_at):
            latest[message.ticket_id] = message
    results = []
    for ticket_id, score in hits:
        ticket = by_id.get(ticket_id)
        if ticket is None:
            continue
        department = ticket.final_department or ticket.predicted_department
        resolution = latest.get(ticket_id)
        results.append(
            {
                "id": ticket.id,
                "subject": ticket.subject,
                "score": round(float(score), 4),
                "department": department_dict(department),
                "priority": ticket.final_priority or ticket.predicted_priority,
                "snippet": clip(ticket.body, 180),
                "resolution": clip(resolution.body, 240) if resolution else None,
            }
        )
    return results


def similar_for_ticket(db, ticket: Ticket, k: int = 4) -> list[dict]:
    try:
        vector = _vector_for(ticket)
        hits = index.search(vector, k=k + 1, exclude=ticket.id)
    except DimensionMismatch as exc:
        raise AppError(str(exc), 503) from exc
    except Exception as exc:
        raise AppError("Similar-ticket search is not available yet.", 503) from exc
    return _hydrate(db, hits, k)


def search_query(db, query: str, limit: int = 8) -> list[dict]:
    text = (query or "").strip()
    if len(text) < 2:
        raise AppError("Enter at least 2 characters.", 422)
    limit = min(max(int(limit), 1), 20)
    try:
        vector = embeddings.encode([text])[0]
        hits = index.search(vector, k=limit)
    except DimensionMismatch as exc:
        raise AppError(str(exc), 503) from exc
    except Exception as exc:
        raise AppError("The embedding model is not available yet. Run bootstrap, then restart the API.", 503) from exc
    return _hydrate(db, hits, limit)
