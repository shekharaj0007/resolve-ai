from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.errors import AppError
from backend.app.services.search import search_query

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
def search(q: str, limit: int = 8, db: Session = Depends(get_db)):
    try:
        return {"query": q, "results": search_query(db, q, limit)}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
