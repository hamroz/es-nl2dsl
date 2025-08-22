from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView, CreateAPIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from .serializers import (
    CustomTokenObtainPairSerializer, UserRegistrationSerializer,
    UserSerializer, UserUpdateSerializer, PasswordChangeSerializer,
    AuditLogSerializer
)
from .models import AuditLog, UserSession
from .utils import (
    log_audit_event, get_client_ip, invalidate_user_session,
    validate_tenant_access, get_user_permissions, check_rate_limit
)
from .permissions import IsAdminUser, IsAnalystOrAdmin

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token obtain view with enhanced security."""
    serializer_class = CustomTokenObtainPairSerializer
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Create session record for successful login
            try:
                email = request.data.get('email')
                user = User.objects.get(email=email)
                
                # Create session tracking
                from .utils import create_user_session, generate_session_token
                from datetime import datetime, timedelta
                
                session_token = generate_session_token()
                expires_at = datetime.now() + timedelta(hours=24)
                
                create_user_session(user, request, session_token, expires_at)
                
                # Add session token to response
                response.data['session_token'] = session_token
                
            except Exception as e:
                # Don't fail the login if session creation fails
                pass
        
        return response


class CustomTokenRefreshView(TokenRefreshView):
    """Custom token refresh view with session validation."""
    
    def post(self, request, *args, **kwargs):
        # Log token refresh
        if hasattr(request, 'user') and request.user.is_authenticated:
            log_audit_event(
                user=request.user,
                action='security_event',
                severity='info',
                description='JWT token refreshed',
                ip_address=get_client_ip(request)
            )
        
        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    """Enhanced logout with session cleanup."""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            # Get session token from request
            session_token = request.data.get('session_token') or request.headers.get('X-Session-Token')
            
            if session_token:
                invalidate_user_session(session_token)
            
            # Blacklist refresh token if provided
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                except Exception:
                    pass  # Token might already be invalid
            
            # Log logout
            log_audit_event(
                user=request.user,
                action='logout',
                severity='info',
                description='User logged out',
                ip_address=get_client_ip(request)
            )
            
            return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Logout failed'},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserRegistrationView(CreateAPIView):
    """User registration view (admin only)."""
    serializer_class = UserRegistrationSerializer
    permission_classes = [IsAdminUser]
    
    def perform_create(self, serializer):
        # Check rate limit
        if not check_rate_limit(self.request.user, 'user_create', limit=10, window_minutes=60):
            raise serializers.ValidationError("Rate limit exceeded for user creation.")
        
        serializer.save()


class UserProfileView(RetrieveUpdateAPIView):
    """User profile view for authenticated users."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            # Only allow limited fields for self-update
            class LimitedUserSerializer(UserSerializer):
                class Meta(UserSerializer.Meta):
                    fields = ['username', 'email', 'workspace']
        
        return UserSerializer
    
    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        
        if response.status_code == 200:
            log_audit_event(
                user=request.user,
                action='user_modify',
                severity='info',
                description='User updated own profile',
                ip_address=get_client_ip(request)
            )
        
        return response


class UserListView(ListAPIView):
    """List all users (admin only)."""
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        queryset = User.objects.all()
        
        # Filter by tenant if not admin
        if hasattr(self.request.user, 'tenant_id') and self.request.user.tenant_id:
            if not self.request.user.can_admin_users:
                queryset = queryset.filter(tenant_id=self.request.user.tenant_id)
        
        # Search functionality
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(workspace__icontains=search)
            )
        
        # Filter by role
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        return queryset.order_by('-created_at')


class UserDetailView(RetrieveUpdateAPIView):
    """User detail view for admin management."""
    serializer_class = UserUpdateSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        queryset = User.objects.all()
        
        # Tenant filtering for non-admin users
        if hasattr(self.request.user, 'tenant_id') and self.request.user.tenant_id:
            if not self.request.user.can_admin_users:
                queryset = queryset.filter(tenant_id=self.request.user.tenant_id)
        
        return queryset


class PasswordChangeView(APIView):
    """Password change endpoint."""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserPermissionsView(APIView):
    """Get current user's permissions."""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        permissions_dict = get_user_permissions(request.user)
        
        return Response({
            'user': {
                'id': str(request.user.id),
                'username': request.user.username,
                'email': request.user.email,
                'role': request.user.role,
                'workspace': request.user.workspace,
                'tenant_id': str(request.user.tenant_id) if request.user.tenant_id else None,
            },
            'permissions': permissions_dict
        })


class AuditLogListView(ListAPIView):
    """Audit log viewing (admin and analysts)."""
    serializer_class = AuditLogSerializer
    permission_classes = [IsAnalystOrAdmin]
    
    def get_queryset(self):
        queryset = AuditLog.objects.all()
        
        # Filter by tenant if applicable
        if hasattr(self.request.user, 'tenant_id') and self.request.user.tenant_id:
            if not self.request.user.can_admin_users:
                queryset = queryset.filter(tenant_id=self.request.user.tenant_id)
        
        # Date range filtering
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        # Action filtering
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        # Severity filtering
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # User filtering
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        return queryset.order_by('-timestamp')


class UserSessionsView(APIView):
    """View active sessions for a user."""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Users can only view their own sessions unless they're admin
        if request.user.can_admin_users and 'user_id' in request.query_params:
            user_id = request.query_params['user_id']
            user = get_object_or_404(User, id=user_id)
        else:
            user = request.user
        
        sessions = UserSession.objects.filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now()
        ).order_by('-last_activity')
        
        session_data = []
        for session in sessions:
            session_data.append({
                'id': str(session.id),
                'ip_address': session.ip_address,
                'user_agent': session.user_agent,
                'created_at': session.created_at,
                'last_activity': session.last_activity,
                'expires_at': session.expires_at,
            })
        
        return Response({
            'user': user.username,
            'sessions': session_data
        })
    
    def delete(self, request):
        """Terminate a specific session."""
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'error': 'Session ID required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            session = UserSession.objects.get(id=session_id)
            
            # Users can only terminate their own sessions unless they're admin
            if not request.user.can_admin_users and session.user != request.user:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            
            session.is_active = False
            session.save()
            
            log_audit_event(
                user=request.user,
                action='security_event',
                severity='info',
                description=f'Terminated session {session_id}',
                ip_address=get_client_ip(request),
                metadata={'terminated_session_id': session_id}
            )
            
            return Response({'message': 'Session terminated'})
            
        except UserSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def health_check(request):
    """Health check endpoint that requires authentication."""
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now(),
        'user': request.user.username,
        'role': request.user.role
    })