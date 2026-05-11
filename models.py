from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Site(Base):
    __tablename__ = "sites"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    users = relationship("User", back_populates="site")
    batches = relationship("WasteBatch", back_populates="site")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # operator, master, manager
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    site = relationship("Site", back_populates="users")
    notifications = relationship("Notification", back_populates="user")


class WasteBatch(Base):
    __tablename__ = "waste_batches"
    id = Column(Integer, primary_key=True, index=True)
    waste_name = Column(String, nullable=False)
    fkko_code = Column(String, nullable=False, default="")
    hazard_class = Column(Integer, nullable=False, default=4)
    volume = Column(Float, nullable=False, default=0.0)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    site = relationship("Site", back_populates="batches")
    operator = relationship("User")
    stages = relationship("BatchStage", back_populates="batch", order_by="BatchStage.order_index")
    deviations = relationship("Deviation", back_populates="batch")

    @property
    def current_stage(self):
        for s in self.stages:
            if s.status in ("in_progress", "paused", "deviation"):
                return s
        for s in self.stages:
            if s.status == "waiting":
                return s
        return self.stages[-1] if self.stages else None

    @property
    def batch_status(self):
        if not self.stages:
            return "active"
        if all(s.status == "completed" for s in self.stages):
            return "completed"
        return "active"


class BatchStage(Base):
    __tablename__ = "batch_stages"
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("waste_batches.id"), nullable=False)
    stage_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="waiting")
    order_index = Column(Integer, nullable=False, default=0)
    norm_minutes = Column(Integer, nullable=False, default=60)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    batch = relationship("WasteBatch", back_populates="stages")


class Deviation(Base):
    __tablename__ = "deviations"
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("waste_batches.id"), nullable=False)
    type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    photo_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    batch = relationship("WasteBatch", back_populates="deviations")


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_type = Column(String, nullable=False)
    batch_id = Column(Integer, ForeignKey("waste_batches.id"), nullable=False)
    batch_name = Column(String, nullable=False)
    site_name = Column(String, nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="notifications")
