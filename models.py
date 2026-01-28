# models.py
from sqlalchemy import Column, Integer, String, Boolean, Time, DateTime, ForeignKey, Text, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class Schedule(Base):
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    schedule_type = Column(String, nullable=False)  # daily, weekly, monthly
    run_time = Column(Time, nullable=False)
    day_of_week = Column(String, nullable=True)  # mon,tue,wed,thu,fri,sat,sun
    day_of_month = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    media_channel_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    logs = relationship("JobLog", back_populates="schedule", cascade="all, delete-orphan")
    
    @property
    def display_schedule(self):
        try:
            time_str = self.run_time.strftime('%H:%M') if self.run_time else "00:00"
            
            if self.schedule_type == "daily":
                return f"Harian pukul {time_str}"
            elif self.schedule_type == "weekly" and self.day_of_week:
                days = {
                    'mon': 'Senin', 'tue': 'Selasa', 'wed': 'Rabu',
                    'thu': 'Kamis', 'fri': 'Jumat', 'sat': 'Sabtu', 'sun': 'Minggu'
                }
                day_list = []
                for d in str(self.day_of_week).split(','):
                    day_key = d.strip().lower()
                    day_list.append(days.get(day_key, day_key))
                return f"Mingguan {', '.join(day_list)} pukul {time_str}"
            elif self.schedule_type == "monthly" and self.day_of_month:
                return f"Bulanan tanggal {self.day_of_month} pukul {time_str}"
            return f"Pukul {time_str}"
        except Exception as e:
            return f"Schedule {self.id}"

class JobLog(Base):
    __tablename__ = "job_logs"
    
    id = Column(Integer, primary_key=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False)  # success, error, warning
    message = Column(Text)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    schedule = relationship("Schedule", back_populates="logs")

class MediaChannel(Base):
    __tablename__ = "media_channels"
    
    id = Column(BigInteger, primary_key=True)
    platform = Column(Text, nullable=True)
    platform_name = Column(Text, nullable=True)
    link = Column(Text, nullable=True)
    ads_type = Column(Text, nullable=True)
    max_posts = Column(BigInteger, nullable=True, default=10)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    @property
    def display_info(self):
        try:
            platform = self.platform_name or self.platform or "Unknown"
            ads_type = self.ads_type or "No type"
            return f"{platform} - {ads_type}"
        except:
            return "Media Channel"