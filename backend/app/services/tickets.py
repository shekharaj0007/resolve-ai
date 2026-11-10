"""Ticket queue, human review, and reply drafts."""

import json
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from backend.app.domain import DEPARTMENTS, PRIORITIES, SENTIMENTS, STATUSES
from backend.app.errors import AppError
from backend.app.ml import embeddings
from backend.app.ml.index import index
from backend.app.ml.inference import intelligence
from backend.app.ml.respond import draft
from backend.app.ml.text import ticket_text
from backend.app.ml.timing import assisted_seconds, baseline_seconds
from backend.app.models import Department, Ticket, TicketMessage, utcnow
from backend.app.schemas import ReplyIn, StatusIn, TicketCreate, ValidationIn
from backend.app.serialize import ticket_dict
from backend.app.services.analytics import PRIORITY_RANK
from backend.app.services.search import similar_for_ticket


def _departments(db) -> dict[str, Department]:
    rows = db.scalars(select(Department).order_by(Department.id)).all()
    return {row.slug: row for row in rows}


def _get(db, ticket_id: int) -> Ticket:
    ticket = db.scalars(
        select(Ticket)
        .options(
            joinedload(Ticket.predicted_department),
            joinedload(Ticket.final_department),
            selectinload(Ticket.messages),
        )
        .where(Ticket.id == ticket_id)
    ).first()
    if ticket is None:
        raise AppError("Ticket not found.", 404)
    return ticket


def _detail(db, ticket: Ticket) -> dict:
    similar = []
    try:
        similar = similar_for_ticket(db, ticket, k=4)
    except AppError:
        similar = []
    return {"ticket": ticket_dict(ticket, detail=True), "similar": similar}


def _contains(column, query: str):
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return func.lower(column).like(f"%{escaped.lower()}%", escape="\\")


def _apply_validation(ticket: Ticket, department: str, priority: str, sentiment: str, agent: str, departments: dict):
    if priority not in PRIORITIES or sentiment not in SENTIMENTS:
        raise AppError("Unknown priority or sentiment.", 422)
    chosen = departments.get(department)
    if chosen is None:
        raise AppError("Unknown department.", 422)
    predicted_slug = ticket.predicted_department.slug if ticket.predicted_department else None
    accepted = (
        department == predicted_slug
        and priority == ticket.predicted_priority
        and sentiment == ticket.predicted_sentiment
    )
    ticket.final_department = chosen
    ticket.final_department_id = chosen.id
    ticket.final_priority = priority
    ticket.final_sentiment = sentiment
    ticket.validation_action = "accepted" if accepted else "corrected"
    ticket.validated_at = utcnow()
    ticket.validated_by = agent
    if ticket.status == "open":
        ticket.status = "triaged"
    ticket.updated_at = utcnow()


