from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.errors import AppError
from backend.app.schemas import ReplyIn, StatusIn, TicketCreate, ValidationIn
from backend.app.services import tickets as service
from fastapi import HTTPException

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("")
def list_tickets(
    q: str | None = None,
    status: str | None = None,
    department: str | None = None,
    priority: str | None = None,
    sentiment: str | None = None,
    review: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    return _run(
        service.list_tickets,
        db,
        q=q,
        status=status,
        department=department,
        priority=priority,
        sentiment=sentiment,
        review=review,
        page=page,
        page_size=page_size,
    )


@router.post("")
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    return _run(service.create_ticket, db, payload)


@router.get("/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    return _run(service.get_ticket, db, ticket_id)


@router.post("/{ticket_id}/validation")
def validate_ticket(ticket_id: int, payload: ValidationIn, db: Session = Depends(get_db)):
    return _run(service.validate_ticket, db, ticket_id, payload)


@router.post("/{ticket_id}/replies")
def reply_to_ticket(ticket_id: int, payload: ReplyIn, db: Session = Depends(get_db)):
    return _run(service.reply_to_ticket, db, ticket_id, payload)


@router.post("/{ticket_id}/suggestion")
def suggest_reply(ticket_id: int, db: Session = Depends(get_db)):
    return _run(service.suggest_reply, db, ticket_id)


@router.patch("/{ticket_id}")
def set_status(ticket_id: int, payload: StatusIn, db: Session = Depends(get_db)):
    return _run(service.set_status, db, ticket_id, payload)
