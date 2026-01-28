from fastapi import FastAPI
from database import engine
from models import Base
from api import schedule


app = FastAPI(title="Schedule Monitoring API")

Base.metadata.create_all(bind=engine)

app.include_router(schedule.router)
