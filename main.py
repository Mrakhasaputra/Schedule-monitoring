from flask import Flask, render_template, jsonify, request
from database import engine, Base
import atexit
import logging
import os
from datetime import datetime
import threading
import time
from dotenv import load_dotenv
import pytz
import traceback

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def init_scheduler(app):
    """Initialize scheduler dengan Flask context"""
    try:
        from scheduler import SchedulerManager
        scheduler = SchedulerManager()
        
        if scheduler.start():
            app.scheduler = scheduler
            logger.info("✅ Scheduler initialized and started")
            
            # Schedule startup message
            jakarta_tz = pytz.timezone('Asia/Jakarta')
            current_time = datetime.now(jakarta_tz).strftime("%Y-%m-%d %H:%M:%S %Z")
            
            print(f"\n{'='*70}")
            print(f"🚀 SCHEDULER SYSTEM STARTED")
            print(f"{'='*70}")
            print(f"⏰ Server Time: {current_time}")
            print(f"📍 Timezone: Asia/Jakarta")
            print(f"🌐 API Endpoint: http://127.0.0.1:5000")
            print(f"📊 Dashboard: http://127.0.0.1:5000/dashboard")
            print(f"{'='*70}\n")
            
            return scheduler
        else:
            logger.error("❌ Failed to start scheduler")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize scheduler: {e}")
        logger.error(traceback.format_exc())
        return None

def create_app():
    """Factory function untuk membuat Flask app"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    app.config['TIMEZONE'] = 'Asia/Jakarta'
    
    # IMPORT BLUEPRINT HERE - AFTER APP CREATION
    from api.schedule import bp as schedule_bp
    app.register_blueprint(schedule_bp)
    
    # Initialize scheduler
    with app.app_context():
        app.scheduler = init_scheduler(app)
    
    # Routes
    @app.route('/')
    def index():
        """Route untuk halaman utama"""
        return render_template('index.html') if os.path.exists('templates/index.html') else get_default_dashboard()
    
    @app.route('/health')
    def health():
        """Health check endpoint"""
        try:
            from database import SessionLocal
            from sqlalchemy import text
            
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        # Check scheduler status
        scheduler_status = {
            "running": hasattr(app, 'scheduler') and app.scheduler and app.scheduler.scheduler.running,
            "jobs_count": len(app.scheduler.scheduler.get_jobs()) if hasattr(app, 'scheduler') and app.scheduler else 0,
            "timezone": str(app.scheduler.scheduler.timezone) if hasattr(app, 'scheduler') and app.scheduler else "unknown"
        }
        
        return jsonify({
            "status": "healthy",
            "scheduler": scheduler_status,
            "database": db_status,
            "timestamp": datetime.now(pytz.timezone('Asia/Jakarta')).isoformat(),
            "server_timezone": "Asia/Jakarta"
        })
    
    @app.route('/debug/imports')
    def debug_imports():
        """Debug import issues"""
        try:
            from models import Schedule, JobLog, MediaChannel
            from scheduler import SchedulerManager, execute_task
            
            return jsonify({
                'success': True,
                'imports': {
                    'models': ['Schedule', 'JobLog', 'MediaChannel'],
                    'scheduler': ['SchedulerManager', 'execute_task']
                }
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 500
    
    @app.errorhandler(500)
    def handle_500(error):
        """Handle 500 errors"""
        logger.error(f"500 Error: {error}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': str(error),
            'traceback': traceback.format_exc() if app.debug else None
        }), 500
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Global exception handler"""
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            "success": False,
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc() if app.debug else None
        }), 500
    
    # Shutdown scheduler on exit
    @atexit.register
    def shutdown_scheduler():
        if hasattr(app, 'scheduler') and app.scheduler:
            app.scheduler.shutdown()
        logger.info("Application shutdown complete")
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Create tables jika belum ada
    try:
        with app.app_context():
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Database tables verified")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        logger.error(traceback.format_exc())
    
    # Run the app
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting server on port {port}")
    
    app.run(
        debug=True,
        host='0.0.0.0',
        port=port,
        use_reloader=False  # Important: Disable reloader for scheduler
    )