"""
Voice IVR routes using Twilio
"""

from flask import Blueprint, request, Response
from twilio.twiml.voice_response import VoiceResponse
from app import db
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.ai_service import HotelAIService
import uuid

voice_bp = Blueprint('voice', __name__)
ai_service = HotelAIService()

@voice_bp.route('/webhook', methods=['POST'])
def voice_webhook():
    """Handle incoming voice calls from Twilio"""
    response = VoiceResponse()
    
    # Get caller information
    caller_number = request.form.get('From')
    call_sid = request.form.get('CallSid')
    
    # Welcome message
    response.say(
        "Welcome to Grand Hotel customer service. I'm your AI assistant. "
        "Please speak your request after the tone.",
        voice='alice'
    )
    
    # Record the caller's message
    response.record(
        action='/voice/process',
        method='POST',
        max_length=30,
        finish_on_key='#'
    )
    
    return str(response)

@voice_bp.route('/process', methods=['POST'])
def process_voice():
    """Process recorded voice message"""
    response = VoiceResponse()
    
    try:
        # Get recording URL and transcription
        recording_url = request.form.get('RecordingUrl')
        caller_number = request.form.get('From')
        call_sid = request.form.get('CallSid')
        
        # For demo purposes, we'll use a placeholder transcription
        # In production, you'd use speech-to-text service
        transcription = "I need help with my room reservation"
        
        # Create or get user
        user = User.query.filter_by(phone=caller_number).first()
        if not user:
            user = User(
                session_id=call_sid,
                phone=caller_number,
                guest_type='caller'
            )
            db.session.add(user)
            db.session.commit()
        
        # Create conversation
        conversation = Conversation(
            user_id=user.id,
            channel='voice'
        )
        db.session.add(conversation)
        db.session.commit()
        
        # Save user message
        Message.create_user_message(
            conversation.id,
            user.id,
            transcription,
            message_type='audio',
            metadata={'recording_url': recording_url}
        )
        
        # Generate AI response
        ai_response = ai_service.generate_response(
            transcription,
            conversation.id,
            {'phone': caller_number}
        )
        
        # Save AI response
        Message.create_ai_message(
            conversation.id,
            ai_response['response'],
            intent=ai_response.get('intent'),
            confidence=ai_response.get('confidence')
        )
        
        # Speak the response
        response.say(ai_response['response'], voice='alice')
        
        # Check if escalation is needed
        if ai_response.get('escalate'):
            response.say(
                "I'm transferring you to a human agent who can better assist you. "
                "Please hold while I connect you.",
                voice='alice'
            )
            # In production, you'd dial the hotel's customer service number
            response.dial('+1234567890')  # Hotel's customer service number
        else:
            # Ask if they need more help
            response.say(
                "Is there anything else I can help you with? "
                "Press 1 for yes, or hang up if you're satisfied.",
                voice='alice'
            )
            
            gather = response.gather(
                action='/voice/continue',
                method='POST',
                num_digits=1,
                timeout=10
            )
            
            response.say("Thank you for calling Grand Hotel. Have a great day!", voice='alice')
        
    except Exception as e:
        response.say(
            "I apologize, but I'm experiencing technical difficulties. "
            "Please call our front desk directly for immediate assistance.",
            voice='alice'
        )
    
    return str(response)

@voice_bp.route('/continue', methods=['POST'])
def continue_conversation():
    """Continue voice conversation"""
    response = VoiceResponse()
    
    digit_pressed = request.form.get('Digits')
    
    if digit_pressed == '1':
        response.say(
            "Please speak your next question after the tone.",
            voice='alice'
        )
        response.record(
            action='/voice/process',
            method='POST',
            max_length=30,
            finish_on_key='#'
        )
    else:
        response.say(
            "Thank you for calling Grand Hotel. Have a great day!",
            voice='alice'
        )
    
    return str(response)
