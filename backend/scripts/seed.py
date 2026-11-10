"""Reset the database and load the generated support queue."""

import csv
import json
import logging
from datetime import datetime, timedelta, timezone

import numpy as np

from backend.app import database
from backend.app.config import DATA_DIR, MODELS_DIR
from backend.app.domain import AGENTS, DEPARTMENTS
from backend.app.ml import embeddings
from backend.app.ml.inference import intelligence
from backend.app.ml.text import ticket_text
from backend.app.ml.timing import assisted_seconds, baseline_seconds
from backend.app.models import Base, Department, Ticket, TicketMessage

logger = logging.getLogger("resolveai.seed")


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def seed() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    csv_path = DATA_DIR / "tickets.csv"
    if not csv_path.exists() or not (MODELS_DIR / "department.joblib").exists():
        raise SystemExit("Train the models first: python -m backend.app.ml.train")

    database.init_engine()
    print(f"Database: {database.engine.url.render_as_string(hide_password=True)}", flush=True)
    if not intelligence.load():
        raise SystemExit("Models failed to load.")
    embedder = embeddings.get_embedder()
    print(f"Embedder: {embedder.name} ({embedder.dim} dimensions)", flush=True)

    Base.metadata.drop_all(bind=database.engine)
    Base.metadata.create_all(bind=database.engine)

    with csv_path.open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    if not records:
        raise SystemExit("data/tickets.csv is empty.")

    texts = [ticket_text(row["subject"], row["body"]) for row in records]
    print(f"Scoring {len(texts)} tickets...", flush=True)
    predictions = intelligence.predict_many(texts)

    rng = np.random.default_rng(42)
    now = datetime.now(timezone.utc)
    created_ats = []
    for _record in records:
        created_ats.append(
            now
            - timedelta(
                days=int(rng.integers(0, 34)),
                hours=int(rng.integers(0, 24)),
                minutes=int(rng.integers(0, 60)),
            )
        )
    newest = {int(index) for index in np.argsort([stamp.timestamp() for stamp in created_ats])[-100:]}

    db = database.SessionLocal()
    try:
        departments = [Department(**row) for row in DEPARTMENTS]
        db.add_all(departments)
        db.flush()
        by_slug = {department.slug: department for department in departments}

        tickets = []
        metas = []
        for index, record in enumerate(records):
            created = _aware(created_ats[index])
            prediction = predictions[index]
            review = index in newest
            if review:
                status = "open"
                validated = False
                include_resolution = False
                used_ai = False
                agent = None
                validated_at = None
                first_response_at = None
            else:
                status = str(
                    rng.choice(
                        ["resolved", "pending_customer", "in_progress", "triaged"],
                        p=[0.62, 0.14, 0.12, 0.12],
                    )
                )
                validated = True
                include_resolution = status in {"resolved", "pending_customer"}
                used_ai = include_resolution and float(rng.random()) < 0.84
                agent = str(rng.choice(list(AGENTS)))
                validated_at = min(created + timedelta(minutes=int(rng.integers(5, 40))), now - timedelta(minutes=1))
                if validated_at < created:
                    validated_at = created
                first_response_at = None
                if include_resolution:
                    first_response_at = min(
                        validated_at + timedelta(minutes=int(rng.integers(2, 18))),
                        now,
                    )

            predicted = by_slug[prediction["department"]]
            final = by_slug[record["department"]] if validated else None
            matched = (
                prediction["department"] == record["department"]
                and prediction["priority"] == record["priority"]
                and prediction["sentiment"] == record["sentiment"]
            )
            ticket = Ticket(
                subject=record["subject"],
                body=record["body"],
                customer_name=record["customer_name"],
                customer_email=record["customer_email"],
                status=status,
                created_at=created,
                updated_at=first_response_at or validated_at or created,
                predicted_department_id=predicted.id,
                predicted_priority=prediction["priority"],
                predicted_sentiment=prediction["sentiment"],
                department_confidence=prediction["department_confidence"],
                priority_confidence=prediction["priority_confidence"],
                sentiment_confidence=prediction["sentiment_confidence"],
                scores_json=json.dumps(prediction["scores"]),
                final_department_id=final.id if final else None,
                final_priority=record["priority"] if validated else None,
                final_sentiment=record["sentiment"] if validated else None,
                validated_at=validated_at,
                validated_by=agent if validated else None,
                validation_action=("accepted" if matched else "corrected") if validated else None,
                baseline_seconds=baseline_seconds(record["subject"], record["body"], rng),
                used_ai_reply=False,
                first_response_at=first_response_at,
                evaluation_set=record.get("split") == "holdout",
            )
            tickets.append(ticket)
            metas.append(
                {
                    "include_resolution": include_resolution,
                    "used_ai": used_ai,
                    "agent": agent,
                    "resolution": record["resolution"],
                    "first_response_at": first_response_at,
                }
            )

        embed_texts = []
        for record, meta in zip(records, metas):
            text = ticket_text(record["subject"], record["body"])
            if meta["include_resolution"]:
                text = f"{text}\n{record['resolution']}"
            embed_texts.append(text)
        vectors = embeddings.encode_many(embed_texts)
        for ticket, vector in zip(tickets, vectors):
            ticket.embedding = embeddings.pack_vector(vector)

        for start in range(0, len(tickets), 400):
            db.add_all(tickets[start : start + 400])
            db.flush()
            print(f"Inserted {min(start + 400, len(tickets))}/{len(tickets)}", flush=True)

        messages = []
        for ticket, meta in zip(tickets, metas):
            if meta["used_ai"] and ticket.baseline_seconds:
                ticket.used_ai_reply = True
                ticket.assisted_seconds = assisted_seconds(ticket.baseline_seconds, ticket.id)
            messages.append(
                TicketMessage(
                    ticket_id=ticket.id,
                    author_type="customer",
                    author_name=ticket.customer_name,
                    body=ticket.body,
                    created_at=ticket.created_at,
                )
            )
            if meta["include_resolution"]:
                messages.append(
                    TicketMessage(
                        ticket_id=ticket.id,
                        author_type="agent",
                        author_name=meta["agent"],
                        body=meta["resolution"],
                        created_at=meta["first_response_at"],
                    )
                )
        db.add_all(messages)
        db.commit()
        print(f"Loaded {len(tickets)} tickets and {len(messages)} messages.", flush=True)
    finally:
        db.close()

    metrics_path = MODELS_DIR / "metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["embedder"] = {"name": embedder.name, "dim": int(embedder.dim)}
        metrics["seeded_tickets"] = len(records)
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print("Queue ready.", flush=True)


if __name__ == "__main__":
    seed()
