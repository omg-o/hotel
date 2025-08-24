"""
API routes for the customer service system
"""

from flask import Blueprint, request, jsonify, session
from app import db, redis_client
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.analytics import Analytics
from app.services.ai_service import HotelAIService
import uuid
import json
from datetime import datetime

api_bp = Blueprint('api', __name__)
ai_service = HotelAIService()

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Docker and load balancers"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        
        # Check Redis connection
        redis_client.ping()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'database': 'ok',
                'redis': 'ok'
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }), 503

@api_bp.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages from web interface"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id') or session.get('session_id')
        user_context = data.get('user_context', {})
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Create or get session
        if not session_id:
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
        
        # Get or create user
        user = User.query.filter_by(session_id=session_id).first()
        if not user:
            user = User(
                session_id=session_id,
                name=user_context.get('name'),
                email=user_context.get('email'),
                phone=user_context.get('phone'),
                room_number=user_context.get('room_number'),
                guest_type=user_context.get('guest_type', 'guest')
            )
            db.session.add(user)
            db.session.commit()
        else:
            user.update_last_active()
        
        # Get or create conversation
        conversation = Conversation.query.filter_by(
            user_id=user.id,
            status='active'
        ).first()
        
        if not conversation:
            conversation = Conversation(
                user_id=user.id,
                channel='web'
            )
            db.session.add(conversation)
            db.session.commit()
        
        # Save user message
        user_msg = Message.create_user_message(
            conversation.id,
            user.id,
            user_message
        )
        
        # Generate AI response
        ai_response = ai_service.generate_response(
            user_message,
            conversation.id,
            user_context
        )
        
        # Save AI message
        ai_msg = Message.create_ai_message(
            conversation.id,
            ai_response['response'],
            intent=ai_response.get('intent'),
            confidence=ai_response.get('confidence'),
            processing_time=ai_response.get('processing_time')
        )
        
        # Update conversation metadata
        conversation.category = ai_response.get('intent')
        conversation.sentiment = ai_response.get('sentiment')
        if ai_response.get('escalate'):
            conversation.priority = 'high'
        
        db.session.commit()
        
        # Cache conversation in Redis
        redis_client.setex(
            f"conversation:{session_id}",
            3600,  # 1 hour TTL
            json.dumps({
                'conversation_id': conversation.id,
                'user_id': user.id,
                'last_message': ai_response['response']
            })
        )
        
        return jsonify({
            'response': ai_response['response'],
            'session_id': session_id,
            'conversation_id': conversation.id,
            'intent': ai_response.get('intent'),
            'sentiment': ai_response.get('sentiment'),
            'escalate': ai_response.get('escalate', False),
            'suggested_responses': ai_service.get_suggested_responses(ai_response.get('intent', 'inquiry'))
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/conversations', methods=['GET'])
def get_conversations():
    """Get conversation history for admin dashboard"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        channel = request.args.get('channel')
        
        query = Conversation.query
        
        if status:
            query = query.filter_by(status=status)
        if channel:
            query = query.filter_by(channel=channel)
        
        conversations = query.order_by(Conversation.created_at.desc())\
                           .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'conversations': [conv.to_dict() for conv in conversations.items],
            'total': conversations.total,
            'pages': conversations.pages,
            'current_page': page
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/conversations/<conversation_id>/messages', methods=['GET'])
def get_conversation_messages(conversation_id):
    """Get messages for a specific conversation"""
    try:
        messages = Message.query.filter_by(conversation_id=conversation_id)\
                               .order_by(Message.created_at.asc()).all()
        
        return jsonify({
            'messages': [msg.to_dict() for msg in messages]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/analytics/dashboard', methods=['GET'])
def get_dashboard_analytics():
    """Get analytics data for admin dashboard"""
    try:
        # Get today's metrics
        today = datetime.utcnow().date()
        
        # Conversation metrics
        total_conversations = Conversation.query.filter(
            db.func.date(Conversation.created_at) == today
        ).count()
        
        active_conversations = Conversation.query.filter_by(status='active').count()
        
        resolved_conversations = Conversation.query.filter(
            db.func.date(Conversation.resolved_at) == today
        ).count()
        
        # Response time metrics
        avg_response_time = db.session.query(
            db.func.avg(Message.processing_time)
        ).filter(
            Message.sender_type == 'ai',
            db.func.date(Message.created_at) == today
        ).scalar() or 0
        
        # Satisfaction metrics
        avg_satisfaction = db.session.query(
            db.func.avg(Conversation.satisfaction_score)
        ).filter(
            Conversation.satisfaction_score.isnot(None),
            db.func.date(Conversation.updated_at) == today
        ).scalar() or 0
        
        # Channel distribution
        channel_stats = db.session.query(
            Conversation.channel,
            db.func.count(Conversation.id)
        ).filter(
            db.func.date(Conversation.created_at) == today
        ).group_by(Conversation.channel).all()
        
        # Intent distribution
        intent_stats = db.session.query(
            Conversation.category,
            db.func.count(Conversation.id)
        ).filter(
            Conversation.category.isnot(None),
            db.func.date(Conversation.created_at) == today
        ).group_by(Conversation.category).all()
        
        return jsonify({
            'summary': {
                'total_conversations': total_conversations,
                'active_conversations': active_conversations,
                'resolved_conversations': resolved_conversations,
                'avg_response_time': round(avg_response_time, 2),
                'avg_satisfaction': round(avg_satisfaction, 1)
            },
            'channel_distribution': dict(channel_stats),
            'intent_distribution': dict(intent_stats)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/conversations/<conversation_id>/escalate', methods=['POST'])
def escalate_conversation(conversation_id):
    """Escalate conversation to human agent"""
    try:
        data = request.get_json()
        agent_id = data.get('agent_id')
        
        conversation = Conversation.query.get_or_404(conversation_id)
        conversation.escalate(agent_id)
        
        return jsonify({
            'message': 'Conversation escalated successfully',
            'conversation': conversation.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/conversations/<conversation_id>/resolve', methods=['POST'])
def resolve_conversation(conversation_id):
    """Mark conversation as resolved"""
    try:
        data = request.get_json()
        satisfaction_score = data.get('satisfaction_score')
        
        conversation = Conversation.query.get_or_404(conversation_id)
        conversation.resolve(satisfaction_score)
        
        return jsonify({
            'message': 'Conversation resolved successfully',
            'conversation': conversation.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
