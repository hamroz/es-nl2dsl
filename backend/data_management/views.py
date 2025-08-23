from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class DataUploadView(APIView):
    def post(self, request):
        return Response({'status': 'uploaded'})

class IndicesView(APIView):
    def get(self, request):
        return Response(['logs_net', 'logs_cic_ids2017'])

class CICProcessView(APIView):
    def post(self, request):
        return Response({'task_id': 'cic_process_001', 'status': 'started'})

class DataTasksView(APIView):
    """
    CRITICAL: Data ingestion tasks endpoint that frontend expects
    """
    def get(self, request):
        # Mock data structure matching frontend expectations
        # TODO: Replace with actual task tracking
        return Response([])
