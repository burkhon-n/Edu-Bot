#!/bin/bash

# CourseMateBot development runner
# Starts both FastAPI and Telegram bot

set -e

echo "🚀 Starting CourseMateBot..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    exit 1
fi

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    if [ ! -z "$BOT_PID" ]; then
        kill $BOT_PID 2>/dev/null || true
    fi
    kill $API_PID 2>/dev/null || true
    exit 0
}

trap cleanup INT TERM

# Start FastAPI in background
echo "📡 Starting FastAPI server..."
uvicorn app.main:app --reload --port 8000 &
API_PID=$!

# Wait a moment for API to start
sleep 2

# Check if WEBHOOK_URL is set
source .env
if [ -n "$WEBHOOK_URL" ]; then
    echo "📡 Using webhook mode (bot integrated in API)"
    echo ""
    echo "✅ API running with webhook!"
    echo "   API: http://localhost:8000"
    echo "   Docs: http://localhost:8000/docs"
    echo "   Webhook: $WEBHOOK_URL/webhook/***"
else
    # Start Telegram bot in background (polling mode)
    echo "🤖 Starting Telegram bot (polling mode)..."
    python -m app.bot &
    BOT_PID=$!
    
    echo ""
    echo "✅ Both services are running!"
    echo "   API: http://localhost:8000"
    echo "   Docs: http://localhost:8000/docs"
    echo "   Bot: Running (polling)..."
fi

echo ""
echo "Press Ctrl+C to stop all services"

# Wait for processes
if [ -z "$WEBHOOK_URL" ]; then
    wait $API_PID $BOT_PID
else
    wait $API_PID
fi
