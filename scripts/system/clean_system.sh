#!/bin/bash

# ES-NL2DSL System Clean Script
# This script completely removes all containers, networks, and volumes
# Use this when you want a fresh start or encounter issues

set -e

# Get the project root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo "🧹 ES-NL2DSL System Deep Clean..."
echo "=================================="
echo "⚠️  WARNING: This will remove ALL containers, networks, and data!"
echo "   Use this only when you want a completely fresh start."
echo ""

# Ask for confirmation
read -p "Are you sure you want to completely clean the system? (y/N): " -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cleanup cancelled"
    exit 0
fi

echo ""
echo "🛑 Stopping all processes..."

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

# Deep clean Docker resources
echo ""
echo "🗑️  Removing all Docker containers and networks..."
cd "$PROJECT_ROOT/docker"

# Stop and remove everything
docker-compose down -v --remove-orphans 2>/dev/null || true

# Remove individual containers by name (in case compose fails)
docker rm -f es8113 es-nl2dsl-redis es-nl2dsl-postgres 2>/dev/null || true

# Clean up networks
docker network rm docker_default 2>/dev/null || true

# Optional: Clean up volumes (commented out for safety)
echo ""
echo "💾 Volume cleanup options:"
echo "   Docker volumes preserved (contains your Elasticsearch data)"
echo "   To also remove volumes (⚠️  DELETES ALL DATA), run:"
echo "   docker volume ls | grep docker_ | awk '{print \$2}' | xargs docker volume rm"

echo ""
echo "✅ Deep clean completed!"
echo ""
echo "💡 Next steps:"
echo "   ./start_system.sh  # Will create fresh containers"
echo "   make start          # Alternative using Makefile"