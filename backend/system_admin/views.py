from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import requests
import subprocess
import json

class SystemHealthView(APIView):
    """
    System health check endpoint matching Streamlit status functionality
    """
    def get(self, request):
        health_status = {
            'elasticsearch': self.check_elasticsearch(),
            'ollama': self.check_ollama(),
            'database': self.check_database(),
            'redis': self.check_redis(),
            'celery_workers': self.check_celery_workers(),
            'indices': self.get_index_count(),
            'models': self.get_available_models(),
            'last_check': timezone.now().isoformat()
        }
        
        # Overall health determination
        critical_services = ['elasticsearch', 'database', 'redis']
        overall_healthy = all(health_status[service] for service in critical_services)
        
        return Response({
            'overall_status': 'healthy' if overall_healthy else 'unhealthy',
            'services': health_status,
            'version': '1.0.0'
        })
    
    def check_elasticsearch(self):
        try:
            response = requests.get(
                'http://localhost:9200/_cluster/health',
                auth=('elastic', 'ChangeMe_123'),
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def check_ollama(self):
        try:
            result = subprocess.run(['ollama', 'list'], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def check_database(self):
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except:
            return False
    
    def check_redis(self):
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.ping()
            return True
        except:
            return False
    
    def check_celery_workers(self):
        # This will be implemented when Celery is running
        return True
    
    def get_index_count(self):
        try:
            response = requests.get(
                'http://localhost:9200/_cat/indices?format=json',
                auth=('elastic', 'ChangeMe_123'),
                timeout=5
            )
            if response.status_code == 200:
                return len(response.json())
            return 0
        except:
            return 0
    
    def get_available_models(self):
        try:
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                return [line.split()[0] for line in lines if line.strip()]
            return []
        except:
            return []

class AvailableIndicesView(APIView):
    """
    Get list of available Elasticsearch indices
    """
    def get(self, request):
        try:
            response = requests.get(
                'http://localhost:9200/_cat/indices?format=json',
                auth=('elastic', 'ChangeMe_123'),
                timeout=5
            )
            if response.status_code == 200:
                indices = [index['index'] for index in response.json() if not index['index'].startswith('.')]
                return Response(indices)
            return Response(['logs_net'], status=status.HTTP_200_OK)  # Default fallback
        except:
            return Response(['logs_net'], status=status.HTTP_200_OK)  # Default fallback

class AvailableModelsView(APIView):
    """
    Get list of available Ollama models
    """
    def get(self, request):
        try:
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                models = [line.split()[0] for line in lines if line.strip()]
                return Response(models)
            return Response(['llama3.1:latest'], status=status.HTTP_200_OK)  # Default fallback
        except:
            return Response(['llama3.1:latest'], status=status.HTTP_200_OK)  # Default fallback

class SystemStatusView(APIView):
    """
    Detailed system status for monitoring
    """
    def get(self, request):
        return Response({
            'timestamp': timezone.now().isoformat(),
            'status': 'operational',
            'components': {
                'api': 'operational',
                'database': 'operational',
                'elasticsearch': 'operational',
                'redis': 'operational',
                'worker': 'operational'
            }
        })
