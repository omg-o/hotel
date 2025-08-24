"""
Multi-Channel AI Customer Service System for Hotels
Flask application factory and configuration
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_socketio import SocketIO
from celery import Celery
import redis
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
socketio = SocketIO(cors_allowed_origins="*")
try:
    redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
    # Test connection
    redis_client.ping()
except:
    # Fallback: Use a mock Redis client
    class MockRedis:
        def setex(self, key, time, value): pass
        def get(self, key): return None
        def delete(self, key): pass
        def ping(self): return True
    redis_client = MockRedis()

def make_celery(app):
    """Create Celery instance for background tasks"""
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

def create_app(config_name='development'):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///hotel_service.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['CELERY_BROKER_URL'] = os.getenv('REDIS_URL') or os.getenv('CELERY_BROKER_URL', 'memory://')
    app.config['CELERY_RESULT_BACKEND'] = os.getenv('REDIS_URL') or os.getenv('CELERY_RESULT_BACKEND', 'cache+memory://')
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, async_mode='eventlet')
    
    # Register blueprints
    from app.routes.chat import chat_bp
    from app.routes.voice import voice_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.documents import documents_bp
    
    app.register_blueprint(chat_bp)
    app.register_blueprint(voice_bp, url_prefix='/voice')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(documents_bp)
    
    # Import models to ensure they're registered
    from app.models import conversation, message, user, analytics, document
    
    # Socket.IO events
    from app.services.socket_handlers import register_socket_handlers
    register_socket_handlers(socketio)
    
    return app

# Create Celery instance
celery = make_celery(create_app())
