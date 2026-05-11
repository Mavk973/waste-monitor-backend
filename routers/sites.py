from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date

import models
import schemas
from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/sites", tags=["sites"])


def _site_stats(site: models.Site, today: date) -> dict:
    batches = site.batches
    today_batches = [b for b in batches if b.created_at and b.created_at.date() == today]
    in_progress = [
        b for b in batches
        if b.current_stage and b.current_stage.status in ("in_progress", "paused", "deviation")
    ]
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
        "id": site.id,
        "name": site.name,
        "total_batches_in_progress": len(in_progress),
        "total_deviations": deviations,
        "percent_on_time": percent,
        "total_batches_today": len(today_batches),
    }


@router.get("")
def list_sites(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    sites = db.query(models.Site).all()
    today = date.today()
    return [_site_stats(s, today) for s in sites]


@router.post("", status_code=201)
def create_site(
    data: schemas.SiteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Только менеджер может создавать объекты")

    existing = db.query(models.Site).filter(models.Site.name == data.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Объект с таким названием уже существует")

    site = models.Site(name=data.name)
    db.add(site)
    db.commit()
    db.refresh(site)
    return {"id": site.id, "name": site.name}


@router.put("/{site_id}")
def update_site(
    site_id: int,
    data: schemas.SiteUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Только менеджер может редактировать объекты")

    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Объект не найден")

    site.name = data.name
    db.commit()
    db.refresh(site)
    return {"id": site.id, "name": site.name}


@router.delete("/{site_id}", status_code=204)
def delete_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Только менеджер может удалять объекты")

    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Объект не найден")

    has_batches = db.query(models.WasteBatch).filter(models.WasteBatch.site_id == site_id).first()
    if has_batches:
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить объект с существующими партиями. Сначала удалите все партии."
        )

    db.query(models.User).filter(models.User.site_id == site_id).update({"site_id": None})
    db.delete(site)
    db.commit()
