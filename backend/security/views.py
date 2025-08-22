from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class SecurityTestView(APIView):
    def post(self, request):
        return Response({'test_id': 'security_001', 'total_prompts': 0})

class SecurityTestResultView(APIView):
    def get(self, request, test_id):
        return Response({'test_id': test_id, 'status': 'completed', 'results': {}})
