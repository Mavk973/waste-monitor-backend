from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

import models
import schemas
from auth import hash_password, get_current_user
from database import get_db

router = APIRouter(prefix="/users", tags=["users"])

VALID_ROLES = ("operator", "master", "manager")


def _user_out(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "site_id": user.site_id,
        "site_name": user.site.name if user.site else None,
    }


@router.get("")
def list_users(
    role: Optional[str] = None,
    site_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Только менеджер может просматривать список пользователей")

    query = db.query(models.User)
    if role:
        query = query.filter(models.User.role == role)
    if site_id:
        query = query.filter(models.User.site_id == site_id)

    return [_user_out(u) for u in query.order_by(models.User.full_name).all()]


@router.post("", status_code=201)
def create_user(
    data: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Только менеджер может создавать пользователей")

    if data.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Недопустимая роль. Допустимые: {VALID_ROLES}")

    existing = db.query(models.User).filter(models.User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Пользователь с таким логином уже существует")

    if data.site_id:
        site = db.query(models.Site).filter(models.Site.id == data.site_id).first()
        if not site:
            raise HTTPException(status_code=404, detail="Объект не найден")

    user = models.User(
        username=data.username,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        site_id=data.site_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.put("/{user_id}")
def update_user(
    user_id: int,
    data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Только менеджер может редактировать пользователей")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if data.role and data.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Недопустимая роль. Допустимые: {VALID_ROLES}")

    if data.site_id:
        site = db.query(models.Site).filter(models.Site.id == data.site_id).first()
        if not site:
            raise HTTPException(status_code=404, detail="Объект не найден")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Только менеджер может удалять пользователей")

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить себя")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    db.delete(user)
    db.commit()
