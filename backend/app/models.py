"""ORM tables for tickets, review decisions, and the message thread."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(400))
    queue_name: Mapped[str] = mapped_column(String(80))


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_email: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    predicted_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    predicted_priority: Mapped[str | None] = mapped_column(String(20), index=True)
    predicted_sentiment: Mapped[str | None] = mapped_column(String(20))
    department_confidence: Mapped[float | None] = mapped_column(Float)
    priority_confidence: Mapped[float | None] = mapped_column(Float)
    sentiment_confidence: Mapped[float | None] = mapped_column(Float)
    scores_json: Mapped[str | None] = mapped_column(Text)

    final_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    final_priority: Mapped[str | None] = mapped_column(String(20))
    final_sentiment: Mapped[str | None] = mapped_column(String(20))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validated_by: Mapped[str | None] = mapped_column(String(120))
    validation_action: Mapped[str | None] = mapped_column(String(20), index=True)

    embedding: Mapped[bytes | None] = mapped_column(LargeBinary)
    suggested_reply: Mapped[str | None] = mapped_column(Text)
    suggestion_source: Mapped[str | None] = mapped_column(String(32))

    baseline_seconds: Mapped[int | None] = mapped_column(Integer)
    assisted_seconds: Mapped[int | None] = mapped_column(Integer)
    used_ai_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evaluation_set: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    predicted_department: Mapped[Department | None] = relationship(foreign_keys=[predicted_department_id])
    final_department: Mapped[Department | None] = relationship(foreign_keys=[final_department_id])
    messages: Mapped[list["TicketMessage"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketMessage.id",
    )


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    author_type: Mapped[str] = mapped_column(String(20))
    author_name: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    ticket: Mapped[Ticket] = relationship(back_populates="messages")
