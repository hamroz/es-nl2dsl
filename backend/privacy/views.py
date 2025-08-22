from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class DPConfigView(APIView):
    def post(self, request):
        return Response({'status': 'configured'})

class PrivacyAnalysisView(APIView):
    def get(self, request):
        return Response({'analysis': 'pending'})
