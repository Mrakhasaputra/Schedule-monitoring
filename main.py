from flask import Flask, render_template
from database import engine, Base
from api.schedule import bp as schedule_bp
import atexit
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inisialisasi scheduler di sini, bukan di module level
def init_scheduler():
    """Initialize scheduler"""
    try:
        from scheduler import DynamicScheduler
        scheduler = DynamicScheduler()
        logger.info("Scheduler initialized")
        return scheduler
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")
        return None

def create_app():
    """Factory function untuk membuat Flask app"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    # Inisialisasi scheduler
    app.scheduler = init_scheduler()
    
    # Register blueprints
    app.register_blueprint(schedule_bp)
    
    # Create tables jika belum ada
    @app.before_first_request
    def create_tables():
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created/verified")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
    
    # Routes
    @app.route('/')
    def index():
        """Route untuk halaman utama"""
        return render_template('index.html')
    
    @app.route('/health')
    def health():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "scheduler": "running" if app.scheduler else "stopped"
        }
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return render_template('error.html', error="Page not found"), 404
    
    @app.errorhandler(500)
    def server_error(error):
        return render_template('error.html', error="Internal server error"), 500
    
    # Shutdown scheduler ketika app berhenti
    @atexit.register
    def shutdown_scheduler():
        if app.scheduler:
            app.scheduler.shutdown()
        logger.info("Application shutdown complete")
    
    return app

if __name__ == '__main__':
    import os
    app = create_app()
    
    # In development, create tables immediately
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    
    # Run the app
    app.run(
        debug=True,
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        use_reloader=False  # Penting untuk APScheduler
    )