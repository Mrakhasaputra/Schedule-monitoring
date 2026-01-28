from flask import Flask, jsonify
from database import engine, Base
from api.schedule import bp as schedule_bp
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key')
    
    # Initialize scheduler
    try:
        from scheduler import SchedulerManager
        app.scheduler = SchedulerManager()
        app.scheduler.start()
        logger.info("✅ Scheduler initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize scheduler: {e}")
        app.scheduler = None
    
    # Register blueprint
    app.register_blueprint(schedule_bp)
    
    # Health check
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'scheduler': 'running' if app.scheduler and app.scheduler.scheduler.running else 'stopped'
        })
    
    # Dashboard
    @app.route('/')
    def index():
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Scheduler Dashboard</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        </head>
        <body class="bg-gray-50">
            <div class="container mx-auto px-4 py-8">
                <h1 class="text-3xl font-bold mb-6">📅 Scheduler Dashboard</h1>
                <div id="app">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                        <div class="bg-white p-6 rounded-lg shadow">
                            <h2 class="text-lg font-semibold mb-4"><i class="fas fa-plus mr-2"></i>Tambah Schedule</h2>
                            <form id="scheduleForm" class="space-y-4">
                                <input type="text" name="name" placeholder="Nama Schedule" class="w-full p-2 border rounded" required>
                                <select name="schedule_type" class="w-full p-2 border rounded">
                                    <option value="daily">Harian</option>
                                    <option value="weekly">Mingguan</option>
                                    <option value="monthly">Bulanan</option>
                                </select>
                                <input type="time" name="run_time" class="w-full p-2 border rounded" value="00:00" required>
                                <button type="submit" class="w-full bg-blue-500 text-white p-2 rounded">Tambah</button>
                            </form>
                        </div>
                        
                        <div class="bg-white p-6 rounded-lg shadow">
                            <h2 class="text-lg font-semibold mb-4"><i class="fas fa-list mr-2"></i>Schedules</h2>
                            <div id="schedulesList" class="space-y-2">
                                Loading...
                            </div>
                        </div>
                        
                        <div class="bg-white p-6 rounded-lg shadow">
                            <h2 class="text-lg font-semibold mb-4"><i class="fas fa-history mr-2"></i>Logs</h2>
                            <div id="logsList" class="space-y-2 max-h-64 overflow-y-auto">
                                Loading...
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <script>
                async function loadSchedules() {
                    const res = await fetch('/api/schedules');
                    const data = await res.json();
                    
                    if (data.success) {
                        const html = data.schedules.map(s => `
                            <div class="border p-3 rounded">
                                <div class="flex justify-between">
                                    <strong>${s.name}</strong>
                                    <span class="text-sm ${s.is_active ? 'text-green-600' : 'text-gray-500'}">
                                        ${s.is_active ? 'Aktif' : 'Nonaktif'}
                                    </span>
                                </div>
                                <div class="text-sm text-gray-600">${s.display_schedule}</div>
                                <div class="flex space-x-2 mt-2">
                                    <button onclick="toggleSchedule(${s.id})" class="text-blue-600 text-sm">
                                        ${s.is_active ? 'Nonaktifkan' : 'Aktifkan'}
                                    </button>
                                    <button onclick="runNow(${s.id})" class="text-green-600 text-sm">Run Now</button>
                                    <button onclick="deleteSchedule(${s.id})" class="text-red-600 text-sm">Hapus</button>
                                </div>
                            </div>
                        `).join('');
                        document.getElementById('schedulesList').innerHTML = html || 'No schedules';
                    }
                }
                
                async function loadLogs() {
                    const res = await fetch('/api/schedules/logs');
                    const data = await res.json();
                    
                    if (data.success) {
                        const html = data.logs.map(log => `
                            <div class="border-l-4 ${log.status === 'success' ? 'border-green-500' : 'border-red-500'} pl-2 py-1">
                                <div class="text-sm">${log.message}</div>
                                <div class="text-xs text-gray-500">${new Date(log.executed_at).toLocaleString()}</div>
                            </div>
                        `).join('');
                        document.getElementById('logsList').innerHTML = html || 'No logs';
                    }
                }
                
                async function createSchedule(e) {
                    e.preventDefault();
                    const formData = new FormData(e.target);
                    const data = {
                        name: formData.get('name'),
                        schedule_type: formData.get('schedule_type'),
                        run_time: formData.get('run_time'),
                        is_active: true
                    };
                    
                    const res = await fetch('/api/schedules', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(data)
                    });
                    
                    const result = await res.json();
                    if (result.success) {
                        alert('Schedule created!');
                        e.target.reset();
                        loadSchedules();
                        loadLogs();
                    } else {
                        alert('Error: ' + result.error);
                    }
                }
                
                async function toggleSchedule(id) {
                    const res = await fetch(`/api/schedules/${id}/toggle`, {method: 'PATCH'});
                    const data = await res.json();
                    if (data.success) {
                        loadSchedules();
                    }
                }
                
                async function runNow(id) {
                    const res = await fetch(`/api/schedules/run-now/${id}`, {method: 'POST'});
                    const data = await res.json();
                    if (data.success) {
                        alert('Schedule executed!');
                        loadLogs();
                    }
                }
                
                async function deleteSchedule(id) {
                    if (confirm('Hapus schedule ini?')) {
                        const res = await fetch(`/api/schedules/${id}`, {method: 'DELETE'});
                        const data = await res.json();
                        if (data.success) {
                            loadSchedules();
                        }
                    }
                }
                
                // Event listeners
                document.getElementById('scheduleForm').addEventListener('submit', createSchedule);
                
                // Initial load
                loadSchedules();
                loadLogs();
                setInterval(loadLogs, 10000); // Refresh logs every 10 seconds
            </script>
        </body>
        </html>
        '''
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Create tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables verified")
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
    
    # Run app
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)