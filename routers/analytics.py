from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import Optional
from collections import defaultdict

import models
from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_date_range(period: str, date_from: Optional[str], date_to: Optional[str]):
    today = date.today()
    if period == "shift":
        start = datetime.combine(today, datetime.min.time()).replace(hour=8)
        end = datetime.utcnow()
    elif period == "today":
        start = datetime.combine(today, datetime.min.time())
        end = datetime.utcnow()
    elif period == "week":
        start = datetime.combine(today - timedelta(days=7), datetime.min.time())
        end = datetime.utcnow()
    elif period == "custom" and date_from and date_to:
        start = datetime.strptime(date_from, "%Y-%m-%d")
        end = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59)
    else:
        start = datetime.combine(today, datetime.min.time())
        end = datetime.utcnow()
    return start, end


@router.get("")
def get_analytics(
    period: str = "today",
    site_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = _get_date_range(period, date_from, date_to)

    resolved_site_id = site_id
    if not resolved_site_id and current_user.role in ("operator", "master"):
        resolved_site_id = current_user.site_id

    query = db.query(models.WasteBatch).filter(
        models.WasteBatch.created_at >= start,
        models.WasteBatch.created_at <= end,
    )
    if resolved_site_id:
        query = query.filter(models.WasteBatch.site_id == resolved_site_id)
    batches = query.all()

    # Stage analytics
    stage_actual = defaultdict(list)
    stage_norms = defaultdict(float)
    on_time = 0
    total_completed = 0
    total_cycle_times = []

    for b in batches:
        cycle_start = None
        cycle_end = None
        for s in b.stages:
            if s.status == "completed" and s.started_at and s.completed_at:
                duration = (s.completed_at - s.started_at).seconds // 60
                stage_actual[s.stage_name].append(duration)
                stage_norms[s.stage_name] = s.norm_minutes
                total_completed += 1
                if duration <= s.norm_minutes:
                    on_time += 1
                if cycle_start is None:
                    cycle_start = s.started_at
                cycle_end = s.completed_at
        if cycle_start and cycle_end:
            total_cycle_times.append((cycle_end - cycle_start).seconds // 60)

    avg_cycle = round(sum(total_cycle_times) / len(total_cycle_times), 1) if total_cycle_times else 0.0
    percent_on_time = round(on_time / total_completed * 100, 1) if total_completed > 0 else 100.0

    stage_analytics = [
        {
            "stage_name": name,
            "actual_minutes": round(sum(vals) / len(vals), 1),
            "norm_minutes": stage_norms[name],
        }
        for name, vals in stage_actual.items()
    ]

    # Deviation reasons
    deviations = db.query(models.Deviation).join(models.WasteBatch).filter(
        models.WasteBatch.created_at >= start,
        models.WasteBatch.created_at <= end,
    )
    if resolved_site_id:
        deviations = deviations.filter(models.WasteBatch.site_id == resolved_site_id)
    deviations = deviations.all()

    reason_counts = defaultdict(int)
    for d in deviations:
        reason_counts[d.type] += 1
    total_dev = len(deviations)

    top_reasons = [
        {
            "reason": reason,
            "count": count,
            "percentage": round(count / total_dev * 100, 1) if total_dev > 0 else 0.0,
        }
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1])[:5]
    ]

    # Site KPIs (for manager)
    site_kpis = []
    if current_user.role == "manager":
        sites = db.query(models.Site).all()
        for site in sites:
            site_batches = [b for b in batches if b.site_id == site.id]
            s_on_time = 0
            s_completed = 0
            s_cycle = []
            s_devs = sum(len(b.deviations) for b in site_batches)
            for b in site_batches:
                cs, ce = None, None
                for s in b.stages:
                    if s.status == "completed" and s.started_at and s.completed_at:
                        dur = (s.completed_at - s.started_at).seconds // 60
                        s_completed += 1
                        if dur <= s.norm_minutes:
                            s_on_time += 1
                        if cs is None:
                            cs = s.started_at
                        ce = s.completed_at
                if cs and ce:
                    s_cycle.append((ce - cs).seconds // 60)
            site_kpis.append({
                "site_id": site.id,
                "site_name": site.name,
                "avg_cycle_time": round(sum(s_cycle) / len(s_cycle), 1) if s_cycle else 0.0,
                "total_deviations": s_devs,
                "percent_on_time": round(s_on_time / s_completed * 100, 1) if s_completed > 0 else 100.0,
            })

    return {
        "avg_cycle_time": avg_cycle,
        "total_deviations": total_dev,
        "percent_on_time": percent_on_time,
        "top_reasons": top_reasons,
        "stage_analytics": stage_analytics,
        "site_kpis": site_kpis,
    }
