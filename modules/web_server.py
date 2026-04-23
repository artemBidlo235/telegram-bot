# ВЕБ-СЕРВЕР - ПОЛНАЯ ВЕРСИЯ
from threading import Thread
from flask import Flask, jsonify

class WebServer:
    def __init__(self, data_manager, host='0.0.0.0', port=8080):
        self.data_manager = data_manager
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.route('/')
        def index():
            users = self.data_manager.load_users()
            admins = self.data_manager.load_admins()
            stats = self.data_manager.get_stats()
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Telegram Бот Рассыльщик</title>
                <meta charset="UTF-8">
                <meta http-equiv="refresh" content="30">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
                    .container {{ background: rgba(255,255,255,0.1); border-radius: 20px; padding: 30px; max-width: 600px; margin: 0 auto; backdrop-filter: blur(10px); }}
                    .status {{ color: #4ade80; font-size: 24px; }}
                    .stat-number {{ font-size: 36px; font-weight: bold; color: #fbbf24; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🤖 Telegram Бот Рассыльщик</h1>
                    <div class="status">✅ Бот работает!</div>
                    <p>👥 Пользователей: <span class="stat-number">{len(users)}</span></p>
                    <p>👑 Администраторов: <span class="stat-number">{len(admins)}</span></p>
                    <p>📨 Отправлено: <span class="stat-number">{stats.get('messages_sent', 0)}</span></p>
                    <p>📢 Рассылок: <span class="stat-number">{stats.get('broadcasts', 0)}</span></p>
                </div>
            </body>
            </html>
            """
        
        @self.app.route('/api/users')
        def api_users():
            return jsonify(self.data_manager.load_users())
        
        @self.app.route('/api/admins')
        def api_admins():
            return jsonify(self.data_manager.load_admins())
        
        @self.app.route('/api/stats')
        def api_stats():
            stats = self.data_manager.get_stats()
            stats['total_users'] = len(self.data_manager.load_users())
            stats['total_admins'] = len(self.data_manager.load_admins())
            return jsonify(stats)
    
    def run(self):
        print(f"🌐 Веб-сервер запущен на http://{self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
    
    def start_in_thread(self):
        thread = Thread(target=self.run, daemon=True)
        thread.start()
        return thread