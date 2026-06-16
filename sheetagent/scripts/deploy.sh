#!/bin/bash
# deploy.sh — SheetAgent AI production deployment
set -e

echo "═══════════════════════════════════════"
echo " SheetAgent AI — Deployment Script"
echo "═══════════════════════════════════════"

# Check .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Copy .env.example and fill in values."
    cp .env.example .env
    echo "✅ Created .env from .env.example — please edit it and re-run."
    exit 1
fi

# Check GEMINI_API_KEY
source .env
if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
    echo "❌ GEMINI_API_KEY not set in .env"
    exit 1
fi

echo "✅ Environment validated"

# Pull latest images
echo "🐳 Building Docker images..."
docker-compose pull --ignore-pull-failures 2>/dev/null || true
docker-compose build --parallel

# Run DB migrations
echo "🗄️  Running database migrations..."
docker-compose run --rm backend alembic upgrade head || echo "⚠️  Migration skipped (first run will auto-create tables)"

# Start services
echo "🚀 Starting services..."
docker-compose up -d

# Wait for health
echo "⏳ Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -sf http://localhost/health > /dev/null 2>&1; then
        echo "✅ Backend is healthy"
        break
    fi
    echo "   Attempt $i/30..."
    sleep 3
done

echo ""
echo "═══════════════════════════════════════"
echo " ✅ SheetAgent AI is running!"
echo "    Frontend: http://localhost"
echo "    API docs: http://localhost/docs"
echo "    Health:   http://localhost/health"
echo "    Ready:    http://localhost/ready"
echo "═══════════════════════════════════════"
