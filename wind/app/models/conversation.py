"""
Conversation model for tracking customer interactions
"""

from app import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    channel = db.Column(db.String(20), nullable=False)  # web, voice, sms
    status = db.Column(db.String(20), default='active')  # active, resolved, escalated
    priority = db.Column(db.String(10), default='normal')  # low, normal, high, urgent
    category = db.Column(db.String(50))  # booking, complaint, inquiry, etc.
    sentiment = db.Column(db.String(20))  # positive, neutral, negative
    satisfaction_score = db.Column(db.Integer)  # 1-5 rating
    agent_id = db.Column(db.String(36))  # human agent if escalated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    
    # Relationships
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Conversation {self.id} - {self.channel}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'channel': self.channel,
            'status': self.status,
            'priority': self.priority,
            'category': self.category,
            'sentiment': self.sentiment,
            'satisfaction_score': self.satisfaction_score,
            'agent_id': self.agent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'message_count': len(self.messages)
        }
    
    def get_last_message(self):
        return self.messages[-1] if self.messages else None
    
    def resolve(self, satisfaction_score=None):
        self.status = 'resolved'
        self.resolved_at = datetime.utcnow()
        if satisfaction_score:
            self.satisfaction_score = satisfaction_score
        db.session.commit()
    
    def escalate(self, agent_id):
        self.status = 'escalated'
        self.agent_id = agent_id
        self.priority = 'high'
        db.session.commit()
