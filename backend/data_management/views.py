from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from elasticsearch import Elasticsearch
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class DataUploadView(APIView):
    def post(self, request):
        return Response({'status': 'uploaded'})

class IndicesView(APIView):
    def get(self, request):
        return Response(['logs_net', 'logs_cic_ids2017'])

class CICProcessView(APIView):
    def post(self, request):
        return Response({'task_id': 'cic_process_001', 'status': 'started'})

class IndexDetailView(APIView):
    """
    Handle individual index operations including deletion
    """
    def delete(self, request, index_name):
        try:
            # Initialize Elasticsearch client
            es = Elasticsearch(
                hosts=['localhost:9200'],
                http_auth=('elastic', 'ChangeMe_123'),
                verify_certs=False,
                ssl_show_warn=False
            )
            
            # Check if index exists
            if not es.indices.exists(index=index_name):
                return Response(
                    {'error': f'Index {index_name} does not exist'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Delete the index
            es.indices.delete(index=index_name)
            
            logger.info(f"Index {index_name} deleted successfully")
            return Response({
                'message': f'Index {index_name} deleted successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error deleting index {index_name}: {str(e)}")
            return Response(
                {'error': f'Failed to delete index: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DataTasksView(APIView):
    """
    CRITICAL: Data ingestion tasks endpoint that frontend expects
    """
    def get(self, request):
        # Mock data structure matching frontend expectations
        # TODO: Replace with actual task tracking
        return Response([])
