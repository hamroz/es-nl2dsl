from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.db import models
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from .models import EvaluationScenario, EvaluationRun, EvaluationBatch
from .serializers import (
    EvaluationScenarioSerializer,
    EvaluationRunSerializer, 
    EvaluationBatchSerializer,
    RunEvaluationRequestSerializer,
    BatchEvaluationRequestSerializer
)
from .utils import (
    calculate_ast_similarity,
    execute_query_for_evaluation,
    calculate_execution_metrics,
    run_validation_for_evaluation
)
from django.conf import settings


class EvaluationScenarioListView(generics.ListAPIView):
    """List all evaluation scenarios"""
    queryset = EvaluationScenario.objects.filter(is_active=True)
    serializer_class = EvaluationScenarioSerializer


class EvaluationRunListView(generics.ListAPIView):
    """List evaluation runs with optional filtering by scenario"""
    serializer_class = EvaluationRunSerializer
    
    def get_queryset(self):
        queryset = EvaluationRun.objects.all()
        scenario_id = self.request.query_params.get('scenario_id')
        method = self.request.query_params.get('method')
        
        if scenario_id:
            queryset = queryset.filter(scenario__scenario_id=scenario_id)
        if method:
            queryset = queryset.filter(method=method)
            
        return queryset


class EvaluationBatchListView(generics.ListAPIView):
    """List evaluation batches"""
    queryset = EvaluationBatch.objects.all()
    serializer_class = EvaluationBatchSerializer


