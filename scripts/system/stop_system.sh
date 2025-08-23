#!/bin/bash

# ES-NL2DSL System Stop Script

set -e

# Get the project root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo "🛑 Stopping ES-NL2DSL System..."
echo "==============================="

# Stop application processes (check backend directory for PID files)
cd "$PROJECT_ROOT/backend"

if [ -f .celery.pid ]; then
    CELERY_PID=$(cat .celery.pid)
    echo "Stopping Celery worker (PID: $CELERY_PID)..."
    kill -TERM $CELERY_PID 2>/dev/null || echo "Celery worker already stopped"
    rm -f .celery.pid
fi

if [ -f .django.pid ]; then
    DJANGO_PID=$(cat .django.pid)
    echo "Stopping Django backend (PID: $DJANGO_PID)..."
    kill -TERM $DJANGO_PID 2>/dev/null || echo "Django backend already stopped"
    rm -f .django.pid
fi

# Check frontend directory for React PID
cd "$PROJECT_ROOT/frontend"

if [ -f .react.pid ]; then
    REACT_PID=$(cat .react.pid)
    echo "Stopping React frontend (PID: $REACT_PID)..."
    kill -TERM $REACT_PID 2>/dev/null || echo "React frontend already stopped"
    rm -f .react.pid
fi

# Stop Docker services (but keep containers for restart)
echo "Stopping Docker services..."
cd "$PROJECT_ROOT/docker" && docker-compose stop

echo "✅ System stopped successfully! (Containers preserved for restart)"