import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.config import MODELS_DIR
from backend.app.database import get_db
from backend.app.services.analytics import overview
from backend.app.services.tickets import list_departments

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/departments")
def departments(db: Session = Depends(get_db)):
    return list_departments(db)


@router.get("/analytics/overview")
def analytics_overview(db: Session = Depends(get_db)):
    return overview(db)


@router.get("/models/metrics")
def model_metrics():
    path = MODELS_DIR / "metrics.json"
    if not path.exists():
        return {"ready": False}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["ready"] = True
    return payload
