"""
Analytics model for tracking system performance and metrics
"""

from app import db
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Analytics(db.Model):
    __tablename__ = 'analytics'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_type = db.Column(db.String(50), nullable=False)  # conversation_count, response_time, satisfaction, etc.
    metric_value = db.Column(db.Float, nullable=False)
    channel = db.Column(db.String(20))  # web, voice, sms
    date = db.Column(db.Date, default=datetime.utcnow().date())
    hour = db.Column(db.Integer)  # 0-23 for hourly metrics
    analytics_metadata = db.Column(db.JSON)  # Additional context data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Analytics {self.metric_type}: {self.metric_value}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'metric_type': self.metric_type,
            'metric_value': self.metric_value,
            'channel': self.channel,
            'date': self.date.isoformat() if self.date else None,
            'hour': self.hour,
            'metadata': self.analytics_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def record_metric(metric_type, value, channel=None, metadata=None):
        now = datetime.utcnow()
        analytics = Analytics(
            metric_type=metric_type,
            metric_value=value,
            channel=channel,
            date=now.date(),
            hour=now.hour,
            analytics_metadata=metadata
        )
        db.session.add(analytics)
        db.session.commit()
        return analytics
    
    @staticmethod
    def get_daily_metrics(metric_type, days=7):
        from sqlalchemy import func
        return db.session.query(
            Analytics.date,
            func.avg(Analytics.metric_value).label('avg_value'),
            func.count(Analytics.id).label('count')
        ).filter(
            Analytics.metric_type == metric_type,
            Analytics.date >= datetime.utcnow().date() - timedelta(days=days)
        ).group_by(Analytics.date).all()
    
    @staticmethod
    def get_hourly_metrics(metric_type, date=None):
        from sqlalchemy import func
        if not date:
            date = datetime.utcnow().date()
        
        return db.session.query(
            Analytics.hour,
            func.avg(Analytics.metric_value).label('avg_value'),
            func.count(Analytics.id).label('count')
        ).filter(
            Analytics.metric_type == metric_type,
            Analytics.date == date
        ).group_by(Analytics.hour).all()
