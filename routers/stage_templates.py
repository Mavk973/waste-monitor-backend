from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/stage-templates", tags=["stage-templates"])


def _require_manager(current_user: models.User):
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Только менеджер может управлять шаблонами этапов")


@router.get("", response_model=List[schemas.StageTemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    return db.query(models.StageTemplate).order_by(models.StageTemplate.order_index).all()


@router.post("", response_model=schemas.StageTemplateOut, status_code=201)
def create_template(
    data: schemas.StageTemplateCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _require_manager(current_user)
    # auto-assign order_index to end if not specified
    if data.order_index == 0:
        count = db.query(models.StageTemplate).count()
        order = count
    else:
        order = data.order_index
    t = models.StageTemplate(
        stage_name=data.stage_name,
        norm_minutes=data.norm_minutes,
        order_index=order,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.put("/{template_id}", response_model=schemas.StageTemplateOut)
def update_template(
    template_id: int,
    data: schemas.StageTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _require_manager(current_user)
    t = db.query(models.StageTemplate).filter(models.StageTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(t, field, value)
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _require_manager(current_user)
    t = db.query(models.StageTemplate).filter(models.StageTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    db.delete(t)
    db.commit()


@router.post("/reorder")
def reorder_templates(
    template_ids: List[int],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _require_manager(current_user)
    for idx, tid in enumerate(template_ids):
        t = db.query(models.StageTemplate).filter(models.StageTemplate.id == tid).first()
        if t:
            t.order_index = idx
    db.commit()
    return {"ok": True}
