from flask import Blueprint, request, jsonify
from datetime import time, datetime, timedelta
from models import Schedule, JobLog, MediaChannel
from database import get_db
from sqlalchemy.orm import Session
import logging
import pytz
from sqlalchemy import func, and_

logger = logging.getLogger(__name__)
bp = Blueprint('schedule', __name__, url_prefix='/api/schedules')

# Helper functions
def schedule_to_dict(schedule):
    """Convert schedule object to dictionary"""
    try:
        data = {
            'id': schedule.id,
            'name': schedule.name,
            'schedule_type': schedule.schedule_type,
            'run_time': schedule.run_time.strftime('%H:%M') if schedule.run_time else '00:00',
            'day_of_week': schedule.day_of_week,
            'day_of_month': schedule.day_of_month,
            'is_active': schedule.is_active if hasattr(schedule, 'is_active') else True,
            'media_channel_id': schedule.media_channel_id,
            'display_schedule': getattr(schedule, 'display_schedule', 'Unknown schedule'),
            'created_at': schedule.created_at.isoformat() if schedule.created_at else None
        }
        
        # Add optional fields if they exist
        if hasattr(schedule, 'last_executed'):
            data['last_executed'] = schedule.last_executed.isoformat() if schedule.last_executed else None
        if hasattr(schedule, 'execution_count'):
            data['execution_count'] = schedule.execution_count or 0
        if hasattr(schedule, 'updated_at'):
            data['updated_at'] = schedule.updated_at.isoformat() if schedule.updated_at else None
            
        return data
    except Exception as e:
        logger.error(f"Error converting schedule to dict: {e}")
        return {
            'id': getattr(schedule, 'id', 0),
            'name': getattr(schedule, 'name', 'Unknown'),
            'schedule_type': getattr(schedule, 'schedule_type', 'daily'),
            'run_time': '00:00',
            'is_active': getattr(schedule, 'is_active', False),
            'display_schedule': 'Error loading schedule'
        }

def get_jakarta_time():
    """Get current time in Jakarta timezone"""
    return datetime.now(pytz.timezone('Asia/Jakarta'))