@api_view(['POST'])
def run_scenario_evaluation(request, scenario_id):
    """Run evaluation for a single scenario"""
    try:
        scenario = get_object_or_404(EvaluationScenario, scenario_id=scenario_id)
        
        # Validate request data
        serializer = RunEvaluationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        method = validated_data['method']
        model = validated_data.get('model', '')
        index = validated_data.get('index', scenario.index)
        
        # Create evaluation run
        run = EvaluationRun.objects.create(
            run_id=str(uuid.uuid4()),
            scenario=scenario,
            method=method,
            model=model,
            status='running',
            generated_query={},
            generation_time=0.0,
            validation_passed=False
        )
        
        # Run query generation
        try:
            generated_query, generation_time = generate_query_for_evaluation(
                scenario.prompt, method, model
            )
            
            # Update run with generated query
            run.generated_query = generated_query
            run.generation_time = generation_time
            
            # Run validation
            validation_result = run_validation_for_evaluation(generated_query)
            run.validation_passed = validation_result['valid']
            run.validation_errors = validation_result['errors']
            
            # Calculate AST similarity
            ast_metrics = calculate_ast_similarity(scenario.expert_query, generated_query)
            run.jaccard_similarity = ast_metrics.get('jaccard_similarity', 0.0)
            run.structural_similarity = ast_metrics.get('clause_f1', 0.0)
            
            # Execute both queries for execution comparison
            expert_results = execute_query_for_evaluation(scenario.expert_query, index)
            generated_results = execute_query_for_evaluation(generated_query, index)
            
            # Calculate execution metrics
            exec_metrics = calculate_execution_metrics(expert_results, generated_results)
            
            run.expert_result_count = expert_results.get('total_hits', 0)
            run.generated_result_count = generated_results.get('total_hits', 0)
            run.execution_time_expert = expert_results.get('execution_time_ms', 0)
            run.execution_time_generated = generated_results.get('execution_time_ms', 0)
            run.f1_score = exec_metrics.get('f1_score', 0.0)
            run.precision = exec_metrics.get('precision', 0.0)
            run.recall = exec_metrics.get('recall', 0.0)
            
            run.status = 'completed'
            run.save()
            
            return Response(EvaluationRunSerializer(run).data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            run.status = 'failed'
            run.error_message = str(e)
            run.save()
            return Response(
                {'error': f'Evaluation failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        return Response(
            {'error': f'Failed to run evaluation: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def run_batch_evaluation(request):
    """Run batch evaluation across multiple scenarios"""
    try:
        # Validate request data
        serializer = BatchEvaluationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        method = validated_data['method']
        model = validated_data.get('model', '')
        scenario_ids = validated_data.get('scenario_ids', [])
        
        # Get scenarios to evaluate
        if scenario_ids:
            scenarios = EvaluationScenario.objects.filter(
                scenario_id__in=scenario_ids, is_active=True
            )
        else:
            scenarios = EvaluationScenario.objects.filter(is_active=True)
        
        if not scenarios.exists():
            return Response(
                {'error': 'No active scenarios found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create batch
        batch = EvaluationBatch.objects.create(
            batch_id=str(uuid.uuid4()),
            name=validated_data['name'],
            description=validated_data.get('description', ''),
            method=method,
            model=model,
            total_scenarios=scenarios.count(),
            status='running'
        )
        
        # Run evaluations for each scenario
        completed_runs = []
        for scenario in scenarios:
            try:
                # Generate query
                generated_query, generation_time = generate_query_for_evaluation(
                    scenario.prompt, method, model
                )
                
                # Create run
                run = EvaluationRun.objects.create(
                    run_id=str(uuid.uuid4()),
                    scenario=scenario,
                    method=method,
                    model=model,
                    generated_query=generated_query,
                    generation_time=generation_time,
                    status='running'
                )
                
                # Validate query
                validation_result = run_validation_for_evaluation(generated_query)
                run.validation_passed = validation_result['valid']
                run.validation_errors = validation_result['errors']
                
                # Calculate metrics
                ast_metrics = calculate_ast_similarity(scenario.expert_query, generated_query)
                run.jaccard_similarity = ast_metrics.get('jaccard_similarity', 0.0)
                run.structural_similarity = ast_metrics.get('clause_f1', 0.0)
                
                # Execute queries
                expert_results = execute_query_for_evaluation(scenario.expert_query, scenario.index)
                generated_results = execute_query_for_evaluation(generated_query, scenario.index)
                
                exec_metrics = calculate_execution_metrics(expert_results, generated_results)
                
                run.expert_result_count = expert_results.get('total_hits', 0)
                run.generated_result_count = generated_results.get('total_hits', 0)
                run.execution_time_expert = expert_results.get('execution_time_ms', 0)
                run.execution_time_generated = generated_results.get('execution_time_ms', 0)
                run.f1_score = exec_metrics.get('f1_score', 0.0)
                run.precision = exec_metrics.get('precision', 0.0)
                run.recall = exec_metrics.get('recall', 0.0)
                
                run.status = 'completed'
                run.save()
                completed_runs.append(run)
                
            except Exception as e:
                run.status = 'failed'
                run.error_message = str(e)
                run.save()
        
        # Calculate batch metrics
        if completed_runs:
            batch.completed_scenarios = len(completed_runs)
            batch.average_f1_score = sum(r.f1_score or 0 for r in completed_runs) / len(completed_runs)
            batch.average_jaccard_similarity = sum(r.jaccard_similarity or 0 for r in completed_runs) / len(completed_runs)
            batch.validation_pass_rate = sum(1 for r in completed_runs if r.validation_passed) / len(completed_runs)
        
        batch.status = 'completed'
        batch.completed_at = timezone.now()
        batch.save()
        
        return Response(EvaluationBatchSerializer(batch).data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': f'Batch evaluation failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_evaluation_metrics(request):
    """Get aggregate evaluation metrics"""
    try:
        total_runs = EvaluationRun.objects.count()
        completed_runs = EvaluationRun.objects.filter(status='completed')
        
        if not completed_runs.exists():
            return Response({
                'total_runs': total_runs,
                'completed_runs': 0,
                'metrics': {}
            })
        
        # Calculate aggregate metrics
        metrics = {
            'total_runs': total_runs,
            'completed_runs': completed_runs.count(),
            'average_f1_score': completed_runs.aggregate(models.Avg('f1_score'))['f1_score__avg'] or 0,
            'average_jaccard_similarity': completed_runs.aggregate(models.Avg('jaccard_similarity'))['jaccard_similarity__avg'] or 0,
            'validation_pass_rate': completed_runs.filter(validation_passed=True).count() / completed_runs.count(),
            'method_breakdown': {}
        }
        
        # Method breakdown
        for method in ['constrained', 'rules', 'zeroshot']:
            method_runs = completed_runs.filter(method=method)
            if method_runs.exists():
                metrics['method_breakdown'][method] = {
                    'count': method_runs.count(),
                    'avg_f1': method_runs.aggregate(models.Avg('f1_score'))['f1_score__avg'] or 0,
                    'avg_jaccard': method_runs.aggregate(models.Avg('jaccard_similarity'))['jaccard_similarity__avg'] or 0
                }
        
        return Response(metrics)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to get metrics: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def generate_query_for_evaluation(prompt, method, model=''):
    """Generate query using the specified method"""
    import time
    
    project_root = settings.BASE_DIR.parent
    
    # Create temporary file for the prompt
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(prompt)
        prompt_file = f.name
    
    # Generate unique output filename
    output_file = str(project_root / "artifacts" / "generated" / f"eval_{uuid.uuid4().hex[:8]}.json")
    
    try:
        start_time = time.time()
        
        if method == 'constrained':
            cmd = [
                sys.executable,
                str(project_root / "src" / "generate_constrained.py"),
                "--prompt", prompt_file,
                "--out", output_file
            ]
            if model:
                cmd.extend(["--model", model])
                
        elif method == 'rules':
            cmd = [
                sys.executable,
                str(project_root / "src" / "baseline_rules.py"),
                "--prompt", prompt_file,
                "--out", output_file
            ]
            
        elif method == 'zeroshot':
            cmd = [
                sys.executable,
                str(project_root / "src" / "baseline_zeroshot.py"),
                "--prompt", prompt_file,
                "--out", output_file
            ]
            if model:
                cmd.extend(["--model", model])
        else:
            raise ValueError(f"Unknown method: {method}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(project_root)
        )
        
        generation_time = time.time() - start_time
        
        if result.returncode != 0:
            raise RuntimeError(f"Query generation failed: {result.stderr}")
        
        # Load generated query (handle different script behaviors)
        if Path(output_file).is_file():
            # Direct file output
            with open(output_file, 'r') as f:
                generated_query = json.load(f)
        elif Path(output_file).is_dir():
            # Some scripts create a directory with the result inside
            result_files = list(Path(output_file).glob('*_generated.json'))
            if result_files:
                with open(result_files[0], 'r') as f:
                    generated_query = json.load(f)
            else:
                raise RuntimeError("No generated query file found in output directory")
        else:
            raise RuntimeError(f"Output file not found: {output_file}")
        
        return generated_query, generation_time
        
    finally:
        # Clean up temp files
        Path(prompt_file).unlink(missing_ok=True)
        output_path = Path(output_file)
        if output_path.is_dir():
            import shutil
            shutil.rmtree(output_path, ignore_errors=True)
        else:
            output_path.unlink(missing_ok=True)
