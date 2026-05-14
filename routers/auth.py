from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from auth import hash_password, verify_password, create_access_token, create_refresh_token, decode_refresh_token, get_current_user
from database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserOut)
def register(data: schemas.UserRegister, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Пользователь с таким логином уже существует")

    if data.role not in ("operator", "master", "manager"):
        raise HTTPException(status_code=400, detail="Недопустимая роль")

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

    return schemas.UserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        site_id=user.site_id,
        site_name=user.site.name if user.site else None,
    )


@router.post("/login", response_model=schemas.Token)
def login(data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == data.username).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    token = create_access_token({"sub": user.username})
    refresh = create_refresh_token({"sub": user.username})
    user_out = schemas.UserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        site_id=user.site_id,
        site_name=user.site.name if user.site else None,
    )
    return schemas.Token(access_token=token, refresh_token=refresh, token_type="bearer", user=user_out)


@router.post("/refresh")
def refresh_token(data: schemas.RefreshTokenIn, db: Session = Depends(get_db)):
    try:
        username = decode_refresh_token(data.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Недействительный refresh-токен")

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    new_access = create_access_token({"sub": user.username})
    new_refresh = create_refresh_token({"sub": user.username})
    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    return schemas.UserOut(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        site_id=current_user.site_id,
        site_name=current_user.site.name if current_user.site else None,
    )


@router.put("/password")
def change_password(
    data: schemas.ChangePassword,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Новый пароль должен быть не менее 6 символов")

    current_user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"ok": True}
