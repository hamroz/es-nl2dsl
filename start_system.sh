#!/bin/bash

# ES-NL2DSL System Startup Script
# This script starts the complete Django/React system with all required services

set -e

echo "🚀 Starting ES-NL2DSL Migration System..."
echo "========================================"

# Function to check if a service is running
check_service() {
    local service_name=$1
    local check_command=$2
    echo -n "Checking $service_name... "
    if eval "$check_command" &>/dev/null; then
        echo "✅ Running"
        return 0
    else
        echo "❌ Not running"
        return 1
    fi
}

# Function to wait for service
wait_for_service() {
    local service_name=$1
    local check_command=$2
    local max_attempts=${3:-30}
    local attempt=1
    
    echo -n "Waiting for $service_name"
    while [ $attempt -le $max_attempts ]; do
        if eval "$check_command" &>/dev/null; then
            echo " ✅ Ready!"
            return 0
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    echo " ❌ Failed to start after $max_attempts attempts"
    return 1
}

# Step 1: Start Docker services
echo -e "\n📦 Starting Docker Services..."
echo "================================"
docker-compose up -d

# Step 2: Wait for services to be ready
echo -e "\n⏳ Waiting for Services..."
echo "=========================="
wait_for_service "Elasticsearch" "curl -s -u elastic:ChangeMe_123 http://localhost:9200/_cluster/health"
wait_for_service "Redis" "redis-cli ping"
wait_for_service "PostgreSQL" "pg_isready -h localhost -p 5432 -U postgres"

# Step 3: Install backend dependencies
echo -e "\n📚 Installing Backend Dependencies..."
echo "==================================="
cd backend
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3.11 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install --quiet -r requirements-auth.txt
pip install --quiet django djangorestframework channels channels-redis requests pyyaml jsonschema

# Step 4: Django migrations and setup
echo -e "\n🗄️  Setting up Django Database..."
echo "================================"
echo "Running migrations..."
python manage.py makemigrations
python manage.py migrate

echo "Creating users..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model

User = get_user_model()

# Admin user
if not User.objects.filter(email='admin@gmail.com').exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@gmail.com',
        password='admin@es2dsl',
        first_name='Admin',
        last_name='User',
        role='admin'
    )
    print("✅ Admin user created: admin@gmail.com")
else:
    # Update password if user exists
    admin_user = User.objects.get(email='admin@gmail.com')
    admin_user.set_password('admin@es2dsl')
    admin_user.role = 'admin'
    admin_user.save()
    print("✅ Admin user updated: admin@gmail.com")

# Analyst user
if not User.objects.filter(email='analyst@gmail.com').exists():
    User.objects.create_user(
        username='analyst',
        email='analyst@gmail.com',
        password='analyst@es2dsl',
        first_name='Analyst',
        last_name='User',
        role='analyst'
    )
    print("✅ Analyst user created: analyst@gmail.com")
else:
    # Update password if user exists
    analyst_user = User.objects.get(email='analyst@gmail.com')
    analyst_user.set_password('analyst@es2dsl')
    analyst_user.role = 'analyst'
    analyst_user.save()
    print("✅ Analyst user updated: analyst@gmail.com")

# Viewer user
if not User.objects.filter(email='viewer@gmail.com').exists():
    User.objects.create_user(
        username='viewer',
        email='viewer@gmail.com',
        password='viewer@es2dsl',
        first_name='Viewer',
        last_name='User',
        role='viewer'
    )
    print("✅ Viewer user created: viewer@gmail.com")
else:
    # Update password if user exists
    viewer_user = User.objects.get(email='viewer@gmail.com')
    viewer_user.set_password('viewer@es2dsl')
    viewer_user.role = 'viewer'
    viewer_user.save()
    print("✅ Viewer user updated: viewer@gmail.com")
EOF

# Step 5: Install frontend dependencies
echo -e "\n🎨 Setting up Frontend..."
echo "========================"
cd ../frontend
if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

# Step 6: Start services in background
echo -e "\n🔄 Starting Application Services..."
echo "=================================="

# Start Celery worker
echo "Starting Celery worker..."
cd ../backend
source venv/bin/activate
nohup celery -A es_nl2dsl_api worker --loglevel=info > logs/celery_worker.log 2>&1 &
CELERY_PID=$!
echo "✅ Celery worker started (PID: $CELERY_PID)"

# Start Django development server
echo "Starting Django backend..."
nohup python manage.py runserver 8000 > logs/django.log 2>&1 &
DJANGO_PID=$!
echo "✅ Django backend started (PID: $DJANGO_PID)"

# Start React frontend
echo "Starting React frontend..."
cd ../frontend
nohup npm run dev > logs/react.log 2>&1 &
REACT_PID=$!
echo "✅ React frontend started (PID: $REACT_PID)"

# Create logs directory if it doesn't exist
mkdir -p ../backend/logs
mkdir -p logs

# Step 7: Wait for services to be ready
echo -e "\n⏳ Waiting for Application Services..."
echo "===================================="
wait_for_service "Django Backend" "curl -s http://localhost:8000/api/v1/"
wait_for_service "React Frontend" "curl -s http://localhost:3000"

# Step 8: Display system status
echo -e "\n✅ System Started Successfully!"
echo "=============================="
echo ""
echo "🌐 Access Points:"
echo "  • Frontend:  http://localhost:3000"
echo "  • Backend:   http://localhost:8000"
echo "  • API Docs:  http://localhost:8000/api/v1/"
echo ""
echo "🔧 User Access:"
echo "  • Admin:     admin@gmail.com / admin@es2dsl"
echo "  • Analyst:   analyst@gmail.com / analyst@es2dsl"
echo "  • Viewer:    viewer@gmail.com / viewer@es2dsl"
echo ""
echo "📊 Infrastructure:"
echo "  • Elasticsearch: http://localhost:9200"
echo "  • Redis:         localhost:6379" 
echo "  • PostgreSQL:    localhost:5432"
echo ""
echo "📝 Process IDs:"
echo "  • Celery Worker: $CELERY_PID"
echo "  • Django:        $DJANGO_PID"
echo "  • React:         $REACT_PID"
echo ""
echo "🛑 To stop the system:"
echo "  kill $CELERY_PID $DJANGO_PID $REACT_PID"
echo "  docker-compose down"
echo ""
echo "📋 Ready to test:"
echo "  1. Open http://localhost:3000"
echo "  2. Login with any user credentials above"
echo "  3. Navigate to Query Generator"
echo "  4. Test: 'Find malicious events from 2017-07-04'"
echo ""

# Save PIDs to file for easy cleanup
echo "$CELERY_PID" > .celery.pid
echo "$DJANGO_PID" > .django.pid  
echo "$REACT_PID" > .react.pid

echo "🎉 ES-NL2DSL Migration System is READY!"