@bp.route('', methods=['GET'])
def get_schedules():
    """Get all schedules"""
    db: Session = None
    try:
        db = next(get_db())
        
        logger.info("Fetching all schedules from database")
        schedules = db.query(Schedule).order_by(Schedule.created_at.desc()).all()
        logger.info(f"Found {len(schedules)} schedules")
        
        result = []
        for schedule in schedules:
            schedule_data = schedule_to_dict(schedule)
            
            # Get recent logs (limit to 5)
            try:
                logs = db.query(JobLog).filter(
                    JobLog.schedule_id == schedule.id
                ).order_by(JobLog.executed_at.desc()).limit(5).all()
                
                schedule_data['recent_logs'] = [
                    {
                        'id': log.id,
                        'status': log.status,
                        'message': log.message,
                        'executed_at': log.executed_at.astimezone(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S') if log.executed_at else None
                    }
                    for log in logs
                ]
            except Exception as e:
                logger.warning(f"Error getting logs for schedule {schedule.id}: {e}")
                schedule_data['recent_logs'] = []
            
            # Get media channel info if exists
            if schedule.media_channel_id:
                try:
                    media = db.query(MediaChannel).filter(
                        MediaChannel.id == schedule.media_channel_id
                    ).first()
                    if media:
                        schedule_data['media_channel'] = {
                            'id': media.id,
                            'platform': media.platform or '',
                            'platform_name': media.platform_name or '',
                            'link': media.link or '',
                            'ads_type': media.ads_type or ''
                        }
                except Exception as e:
                    logger.warning(f"Error getting media channel {schedule.media_channel_id}: {e}")
            
            result.append(schedule_data)
        
        logger.info(f"Returning {len(result)} schedules")
        return jsonify({
            'success': True,
            'count': len(result),
            'schedules': result
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting schedules: {e}", exc_info=True)
        return jsonify({
            'success': False, 
            'error': str(e),
            'message': 'Failed to load schedules'
        }), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@bp.route('', methods=['POST'])
def create_schedule():
    """Create new schedule"""
    db: Session = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        logger.info(f"Creating new schedule with data: {data}")
        
        # Validate required fields
        required = ['name', 'schedule_type', 'run_time']
        missing_fields = [field for field in required if field not in data]
        if missing_fields:
            return jsonify({'success': False, 'error': f'Missing fields: {", ".join(missing_fields)}'}), 400
        
        db = next(get_db())
        
        # Parse time
        try:
            time_str = data['run_time']
            if ':' in time_str:
                hour, minute = map(int, time_str.split(':'))
            else:
                hour, minute = 0, 0
            run_time = time(hour=hour, minute=minute)
        except Exception as e:
            logger.error(f"Error parsing time {data['run_time']}: {e}")
            return jsonify({'success': False, 'error': f'Invalid time format: {data["run_time"]}. Use HH:MM'}), 400
        
        # Create schedule object
        schedule = Schedule(
            name=data['name'].strip(),
            schedule_type=data['schedule_type'],
            run_time=run_time,
            day_of_week=data.get('day_of_week'),
            day_of_month=data.get('day_of_month'),
            is_active=data.get('is_active', True),
            media_channel_id=data.get('media_channel_id')
        )
        
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        
        logger.info(f"Schedule created with ID: {schedule.id}")
        
        # Try to add to scheduler
        try:
            from flask import current_app
            if hasattr(current_app, 'scheduler') and current_app.scheduler:
                current_app.scheduler.add_schedule(schedule)
                logger.info(f"Schedule {schedule.id} added to scheduler")
        except Exception as e:
            logger.warning(f"Could not add schedule to scheduler: {e}")
        
        # Create initial log
        current_time = get_jakarta_time()
        log = JobLog(
            schedule_id=schedule.id,
            status="success",
            message=f"Schedule '{schedule.name}' created at {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        db.add(log)
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Schedule created successfully',
            'schedule': schedule_to_dict(schedule)
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating schedule: {e}", exc_info=True)
        if db:
            db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@bp.route('/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    """Delete schedule"""
    db: Session = None
    try:
        db = next(get_db())
        
        logger.info(f"Attempting to delete schedule {schedule_id}")
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            return jsonify({'success': False, 'error': f'Schedule with ID {schedule_id} not found'}), 404
        
        # Remove from scheduler if possible
        try:
            from flask import current_app
            if hasattr(current_app, 'scheduler'):
                current_app.scheduler.remove_schedule(schedule_id)
        except Exception as e:
            logger.warning(f"Could not remove schedule from scheduler: {e}")
        
        # Delete from database
        db.delete(schedule)
        db.commit()
        
        logger.info(f"Schedule {schedule_id} deleted successfully")
        return jsonify({
            'success': True,
            'message': f'Schedule "{schedule.name}" deleted'
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting schedule {schedule_id}: {e}", exc_info=True)
        if db:
            db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@bp.route('/<int:schedule_id>/toggle', methods=['PATCH'])
def toggle_schedule(schedule_id):
    """Toggle schedule active status"""
    db: Session = None
    try:
        db = next(get_db())
        
        logger.info(f"Toggling schedule {schedule_id}")
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            return jsonify({'success': False, 'error': 'Schedule not found'}), 404
        
        # Toggle status
        new_status = not schedule.is_active
        schedule.is_active = new_status
        db.commit()
        
        logger.info(f"Schedule {schedule_id} status changed to {'active' if new_status else 'inactive'}")
        
        # Update scheduler
        try:
            from flask import current_app
            if hasattr(current_app, 'scheduler'):
                if new_status:
                    current_app.scheduler.add_schedule(schedule)
                    logger.info(f"Schedule {schedule_id} added to scheduler")
                else:
                    current_app.scheduler.remove_schedule(schedule_id)
                    logger.info(f"Schedule {schedule_id} removed from scheduler")
        except Exception as e:
            logger.warning(f"Could not update scheduler: {e}")
        
        # Log the change
        log = JobLog(
            schedule_id=schedule_id,
            status="success",
            message=f"Schedule {'activated' if new_status else 'deactivated'}"
        )
        db.add(log)
        db.commit()
        
        return jsonify({
            'success': True,
            'message': f"Schedule {'activated' if new_status else 'deactivated'}",
            'is_active': new_status
        }), 200
        
    except Exception as e:
        logger.error(f"Error toggling schedule {schedule_id}: {e}", exc_info=True)
        if db:
            db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@bp.route('/media-channels', methods=['GET'])
def get_media_channels():
    """Get all media channels"""
    db: Session = None
    try:
        db = next(get_db())
        
        logger.info("Fetching media channels")
        channels = db.query(MediaChannel).order_by(MediaChannel.created_at.desc()).all()
        
        result = []
        for mc in channels:
            channel_data = {
                'id': mc.id,
                'platform': mc.platform or '',
                'platform_name': mc.platform_name or '',
                'link': mc.link or '',
                'ads_type': mc.ads_type or '',
                'max_posts': mc.max_posts if mc.max_posts is not None else 10,
                'created_at': mc.created_at.isoformat() if mc.created_at else None
            }
            
            # Add display_info if property exists
            if hasattr(mc, 'display_info'):
                try:
                    channel_data['display_info'] = mc.display_info
                except:
                    channel_data['display_info'] = f"{channel_data['platform_name']} - {channel_data['ads_type']}"
            else:
                channel_data['display_info'] = f"{channel_data['platform_name']} - {channel_data['ads_type']}"
            
            result.append(channel_data)
        
        logger.info(f"Returning {len(result)} media channels")
        return jsonify({
            'success': True,
            'count': len(result),
            'media_channels': result
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting media channels: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@bp.route('/run-now/<int:schedule_id>', methods=['POST'])
def run_schedule_now(schedule_id):
    """Run schedule immediately"""
    db: Session = None
    try:
        db = next(get_db())
        
        logger.info(f"Running schedule {schedule_id} now")
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            return jsonify({'success': False, 'error': 'Schedule not found'}), 404
        
        # Import and execute task
        try:
            from scheduler import execute_task
            execute_task(schedule.id, schedule.name, schedule.media_channel_id)
            
            logger.info(f"Schedule {schedule_id} executed successfully")
            return jsonify({
                'success': True,
                'message': f"Schedule '{schedule.name}' executed"
            }), 200
        except Exception as e:
            logger.error(f"Error executing schedule {schedule_id}: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f'Execution failed: {str(e)}'}), 500
        
    except Exception as e:
        logger.error(f"Error running schedule {schedule_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@bp.route('/logs', methods=['GET'])
def get_logs():
    """Get all logs"""
    db: Session = None
    try:
        db = next(get_db())
        
        logger.info("Fetching job logs")
        logs = db.query(JobLog).order_by(JobLog.executed_at.desc()).limit(100).all()
        
        result = []
        for log in logs:
            try:
                executed_at = log.executed_at
                if executed_at:
                    # Ensure timezone aware
                    if executed_at.tzinfo is None:
                        executed_at = pytz.utc.localize(executed_at)
                    executed_at_str = executed_at.astimezone(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    executed_at_str = None
                    
                result.append({
                    'id': log.id,
                    'schedule_id': log.schedule_id,
                    'status': log.status,
                    'message': log.message or '',
                    'executed_at': executed_at_str
                })
            except Exception as e:
                logger.warning(f"Error processing log {log.id}: {e}")
                continue
        
        logger.info(f"Returning {len(result)} logs")
        return jsonify({
            'success': True,
            'count': len(result),
            'logs': result
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@bp.route('/<int:schedule_id>/logs', methods=['GET'])
def get_schedule_logs(schedule_id):
    """Get logs for specific schedule"""
    db: Session = None
    try:
        db = next(get_db())
        
        # Check if schedule exists
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            return jsonify({'success': False, 'error': 'Schedule not found'}), 404
        
        logger.info(f"Fetching logs for schedule {schedule_id}")
        logs = db.query(JobLog).filter(
            JobLog.schedule_id == schedule_id
        ).order_by(JobLog.executed_at.desc()).limit(50).all()
        
        result = []
        for log in logs:
            try:
                executed_at = log.executed_at
                if executed_at:
                    if executed_at.tzinfo is None:
                        executed_at = pytz.utc.localize(executed_at)
                    executed_at_str = executed_at.astimezone(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    executed_at_str = None
                    
                result.append({
                    'id': log.id,
                    'status': log.status,
                    'message': log.message or '',
                    'executed_at': executed_at_str
                })
            except Exception as e:
                logger.warning(f"Error processing log {log.id}: {e}")
                continue
        
        logger.info(f"Returning {len(result)} logs for schedule {schedule_id}")
        return jsonify({
            'success': True,
            'schedule_id': schedule_id,
            'schedule_name': schedule.name,
            'count': len(result),
            'logs': result
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting schedule logs for {schedule_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@bp.route('/midnight-check', methods=['GET'])
def check_midnight_schedules():
    """Check status of midnight schedules"""
    db: Session = None
    try:
        db = next(get_db())
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        current_time = datetime.now(jakarta_tz)
        
        logger.info("Checking midnight schedules")
        
        # Get midnight schedules - multiple ways to filter
        midnight_schedules = []
        
        # Method 1: Compare time string
        try:
            schedules = db.query(Schedule).all()
            for schedule in schedules:
                try:
                    run_time_str = schedule.run_time.strftime('%H:%M:%S') if schedule.run_time else '00:00:00'
                    if run_time_str == '00:00:00':
                        midnight_schedules.append(schedule)
                except:
                    continue
        except Exception as e:
            logger.warning(f"Error in time comparison method: {e}")
        
        # If no schedules found with method 1, try method 2
        if not midnight_schedules:
            try:
                # Using SQL function for PostgreSQL
                midnight_schedules = db.query(Schedule).filter(
                    func.to_char(Schedule.run_time, 'HH24:MI:SS') == '00:00:00'
                ).all()
            except:
                # Fallback to simple filter
                midnight_schedules = db.query(Schedule).filter(
                    Schedule.run_time == '00:00'
                ).all()
        
        logger.info(f"Found {len(midnight_schedules)} midnight schedules")
        
        result = []
        for schedule in midnight_schedules:
            try:
                # Check recent executions (last 24 hours)
                yesterday = current_time - timedelta(days=1)
                yesterday_utc = yesterday.astimezone(pytz.utc)
                
                recent_logs = db.query(JobLog).filter(
                    JobLog.schedule_id == schedule.id,
                    JobLog.executed_at >= yesterday_utc
                ).order_by(JobLog.executed_at.desc()).all()
                
                # Check if should have run today
                should_have_run = False
                if schedule.is_active and schedule.schedule_type == "daily":
                    # For daily schedules, should run every day
                    today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                    today_start_utc = today_start.astimezone(pytz.utc)
                    
                    # Count logs from today
                    today_logs = db.query(JobLog).filter(
                        JobLog.schedule_id == schedule.id,
                        JobLog.executed_at >= today_start_utc
                    ).count()
                    
                    should_have_run = today_logs == 0 and current_time.hour > 0
                
                last_execution = None
                if recent_logs and recent_logs[0].executed_at:
                    last_exec = recent_logs[0].executed_at
                    if last_exec.tzinfo is None:
                        last_exec = pytz.utc.localize(last_exec)
                    last_execution = last_exec.astimezone(jakarta_tz).strftime('%Y-%m-%d %H:%M:%S')
                
                result.append({
                    'id': schedule.id,
                    'name': schedule.name,
                    'is_active': schedule.is_active,
                    'schedule_type': schedule.schedule_type,
                    'run_time': schedule.run_time.strftime('%H:%M:%S') if schedule.run_time else '00:00:00',
                    'recent_executions': len(recent_logs),
                    'last_execution': last_execution,
                    'should_have_run_today': should_have_run,
                    'status': 'ok' if not should_have_run else 'missed'
                })
            except Exception as e:
                logger.warning(f"Error processing schedule {schedule.id}: {e}")
                continue
        
        logger.info(f"Returning midnight check results: {len(result)} schedules")
        return jsonify({
            'success': True,
            'current_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'timezone': 'Asia/Jakarta',
            'midnight_schedules': result,
            'total': len(result),
            'active': len([s for s in result if s.get('is_active', False)]),
            'missed': len([s for s in result if s.get('should_have_run_today', False)])
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking midnight schedules: {e}", exc_info=True)
        return jsonify({
            'success': False, 
            'error': str(e),
            'message': 'Failed to check midnight schedules'
        }), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@bp.route('/midnight/force-run', methods=['POST'])
def force_run_midnight():
    """Force run all active midnight schedules"""
    db: Session = None
    try:
        data = request.get_json() or {}
        single_schedule_id = data.get('schedule_id')
        
        db = next(get_db())
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        current_time = datetime.now(jakarta_tz)
        
        if single_schedule_id:
            # Run single schedule
            logger.info(f"Force running single midnight schedule {single_schedule_id}")
            schedule = db.query(Schedule).filter(
                Schedule.id == single_schedule_id,
                Schedule.is_active == True
            ).first()
            
            if not schedule:
                return jsonify({
                    'success': False,
                    'error': f'Schedule {single_schedule_id} not found or not active'
                }), 404
            
            schedules = [schedule]
        else:
            # Get active midnight schedules
            logger.info("Force running all active midnight schedules")
            
            # Find midnight schedules by checking time
            all_schedules = db.query(Schedule).filter(
                Schedule.is_active == True
            ).all()
            
            schedules = []
            for s in all_schedules:
                try:
                    run_time_str = s.run_time.strftime('%H:%M:%S') if s.run_time else '00:00:00'
                    if run_time_str == '00:00:00':
                        schedules.append(s)
                except:
                    continue
        
        if not schedules:
            return jsonify({
                'success': True,
                'message': 'No active midnight schedules found to run',
                'executed': 0
            }), 200
        
        results = []
        from scheduler import execute_task
        
        for schedule in schedules:
            try:
                logger.info(f"Executing schedule {schedule.id}: {schedule.name}")
                execute_task(schedule.id, schedule.name, schedule.media_channel_id)
                
                results.append({
                    'id': schedule.id,
                    'name': schedule.name,
                    'status': 'success',
                    'message': f'Executed at {current_time.strftime("%H:%M:%S")}'
                })
            except Exception as e:
                logger.error(f"Error executing schedule {schedule.id}: {e}")
                results.append({
                    'id': schedule.id,
                    'name': schedule.name,
                    'status': 'error',
                    'message': str(e)
                })
        
        logger.info(f"Force run completed: {len([r for r in results if r['status'] == 'success'])} successful")
        return jsonify({
            'success': True,
            'message': f'Executed {len([r for r in results if r["status"] == "success"])} midnight schedule(s)',
            'total': len(schedules),
            'successful': len([r for r in results if r['status'] == 'success']),
            'failed': len([r for r in results if r['status'] == 'error']),
            'results': results
        }), 200
        
    except Exception as e:
        logger.error(f"Error forcing midnight schedules: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@bp.route('/test-scraping', methods=['POST'])
def test_scraping():
    """Test scraping for a media channel"""
    db: Session = None
    try:
        data = request.get_json()
        if not data or 'media_channel_id' not in data:
            return jsonify({'success': False, 'error': 'Media channel ID required'}), 400
        
        media_channel_id = data['media_channel_id']
        
        db = next(get_db())
        
        media_channel = db.query(MediaChannel).filter(
            MediaChannel.id == media_channel_id
        ).first()
        
        if not media_channel:
            return jsonify({'success': False, 'error': 'Media channel not found'}), 404
        
        # Create test log
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        current_time = datetime.now(jakarta_tz)
        
        log = JobLog(
            schedule_id=None,
            status="test",
            message=f"Test scraping for {media_channel.platform_name or media_channel.platform} at {current_time.strftime('%H:%M:%S')}"
        )
        db.add(log)
        db.commit()
        
        logger.info(f"Test scraping initiated for media channel {media_channel_id}")
        return jsonify({
            'success': True,
            'message': f"Test scraping initiated for {media_channel.platform_name or media_channel.platform}",
            'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
        }), 200
        
    except Exception as e:
        logger.error(f"Error testing scraping: {e}", exc_info=True)
        if db:
            db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for schedules API"""
    db: Session = None
    try:
        db = next(get_db())
        
        # Test database connection
        schedule_count = db.query(Schedule).count()
        log_count = db.query(JobLog).count()
        media_count = db.query(MediaChannel).count()
        
        # Check midnight schedules
        midnight_count = 0
        try:
            schedules = db.query(Schedule).all()
            for schedule in schedules:
                try:
                    if schedule.run_time and schedule.run_time.strftime('%H:%M:%S') == '00:00:00':
                        midnight_count += 1
                except:
                    continue
        except:
            pass
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'database': 'connected',
            'stats': {
                'schedules': schedule_count,
                'logs': log_count,
                'media_channels': media_count,
                'midnight_schedules': midnight_count
            },
            'timestamp': datetime.now(pytz.timezone('Asia/Jakarta')).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        }), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass

@bp.route('/debug', methods=['GET'])
def debug_info():
    """Debug information endpoint"""
    try:
        from flask import current_app
        
        scheduler_status = "unknown"
        if hasattr(current_app, 'scheduler') and current_app.scheduler:
            scheduler = current_app.scheduler.scheduler
            scheduler_status = {
                'running': scheduler.running,
                'job_count': len(scheduler.get_jobs()),
                'timezone': str(scheduler.timezone)
            }
        
        return jsonify({
            'success': True,
            'endpoints': {
                'GET /': 'Get all schedules',
                'POST /': 'Create schedule',
                'GET /logs': 'Get all logs',
                'GET /midnight-check': 'Check midnight schedules',
                'POST /midnight/force-run': 'Force run midnight schedules',
                'GET /media-channels': 'Get media channels',
                'GET /health': 'Health check'
            },
            'scheduler': scheduler_status,
            'timezone': 'Asia/Jakarta',
            'current_time': datetime.now(pytz.timezone('Asia/Jakarta')).isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500