def list_tickets(db, **filters) -> dict:
    page = max(int(filters.get("page") or 1), 1)
    page_size = min(max(int(filters.get("page_size") or 20), 1), 100)
    clauses = []

    status = filters.get("status") or None
    if status:
        if status not in STATUSES:
            raise AppError("Unknown status.", 422)
        clauses.append(Ticket.status == status)

    department = filters.get("department") or None
    if department:
        chosen = db.scalar(select(Department).where(Department.slug == department))
        if chosen is None:
            raise AppError("Unknown department.", 422)
        clauses.append(func.coalesce(Ticket.final_department_id, Ticket.predicted_department_id) == chosen.id)

    priority = filters.get("priority") or None
    if priority:
        if priority not in PRIORITIES:
            raise AppError("Unknown priority.", 422)
        clauses.append(func.coalesce(Ticket.final_priority, Ticket.predicted_priority) == priority)

    sentiment = filters.get("sentiment") or None
    if sentiment:
        if sentiment not in SENTIMENTS:
            raise AppError("Unknown sentiment.", 422)
        clauses.append(func.coalesce(Ticket.final_sentiment, Ticket.predicted_sentiment) == sentiment)

    review = filters.get("review") or None
    if review in {None, "", "all"}:
        pass
    elif review == "needs":
        clauses.append(Ticket.validated_at.is_(None))
    elif review == "corrected":
        clauses.append(Ticket.validation_action == "corrected")
    elif review == "accepted":
        clauses.append(Ticket.validation_action == "accepted")
    else:
        raise AppError("Unknown review filter.", 422)

    query = (filters.get("q") or "").strip()
    if len(query) > 200:
        raise AppError("Search text is too long.", 422)
    if query:
        clauses.append(
            or_(
                _contains(Ticket.subject, query),
                _contains(Ticket.body, query),
                _contains(Ticket.customer_name, query),
                _contains(Ticket.customer_email, query),
            )
        )

    count_stmt = select(func.count(Ticket.id))
    list_stmt = select(Ticket).options(
        joinedload(Ticket.predicted_department),
        joinedload(Ticket.final_department),
    )
    if clauses:
        count_stmt = count_stmt.where(*clauses)
        list_stmt = list_stmt.where(*clauses)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        list_stmt.order_by(PRIORITY_RANK, Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).unique().all()
    return {
        "items": [ticket_dict(ticket) for ticket in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_ticket(db, ticket_id: int) -> dict:
    return _detail(db, _get(db, ticket_id))


def create_ticket(db, payload: TicketCreate) -> dict:
    try:
        prediction = intelligence.predict_many([ticket_text(payload.subject, payload.body)])[0]
    except RuntimeError as exc:
        raise AppError(str(exc), 503) from exc
    departments = _departments(db)
    if not departments:
        raise AppError("Departments are not loaded. Run python -m backend.scripts.bootstrap.", 503)
    department = departments.get(prediction["department"])
    if department is None:
        raise AppError("The model returned a department that is not in the routing list.", 500)
    now = utcnow()
    ticket = Ticket(
        subject=payload.subject,
        body=payload.body,
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        status="open",
        created_at=now,
        updated_at=now,
        predicted_department_id=department.id,
        predicted_department=department,
        predicted_priority=prediction["priority"],
        predicted_sentiment=prediction["sentiment"],
        department_confidence=prediction["department_confidence"],
        priority_confidence=prediction["priority_confidence"],
        sentiment_confidence=prediction["sentiment_confidence"],
        scores_json=json.dumps(prediction["scores"]),
        baseline_seconds=baseline_seconds(payload.subject, payload.body),
        used_ai_reply=False,
        evaluation_set=False,
    )
    ticket.messages.append(
        TicketMessage(
            author_type="customer",
            author_name=payload.customer_name,
            body=payload.body,
            created_at=now,
        )
    )
    try:
        vector = embeddings.encode([ticket_text(payload.subject, payload.body)])[0]
        ticket.embedding = embeddings.pack_vector(vector)
    except Exception as exc:
        raise AppError("The embedding model is not available yet.", 503) from exc
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    index.add(ticket.id, vector)
    return _detail(db, _get(db, ticket.id))


def validate_ticket(db, ticket_id: int, payload: ValidationIn) -> dict:
    ticket = _get(db, ticket_id)
    _apply_validation(ticket, payload.department, payload.priority, payload.sentiment, payload.agent, _departments(db))
    db.commit()
    return _detail(db, _get(db, ticket.id))


def reply_to_ticket(db, ticket_id: int, payload: ReplyIn) -> dict:
    ticket = _get(db, ticket_id)
    departments = _departments(db)
    if payload.department and payload.priority and payload.sentiment:
        _apply_validation(ticket, payload.department, payload.priority, payload.sentiment, payload.agent, departments)
    elif ticket.validated_at is None:
        raise AppError("Choose a queue, priority, and sentiment before sending.", 422)

    now = utcnow()
    ticket.messages.append(
        TicketMessage(
            author_type="agent",
            author_name=payload.agent,
            body=payload.body,
            created_at=now,
        )
    )
    if ticket.first_response_at is None:
        ticket.first_response_at = now
    if payload.used_suggestion and ticket.baseline_seconds and not ticket.used_ai_reply:
        ticket.used_ai_reply = True
        ticket.assisted_seconds = assisted_seconds(ticket.baseline_seconds, ticket.id)
    if payload.resolve:
        ticket.status = "resolved"
    elif ticket.status in {"open", "triaged", "in_progress"}:
        ticket.status = "pending_customer"
    ticket.updated_at = now
    db.commit()
    return _detail(db, _get(db, ticket.id))


def set_status(db, ticket_id: int, payload: StatusIn) -> dict:
    if payload.status not in STATUSES:
        raise AppError("Unknown status.", 422)
    ticket = _get(db, ticket_id)
    ticket.status = payload.status
    ticket.updated_at = utcnow()
    db.commit()
    return _detail(db, _get(db, ticket.id))


def suggest_reply(db, ticket_id: int) -> dict:
    ticket = _get(db, ticket_id)
    department = ticket.final_department or ticket.predicted_department
    if department is None:
        raise AppError("This ticket has no routing department yet.", 422)
    similar = similar_for_ticket(db, ticket, k=4)
    text, source = draft(
        {
            "subject": ticket.subject,
            "body": ticket.body,
            "customer_name": ticket.customer_name,
            "department_slug": department.slug,
            "department_name": department.name,
            "priority": ticket.final_priority or ticket.predicted_priority,
            "sentiment": ticket.final_sentiment or ticket.predicted_sentiment,
        },
        similar,
    )
    ticket.suggested_reply = text
    ticket.suggestion_source = source
    ticket.updated_at = utcnow()
    db.commit()
    return _detail(db, _get(db, ticket.id))


def list_departments(db) -> list[dict]:
    rows = db.scalars(select(Department).order_by(Department.id)).all()
    if rows:
        return [
            {
                "slug": row.slug,
                "name": row.name,
                "queue_name": row.queue_name,
                "description": row.description,
            }
            for row in rows
        ]
    return [
        {
            "slug": item["slug"],
            "name": item["name"],
            "queue_name": item["queue_name"],
            "description": item["description"],
        }
        for item in DEPARTMENTS
    ]
