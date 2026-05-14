import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import Base, engine, SessionLocal
from routers import auth, batches, sites, dashboard, analytics, notifications, users, export, stage_templates
from push_service import init_firebase

logger = logging.getLogger(__name__)


def _wait_for_db(retries: int = 10, delay: int = 3):
    from sqlalchemy import text
    for attempt in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection established.")
            return
        except Exception as e:
            logger.warning(f"DB not ready (attempt {attempt + 1}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("Could not connect to the database after multiple retries.")


def _seed_defaults():
    import models as m
    from auth import hash_password
    db = SessionLocal()
    try:
        # Create admin if not exists (check by username, not by user count)
        if not db.query(m.User).filter(m.User.username == "admin").first():
            db.add(m.User(
                username="admin",
                full_name="Администратор",
                hashed_password=hash_password("Admin1234!"),
                role="manager",
            ))
            db.commit()
            logger.info("Default admin user created: admin / Admin1234!")

        # Create default sites if none exist
        if not db.query(m.Site).first():
            db.add_all([
                m.Site(name="Площадка №1"),
                m.Site(name="Площадка №2"),
            ])
            db.commit()
            logger.info("Default sites created.")

        # Create default stage templates if none exist
        if not db.query(m.StageTemplate).first():
            default_templates = [
                {"stage_name": "Приём и регистрация", "norm_minutes": 20, "order_index": 0},
                {"stage_name": "Контроль и взвешивание", "norm_minutes": 15, "order_index": 1},
                {"stage_name": "Временное хранение", "norm_minutes": 30, "order_index": 2},
                {"stage_name": "Транспортировка", "norm_minutes": 60, "order_index": 3},
                {"stage_name": "Обезвреживание / Переработка", "norm_minutes": 90, "order_index": 4},
                {"stage_name": "Утилизация", "norm_minutes": 45, "order_index": 5},
            ]
            for t in default_templates:
                db.add(m.StageTemplate(**t))
            db.commit()
            logger.info("Default stage templates created.")
    except Exception as e:
        logger.error(f"Failed to seed defaults: {e}")
        db.rollback()
    finally:
        db.close()


def _run_migrations():
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token VARCHAR",
        "ALTER TABLE deviations ADD COLUMN IF NOT EXISTS photo_data TEXT",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception:
                pass
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _wait_for_db()
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _seed_defaults()
    init_firebase()
    yield


app = FastAPI(title="Waste Monitor API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router)
app.include_router(batches.router)
app.include_router(sites.router)
app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(notifications.router)
app.include_router(users.router)
app.include_router(export.router)
app.include_router(stage_templates.router)


@app.get("/deviation-types")
def get_deviation_types():
    return [
        "Оборудование",
        "Нарушение технологии",
        "Человеческий фактор",
        "Качество сырья",
        "Внешние факторы",
        "Другое",
    ]


@app.get("/batch-stages/defaults")
def get_default_stages():
    from routers.batches import DEFAULT_STAGES
    return DEFAULT_STAGES


@app.get("/")
def root():
    return {"status": "ok", "message": "Waste Monitor API v2.0"}
