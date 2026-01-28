from sqlalchemy import Column, Integer, String, Boolean, Time, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class Schedule(Base):
    __tablename__ = "schedules"
    
    # FIXED: Semua kolom harus berada dalam class dengan indentasi yang benar
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    schedule_type = Column(String, nullable=False)  # daily, weekly, monthly
    run_time = Column(Time, nullable=False)  # Format: HH:MM:SS
    day_of_week = Column(String, nullable=True)  # mon,tue,wed,thu,fri,sat,sun
    day_of_month = Column(Integer, nullable=True)  # 1-31
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    logs = relationship("JobLog", back_populates="schedule", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Schedule {self.name} ({self.schedule_type})>"
    
    @property
    def hour(self):
        """Get hour from run_time"""
        return self.run_time.hour if self.run_time else 0
    
    @property
    def minute(self):
        """Get minute from run_time"""
        return self.run_time.minute if self.run_time else 0
    
    @property
    def cron_expression(self):
        """Generate cron expression based on schedule type"""
        if self.schedule_type == "daily":
            return f"{self.minute} {self.hour} * * *"
        elif self.schedule_type == "weekly" and self.day_of_week:
            # Convert day names to cron format (0-6 where 0=Sunday)
            days_map = {
                'sun': '0', 'mon': '1', 'tue': '2', 'wed': '3',
                'thu': '4', 'fri': '5', 'sat': '6'
            }
            day_numbers = [days_map[d.strip().lower()] for d in self.day_of_week.split(',')]
            return f"{self.minute} {self.hour} * * {','.join(day_numbers)}"
        elif self.schedule_type == "monthly" and self.day_of_month:
            return f"{self.minute} {self.hour} {self.day_of_month} * *"
        else:
            return f"{self.minute} {self.hour} * * *"
    
    @property
    def display_schedule(self):
        """Format schedule for display"""
        if self.schedule_type == "daily":
            return f"Daily at {self.run_time.strftime('%H:%M')}"
        elif self.schedule_type == "weekly":
            days = ', '.join([d.capitalize() for d in self.day_of_week.split(',')])
            return f"Weekly on {days} at {self.run_time.strftime('%H:%M')}"
        elif self.schedule_type == "monthly":
            return f"Monthly on day {self.day_of_month} at {self.run_time.strftime('%H:%M')}"
        return f"At {self.run_time.strftime('%H:%M')}"


class JobLog(Base):
    __tablename__ = "job_logs"
    
    id = Column(Integer, primary_key=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id", ondelete="CASCADE"))
    status = Column(String)  # success, error, running
    message = Column(String)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    schedule = relationship("Schedule", back_populates="logs")
    
    def __repr__(self):
        return f"<JobLog {self.schedule_id} - {self.status} at {self.executed_at}>"