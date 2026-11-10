"""JSON shapes returned by the API."""

import json
from datetime import datetime, timezone


def _message_stamp(message) -> float:
    value = message.created_at
    if value is None:
        return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def clip(text: str | None, limit: int) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def department_dict(department) -> dict | None:
    if department is None:
        return None
    return {
        "slug": department.slug,
        "name": department.name,
        "queue_name": department.queue_name,
    }


def message_dict(message) -> dict:
    return {
        "id": message.id,
        "author_type": message.author_type,
        "author_name": message.author_name,
        "body": message.body,
        "created_at": iso(message.created_at),
    }


def ticket_dict(ticket, *, detail: bool = False) -> dict:
    routing_department = ticket.final_department or ticket.predicted_department
    data = {
        "id": ticket.id,
        "subject": ticket.subject,
        "body": ticket.body if detail else clip(ticket.body, 220),
        "customer_name": ticket.customer_name,
        "customer_email": ticket.customer_email,
        "status": ticket.status,
        "created_at": iso(ticket.created_at),
        "updated_at": iso(ticket.updated_at),
        "predicted_department": department_dict(ticket.predicted_department),
        "predicted_priority": ticket.predicted_priority,
        "predicted_sentiment": ticket.predicted_sentiment,
        "department_confidence": ticket.department_confidence,
        "priority_confidence": ticket.priority_confidence,
        "sentiment_confidence": ticket.sentiment_confidence,
        "final_department": department_dict(ticket.final_department),
        "final_priority": ticket.final_priority,
        "final_sentiment": ticket.final_sentiment,
        "routing_department": department_dict(routing_department),
        "routing_priority": ticket.final_priority or ticket.predicted_priority,
        "routing_sentiment": ticket.final_sentiment or ticket.predicted_sentiment,
        "validated_at": iso(ticket.validated_at),
        "validated_by": ticket.validated_by,
        "validation_action": ticket.validation_action,
        "needs_review": ticket.validated_at is None,
        "baseline_seconds": ticket.baseline_seconds,
        "assisted_seconds": ticket.assisted_seconds,
        "used_ai_reply": bool(ticket.used_ai_reply),
    }
    if detail:
        scores = None
        if ticket.scores_json:
            scores = json.loads(ticket.scores_json)
        messages = sorted(ticket.messages, key=_message_stamp)
        data.update(
            {
                "scores": scores,
                "suggested_reply": ticket.suggested_reply,
                "suggestion_source": ticket.suggestion_source,
                "first_response_at": iso(ticket.first_response_at),
                "messages": [message_dict(message) for message in messages],
            }
        )
    return data
