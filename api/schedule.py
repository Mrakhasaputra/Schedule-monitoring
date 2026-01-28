from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Schedule
from dtos.schedule import ScheduleCreate


router = APIRouter(prefix="/schedules", tags=["Schedules"])


def get_db():   
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/")
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db)):
    schedule = Schedule(**payload.dict())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("/")
def get_schedules(db: Session = Depends(get_db)):
    return db.query(Schedule).all()