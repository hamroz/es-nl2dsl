"""
API Views for Session Management and Security Policies
Provides comprehensive session control and security policy management
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.core.paginator import Paginator

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from .models import CustomUser, UserSession, AuditLog, SecurityPolicy
from .session_manager import SessionManager
from .security_policies import SecurityPolicyEngine

User = get_user_model()
logger = logging.getLogger(__name__)


class SessionListView(APIView):
    """List and filter user sessions"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get filtered list of sessions"""
        
        # Check admin permissions for viewing all sessions
        if not request.user.can_admin_users:
            # Non-admin users can only see their own sessions
            sessions = UserSession.objects.filter(user=request.user)
        else:
            sessions = UserSession.objects.all()
        
        # Apply filters
        role_filter = request.GET.get('role')
        if role_filter:
            sessions = sessions.filter(user__role=role_filter)
        
        security_level = request.GET.get('security_level')
        if security_level:
            sessions = sessions.filter(security_level=security_level)
        
        if request.GET.get('suspicious_only') == 'true':
            sessions = sessions.filter(is_suspicious=True)
        
        if request.GET.get('include_terminated') != 'true':
            sessions = sessions.filter(is_terminated=False)
        
        # Order by most recent activity
        sessions = sessions.select_related('user').order_by('-last_activity', '-created_at')
        
        # Paginate
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        paginator = Paginator(sessions, page_size)
        page_obj = paginator.get_page(page)
        
        # Serialize sessions
        session_data = []
        for session in page_obj:
            session_data.append({
                'id': str(session.id),
                'session_id': session.session_id,
                'user': {
                    'id': str(session.user.id),
                    'username': session.user.username,
                    'email': session.user.email,
                    'role': session.user.role,
                },
                'ip_address': session.ip_address,
                'user_agent': session.user_agent,
                'browser': session.browser,
                'os': session.os,
                'device': session.device,
                'location_country': session.location_country,
                'location_city': session.location_city,
                'security_level': session.security_level,
                'risk_score': session.risk_score,
                'is_suspicious': session.is_suspicious,
                'request_count': session.request_count,
                'created_at': session.created_at.isoformat(),
                'last_activity': session.last_activity.isoformat() if session.last_activity else None,
                'expires_at': session.expires_at.isoformat(),
                'is_terminated': session.is_terminated,
                'terminated_at': session.terminated_at.isoformat() if session.terminated_at else None,
                'termination_reason': session.termination_reason,
                'session_duration': str(session.session_duration) if hasattr(session, 'session_duration') else None,
            })
        
        return Response({
            'sessions': session_data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        })


class SessionDetailView(APIView):
    """Get details for a specific session"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, session_id):
        """Get session details"""
        
        try:
            if request.user.can_admin_users:
                session = UserSession.objects.select_related('user').get(session_id=session_id)
            else:
                session = UserSession.objects.select_related('user').get(
                    session_id=session_id, 
                    user=request.user
                )
            
            # Get session validation info
            session_manager = SessionManager()
            validation = session_manager.validate_session(session, request)
            
            session_data = {
                'id': str(session.id),
                'session_id': session.session_id,
                'user': {
                    'id': str(session.user.id),
                    'username': session.user.username,
                    'email': session.user.email,
                    'role': session.user.role,
                },
                'ip_address': session.ip_address,
                'user_agent': session.user_agent,
                'browser': session.browser,
                'os': session.os,
                'device': session.device,
                'location_country': session.location_country,
                'location_city': session.location_city,
                'security_level': session.security_level,
                'risk_score': session.risk_score,
                'is_suspicious': session.is_suspicious,
                'request_count': session.request_count,
                'session_data': json.loads(session.session_data or '{}'),
                'created_at': session.created_at.isoformat(),
                'last_activity': session.last_activity.isoformat() if session.last_activity else None,
                'expires_at': session.expires_at.isoformat(),
                'is_terminated': session.is_terminated,
                'terminated_at': session.terminated_at.isoformat() if session.terminated_at else None,
                'termination_reason': session.termination_reason,
                'validation': validation,
                'is_active': session.is_active,
                'session_duration': str(session.session_duration),
            }
            
            return Response(session_data)
            
        except UserSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class SessionTerminateView(APIView):
    """Terminate a specific session"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, session_id):
        """Terminate session"""
        
        try:
            if request.user.can_admin_users:
                session = UserSession.objects.get(session_id=session_id)
            else:
                session = UserSession.objects.get(
                    session_id=session_id, 
                    user=request.user
                )
            
            reason = request.data.get('reason', 'user_terminated')
            
            session_manager = SessionManager()
            session_manager.terminate_session(session, reason, request.user)
            
            return Response({'message': 'Session terminated successfully'})
            
        except UserSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class UserSessionsTerminateView(APIView):
    """Terminate all sessions for a user"""
    
    permission_classes = [IsAdminUser]
    
    def post(self, request, user_id):
        """Terminate all user sessions"""
        
        try:
            user = CustomUser.objects.get(id=user_id)
            reason = request.data.get('reason', 'admin_action')
            except_session = request.data.get('except_session_id')
            
            session_manager = SessionManager()
            terminated_count = session_manager.terminate_all_user_sessions(
                user, except_session, reason
            )
            
            return Response({
                'message': f'Terminated {terminated_count} sessions for user {user.username}'
            })
            
        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class SessionAnalyticsView(APIView):
    """Get session analytics and statistics"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get session analytics"""
        
        days = int(request.GET.get('days', 30))
        user_filter = None
        
        # Non-admin users can only see their own analytics
        if not request.user.can_admin_users:
            user_filter = request.user
        
        session_manager = SessionManager()
        analytics = session_manager.get_session_analytics(user_filter, days)
        
        return Response(analytics)


