from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class UserRegister(BaseModel):
    username: str
    password: str
    full_name: str
    role: str
    site_id: Optional[int] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    site_id: Optional[int]
    site_name: Optional[str] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: str
    site_id: Optional[int] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    site_id: Optional[int] = None


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserOut


class RefreshTokenIn(BaseModel):
    refresh_token: str


class StageIn(BaseModel):
    stage_name: str
    norm_minutes: int = 60


class StageOut(BaseModel):
    id: int
    stage_name: str
    status: str
    order_index: int
    norm_minutes: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class BatchCreate(BaseModel):
    waste_name: str
    fkko_code: str = ""
    hazard_class: int = 4
    volume: float
    site_id: Optional[int] = None
    operator_id: Optional[int] = None
    stages: List[StageIn] = []


class BatchUpdate(BaseModel):
    waste_name: Optional[str] = None
    fkko_code: Optional[str] = None
    hazard_class: Optional[int] = None
    volume: Optional[float] = None
    operator_id: Optional[int] = None


class BatchOut(BaseModel):
    id: int
    waste_name: str
    fkko_code: str
    hazard_class: int
    volume: float
    site_id: int
    site_name: str
    operator_id: Optional[int]
    operator_name: str
    current_stage_name: str
    current_status: str
    current_stage_id: int
    stage_started_at: Optional[datetime]
    stage_norm_minutes: int
    batch_status: str = "active"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BatchDetailOut(BatchOut):
    stages: List[StageOut] = []
    deviations: List[dict] = []

    class Config:
        from_attributes = True


class StageActionIn(BaseModel):
    action: str  # start, pause, resume, complete


class SiteOut(BaseModel):
    id: int
    name: str
    total_batches_in_progress: int
    total_deviations: int
    percent_on_time: float
    total_batches_today: int

    class Config:
        from_attributes = True


class SiteCreate(BaseModel):
    name: str


class SiteUpdate(BaseModel):
    name: str


class DashboardSummary(BaseModel):
    total_batches_today: int
    deviations: int
    percent_on_time: float


class NotificationOut(BaseModel):
    id: int
    event_type: str
    batch_name: str
    site_name: str
    description: str
    is_read: bool
    batch_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class StageAnalyticsOut(BaseModel):
    stage_name: str
    actual_minutes: float
    norm_minutes: float


class DowntimeReasonOut(BaseModel):
    reason: str
    count: int
    percentage: float


class SiteKpiOut(BaseModel):
    site_id: int
    site_name: str
    avg_cycle_time: float
    total_deviations: int
    percent_on_time: float


class AnalyticsOut(BaseModel):
    avg_cycle_time: float
    total_deviations: int
    percent_on_time: float
    top_reasons: List[DowntimeReasonOut]
    stage_analytics: List[StageAnalyticsOut]
    site_kpis: List[SiteKpiOut]


class StageTemplateOut(BaseModel):
    id: int
    stage_name: str
    norm_minutes: int
    order_index: int
    is_active: bool

    class Config:
        from_attributes = True


class StageTemplateCreate(BaseModel):
    stage_name: str
    norm_minutes: int = 60
    order_index: int = 0


class StageTemplateUpdate(BaseModel):
    stage_name: Optional[str] = None
    norm_minutes: Optional[int] = None
    order_index: Optional[int] = None
    is_active: Optional[bool] = None


class AuditLogOut(BaseModel):
    id: int
    user_name: str
    action: str
    details: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
