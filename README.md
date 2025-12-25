# Trekkr

A location-based exploration app built with React Native (Expo) and FastAPI.

## Project Structure

```
Trekkr/
├── backend/          # FastAPI backend
│   ├── models/       # SQLAlchemy database models
│   ├── routers/      # API route handlers
│   ├── schemas/      # Pydantic request/response schemas
│   ├── services/     # Business logic and utilities
│   └── main.py       # FastAPI application entry point
│
└── frontend/         # React Native (Expo) frontend
    ├── app/          # Expo Router file-based routing
    ├── components/   # Reusable React components
    ├── contexts/     # React context providers
    ├── services/     # API and storage services
    ├── config/       # Configuration files
    └── hooks/        # Custom React hooks
```

## Features

- 🔐 User authentication (JWT-based)
- 📍 Location tracking
- 🗺️ Map integration (Mapbox)
- 📱 Cross-platform (iOS, Android, Web)

## Getting Started

### Prerequisites

- Python 3.8+ (for backend)
- Node.js 18+ (for frontend)
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. (Optional) Create a `.env` file with:
   ```
   DATABASE_URL=sqlite:///./trekkr.db
   SECRET_KEY=your-secret-key-here
   ```

5. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

The API will be available at `http://127.0.0.1:8000`
- API Docs: `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/api/health`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```

4. Update API configuration:
   - Edit `frontend/config/api.ts` to set the correct API base URL
   - For iOS physical devices, update the IP address
   - Android emulator automatically uses `10.0.2.2`

5. Configure Mapbox (if using maps):
   - Update `app.json` with your Mapbox secret token

## Development

### Backend

- FastAPI with automatic API documentation
- SQLAlchemy ORM for database operations
- JWT authentication with refresh tokens
- SQLite database (can be switched to PostgreSQL)

### Frontend

- Expo Router for file-based routing
- React Context for state management
- Expo Secure Store for token storage
- TypeScript for type safety

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register a new user
- `POST /api/auth/login` - Login user
- `POST /api/auth/logout` - Logout user
- `POST /api/auth/refresh` - Refresh access token
- `GET /api/auth/me` - Get current user info

### Health
- `GET /api/health` - Health check

## Environment Variables

### Backend
- `DATABASE_URL` - Database connection string (default: `sqlite:///./trekkr.db`)
- `SECRET_KEY` - JWT secret key (change in production!)

### Frontend
- API base URL configured in `frontend/config/api.ts`

## License

MIT

