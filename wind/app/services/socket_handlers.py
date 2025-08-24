"""
Socket.IO event handlers for real-time communication
"""

from flask_socketio import emit, join_room, leave_room
from flask import session, request
from app import db, redis_client
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.ai_service import HotelAIService
import json
import uuid

ai_service = HotelAIService()

def register_socket_handlers(socketio):
    """Register all Socket.IO event handlers"""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        session_id = request.args.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
        
        session['session_id'] = session_id
        join_room(session_id)
        
        emit('connected', {
            'session_id': session_id,
            'message': 'Connected to customer service'
        })
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        session_id = session.get('session_id')
        if session_id:
            leave_room(session_id)
    
    @socketio.on('join_conversation')
    def handle_join_conversation(data):
        """Join a specific conversation room"""
        conversation_id = data.get('conversation_id')
        if conversation_id:
            join_room(f"conversation_{conversation_id}")
            emit('joined_conversation', {'conversation_id': conversation_id})
    
    @socketio.on('send_message')
    def handle_message(data):
        """Handle incoming chat messages"""
        try:
            user_message = data.get('message', '').strip()
            session_id = session.get('session_id') or data.get('session_id')
            user_context = data.get('user_context', {})
            
            if not user_message or not session_id:
                emit('error', {'message': 'Message and session_id are required'})
                return
            
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
            
            # Emit user message to conversation room
            socketio.emit('new_message', {
                'message': user_msg.to_dict(),
                'conversation_id': conversation.id
            }, room=f"conversation_{conversation.id}")
            
            # Generate AI response
            try:
                ai_response = ai_service.generate_response(
                    user_message,
                    conversation.id,
                    user_context
                )
            except Exception as e:
                print(f"AI Service Error: {e}")
                # Fallback response
                ai_response = {
                    'response': "Thank you for your message. I'm here to help you with any questions about our hotel services. How can I assist you today?",
                    'intent': 'inquiry',
                    'confidence': 0.5,
                    'sentiment': 'neutral',
                    'processing_time': 0.1,
                    'escalate': False
                }
            
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
            
            # Cache in Redis
            redis_client.setex(
                f"conversation:{session_id}",
                3600,
                json.dumps({
                    'conversation_id': conversation.id,
                    'user_id': user.id,
                    'last_message': ai_response['response']
                })
            )
            
            # Emit AI response
            emit('ai_response', {
                'message': ai_msg.to_dict(),
                'conversation_id': conversation.id,
                'intent': ai_response.get('intent'),
                'sentiment': ai_response.get('sentiment'),
                'escalate': ai_response.get('escalate', False),
                'suggested_responses': ai_service.get_suggested_responses(
                    ai_response.get('intent', 'inquiry')
                )
            })
            
            # Emit to conversation room for admin monitoring
            socketio.emit('new_message', {
                'message': ai_msg.to_dict(),
                'conversation_id': conversation.id
            }, room=f"conversation_{conversation.id}")
            
            # If escalation is needed, notify admin
            if ai_response.get('escalate'):
                socketio.emit('escalation_needed', {
                    'conversation_id': conversation.id,
                    'user_id': user.id,
                    'message': user_message,
                    'intent': ai_response.get('intent'),
                    'sentiment': ai_response.get('sentiment')
                }, room='admin')
            
        except Exception as e:
            emit('error', {'message': str(e)})
    
    @socketio.on('typing')
    def handle_typing(data):
        """Handle typing indicators"""
        session_id = session.get('session_id')
        conversation_id = data.get('conversation_id')
        
        if conversation_id:
            emit('user_typing', {
                'session_id': session_id,
                'typing': data.get('typing', False)
            }, room=f"conversation_{conversation_id}", include_self=False)
    
    @socketio.on('admin_join')
    def handle_admin_join():
        """Handle admin joining for monitoring"""
        join_room('admin')
        emit('admin_joined', {'message': 'Admin monitoring active'})
    
    @socketio.on('admin_message')
    def handle_admin_message(data):
        """Handle messages from admin to specific conversation"""
        try:
            conversation_id = data.get('conversation_id')
            message = data.get('message')
            agent_id = data.get('agent_id', 'admin')
            
            if not conversation_id or not message:
                emit('error', {'message': 'Conversation ID and message are required'})
                return
            
            # Save admin message
            admin_msg = Message(
                conversation_id=conversation_id,
                sender_type='agent',
                sender_id=agent_id,
                content=message
            )
            db.session.add(admin_msg)
            db.session.commit()
            
            # Emit to conversation participants
            socketio.emit('agent_message', {
                'message': admin_msg.to_dict()
            }, room=f"conversation_{conversation_id}")
            
        except Exception as e:
            emit('error', {'message': str(e)})
    
    @socketio.on('get_conversation_history')
    def handle_get_history(data):
        """Get conversation history"""
        try:
            conversation_id = data.get('conversation_id')
            limit = data.get('limit', 50)
            
            if not conversation_id:
                emit('error', {'message': 'Conversation ID is required'})
                return
            
            messages = Message.query.filter_by(conversation_id=conversation_id)\
                                   .order_by(Message.created_at.asc())\
                                   .limit(limit).all()
            
            emit('conversation_history', {
                'conversation_id': conversation_id,
                'messages': [msg.to_dict() for msg in messages]
            })
            
        except Exception as e:
            emit('error', {'message': str(e)})
