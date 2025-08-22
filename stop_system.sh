#!/bin/bash

# ES-NL2DSL System Stop Script

set -e

echo "🛑 Stopping ES-NL2DSL System..."
echo "==============================="

# Stop application processes
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

if [ -f .react.pid ]; then
    REACT_PID=$(cat .react.pid)
    echo "Stopping React frontend (PID: $REACT_PID)..."
    kill -TERM $REACT_PID 2>/dev/null || echo "React frontend already stopped"
    rm -f .react.pid
fi

# Stop Docker services
echo "Stopping Docker services..."
docker-compose down

echo "✅ System stopped successfully!"