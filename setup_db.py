"""
Создаёт тестовые данные: площадки, пользователей и одну партию.
Запускать один раз после первого старта сервера.
"""
from database import SessionLocal
from models import Site, User, WasteBatch, BatchStage
from auth import hash_password

db = SessionLocal()

# Площадки
site1 = Site(name="Площадка №1")
site2 = Site(name="Площадка №2")
db.add_all([site1, site2])
db.commit()
db.refresh(site1)
db.refresh(site2)

# Пользователи
users = [
    User(username="operator1", full_name="Иван Иванов", hashed_password=hash_password("123456"), role="operator", site_id=site1.id),
    User(username="master1",   full_name="Пётр Петров",  hashed_password=hash_password("123456"), role="master",   site_id=site1.id),
    User(username="manager1",  full_name="Анна Сидорова", hashed_password=hash_password("123456"), role="manager",  site_id=None),
]
db.add_all(users)
db.commit()
for u in users:
    db.refresh(u)

op = users[0]

# Тестовая партия
batch = WasteBatch(
    waste_name="Ртутьсодержащие отходы",
    fkko_code="4 71 101 01 52 1",
    hazard_class=1,
    volume=0.5,
    site_id=site1.id,
    operator_id=op.id,
)
db.add(batch)
db.commit()
db.refresh(batch)

stages = [
    BatchStage(batch_id=batch.id, stage_name="Приёмка",        order_index=0, norm_minutes=30,  status="completed"),
    BatchStage(batch_id=batch.id, stage_name="Сортировка",      order_index=1, norm_minutes=60,  status="in_progress"),
    BatchStage(batch_id=batch.id, stage_name="Обезвреживание",  order_index=2, norm_minutes=120, status="waiting"),
    BatchStage(batch_id=batch.id, stage_name="Упаковка",        order_index=3, norm_minutes=45,  status="waiting"),
    BatchStage(batch_id=batch.id, stage_name="Передача",        order_index=4, norm_minutes=30,  status="waiting"),
]
db.add_all(stages)
db.commit()
db.close()

print("✓ База данных заполнена тестовыми данными")
print()
print("Тестовые аккаунты:")
print("  operator1 / 123456  (оператор, Площадка №1)")
print("  master1   / 123456  (мастер,   Площадка №1)")
print("  manager1  / 123456  (менеджер)")
