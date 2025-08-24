"""
Message model for storing conversation messages
"""

from app import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = db.Column(db.String(36), db.ForeignKey('conversations.id'), nullable=False)
    sender_type = db.Column(db.String(20), nullable=False)  # user, ai, agent
    sender_id = db.Column(db.String(36))  # user_id or agent_id
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')  # text, image, audio, file
    message_metadata = db.Column(db.JSON)  # Additional data like file URLs, audio duration, etc.
    intent = db.Column(db.String(50))  # detected intent from AI
    confidence = db.Column(db.Float)  # AI confidence score
    processing_time = db.Column(db.Float)  # Response generation time
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Message {self.id} - {self.sender_type}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'sender_type': self.sender_type,
            'sender_id': self.sender_id,
            'content': self.content,
            'message_type': self.message_type,
            'metadata': self.message_metadata,
            'intent': self.intent,
            'confidence': self.confidence,
            'processing_time': self.processing_time,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def create_user_message(conversation_id, user_id, content, message_type='text', metadata=None):
        message = Message(
            conversation_id=conversation_id,
            sender_type='user',
            sender_id=user_id,
            content=content,
            message_type=message_type,
            message_metadata=metadata
        )
        db.session.add(message)
        db.session.commit()
        return message
    
    @staticmethod
    def create_ai_message(conversation_id, content, intent=None, confidence=None, processing_time=None, metadata=None):
        message = Message(
            conversation_id=conversation_id,
            sender_type='ai',
            content=content,
            intent=intent,
            confidence=confidence,
            processing_time=processing_time,
            message_metadata=metadata
        )
        db.session.add(message)
        db.session.commit()
        return message
