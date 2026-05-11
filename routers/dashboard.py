from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional

import models
from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_summary(
    site_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    resolved_site_id = site_id or current_user.site_id
    today = date.today()

    query = db.query(models.WasteBatch)
    if resolved_site_id:
        query = query.filter(models.WasteBatch.site_id == resolved_site_id)

    batches = query.all()
    today_batches = [b for b in batches if b.created_at and b.created_at.date() == today]

    deviations = sum(len(b.deviations) for b in today_batches)

    on_time = 0
    completed = 0
    for b in today_batches:
        for s in b.stages:
            if s.status == "completed" and s.started_at and s.completed_at:
                completed += 1
                duration = (s.completed_at - s.started_at).seconds // 60
                if duration <= s.norm_minutes:
                    on_time += 1

    percent = round(on_time / completed * 100, 1) if completed > 0 else 100.0

    return {
        "total_batches_today": len(today_batches),
        "deviations": deviations,
        "percent_on_time": percent,
    }
