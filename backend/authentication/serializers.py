from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import CustomUser, AuditLog
from .utils import log_audit_event
from django.utils import timezone
from datetime import timedelta


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with enhanced security."""
    
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove username field, use email instead
        self.fields.pop('username', None)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if not email or not password:
            raise serializers.ValidationError('Email and password are required.')
        
        # Get user by email
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            # Log failed login attempt
            log_audit_event(
                user=None,
                action='login',
                severity='warning',
                description=f'Failed login attempt for non-existent email: {email}',
                ip_address=self.context.get('request').META.get('REMOTE_ADDR'),
                metadata={'email': email}
            )
            raise serializers.ValidationError('Invalid credentials.')
        
        # Check if account is locked
        if user.is_locked_out:
            if user.lockout_until and timezone.now() < user.lockout_until:
                log_audit_event(
                    user=user,
                    action='login',
                    severity='warning',
                    description='Attempted login to locked account',
                    ip_address=self.context.get('request').META.get('REMOTE_ADDR')
                )
                raise serializers.ValidationError('Account is temporarily locked due to too many failed attempts.')
            else:
                # Reset lockout if time has expired
                user.is_locked_out = False
                user.lockout_until = None
                user.failed_login_attempts = 0
                user.save()
        
        # Authenticate user (using email as USERNAME_FIELD)
        user = authenticate(username=email, password=password)
        if not user:
            # Update failed login attempts
            failed_user = CustomUser.objects.get(email=email)
            failed_user.failed_login_attempts += 1
            failed_user.last_failed_login = timezone.now()
            
            # Lock account after 5 failed attempts
            if failed_user.failed_login_attempts >= 5:
                failed_user.is_locked_out = True
                failed_user.lockout_until = timezone.now() + timedelta(minutes=30)
                
                log_audit_event(
                    user=failed_user,
                    action='security_event',
                    severity='critical',
                    description='Account locked due to repeated failed login attempts',
                    ip_address=self.context.get('request').META.get('REMOTE_ADDR')
                )
            
            failed_user.save()
            
            log_audit_event(
                user=failed_user,
                action='login',
                severity='warning',
                description='Failed login attempt with incorrect password',
                ip_address=self.context.get('request').META.get('REMOTE_ADDR')
            )
            raise serializers.ValidationError('Invalid credentials.')
        
        if not user.is_active:
            log_audit_event(
                user=user,
                action='login',
                severity='warning',
                description='Attempted login to inactive account',
                ip_address=self.context.get('request').META.get('REMOTE_ADDR')
            )
            raise serializers.ValidationError('Account is deactivated.')
        
        # Reset failed attempts on successful authentication
        user.failed_login_attempts = 0
        user.last_activity = timezone.now()
        user.save()
        
        # Log successful login
        log_audit_event(
            user=user,
            action='login',
            severity='info',
            description='Successful login',
            ip_address=self.context.get('request').META.get('REMOTE_ADDR')
        )
        
        # Use email as username for token generation
        attrs['username'] = user.username
        return super().validate(attrs)
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['email'] = user.email
        token['role'] = user.role
        token['tenant_id'] = str(user.tenant_id) if user.tenant_id else None
        token['workspace'] = user.workspace
        token['can_admin_users'] = user.can_admin_users
        token['can_modify_queries'] = user.can_modify_queries
        token['is_read_only'] = user.is_read_only
        
        return token


class UserRegistrationSerializer(serializers.ModelSerializer):
    """User registration serializer with validation."""
    
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'password_confirm', 'role', 'workspace']
        extra_kwargs = {
            'role': {'required': True},
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs.get('password_confirm'):
            raise serializers.ValidationError("Passwords don't match.")
        attrs.pop('password_confirm')
        return attrs
    
    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data.get('role', 'viewer'),
            workspace=validated_data.get('workspace', ''),
        )
        
        # Log user creation
        log_audit_event(
            user=self.context.get('request').user if self.context.get('request') else None,
            action='user_create',
            severity='info',
            description=f'Created new user: {user.username}',
            resource_type='user',
            resource_id=str(user.id),
            metadata={'new_user_email': user.email, 'role': user.role}
        )
        
        return user


class UserSerializer(serializers.ModelSerializer):
    """User profile serializer."""
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'role', 'workspace', 'tenant_id',
            'is_active', 'is_mfa_enabled', 'last_activity', 'created_at',
            'can_admin_users', 'can_modify_queries', 'is_read_only'
        ]
        read_only_fields = ['id', 'created_at', 'can_admin_users', 'can_modify_queries', 'is_read_only']


class UserUpdateSerializer(serializers.ModelSerializer):
    """User update serializer for admin use."""
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'role', 'workspace', 'is_active']
    
    def update(self, instance, validated_data):
        old_role = instance.role
        old_active = instance.is_active
        
        user = super().update(instance, validated_data)
        
        # Log role changes
        if old_role != user.role:
            log_audit_event(
                user=self.context.get('request').user,
                action='role_change',
                severity='warning',
                description=f'Changed user role from {old_role} to {user.role}',
                resource_type='user',
                resource_id=str(user.id),
                metadata={
                    'target_user': user.username,
                    'old_role': old_role,
                    'new_role': user.role
                }
            )
        
        # Log activation/deactivation
        if old_active != user.is_active:
            action = 'activated' if user.is_active else 'deactivated'
            log_audit_event(
                user=self.context.get('request').user,
                action='user_modify',
                severity='warning',
                description=f'User account {action}',
                resource_type='user',
                resource_id=str(user.id),
                metadata={'target_user': user.username, 'action': action}
            )
        
        return user


class PasswordChangeSerializer(serializers.Serializer):
    """Password change serializer."""
    
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)
    
    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match.")
        return attrs
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        
        # Log password change
        log_audit_event(
            user=user,
            action='security_event',
            severity='info',
            description='Password changed successfully',
            ip_address=self.context['request'].META.get('REMOTE_ADDR')
        )
        
        return user


class AuditLogSerializer(serializers.ModelSerializer):
    """Audit log serializer for viewing logs."""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user_email', 'user_username', 'action', 'severity',
            'description', 'ip_address', 'endpoint', 'resource_type',
            'resource_id', 'metadata', 'timestamp'
        ]
        read_only_fields = (
            'id', 'user_email', 'user_username', 'action', 'severity',
            'description', 'ip_address', 'endpoint', 'resource_type', 
            'resource_id', 'metadata', 'timestamp'
        )