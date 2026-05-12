import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine, SessionLocal
from routers import auth, batches, sites, dashboard, analytics, notifications, users, export

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
    except Exception as e:
        logger.error(f"Failed to seed defaults: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _wait_for_db()
    Base.metadata.create_all(bind=engine)
    _seed_defaults()
    yield


app = FastAPI(title="Waste Monitor API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(batches.router)
app.include_router(sites.router)
app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(notifications.router)
app.include_router(users.router)
app.include_router(export.router)


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
