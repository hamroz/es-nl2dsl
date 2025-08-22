from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class ScenarioListView(APIView):
    def get(self, request):
        return Response([])

class RunEvaluationView(APIView):
    def post(self, request, scenario_id):
        return Response({'test_id': 'eval_001', 'status': 'started'})

class EvaluationResultsView(APIView):
    def get(self, request):
        return Response([])
