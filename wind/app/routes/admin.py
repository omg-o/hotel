"""
Admin dashboard routes
"""

from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.models.analytics import Analytics
from datetime import datetime, timedelta
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
def dashboard():
    """Admin dashboard main page"""
    return render_template('admin/dashboard.html')

@admin_bp.route('/conversations')
def conversations():
    """Conversations management page"""
    return render_template('admin/conversations.html')

@admin_bp.route('/analytics')
def analytics():
    """Analytics page"""
    return render_template('admin/analytics.html')

@admin_bp.route('/api/stats')
def get_stats():
    """Get real-time statistics for dashboard"""
    try:
        # Today's date
        today = datetime.utcnow().date()
        
        # Basic counts
        total_conversations = Conversation.query.count()
        active_conversations = Conversation.query.filter_by(status='active').count()
        total_users = User.query.count()
        total_messages = Message.query.count()
        
        # Today's metrics
        today_conversations = Conversation.query.filter(
            func.date(Conversation.created_at) == today
        ).count()
        
        today_resolved = Conversation.query.filter(
            func.date(Conversation.resolved_at) == today
        ).count()
        
        # Average response time (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        avg_response_time = db.session.query(
            func.avg(Message.processing_time)
        ).filter(
            Message.sender_type == 'ai',
            Message.created_at >= yesterday
        ).scalar() or 0
        
        # Satisfaction score
        avg_satisfaction = db.session.query(
            func.avg(Conversation.satisfaction_score)
        ).filter(
            Conversation.satisfaction_score.isnot(None)
        ).scalar() or 0
        
        return jsonify({
            'total_conversations': total_conversations,
            'active_conversations': active_conversations,
            'total_users': total_users,
            'total_messages': total_messages,
            'today_conversations': today_conversations,
            'today_resolved': today_resolved,
            'avg_response_time': round(avg_response_time, 2),
            'avg_satisfaction': round(avg_satisfaction, 1)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/charts/conversations')
def conversation_charts():
    """Get data for conversation charts"""
    try:
        # Last 7 days conversation data
        days = []
        conversation_data = []
        resolved_data = []
        
        for i in range(7):
            date = datetime.utcnow().date() - timedelta(days=i)
            days.append(date.strftime('%Y-%m-%d'))
            
            conv_count = Conversation.query.filter(
                func.date(Conversation.created_at) == date
            ).count()
            conversation_data.append(conv_count)
            
            resolved_count = Conversation.query.filter(
                func.date(Conversation.resolved_at) == date
            ).count()
            resolved_data.append(resolved_count)
        
        # Reverse to show chronological order
        days.reverse()
        conversation_data.reverse()
        resolved_data.reverse()
        
        # Channel distribution
        channel_data = db.session.query(
            Conversation.channel,
            func.count(Conversation.id)
        ).group_by(Conversation.channel).all()
        
        # Intent distribution
        intent_data = db.session.query(
            Conversation.category,
            func.count(Conversation.id)
        ).filter(
            Conversation.category.isnot(None)
        ).group_by(Conversation.category).all()
        
        return jsonify({
            'daily_conversations': {
                'labels': days,
                'datasets': [
                    {
                        'label': 'New Conversations',
                        'data': conversation_data,
                        'borderColor': 'rgb(75, 192, 192)',
                        'backgroundColor': 'rgba(75, 192, 192, 0.2)'
                    },
                    {
                        'label': 'Resolved Conversations',
                        'data': resolved_data,
                        'borderColor': 'rgb(54, 162, 235)',
                        'backgroundColor': 'rgba(54, 162, 235, 0.2)'
                    }
                ]
            },
            'channel_distribution': {
                'labels': [item[0] for item in channel_data],
                'datasets': [{
                    'data': [item[1] for item in channel_data],
                    'backgroundColor': [
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 205, 86, 0.8)'
                    ]
                }]
            },
            'intent_distribution': {
                'labels': [item[0] for item in intent_data],
                'datasets': [{
                    'data': [item[1] for item in intent_data],
                    'backgroundColor': [
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 205, 86, 0.8)',
                        'rgba(75, 192, 192, 0.8)',
                        'rgba(153, 102, 255, 0.8)'
                    ]
                }]
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
