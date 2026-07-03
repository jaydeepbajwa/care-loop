from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..metrics import METRICS

router = APIRouter(tags=["ops"])


@router.get("/health")
def health(response: Response, db: Session = Depends(get_db)) -> dict:
    """Liveness + DB reachability. This is what an on-call alert would probe."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unreachable"
        response.status_code = 503
    return {"status": "ok" if db_status == "ok" else "degraded", "database": db_status}


@router.get("/metrics")
def metrics() -> dict:
    return METRICS.snapshot()
