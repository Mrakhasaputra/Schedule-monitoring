from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, time
import logging
import os
import pytz

logger = logging.getLogger(__name__)

def execute_task(schedule_id: int, schedule_name: str, media_channel_id: int = None):
    """Execute schedule task"""
    try:
        # IMPORT INSIDE FUNCTION TO AVOID CIRCULAR IMPORTS
        from database import SessionLocal
        from models import JobLog, MediaChannel, Schedule
        
        db = SessionLocal()
        
        # Log start
        current_time = datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"⏰ [{current_time}] Starting schedule: {schedule_name} (ID: {schedule_id})")
        
        if media_channel_id:
            # Scraping task
            media_channel = db.query(MediaChannel).filter(
                MediaChannel.id == media_channel_id
            ).first()
            
            if media_channel:
                logger.info(f"🌐 Scraping from: {media_channel.platform}")
                message = f"✅ Scraping '{schedule_name}' completed\nPlatform: {media_channel.platform}\nURL: {media_channel.link}"
            else:
                message = f"⚠️ Media channel {media_channel_id} not found"
        else:
            # Print task
            logger.info(f"🖨️ Printing task: {schedule_name}")
            message = f"✅ Print task '{schedule_name}' completed"
        
        # Save log
        log = JobLog(
            schedule_id=schedule_id,
            status="success",
            message=message
        )
        db.add(log)
        db.commit()
        
        logger.info(f"✅ Schedule completed: {schedule_name}")
        print(f"\n🎯 Schedule executed: {schedule_name}")
        print(f"   Time: {current_time}")
        print(f"   Log saved to database\n")
        
        db.close()
        
    except Exception as e:
        logger.error(f"❌ Error in schedule {schedule_id}: {e}")
        
        # Log error
        try:
            from database import SessionLocal
            from models import JobLog
            
            db = SessionLocal()
            log = JobLog(
                schedule_id=schedule_id,
                status="error",
                message=f"Error: {str(e)}"
            )
            db.add(log)
            db.commit()
            db.close()
        except Exception as db_error:
            logger.error(f"❌ Failed to save error log: {db_error}")

class SchedulerManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler(
            jobstores={
                'default': SQLAlchemyJobStore(
                    url=os.getenv('DATABASE_URL', 'sqlite:///./scheduler.db'),
                    tablename='apscheduler_jobs'
                )
            },
            timezone=pytz.timezone('Asia/Jakarta')
        )
        
    def start(self):
        """Start scheduler and load all schedules"""
        try:
            self.scheduler.start()
            logger.info("✅ Scheduler started")
            self.load_schedules()
            
            # Log all loaded jobs
            self.log_scheduler_status()
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start scheduler: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def load_schedules(self):
        """Load all active schedules from database"""
        try:
            # IMPORT INSIDE FUNCTION
            from database import SessionLocal
            from models import Schedule
            
            db = SessionLocal()
            schedules = db.query(Schedule).filter(
                Schedule.is_active == True
            ).all()
            
            logger.info(f"📥 Loading {len(schedules)} active schedules")
            
            for schedule in schedules:
                self.add_schedule(schedule)
            
            db.close()
            
            # Log all jobs
            self.log_scheduler_status()
                
        except Exception as e:
            logger.error(f"❌ Failed to load schedules: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def add_schedule(self, schedule):
        """Add single schedule to scheduler"""
        try:
            job_id = f"schedule_{schedule.id}"
            
            # Remove existing job
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            
            # Parse cron from schedule
            hour = schedule.run_time.hour
            minute = schedule.run_time.minute
            
            # Debug info
            logger.info(f"📅 Scheduling: {schedule.name}")
            logger.info(f"   Run Time: {hour:02d}:{minute:02d}")
            logger.info(f"   Type: {schedule.schedule_type}")
            
            if schedule.schedule_type == "daily":
                trigger = CronTrigger(
                    minute=minute,
                    hour=hour,
                    timezone='Asia/Jakarta'
                )
                
            elif schedule.schedule_type == "weekly" and schedule.day_of_week:
                # Convert days to numbers (0=Monday, 1=Tuesday, etc. for APScheduler)
                day_map = {'mon': 'mon', 'tue': 'tue', 'wed': 'wed', 'thu': 'thu', 
                          'fri': 'fri', 'sat': 'sat', 'sun': 'sun'}
                days = schedule.day_of_week.split(',')
                day_list = [day_map.get(d.strip().lower(), 'mon') for d in days]
                
                trigger = CronTrigger(
                    minute=minute,
                    hour=hour,
                    day_of_week=','.join(day_list),
                    timezone='Asia/Jakarta'
                )
                
            elif schedule.schedule_type == "monthly" and schedule.day_of_month:
                trigger = CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=schedule.day_of_month,
                    timezone='Asia/Jakarta'
                )
            else:
                # Default to daily
                trigger = CronTrigger(
                    minute=minute,
                    hour=hour,
                    timezone='Asia/Jakarta'
                )
            
            # Create job with proper trigger
            job = self.scheduler.add_job(
                func=execute_task,
                trigger=trigger,
                args=[schedule.id, schedule.name, schedule.media_channel_id],
                id=job_id,
                name=schedule.name,
                replace_existing=True,
                misfire_grace_time=3600  # Allow 1 hour grace period
            )
            
            next_run = job.next_run_time
            if next_run:
                next_run_str = next_run.astimezone(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"   ✅ Scheduled successfully")
                logger.info(f"   Next run: {next_run_str}")
                
                # Special log for 00:00 schedules
                if hour == 0 and minute == 0:
                    logger.info(f"   ⭐ MIDNIGHT SCHEDULE DETECTED - Will run daily at 00:00")
                    print(f"\n{'='*60}")
                    print(f"🌙 MIDNIGHT SCHEDULE: {schedule.name}")
                    print(f"   Will execute daily at 00:00 Jakarta time")
                    print(f"   Next execution: {next_run_str}")
                    print(f"{'='*60}\n")
            else:
                logger.warning(f"   ⚠️ No next run time calculated")
            
        except Exception as e:
            logger.error(f"❌ Failed to schedule {schedule.name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def remove_schedule(self, schedule_id):
        """Remove schedule from scheduler"""
        try:
            job_id = f"schedule_{schedule_id}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"🗑️ Removed schedule {schedule_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Failed to remove schedule {schedule_id}: {e}")
            return False
    
    def log_scheduler_status(self):
        """Log detailed scheduler status"""
        try:
            jobs = self.scheduler.get_jobs()
            logger.info(f"📊 Scheduler Status:")
            logger.info(f"   Total Jobs: {len(jobs)}")
            logger.info(f"   Running: {self.scheduler.running}")
            logger.info(f"   Timezone: {self.scheduler.timezone}")
            
            midnight_jobs = []
            for job in jobs:
                next_run = job.next_run_time
                if next_run:
                    next_run_str = next_run.astimezone(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    next_run_str = "None"
                
                # Check if this is a midnight job
                if '00:00' in str(job.trigger) or '0 0' in str(job.trigger):
                    midnight_jobs.append(job.id)
                
                logger.info(f"   • {job.id} ({job.name})")
                logger.info(f"     Next run: {next_run_str}")
                logger.info(f"     Trigger: {job.trigger}")
            
            if midnight_jobs:
                logger.info(f"   🌙 Midnight schedules detected: {len(midnight_jobs)}")
                for job_id in midnight_jobs:
                    logger.info(f"     - {job_id}")
                    
        except Exception as e:
            logger.error(f"❌ Failed to log scheduler status: {e}")
    
    def shutdown(self):
        """Shutdown scheduler"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("🛑 Scheduler stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping scheduler: {e}")
    
    def get_all_jobs(self):
        """Get all scheduled jobs"""
        return self.scheduler.get_jobs()