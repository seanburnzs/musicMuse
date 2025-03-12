from celery import Celery
import os
from dotenv import load_dotenv
from celery.schedules import crontab

# Load environment variables
load_dotenv()

# Create Celery app
celery_app = Celery(
    'musicmuse',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour task timeout
    worker_max_tasks_per_child=200,  # Restart worker after 200 tasks
    task_routes={
        'tasks.data_import.*': {'queue': 'data_import'},
        'tasks.analytics.*': {'queue': 'analytics'},
    }
)

# Celery Beat schedule
celery_app.conf.beat_schedule = {
    'refresh-analytics-views-daily': {
        'task': 'tasks.scheduled_tasks.refresh_analytics_views',
        'schedule': crontab(hour=3, minute=0),  # Run at 3:00 AM every day
    },
    'clean-old-sessions-weekly': {
        'task': 'tasks.scheduled_tasks.clean_old_sessions',
        'schedule': crontab(day_of_week=0, hour=2, minute=0),  # Run at 2:00 AM every Sunday
    },
}