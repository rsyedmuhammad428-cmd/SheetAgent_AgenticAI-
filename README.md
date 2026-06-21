---
title: SheetAgent
sdk: docker
app_port: 7860
---

# SheetAgent AI - Intelligent Data Operating System

## Project Description
SheetAgent AI is a powerful, AI-driven platform that transforms how you work with data. It leverages Large Language Models (specifically Google Gemini) to automate spreadsheet tasks, data analysis, visualization, and more—all through natural language interaction.

## Key Features

### 📊 Core Capabilities
- **File Upload & Processing**: Support for CSV, Excel, PDF, and image files (OCR enabled)
- **AI-Powered Schema Detection**: Automatically identifies data types and structure (invoices, sales, HR, etc.)
- **Intelligent Data Cleaning**: Suggestions for duplicates, missing values, dates, currency formatting
- **Human-in-the-Loop Approval**: Review changes before they're applied
- **Styled Excel Generation**: Professional output with freeze panes, filters, conditional formatting

### 🤖 AI Agents
- **Input Agent**: Handles user input and file processing
- **Schema Agent**: Detects and validates data schemas
- **Cleaning Agent**: Proposes data cleaning operations
- **Formula Agent**: Converts natural language to Excel formulas
- **Analytics Agent**: Answers plain-English questions about your data
- **Visualization Agent**: Auto-generates charts (bar, line, pie, etc.)
- **Reflection Agent**: Scores output quality and creates quality reports
- **OCR Agent**: Extracts data from scanned documents and images
- **Extraction Agent**: Pulls structured data from various file formats
- **Planner Agent**: Creates execution plans for complex tasks
- **Memory Agent**: Maintains session context and history
- **Chat Agent**: Full-featured conversational interface
- **Intelligence Engine**: Deep task understanding using Gemini (Phase 6)

### 🛠️ Technical Features
- **WebSocket Communication**: Real-time execution logs
- **Rate Limiting**: Protects API endpoints
- **Structured Logging**: JSON-based logging for production
- **Database Support**: PostgreSQL (production) / SQLite (development)
- **Redis Integration**: Session storage and caching
- **Docker Support**: Containerized deployment with docker-compose
- **Nginx Reverse Proxy**: Production-ready routing
- **Health & Monitoring**: /health, /ready, and /metrics endpoints

## Technology Stack

### Backend
- **Framework**: FastAPI 0.111.0
- **LLM Integration**: LangChain, LangGraph, Google Generative AI (Gemini)
- **Data Processing**: Pandas, NumPy, OpenPyXL
- **PDF Handling**: PyPDF, PDFPlumber, pdf2image
- **OCR**: EasyOCR, img2table, OpenCV
- **Database**: SQLAlchemy 2.0.36, AsyncPG, Alembic (migrations)
- **Caching/Queues**: Redis 5.1.1, ARQ
- **Auth**: Python-JOSE, Passlib
- **Rate Limiting**: SlowAPI, Limits
- **Monitoring**: Sentry, Prometheus

### Frontend
- **Framework**: React 19.2.0, TypeScript 5.8.3
- **Build Tool**: Vite 8.0.16
- **Routing**: TanStack React Router
- **State Management**: TanStack React Query
- **UI Components**: Radix UI, Tailwind CSS 4.2.1
- **Charts**: Recharts
- **Forms**: React Hook Form, Zod
- **Icons**: Lucide React
- **Notifications**: Sonner

### Infrastructure
- **Containerization**: Docker, Docker Compose
- **Web Server**: Nginx
- **Databases**: PostgreSQL 16, Redis 7

## Project Structure
```
sheetagent/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── agents/          # AI agent implementations
│   │   ├── api/             # API routes
│   │   ├── models/          # Database models and schemas
│   │   ├── parsers/         # File parsers (CSV, PDF, OCR)
│   │   ├── services/        # Business logic services
│   │   ├── utils/           # Utilities (logging, rate limiting, etc.)
│   │   ├── config.py        # Configuration
│   │   └── main.py          # FastAPI application entry point
│   ├── requirements.txt     # Python dependencies
│   ├── Dockerfile           # Backend Docker image
│   └── alembic.ini          # Database migrations config
├── frontend/                # React + TypeScript frontend
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom hooks
│   │   ├── lib/             # Utilities and API clients
│   │   └── routes/          # Route definitions
│   ├── package.json         # Node.js dependencies
│   ├── Dockerfile           # Frontend Docker image
│   └── vite.config.ts       # Vite configuration
├── nginx/                   # Nginx configuration
├── workspace/               # Sandboxed file storage
├── docker-compose.yml       # Production Docker Compose
└── docker-compose.dev.yml   # Development Docker Compose
```

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Google Gemini API key (get one from [Google AI Studio](https://aistudio.google.com/app/apikey))

### Production Deployment
```bash
cd sheetagent
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY, SECRET_KEY, POSTGRES_PASSWORD
docker-compose up --build -d
```
Open http://localhost in your browser.

### Local Development
```bash
cd sheetagent
cp .env.example .env
# Only GEMINI_API_KEY is needed for dev mode
docker-compose -f docker-compose.dev.yml up --build
```
Open http://localhost:5173 in your browser.

### Manual Setup (Without Docker)

**Backend:**
```bash
cd sheetagent/backend
cp .env.example .env
# Add your GEMINI_API_KEY to .env
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd sheetagent/frontend
npm install
npm run dev
```

## Environment Variables
See `.env.example` for all available configuration options. Key variables include:
- `GEMINI_API_KEY`: Your Google Gemini API key (required)
- `GEMINI_MODEL`: Gemini model to use (default: gemini-1.5-flash)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SECRET_KEY`: Secret key for authentication
- `ENVIRONMENT`: Environment (production/development)
- `LOG_LEVEL`: Logging level (INFO/DEBUG/WARNING/ERROR)

## API Documentation
Once the backend is running, visit http://localhost:8000/docs for interactive API documentation (Swagger UI).

## Roadmap & Phases
- **Phase 1**: Core pipeline (CSV/Excel → Gemini analysis → styled Excel)
- **Phase 2**: Formula agent, reflection agent, visualization, analytics
- **Phase 3**: OCR pipeline (scanned PDFs, images)
- **Phase 4**: Memory system + session history
- **Phase 5**: Production hardening, full chat interface, download
- **Phase 6**: Intelligence upgrade (deep task understanding)

## License
This project is for demonstration and educational purposes.