class SecurityPolicyListView(APIView):
    """List and manage security policies"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Get list of security policies"""
        
        policies = SecurityPolicy.objects.all().order_by('priority', 'name')
        
        policy_type = request.GET.get('policy_type')
        if policy_type:
            policies = policies.filter(policy_type=policy_type)
        
        user_role = request.GET.get('user_role')
        if user_role:
            policies = policies.filter(user_role=user_role)
        
        is_active = request.GET.get('is_active')
        if is_active is not None:
            policies = policies.filter(is_active=is_active.lower() == 'true')
        
        policy_data = []
        for policy in policies:
            policy_data.append({
                'id': str(policy.id),
                'name': policy.name,
                'description': policy.description,
                'policy_type': policy.policy_type,
                'user_role': policy.user_role,
                'priority': policy.priority,
                'policy_config': policy.policy_config,
                'is_active': policy.is_active,
                'created_by': policy.created_by.username if policy.created_by else None,
                'created_at': policy.created_at.isoformat(),
                'updated_at': policy.updated_at.isoformat(),
            })
        
        return Response({'policies': policy_data})
    
    def post(self, request):
        """Create new security policy"""
        
        data = request.data
        
        try:
            policy = SecurityPolicy.objects.create(
                name=data['name'],
                description=data.get('description', ''),
                policy_type=data['policy_type'],
                user_role=data.get('user_role', 'all'),
                priority=data.get('priority', 100),
                policy_config=data['policy_config'],
                is_active=data.get('is_active', True),
                created_by=request.user,
            )
            
            # Log policy creation
            AuditLog.objects.create(
                user=request.user,
                event_type='security_policy_created',
                resource_type='security_policy',
                resource_id=str(policy.id),
                description=f'Created security policy: {policy.name}',
                metadata={'policy_type': policy.policy_type},
            )
            
            return Response(
                {'id': str(policy.id), 'message': 'Policy created successfully'},
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            return Response(
                {'error': f'Failed to create policy: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class SecurityPolicyDetailView(APIView):
    """Get, update, or delete a specific security policy"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request, policy_id):
        """Get policy details"""
        
        try:
            policy = SecurityPolicy.objects.get(id=policy_id)
            
            return Response({
                'id': str(policy.id),
                'name': policy.name,
                'description': policy.description,
                'policy_type': policy.policy_type,
                'user_role': policy.user_role,
                'priority': policy.priority,
                'policy_config': policy.policy_config,
                'is_active': policy.is_active,
                'created_by': policy.created_by.username if policy.created_by else None,
                'created_at': policy.created_at.isoformat(),
                'updated_at': policy.updated_at.isoformat(),
            })
            
        except SecurityPolicy.DoesNotExist:
            return Response(
                {'error': 'Policy not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def patch(self, request, policy_id):
        """Update policy"""
        
        try:
            policy = SecurityPolicy.objects.get(id=policy_id)
            data = request.data
            
            if 'name' in data:
                policy.name = data['name']
            if 'description' in data:
                policy.description = data['description']
            if 'policy_type' in data:
                policy.policy_type = data['policy_type']
            if 'user_role' in data:
                policy.user_role = data['user_role']
            if 'priority' in data:
                policy.priority = data['priority']
            if 'policy_config' in data:
                policy.policy_config = data['policy_config']
            if 'is_active' in data:
                policy.is_active = data['is_active']
            
            policy.save()
            
            # Log policy update
            AuditLog.objects.create(
                user=request.user,
                event_type='security_policy_updated',
                resource_type='security_policy',
                resource_id=str(policy.id),
                description=f'Updated security policy: {policy.name}',
                metadata={'changes': list(data.keys())},
            )
            
            return Response({'message': 'Policy updated successfully'})
            
        except SecurityPolicy.DoesNotExist:
            return Response(
                {'error': 'Policy not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request, policy_id):
        """Delete policy"""
        
        try:
            policy = SecurityPolicy.objects.get(id=policy_id)
            policy_name = policy.name
            
            policy.delete()
            
            # Log policy deletion
            AuditLog.objects.create(
                user=request.user,
                event_type='security_policy_deleted',
                resource_type='security_policy',
                resource_id=policy_id,
                description=f'Deleted security policy: {policy_name}',
            )
            
            return Response({'message': 'Policy deleted successfully'})
            
        except SecurityPolicy.DoesNotExist:
            return Response(
                {'error': 'Policy not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class PolicyEvaluationView(APIView):
    """Test policy evaluation for debugging"""
    
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        """Evaluate policies for a user scenario"""
        
        data = request.data
        user_id = data.get('user_id')
        evaluation_type = data.get('evaluation_type', 'login')  # login, access, session
        context = data.get('context', {})
        
        try:
            user = CustomUser.objects.get(id=user_id)
            policy_engine = SecurityPolicyEngine()
            
            if evaluation_type == 'login':
                results = policy_engine.evaluate_login_policy(user, request, context)
            elif evaluation_type == 'access':
                results = policy_engine.evaluate_access_policy(
                    user, context.get('resource', ''), context.get('action', ''), request, context
                )
            elif evaluation_type == 'session':
                results = policy_engine.evaluate_session_policy(user, context, request)
            else:
                return Response(
                    {'error': 'Invalid evaluation type'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Serialize results
            result_data = []
            for result in results:
                result_data.append({
                    'action': result.action,
                    'reason': result.reason,
                    'metadata': result.metadata,
                    'timestamp': result.timestamp.isoformat(),
                })
            
            return Response({
                'user': user.username,
                'evaluation_type': evaluation_type,
                'context': context,
                'results': result_data,
            })
            
        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class InitializePoliciesView(APIView):
    """Initialize default security policies"""
    
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        """Create default security policies"""
        
        try:
            policy_engine = SecurityPolicyEngine()
            created_policies = policy_engine.create_default_policies()
            
            policy_names = [policy.name for policy in created_policies]
            
            # Log policy initialization
            AuditLog.objects.create(
                user=request.user,
                event_type='security_policies_initialized',
                resource_type='security_policy',
                description=f'Initialized {len(created_policies)} default security policies',
                metadata={'policy_names': policy_names},
            )
            
            return Response({
                'message': f'Created {len(created_policies)} default policies',
                'policies': policy_names,
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to initialize policies: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# URL patterns would include:
# path('sessions/', SessionListView.as_view(), name='session-list'),
# path('sessions/<str:session_id>/', SessionDetailView.as_view(), name='session-detail'),
# path('sessions/<str:session_id>/terminate/', SessionTerminateView.as_view(), name='session-terminate'),
# path('users/<str:user_id>/terminate-sessions/', UserSessionsTerminateView.as_view(), name='user-sessions-terminate'),
# path('session-analytics/', SessionAnalyticsView.as_view(), name='session-analytics'),
# path('security-policies/', SecurityPolicyListView.as_view(), name='security-policy-list'),
# path('security-policies/<str:policy_id>/', SecurityPolicyDetailView.as_view(), name='security-policy-detail'),
# path('policy-evaluation/', PolicyEvaluationView.as_view(), name='policy-evaluation'),
# path('initialize-policies/', InitializePoliciesView.as_view(), name='initialize-policies'),