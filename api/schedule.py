from flask import Blueprint, request, jsonify
from datetime import time
from dtos.schedule import ScheduleCreate, ScheduleUpdate, ScheduleResponse, JobLogResponse
from models import Schedule, JobLog
from database import get_db
from contextlib import contextmanager
from sqlalchemy.orm import joinedload

bp = Blueprint('schedule', __name__, url_prefix='/api/schedules')

@contextmanager
def db_session():
    """Context manager untuk session database"""
    db = next(get_db())
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

@bp.route('', methods=['POST'])
def create_schedule():
    """Endpoint untuk membuat schedule baru"""
    try:
        data = request.get_json()
        schedule_data = ScheduleCreate(**data)
        
        with db_session() as db:
            # Convert time string to time object
            hour, minute = map(int, schedule_data.run_time.split(':'))
            time_obj = time(hour=hour, minute=minute)
            
            # Buat schedule baru
            new_schedule = Schedule(
                name=schedule_data.name,
                schedule_type=schedule_data.schedule_type,
                run_time=time_obj,
                day_of_week=schedule_data.day_of_week,
                day_of_month=schedule_data.day_of_month
            )
            
            db.add(new_schedule)
            db.flush()  # Get the ID
            
            # Buat job di scheduler - melalui current_app
            from flask import current_app
            if current_app.scheduler:
                current_app.scheduler.schedule_from_model(new_schedule)
            
            # Refresh untuk mendapatkan data lengkap
            db.refresh(new_schedule)
            
            # Convert to response schema
            response_data = ScheduleResponse.from_orm(new_schedule)
            
            return jsonify({
                "message": "Schedule created successfully",
                "schedule": response_data.dict()
            }), 201
            
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route('', methods=['GET'])
def get_schedules():
    """Endpoint untuk mendapatkan semua schedules dengan eager loading"""
    with db_session() as db:
        # Eager loading dengan joinedload untuk logs
        schedules = db.query(Schedule)\
            .options(joinedload(Schedule.logs))\
            .order_by(Schedule.created_at.desc())\
            .all()
        
        # Get active jobs dari scheduler
        from flask import current_app
        active_jobs = set()
        if current_app.scheduler:
            active_jobs = {job.id for job in current_app.scheduler.get_all_jobs()}
        
        # Tambahkan status real-time ke response
        schedules_data = []
        for schedule in schedules:
            schedule_dict = ScheduleResponse.from_orm(schedule).dict()
            job_id = f"schedule_{schedule.id}"
            schedule_dict["is_running"] = job_id in active_jobs
            
            # Add recent logs
            schedule_dict["recent_logs"] = [
                JobLogResponse.from_orm(log).dict()
                for log in schedule.logs[-5:]  # 5 logs terakhir
            ]
            
            schedules_data.append(schedule_dict)
        
        return jsonify({
            "count": len(schedules_data),
            "schedules": schedules_data
        }), 200

@bp.route('/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id: int):
    """Endpoint untuk menghapus schedule"""
    with db_session() as db:
        schedule = db.query(Schedule).get(schedule_id)
        
        if not schedule:
            return jsonify({"error": "Schedule not found"}), 404
        
        # Hapus job dari scheduler
        from flask import current_app
        if current_app.scheduler:
            current_app.scheduler.remove_job(f"schedule_{schedule_id}")
        
        # Hapus dari database (logs akan terhapus otomatis karena cascade)
        db.delete(schedule)
        
        return jsonify({
            "message": "Schedule deleted successfully",
            "schedule_id": schedule_id
        }), 200

@bp.route('/<int:schedule_id>/toggle', methods=['PATCH'])
def toggle_schedule(schedule_id: int):
    """Endpoint untuk toggle aktif/nonaktif schedule"""
    with db_session() as db:
        schedule = db.query(Schedule).get(schedule_id)
        
        if not schedule:
            return jsonify({"error": "Schedule not found"}), 404
        
        # Toggle status
        schedule.is_active = not schedule.is_active
        db.add(schedule)
        
        # Update scheduler
        from flask import current_app
        if current_app.scheduler:
            if schedule.is_active:
                current_app.scheduler.schedule_from_model(schedule)
            else:
                current_app.scheduler.remove_job(f"schedule_{schedule_id}")
        
        return jsonify({
            "message": f"Schedule {'activated' if schedule.is_active else 'deactivated'}",
            "is_active": schedule.is_active
        }), 200