from sqlalchemy import Column, Integer, String, Boolean, Time, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base


class Schedule(Base):
    __tablename__ = "schedules"


id = Column(Integer, primary_key=True, index=True)
name = Column(String, nullable=False)
schedule_type = Column(String, nullable=False) # daily, weekly, monthly
run_time = Column(Time, nullable=False)
day_of_week = Column(String, nullable=True) # mon,tue
day_of_month = Column(Integer, nullable=True) # 1-31
is_active = Column(Boolean, default=True)
created_at = Column(DateTime(timezone=True), server_default=func.now())


class JobLog(Base):
    __tablename__ = "job_logs"


id = Column(Integer, primary_key=True)
schedule_id = Column(Integer, ForeignKey("schedules.id"))
status = Column(String)
message = Column(String)
executed_at = Column(DateTime(timezone=True), server_default=func.now())