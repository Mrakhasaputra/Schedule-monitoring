from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, time
import logging
from database import engine  # Hanya import engine, bukan get_db

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def execute_print_task(schedule_id: int, task_name: str):
    """Fungsi untuk studi kasus Dynamic Printing Task"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Log ke console
    print(f"[{current_time}] Berhasil menjalankan task: {task_name} (Schedule ID: {schedule_id})")
    
    # Log ke database - import di dalam function untuk avoid circular import
    try:
        from database import SessionLocal
        from models import JobLog
        
        db = SessionLocal()
        
        log_entry = JobLog(
            schedule_id=schedule_id,
            status="success",
            message=f"Task '{task_name}' executed successfully at {current_time}"
        )
        
        db.add(log_entry)
        db.commit()
        logger.info(f"Task '{task_name}' (ID: {schedule_id}) executed and logged")
        
    except Exception as e:
        logger.error(f"Failed to log task execution: {e}")
    finally:
        if 'db' in locals():
            db.close()

class DynamicScheduler:
    """Manager untuk dynamic scheduler dengan model baru"""
    
    def __init__(self):
        # Konfigurasi jobstore - gunakan connection string langsung, bukan engine
        # untuk menghindari masalah dengan NullPool
        jobstores = {
            'default': SQLAlchemyJobStore(
                url="postgresql://postgres.fbwtabjrjvmgyfhopvmi:tJwnUP365RHRrsMq@aws-1-ap-south-1.pooler.supabase.com:6543/postgres",
                tablename='apscheduler_jobs'
            )
        }
        
        # Konfigurasi executor
        executors = {
            'default': {
                'type': 'threadpool',
                'max_workers': 5  # Sesuaikan dengan kebutuhan
            }
        }
        
        # Konfigurasi job defaults
        job_defaults = {
            'coalesce': True,
            'max_instances': 1,  # Supabase mungkin punya batasan
            'misfire_grace_time': 60  # 60 detik toleransi
        }
        
        # Inisialisasi scheduler
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Jakarta'
        )
        
        # Start scheduler
        try:
            self.scheduler.start()
            logger.info("Scheduler started successfully")
            
            # Load existing schedules
            self.load_all_schedules()
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise
    
    def schedule_from_model(self, schedule):
        """Create/update job dari model Schedule"""
        job_id = f"schedule_{schedule.id}"
        
        # Hapus job lama jika ada
        self.remove_job(job_id)
        
        # Jika schedule tidak aktif, jangan buat job
        if not schedule.is_active:
            logger.info(f"Schedule {schedule.id} is inactive, job not created")
            return
        
        try:
            # Parse cron expression dari model
            cron_parts = schedule.cron_expression.split()
            
            # Create job dengan cron trigger
            self.scheduler.add_job(
                func=execute_print_task,
                trigger=CronTrigger(
                    minute=cron_parts[0],
                    hour=cron_parts[1],
                    day=cron_parts[2],
                    month=cron_parts[3],
                    day_of_week=cron_parts[4]
                ),
                args=[schedule.id, schedule.name],
                id=job_id,
                name=f"print_task_{schedule.name}",
                replace_existing=True,
                misfire_grace_time=60
            )
            
            logger.info(f"Job scheduled: {job_id} with cron {schedule.cron_expression}")
            
        except Exception as e:
            logger.error(f"Failed to schedule job {job_id}: {e}")
    
    def load_all_schedules(self):
        """Load semua schedules dari database dan buat jobs"""
        try:
            from database import SessionLocal
            from models import Schedule
            
            db = SessionLocal()
            schedules = db.query(Schedule).filter(Schedule.is_active == True).all()
            
            for schedule in schedules:
                self.schedule_from_model(schedule)
            
            logger.info(f"Loaded {len(schedules)} schedules from database")
            
        except Exception as e:
            logger.error(f"Failed to load schedules: {e}")
        finally:
            if 'db' in locals():
                db.close()
    
    def remove_job(self, job_id: str):
        """Menghapus job dari scheduler"""
        try:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"Job removed: {job_id}")
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
    
    def get_all_jobs(self):
        """Mendapatkan semua jobs"""
        return self.scheduler.get_jobs()
    
    def shutdown(self):
        """Shutdown scheduler dengan graceful shutdown"""
        try:
            self.scheduler.shutdown()
            logger.info("Scheduler shutdown successfully")
        except Exception as e:
            logger.error(f"Error during scheduler shutdown: {e}")

# Global scheduler instance - BUAT DI main.py, bukan di sini
# scheduler = DynamicScheduler()