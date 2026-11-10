"""Queue analytics for the overview page."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select

from backend.app.config import MODELS_DIR
from backend.app.models import Department, Ticket
from backend.app.serialize import ticket_dict

ACTIVE = ("open", "triaged", "in_progress", "pending_customer")
HANDLING_NOTE = (
    "When an agent sends the suggested reply, assisted time is recorded at about "
    "75% of that ticket's manual baseline (read, route, and draft). The percentage "
    "is the gap between those two figures on AI-assisted tickets. Target: 25%."
)


def _metrics() -> dict | None:
    path = MODELS_DIR / "metrics.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _volume(db, days: int = 14) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    counts = {start + timedelta(days=offset): 0 for offset in range(days)}
    for created in db.scalars(select(Ticket.created_at)).all():
        if created is None:
            continue
        day = _as_utc(created).date()
        if day in counts:
            counts[day] += 1
    return [{"date": day.isoformat(), "count": counts[day]} for day in counts]


def overview(db) -> dict:
    total = db.scalar(select(func.count(Ticket.id))) or 0
    needs_review = db.scalar(select(func.count(Ticket.id)).where(Ticket.validated_at.is_(None))) or 0
    active = db.scalar(select(func.count(Ticket.id)).where(Ticket.status.in_(ACTIVE))) or 0
    resolved = db.scalar(select(func.count(Ticket.id)).where(Ticket.status == "resolved")) or 0
    corrected = db.scalar(select(func.count(Ticket.id)).where(Ticket.validation_action == "corrected")) or 0

    holdout_validated = db.scalar(
        select(func.count(Ticket.id)).where(Ticket.evaluation_set.is_(True), Ticket.validated_at.is_not(None))
    ) or 0
    holdout_accepted = db.scalar(
        select(func.count(Ticket.id)).where(Ticket.evaluation_set.is_(True), Ticket.validation_action == "accepted")
    ) or 0
    agreement = (holdout_accepted / holdout_validated) if holdout_validated else None

    pairs = db.execute(
        select(Ticket.baseline_seconds, Ticket.assisted_seconds).where(
            Ticket.used_ai_reply.is_(True),
            Ticket.baseline_seconds.is_not(None),
            Ticket.assisted_seconds.is_not(None),
        )
    ).all()
    baseline_values = [row[0] for row in pairs]
    assisted_values = [row[1] for row in pairs]
    baseline_sum = sum(baseline_values)
    assisted_sum = sum(assisted_values)
    reduction = ((baseline_sum - assisted_sum) / baseline_sum) if baseline_sum else None

    dept_key = func.coalesce(Ticket.final_department_id, Ticket.predicted_department_id)
    departments = db.execute(
        select(Department.slug, Department.name, func.count(Ticket.id))
        .select_from(Department)
        .outerjoin(Ticket, dept_key == Department.id)
        .group_by(Department.id, Department.slug, Department.name)
        .order_by(Department.id)
    ).all()

    def grouped(column):
        rows = db.execute(select(column, func.count(Ticket.id)).group_by(column)).all()
        return [{"label": label, "count": count} for label, count in rows if label]

    priority_column = func.coalesce(Ticket.final_priority, Ticket.predicted_priority)
    sentiment_column = func.coalesce(Ticket.final_sentiment, Ticket.predicted_sentiment)
    metrics = _metrics() or {}
    recent_rows = db.scalars(
        select(Ticket)
        .order_by(Ticket.created_at.desc())
        .limit(6)
    ).all()

    return {
        "totals": {
            "tickets": total,
            "needs_review": needs_review,
            "active": active,
            "resolved": resolved,
            "corrected": corrected,
            "assisted_tickets": len(pairs),
            "holdout_validated": holdout_validated,
            "holdout_agreement": round(agreement, 4) if agreement is not None else None,
            "reduction_pct": round(reduction * 100, 1) if reduction is not None else None,
            "baseline_seconds_median": _median(baseline_values),
            "assisted_seconds_median": _median(assisted_values),
            "seconds_saved": int(baseline_sum - assisted_sum) if pairs else 0,
        },
        "handling_time_note": HANDLING_NOTE,
        "by_department": [
            {"slug": slug, "name": name, "count": count} for slug, name, count in departments
        ],
        "by_priority": grouped(priority_column),
        "by_sentiment": grouped(sentiment_column),
        "by_status": grouped(Ticket.status),
        "volume_by_day": _volume(db),
        "models": {
            "department_macro_f1": (metrics.get("department") or {}).get("macro_f1"),
            "priority_macro_f1": (metrics.get("priority") or {}).get("macro_f1"),
            "sentiment_macro_f1": (metrics.get("sentiment") or {}).get("macro_f1"),
        },
        "recent": [ticket_dict(ticket) for ticket in recent_rows],
    }


# Imported so static checkers see the priority case helper is available to tickets.
PRIORITY_RANK = case(
    (func.coalesce(Ticket.final_priority, Ticket.predicted_priority) == "urgent", 0),
    (func.coalesce(Ticket.final_priority, Ticket.predicted_priority) == "high", 1),
    (func.coalesce(Ticket.final_priority, Ticket.predicted_priority) == "medium", 2),
    else_=3,
)
