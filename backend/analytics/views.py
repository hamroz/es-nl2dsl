from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from django.http import HttpResponse
from django.utils import timezone
from django.core.exceptions import ValidationError
from authentication.permissions import IsAnalystOrAdmin, IsAdminUser
from authentication.utils import log_audit_event, get_client_ip
from .models import CustomMetric, MetricData, AlertRule, Alert, AnalyticsSnapshot
from .services import AnalyticsService, CustomMetricsService, AlertingService
from .serializers import (
    CustomMetricSerializer, MetricDataSerializer, 
    AlertRuleSerializer, AlertSerializer, AnalyticsExportSerializer
)
import csv
import json
from io import StringIO
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class AnalyticsAPIView(APIView):
    """Main analytics data endpoint."""
    
    permission_classes = [IsAnalystOrAdmin]
    
    def get(self, request):
        """Get comprehensive analytics data."""
        try:
            # Get parameters
            time_range = request.query_params.get('range', '7d')
            tenant_id = request.query_params.get('tenant_id')
            
            # Validate time range
            valid_ranges = ['1h', '24h', '7d', '30d', '90d']
            if time_range not in valid_ranges:
                return Response(
                    {'error': f'Invalid time range. Must be one of: {valid_ranges}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate tenant access
            if tenant_id and not request.user.can_admin_users:
                if str(request.user.tenant_id) != tenant_id:
                    return Response(
                        {'error': 'Access denied to requested tenant'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            # Generate analytics data
            analytics_service = AnalyticsService()
            analytics_data = analytics_service.get_analytics_data(
                time_range=time_range,
                tenant_id=tenant_id
            )
            
            # Log access
            log_audit_event(
                user=request.user,
                action='system_config',
                severity='info',
                description='Analytics data accessed',
                ip_address=get_client_ip(request),
                endpoint=request.path,
                metadata={
                    'time_range': time_range,
                    'tenant_id': tenant_id
                }
            )
            
            return Response(analytics_data)
            
        except Exception as e:
            logger.error(f"Analytics API error: {e}")
            
            log_audit_event(
                user=request.user,
                action='system_config',
                severity='error',
                description=f'Analytics API error: {str(e)}',
                ip_address=get_client_ip(request),
                endpoint=request.path
            )
            
            return Response(
                {'error': 'Failed to generate analytics data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnalyticsExportView(APIView):
    """Export analytics data in various formats."""
    
    permission_classes = [IsAnalystOrAdmin]
    
    def get(self, request):
        """Export analytics data as CSV or PDF."""
        try:
            # Get parameters
            export_format = request.query_params.get('format', 'csv')
            time_range = request.query_params.get('range', '7d')
            tenant_id = request.query_params.get('tenant_id')
            
            if export_format not in ['csv', 'json', 'pdf']:
                return Response(
                    {'error': 'Invalid format. Must be csv, json, or pdf'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get analytics data
            analytics_service = AnalyticsService()
            analytics_data = analytics_service.get_analytics_data(
                time_range=time_range,
                tenant_id=tenant_id
            )
            
            # Generate export
            if export_format == 'csv':
                response = self._export_csv(analytics_data, time_range)
            elif export_format == 'json':
                response = self._export_json(analytics_data, time_range)
            elif export_format == 'pdf':
                response = self._export_pdf(analytics_data, time_range)
            
            # Log export
            log_audit_event(
                user=request.user,
                action='data_export',
                severity='info',
                description=f'Analytics data exported as {export_format}',
                ip_address=get_client_ip(request),
                endpoint=request.path,
                metadata={
                    'format': export_format,
                    'time_range': time_range,
                    'tenant_id': tenant_id
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Analytics export error: {e}")
            return Response(
                {'error': 'Failed to export analytics data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _export_csv(self, data, time_range):
        """Export data as CSV."""
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Analytics Report', f'Time Range: {time_range}', f'Generated: {timezone.now()}'])
        writer.writerow([])
        
        # User metrics
        writer.writerow(['USER METRICS'])
        user_metrics = data['user_metrics']
        writer.writerow(['Total Users', user_metrics['total_users']])
        writer.writerow(['Active Users (24h)', user_metrics['active_users_24h']])
        writer.writerow(['New Users (7d)', user_metrics['new_users_7d']])
        writer.writerow(['User Growth Rate', f"{user_metrics['user_growth_rate']}%"])
        writer.writerow([])
        
        # Query metrics
        writer.writerow(['QUERY METRICS'])
        query_metrics = data['query_metrics']
        writer.writerow(['Total Queries', query_metrics['total_queries']])
        writer.writerow(['Queries (24h)', query_metrics['queries_24h']])
        writer.writerow(['Avg Response Time', f"{query_metrics['avg_response_time']}ms"])
        writer.writerow(['Success Rate', f"{query_metrics['success_rate']}%"])
        writer.writerow([])
        
        # Security metrics
        writer.writerow(['SECURITY METRICS'])
        security_metrics = data['security_metrics']
        writer.writerow(['Failed Logins (24h)', security_metrics['failed_logins_24h']])
        writer.writerow(['Locked Accounts', security_metrics['locked_accounts']])
        writer.writerow(['Security Events', security_metrics['security_events']])
        writer.writerow(['Threat Level', security_metrics['threat_level']])
        writer.writerow([])
        
        # System metrics
        writer.writerow(['SYSTEM METRICS'])
        system_metrics = data['system_metrics']
        writer.writerow(['Uptime', f"{system_metrics['uptime_percentage']}%"])
        writer.writerow(['CPU Usage', f"{system_metrics['avg_cpu_usage']}%"])
        writer.writerow(['Memory Usage', f"{system_metrics['memory_usage_gb']}GB"])
        writer.writerow(['Active Sessions', system_metrics['active_sessions']])
        writer.writerow(['Error Rate', f"{system_metrics['error_rate']}%"])
        
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="analytics-{time_range}.csv"'
        return response
    
    def _export_json(self, data, time_range):
        """Export data as JSON."""
        response = HttpResponse(
            json.dumps(data, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="analytics-{time_range}.json"'
        return response
    
    def _export_pdf(self, data, time_range):
        """Export data as PDF (placeholder - would use reportlab)."""
        # This would generate a proper PDF report using reportlab
        # For now, returning a simple text response
        content = f"Analytics Report - {time_range}\nGenerated: {timezone.now()}\n\n"
        content += f"This would be a formatted PDF report with charts and tables.\n"
        content += f"Data includes: {len(data)} metric categories"
        
        response = HttpResponse(content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="analytics-{time_range}.pdf"'
        return response


class CustomMetricsView(ListCreateAPIView):
    """Manage custom metrics."""
    
    serializer_class = CustomMetricSerializer
    permission_classes = [IsAnalystOrAdmin]
    
    def get_queryset(self):
        """Get custom metrics based on user permissions."""
        queryset = CustomMetric.objects.filter(is_active=True)
        
        if not self.request.user.can_admin_users:
            # Non-admin users see their own metrics and public ones
            queryset = queryset.filter(
                models.Q(created_by=self.request.user) |
                models.Q(is_public=True)
            )
        
        # Filter by tenant if applicable
        if hasattr(self.request.user, 'tenant_id') and self.request.user.tenant_id:
            queryset = queryset.filter(
                models.Q(tenant_id=self.request.user.tenant_id) |
                models.Q(tenant_id__isnull=True, is_public=True)
            )
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Create custom metric with user context."""
        serializer.save(
            created_by=self.request.user,
            tenant_id=getattr(self.request.user, 'tenant_id', None)
        )
        
        log_audit_event(
            user=self.request.user,
            action='system_config',
            severity='info',
            description='Custom metric created',
            ip_address=get_client_ip(self.request),
            resource_type='custom_metric',
            resource_id=str(serializer.instance.id),
            metadata={'metric_name': serializer.instance.name}
        )


class CustomMetricDetailView(RetrieveUpdateDestroyAPIView):
    """Individual custom metric operations."""
    
    serializer_class = CustomMetricSerializer
    permission_classes = [IsAnalystOrAdmin]
    
    def get_queryset(self):
        return CustomMetric.objects.filter(is_active=True)
    
    def get_object(self):
        """Get custom metric with permission checks."""
        obj = super().get_object()
        
        # Check permissions
        if not self.request.user.can_admin_users:
            if obj.created_by != self.request.user and not obj.is_public:
                raise permissions.PermissionDenied("Access denied to this metric")
        
        return obj
    
    def perform_destroy(self, instance):
        """Soft delete custom metric."""
        instance.is_active = False
        instance.save()
        
        log_audit_event(
            user=self.request.user,
            action='system_config',
            severity='warning',
            description='Custom metric deleted',
            ip_address=get_client_ip(self.request),
            resource_type='custom_metric',
            resource_id=str(instance.id),
            metadata={'metric_name': instance.name}
        )


class ExecuteCustomMetricView(APIView):
    """Execute a custom metric and return results."""
    
    permission_classes = [IsAnalystOrAdmin]
    
    def post(self, request, pk):
        """Execute custom metric."""
        try:
            metric = CustomMetric.objects.get(pk=pk, is_active=True)
            
            # Check permissions
            if not request.user.can_admin_users:
                if metric.created_by != request.user and not metric.is_public:
                    return Response(
                        {'error': 'Access denied to this metric'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            # Execute metric
            service = CustomMetricsService()
            result = service.execute_custom_metric(metric)
            
            log_audit_event(
                user=request.user,
                action='system_config',
                severity='info',
                description='Custom metric executed',
                ip_address=get_client_ip(request),
                resource_type='custom_metric',
                resource_id=str(metric.id),
                metadata={'metric_name': metric.name}
            )
            
            return Response(result)
            
        except CustomMetric.DoesNotExist:
            return Response(
                {'error': 'Metric not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Custom metric execution error: {e}")
            return Response(
                {'error': 'Failed to execute metric'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AlertRulesView(ListCreateAPIView):
    """Manage alert rules."""
    
    serializer_class = AlertRuleSerializer
    permission_classes = [IsAnalystOrAdmin]
    
    def get_queryset(self):
        """Get alert rules based on user permissions."""
        queryset = AlertRule.objects.filter(is_active=True)
        
        if not self.request.user.can_admin_users:
            queryset = queryset.filter(created_by=self.request.user)
        
        if hasattr(self.request.user, 'tenant_id') and self.request.user.tenant_id:
            queryset = queryset.filter(tenant_id=self.request.user.tenant_id)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Create alert rule with user context."""
        serializer.save(
            created_by=self.request.user,
            tenant_id=getattr(self.request.user, 'tenant_id', None)
        )
        
        log_audit_event(
            user=self.request.user,
            action='system_config',
            severity='info',
            description='Alert rule created',
            ip_address=get_client_ip(self.request),
            resource_type='alert_rule',
            resource_id=str(serializer.instance.id),
            metadata={'rule_name': serializer.instance.name}
        )


class AlertsView(ListCreateAPIView):
    """View and manage alerts."""
    
    serializer_class = AlertSerializer
    permission_classes = [IsAnalystOrAdmin]
    
    def get_queryset(self):
        """Get alerts based on user permissions."""
        queryset = Alert.objects.all()
        
        if not self.request.user.can_admin_users:
            queryset = queryset.filter(rule__created_by=self.request.user)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-triggered_at')


class AlertDetailView(RetrieveUpdateDestroyAPIView):
    """Individual alert operations."""
    
    serializer_class = AlertSerializer
    permission_classes = [IsAnalystOrAdmin]
    
    def get_queryset(self):
        return Alert.objects.all()


@api_view(['POST'])
@permission_classes([IsAnalystOrAdmin])
def acknowledge_alert(request, pk):
    """Acknowledge an alert."""
    try:
        alert = Alert.objects.get(pk=pk)
        
        # Check permissions
        if not request.user.can_admin_users:
            if alert.rule.created_by != request.user:
                return Response(
                    {'error': 'Access denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        alert.acknowledge(request.user)
        
        log_audit_event(
            user=request.user,
            action='system_config',
            severity='info',
            description='Alert acknowledged',
            ip_address=get_client_ip(request),
            resource_type='alert',
            resource_id=str(alert.id)
        )
        
        return Response({'message': 'Alert acknowledged'})
        
    except Alert.DoesNotExist:
        return Response(
            {'error': 'Alert not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAnalystOrAdmin])
def resolve_alert(request, pk):
    """Resolve an alert."""
    try:
        alert = Alert.objects.get(pk=pk)
        
        # Check permissions
        if not request.user.can_admin_users:
            if alert.rule.created_by != request.user:
                return Response(
                    {'error': 'Access denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        alert.resolve()
        
        log_audit_event(
            user=request.user,
            action='system_config',
            severity='info',
            description='Alert resolved',
            ip_address=get_client_ip(request),
            resource_type='alert',
            resource_id=str(alert.id)
        )
        
        return Response({'message': 'Alert resolved'})
        
    except Alert.DoesNotExist:
        return Response(
            {'error': 'Alert not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAnalystOrAdmin])
def analytics_summary(request):
    """Get analytics summary for dashboard widgets."""
    try:
        # Get cached summary or generate new one
        from django.core.cache import cache
        cache_key = f"analytics_summary_{request.user.tenant_id or 'global'}"
        
        summary = cache.get(cache_key)
        if not summary:
            analytics_service = AnalyticsService()
            data = analytics_service.get_analytics_data('24h')
            
            summary = {
                'active_users': data['user_metrics']['active_users_24h'],
                'queries_today': data['query_metrics']['queries_24h'],
                'success_rate': data['query_metrics']['success_rate'],
                'threat_level': data['security_metrics']['threat_level'],
                'uptime': data['system_metrics']['uptime_percentage'],
                'last_updated': timezone.now().isoformat()
            }
            
            cache.set(cache_key, summary, 300)  # Cache for 5 minutes
        
        return Response(summary)
        
    except Exception as e:
        logger.error(f"Analytics summary error: {e}")
        return Response(
            {'error': 'Failed to generate summary'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )