# Multi-Channel AI Customer Service System for Hotels

A comprehensive AI-powered customer service platform supporting web chat, voice IVR, and admin dashboard functionality.

## Features

- **Multi-Channel Support**: Web chat interface and voice IVR system
- **AI-Powered Responses**: Google Gemini API integration via LangChain
- **Real-time Communication**: Socket.IO for instant messaging
- **Admin Dashboard**: Analytics and conversation management
- **Session Management**: Redis-based session handling
- **Background Processing**: Celery for async tasks
- **Database**: SQLAlchemy ORM with migration support

## Architecture

```
├── app/
│   ├── __init__.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   └── static/
├── config/
├── migrations/
├── tests/
└── requirements.txt
```

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Setup**
   ```bash
   cp .env.example .env
   # Add your Google Gemini API key and other configurations
   ```

3. **Database Setup**
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

4. **Start Redis Server**
   ```bash
   redis-server
   ```

5. **Start Celery Worker**
   ```bash
   celery -A app.celery worker --loglevel=info
   ```

6. **Run Application**
   ```bash
   python run.py
   ```

## Configuration

Create a `.env` file with the following variables:

```
GOOGLE_API_KEY=your_gemini_api_key
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite:///hotel_service.db
SECRET_KEY=your_secret_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
```

## API Endpoints

- `POST /api/chat` - Send chat messages
- `GET /api/conversations` - Get conversation history
- `POST /api/voice/webhook` - Twilio voice webhook
- `GET /admin/dashboard` - Admin analytics dashboard

## Technologies Used

- **Backend**: Python, Flask, SQLAlchemy, Redis, Celery
- **AI/ML**: LangChain, Google Gemini API
- **Frontend**: HTML/CSS/JavaScript, Socket.IO, Chart.js
- **Voice**: Twilio Voice API, Speech Recognition
- **Database**: SQLite (development), PostgreSQL (production)

## License

MIT License
