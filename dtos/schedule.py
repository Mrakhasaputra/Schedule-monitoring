from pydantic import BaseModel
from datetime import time


class ScheduleCreate(BaseModel):
    name: str
    schedule_type: str
    run_time: time
    day_of_week: str | None = None
    day_of_month: int | None = None
    is_active: bool = True

class Config:
    orm_mode = True