"""
Document model for storing hotel policy PDFs and other documents
"""

from app import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    category = db.Column(db.String(50))  # 'policy', 'menu', 'amenities', 'procedures'
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    content_text = db.Column(db.Text)  # Extracted text from PDF
    is_indexed = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    uploaded_by = db.Column(db.String(100))
    
    # Relationships
    chunks = db.relationship('DocumentChunk', backref='document', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Document {self.filename}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'category': self.category,
            'title': self.title,
            'description': self.description,
            'is_indexed': self.is_indexed,
            'is_active': self.is_active,
            'upload_date': self.upload_date.isoformat() if self.upload_date else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'uploaded_by': self.uploaded_by,
            'chunk_count': len(self.chunks)
        }

class DocumentChunk(db.Model):
    __tablename__ = 'document_chunks'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = db.Column(db.String(36), db.ForeignKey('documents.id'), nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    page_number = db.Column(db.Integer)
    start_char = db.Column(db.Integer)
    end_char = db.Column(db.Integer)
    embedding = db.Column(db.JSON)  # Store vector embeddings as JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DocumentChunk {self.document_id}:{self.chunk_index}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'document_id': self.document_id,
            'chunk_index': self.chunk_index,
            'content': self.content[:200] + '...' if len(self.content) > 200 else self.content,
            'page_number': self.page_number,
            'start_char': self.start_char,
            'end_char': self.end_char,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class GuestRequest(db.Model):
    __tablename__ = 'guest_requests'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = db.Column(db.String(36), db.ForeignKey('conversations.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    request_type = db.Column(db.String(50), nullable=False)  # 'room_service', 'housekeeping', 'maintenance', 'concierge', 'complaint'
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='medium')  # 'low', 'medium', 'high', 'urgent'
    status = db.Column(db.String(20), default='no')  # 'no', 'in_progress', 'yes', 'cancelled'
    room_number = db.Column(db.String(10))
    requested_time = db.Column(db.DateTime)
    completed_time = db.Column(db.DateTime)
    assigned_to = db.Column(db.String(100))
    notes = db.Column(db.Text)
    guest_rating = db.Column(db.Integer)  # 1-5 rating
    guest_feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<GuestRequest {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'user_id': self.user_id,
            'request_type': self.request_type,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'room_number': self.room_number,
            'requested_time': self.requested_time.isoformat() if self.requested_time else None,
            'completed_time': self.completed_time.isoformat() if self.completed_time else None,
            'assigned_to': self.assigned_to,
            'notes': self.notes,
            'guest_rating': self.guest_rating,
            'guest_feedback': self.guest_feedback,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @staticmethod
    def create_request(conversation_id, user_id, request_type, title, description, **kwargs):
        """Create a new guest request"""
        request = GuestRequest(
            conversation_id=conversation_id,
            user_id=user_id,
            request_type=request_type,
            title=title,
            description=description,
            **kwargs
        )
        db.session.add(request)
        db.session.commit()
        return request
