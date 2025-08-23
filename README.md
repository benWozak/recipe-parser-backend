# HomeChef Companion Backend

FastAPI backend for the Recipe Management PWA application.

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+**
- **PostgreSQL** (Neon account recommended)

### Installation & Setup

1. **Navigate to backend directory:**

   ```bash
   cd backend
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env with your database URL and secrets
   ```

5. **Generate secure secret key:**

   ```bash
   python generate_secret_key.py
   # Follow prompts and update .env with generated key
   ```

6. **Set up database:**

   ```bash
   # Create initial migration
   alembic revision --autogenerate -m "Initial schema"

   # Apply migration
   alembic upgrade head
   ```

7. **Start development server:**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

8. **Visit API documentation:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Documentation

Once the server is running, you can access:

- API Documentation: http://localhost:8000/docs
- Alternative API docs: http://localhost:8000/redoc

## Project Structure

```
app/
├── api/                 # API route handlers
│   ├── auth/           # Authentication endpoints
│   ├── recipes/        # Recipe CRUD endpoints
│   ├── meal_plans/     # Meal planning endpoints
│   ├── users/          # User profile endpoints
│   └── parsing/        # Recipe parsing endpoints
├── core/               # Core functionality
│   ├── config.py       # Configuration settings
│   ├── database.py     # Database connection
│   └── security.py     # Security utilities
├── models/             # SQLAlchemy database models
├── schemas/            # Pydantic request/response schemas
├── services/           # Business logic layer
└── main.py            # FastAPI application entry point
```

## Environment Variables

Required environment variables (see `.env.example`):

- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: JWT signing key
- `CLERK_SECRET_KEY`: Clerk authentication secret
- `CLERK_PUBLISHABLE_KEY`: Clerk publishable key
- `CLERK_WEBHOOK_SECRET`: Clerk webhook secret

Optional:

- `GOOGLE_CLOUD_VISION_CREDENTIALS`: For OCR functionality
- `OPENAI_API_KEY`: For AI-powered recipe parsing

## Database Migrations

To create a new migration after model changes:

```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

## Features

- **Authentication**: Clerk-based user authentication
- **Recipe Management**: Full CRUD operations for recipes
- **Meal Planning**: Create and manage meal plans
- **Recipe Parsing**: Extract recipes from URLs, images, and Instagram
- **Search & Filtering**: Advanced recipe search and filtering
- **Database**: PostgreSQL with SQLAlchemy ORM
- **API Documentation**: Auto-generated OpenAPI/Swagger docs
