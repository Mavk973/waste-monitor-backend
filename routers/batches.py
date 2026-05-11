from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
import os, shutil

import models
import schemas
from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/batches", tags=["batches"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

DEFAULT_STAGES = [
    {"stage_name": "Приём и регистрация", "norm_minutes": 20},
    {"stage_name": "Контроль и взвешивание", "norm_minutes": 15},
    {"stage_name": "Временное хранение", "norm_minutes": 30},
    {"stage_name": "Транспортировка", "norm_minutes": 60},
    {"stage_name": "Обезвреживание / Переработка", "norm_minutes": 90},
    {"stage_name": "Утилизация", "norm_minutes": 45},
]


def _batch_to_out(batch: models.WasteBatch) -> dict:
    stage = batch.current_stage
    all_completed = (
        len(batch.stages) > 0 and all(s.status == "completed" for s in batch.stages)
    )
    return {
        "id": batch.id,
        "waste_name": batch.waste_name,
        "fkko_code": batch.fkko_code,
        "hazard_class": batch.hazard_class,
        "volume": batch.volume,
        "site_id": batch.site_id,
        "site_name": batch.site.name if batch.site else "",
        "operator_id": batch.operator_id,
        "operator_name": batch.operator.full_name if batch.operator else "",
        "current_stage_name": stage.stage_name if stage else "",
        "current_status": stage.status if stage else "waiting",
        "current_stage_id": stage.id if stage else 0,
        "stage_started_at": stage.started_at if stage else None,
        "stage_norm_minutes": stage.norm_minutes if stage else 0,
        "batch_status": "completed" if all_completed else "active",
        "created_at": batch.created_at,
    }


@router.get("", response_model=list[schemas.BatchOut])
def list_batches(
    site_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.WasteBatch)

    if site_id:
        query = query.filter(models.WasteBatch.site_id == site_id)
    elif current_user.role in ("operator", "master") and current_user.site_id:
        query = query.filter(models.WasteBatch.site_id == current_user.site_id)

    if search:
        query = query.filter(
            models.WasteBatch.waste_name.ilike(f"%{search}%")
            | models.WasteBatch.fkko_code.ilike(f"%{search}%")
        )

    if date_from:
        query = query.filter(
            models.WasteBatch.created_at >= datetime.strptime(date_from, "%Y-%m-%d")
        )
    if date_to:
        query = query.filter(
            models.WasteBatch.created_at
            <= datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59)
        )

    batches = query.order_by(models.WasteBatch.created_at.desc()).all()

    if status and status != "all":
        batches = [
            b for b in batches
            if (
                (status == "completed" and len(b.stages) > 0 and all(s.status == "completed" for s in b.stages))
                or (status == "active" and not (len(b.stages) > 0 and all(s.status == "completed" for s in b.stages)))
            )
        ]

    return [_batch_to_out(b) for b in batches]


