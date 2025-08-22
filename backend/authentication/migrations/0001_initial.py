# Generated migration for authentication app

from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import migrations, models
import django.contrib.auth.models
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomUser',
            fields=[
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(error_messages={'unique': 'A user with that username already exists.'}, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, unique=True, validators=[UnicodeUsernameValidator()], verbose_name='username')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('role', models.CharField(choices=[('admin', 'Administrator'), ('analyst', 'Security Analyst'), ('viewer', 'Read-Only Viewer')], default='viewer', max_length=20)),
                ('tenant_id', models.UUIDField(blank=True, help_text='Tenant for data isolation', null=True)),
                ('workspace', models.CharField(blank=True, help_text='User workspace identifier', max_length=100)),
                ('is_mfa_enabled', models.BooleanField(default=False)),
                ('failed_login_attempts', models.PositiveIntegerField(default=0)),
                ('last_failed_login', models.DateTimeField(blank=True, null=True)),
                ('is_locked_out', models.BooleanField(default=False)),
                ('lockout_until', models.DateTimeField(blank=True, null=True)),
                ('last_activity', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'db_table': 'auth_users',
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(choices=[('login', 'User Login'), ('logout', 'User Logout'), ('query_generate', 'Query Generation'), ('query_execute', 'Query Execution'), ('data_export', 'Data Export'), ('user_create', 'User Creation'), ('user_modify', 'User Modification'), ('user_delete', 'User Deletion'), ('role_change', 'Role Change'), ('system_config', 'System Configuration'), ('security_event', 'Security Event')], max_length=50)),
                ('severity', models.CharField(choices=[('info', 'Information'), ('warning', 'Warning'), ('error', 'Error'), ('critical', 'Critical')], default='info', max_length=20)),
                ('description', models.TextField()),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('endpoint', models.CharField(blank=True, max_length=255)),
                ('resource_type', models.CharField(blank=True, max_length=100)),
                ('resource_id', models.CharField(blank=True, max_length=100)),
                ('tenant_id', models.UUIDField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, to='authentication.customuser')),
            ],
            options={
                'db_table': 'audit_logs',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='UserSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('session_token', models.CharField(max_length=255, unique=True)),
                ('ip_address', models.GenericIPAddressField()),
                ('user_agent', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_activity', models.DateTimeField(auto_now=True)),
                ('expires_at', models.DateTimeField()),
                ('is_active', models.BooleanField(default=True)),
                ('user', models.ForeignKey(on_delete=models.CASCADE, related_name='sessions', to='authentication.customuser')),
            ],
            options={
                'db_table': 'auth_user_sessions',
            },
        ),
        migrations.AddIndex(
            model_name='usersession',
            index=models.Index(fields=['user', 'is_active'], name='auth_user_s_user_id_f87b7d_idx'),
        ),
        migrations.AddIndex(
            model_name='usersession',
            index=models.Index(fields=['expires_at'], name='auth_user_s_expires_d2e18f_idx'),
        ),
        migrations.AddIndex(
            model_name='usersession',
            index=models.Index(fields=['session_token'], name='auth_user_s_session_3e9f47_idx'),
        ),
        migrations.AddIndex(
            model_name='customuser',
            index=models.Index(fields=['tenant_id'], name='auth_users_tenant__2b8cf9_idx'),
        ),
        migrations.AddIndex(
            model_name='customuser',
            index=models.Index(fields=['role'], name='auth_users_role_6b81ff_idx'),
        ),
        migrations.AddIndex(
            model_name='customuser',
            index=models.Index(fields=['is_active', 'is_locked_out'], name='auth_users_is_acti_f6e0ef_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['user', 'timestamp'], name='audit_logs_user_id_1da6a9_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['action', 'timestamp'], name='audit_logs_action_b3a9a1_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['severity', 'timestamp'], name='audit_logs_severit_b8cf42_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['tenant_id', 'timestamp'], name='audit_logs_tenant__7f2e5a_idx'),
        ),
    ]