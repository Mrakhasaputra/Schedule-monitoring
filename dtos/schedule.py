from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import time
import re

class ScheduleBase(BaseModel):
    """Base schema untuk Schedule dengan model baru"""
    name: str = Field(..., min_length=1, max_length=100)
    schedule_type: str = Field(..., pattern="^(daily|weekly|monthly)$")
    run_time: str = Field(..., description="Format: HH:MM")
    
    @validator('run_time')
    def validate_time_format(cls, v):
        """Validasi format waktu HH:MM"""
        if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError('run_time harus dalam format HH:MM (24 jam)')
        return v
    
    @property
    def time_obj(self):
        """Convert string time to time object"""
        hour, minute = map(int, self.run_time.split(':'))
        return time(hour=hour, minute=minute)

class ScheduleCreate(ScheduleBase):
    """Schema untuk create schedule dengan validasi conditional"""
    day_of_week: Optional[str] = None
    day_of_month: Optional[int] = None
    
    @validator('day_of_week')
    def validate_day_of_week(cls, v, values):
        if values.get('schedule_type') == 'weekly' and not v:
            raise ValueError('day_of_week diperlukan untuk schedule_type weekly')
        
        if v:
            valid_days = {'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'}
            days = [d.strip().lower() for d in v.split(',')]
            invalid_days = set(days) - valid_days
            
            if invalid_days:
                raise ValueError(f'Hari tidak valid: {invalid_days}. Gunakan: mon,tue,wed,thu,fri,sat,sun')
        
        return v
    
    @validator('day_of_month')
    def validate_day_of_month(cls, v, values):
        if values.get('schedule_type') == 'monthly' and not v:
            raise ValueError('day_of_month diperlukan untuk schedule_type monthly')
        
        if v and not (1 <= v <= 31):
            raise ValueError('day_of_month harus antara 1-31')
        
        return v

class ScheduleUpdate(BaseModel):
    """Schema untuk update schedule"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    schedule_type: Optional[str] = Field(None, pattern="^(daily|weekly|monthly)$")
    run_time: Optional[str] = None
    day_of_week: Optional[str] = None
    day_of_month: Optional[int] = None
    is_active: Optional[bool] = None
    
    @validator('run_time')
    def validate_time_format(cls, v):
        if v and not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError('run_time harus dalam format HH:MM (24 jam)')
        return v

class ScheduleResponse(ScheduleBase):
    """Schema untuk response schedule"""
    id: int
    day_of_week: Optional[str] = None
    day_of_month: Optional[int] = None
    is_active: bool
    display_schedule: str
    created_at: str
    
    class Config:
        from_attributes = True

class JobLogResponse(BaseModel):
    """Schema untuk response job log"""
    id: int
    schedule_id: int
    status: str
    message: str
    executed_at: str
    
    class Config:
        from_attributes = True