@router.post("", response_model=schemas.BatchOut, status_code=201)
def create_batch(
    data: schemas.BatchCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    site_id = data.site_id
    if not site_id:
        if current_user.role in ("operator", "master") and current_user.site_id:
            site_id = current_user.site_id
        else:
            raise HTTPException(status_code=400, detail="Укажите объект (site_id)")

    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Объект не найден")

    if current_user.role in ("operator", "master") and current_user.site_id != site_id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому объекту")

    operator_id = data.operator_id
    if not operator_id and current_user.role == "operator":
        operator_id = current_user.id

    batch = models.WasteBatch(
        waste_name=data.waste_name,
        fkko_code=data.fkko_code,
        hazard_class=data.hazard_class,
        volume=data.volume,
        site_id=site_id,
        operator_id=operator_id,
    )
    db.add(batch)
    db.flush()

    stage_list = data.stages if data.stages else [schemas.StageIn(**s) for s in DEFAULT_STAGES]
    for idx, s in enumerate(stage_list):
        stage = models.BatchStage(
            batch_id=batch.id,
            stage_name=s.stage_name,
            norm_minutes=s.norm_minutes,
            order_index=idx,
            status="waiting",
        )
        db.add(stage)

    db.commit()
    db.refresh(batch)
    return _batch_to_out(batch)


@router.get("/{batch_id}")
def get_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    batch = db.query(models.WasteBatch).filter(models.WasteBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Партия не найдена")

    result = _batch_to_out(batch)
    result["stages"] = [
        {
            "id": s.id,
            "stage_name": s.stage_name,
            "status": s.status,
            "order_index": s.order_index,
            "norm_minutes": s.norm_minutes,
            "started_at": s.started_at,
            "completed_at": s.completed_at,
        }
        for s in batch.stages
    ]
    result["deviations"] = [
        {
            "id": d.id,
            "type": d.type,
            "description": d.description,
            "photo_path": d.photo_path,
            "created_at": d.created_at,
        }
        for d in batch.deviations
    ]
    return result


@router.patch("/{batch_id}", response_model=schemas.BatchOut)
def update_batch(
    batch_id: int,
    data: schemas.BatchUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    batch = db.query(models.WasteBatch).filter(models.WasteBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Партия не найдена")

    if current_user.role == "operator" and batch.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    if current_user.role == "master" and batch.site_id != current_user.site_id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(batch, field, value)

    db.commit()
    db.refresh(batch)
    return _batch_to_out(batch)


@router.delete("/{batch_id}", status_code=204)
def delete_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Только менеджер может удалять партии")

    batch = db.query(models.WasteBatch).filter(models.WasteBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Партия не найдена")

    db.query(models.Deviation).filter(models.Deviation.batch_id == batch_id).delete()
    db.query(models.BatchStage).filter(models.BatchStage.batch_id == batch_id).delete()
    db.query(models.Notification).filter(models.Notification.batch_id == batch_id).delete()
    db.delete(batch)
    db.commit()


@router.get("/{batch_id}/deviations")
def list_deviations(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    batch = db.query(models.WasteBatch).filter(models.WasteBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Партия не найдена")
    return [
        {
            "id": d.id,
            "type": d.type,
            "description": d.description,
            "photo_path": d.photo_path,
            "created_at": d.created_at,
        }
        for d in batch.deviations
    ]


@router.post("/{batch_id}/stages/{stage_id}/action")
def stage_action(
    batch_id: int,
    stage_id: int,
    data: schemas.StageActionIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stage = db.query(models.BatchStage).filter(
        models.BatchStage.id == stage_id,
        models.BatchStage.batch_id == batch_id,
    ).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Этап не найден")

    now = datetime.utcnow()
    action = data.action

    if action == "start":
        stage.status = "in_progress"
        stage.started_at = now
    elif action == "pause":
        stage.status = "paused"
    elif action == "resume":
        stage.status = "in_progress"
    elif action == "complete":
        stage.status = "completed"
        stage.completed_at = now
        batch = stage.batch
        next_started = False
        for s in batch.stages:
            if s.order_index == stage.order_index + 1:
                s.status = "waiting"
                next_started = True
                break
        _create_notification(db, batch, "stage_completed", f"Этап «{stage.stage_name}» завершён")
        if not next_started:
            _create_notification(db, batch, "batch_completed", f"Партия «{batch.waste_name}» полностью завершена")
    else:
        raise HTTPException(status_code=400, detail="Неизвестное действие")

    db.commit()
    return {"ok": True}


@router.post("/{batch_id}/deviations")
async def record_deviation(
    batch_id: int,
    type: str = Form(...),
    description: str = Form(...),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    batch = db.query(models.WasteBatch).filter(models.WasteBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Партия не найдена")

    photo_path = None
    if photo:
        filename = f"{batch_id}_{datetime.utcnow().timestamp()}_{photo.filename}"
        path = os.path.join(UPLOAD_DIR, filename)
        with open(path, "wb") as f:
            shutil.copyfileobj(photo.file, f)
        photo_path = path

    deviation = models.Deviation(
        batch_id=batch_id,
        type=type,
        description=description,
        photo_path=photo_path,
    )
    db.add(deviation)

    stage = batch.current_stage
    if stage and stage.status == "in_progress":
        stage.status = "deviation"

    _create_notification(db, batch, "deviation", f"Отклонение: {description[:80]}")
    db.commit()
    return {"ok": True}


def _create_notification(db: Session, batch: models.WasteBatch, event_type: str, description: str):
    users = db.query(models.User).filter(
        models.User.role.in_(["master", "manager"])
    ).all()
    for user in users:
        notif = models.Notification(
            user_id=user.id,
            event_type=event_type,
            batch_id=batch.id,
            batch_name=batch.waste_name,
            site_name=batch.site.name if batch.site else "",
            description=description,
        )
        db.add(notif)
