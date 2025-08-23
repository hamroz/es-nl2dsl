# API Audit Report - ES-NL2DSL System

## Backend Endpoints Available

### Authentication Module (`/api/v1/auth/`)
- ✅ `POST /login/` - Token obtain
- ✅ `POST /refresh/` - Token refresh  
- ✅ `POST /verify/` - Token verify
- ✅ `POST /logout/` - Logout
- ✅ `POST /register/` - User registration
- ✅ `GET /profile/` - User profile
- ✅ `POST /change-password/` - Change password
- ✅ `GET /permissions/` - User permissions
- ✅ `GET /users/` - User list
- ✅ `GET/PUT/PATCH /users/<uuid:pk>/` - User detail
- ✅ `POST /users/<str:user_id>/terminate-sessions/` - Terminate user sessions
- ✅ `GET /sessions/` - Session list
- ✅ `GET /sessions/<str:session_id>/` - Session detail
- ✅ `POST /sessions/<str:session_id>/terminate/` - Terminate session
- ✅ `GET /session-analytics/` - Session analytics
- ✅ `GET /security-policies/` - Security policy list
- ✅ `GET/PUT /security-policies/<str:policy_id>/` - Security policy detail
- ✅ `POST /policy-evaluation/` - Policy evaluation
- ✅ `POST /initialize-policies/` - Initialize policies
- ✅ `GET /admin/system-health/` - Admin system health
- ✅ `GET /admin/system-stats/` - Admin system stats
- ✅ `GET /admin/metrics-history/` - Metrics history
- ✅ `GET /admin/performance-metrics/` - Performance metrics
- ✅ `GET /admin/security-events/` - Security events
- ✅ `GET /admin/threat-analysis/` - Threat analysis
- ✅ `GET/PUT /admin/security-configuration/` - Security configuration
- ✅ `POST /admin/maintenance/<str:action>/` - Maintenance actions
- ✅ `POST /admin/security/block-ip/` - Block IP
- ✅ `POST /admin/security/unblock-ip/` - Unblock IP
- ✅ `GET /audit-logs/` - Audit logs
- ✅ `GET /health/` - Health check

### Analytics Module (`/api/v1/analytics/`)
- ✅ `GET /` - Analytics data
- ✅ `GET /export/` - Analytics export
- ✅ `GET /summary/` - Analytics summary
- ✅ `GET/POST /custom-metrics/` - Custom metrics
- ✅ `GET/PUT/DELETE /custom-metrics/<uuid:pk>/` - Custom metric detail
- ✅ `POST /custom-metrics/<uuid:pk>/execute/` - Execute custom metric
- ✅ `GET/POST /alert-rules/` - Alert rules
- ✅ `GET/PUT/DELETE /alert-rules/<uuid:pk>/` - Alert rule detail
- ✅ `GET /alerts/` - Alerts list
- ✅ `GET /alerts/<uuid:pk>/` - Alert detail
- ✅ `POST /alerts/<uuid:pk>/acknowledge/` - Acknowledge alert
- ✅ `POST /alerts/<uuid:pk>/resolve/` - Resolve alert

### Queries Module (`/api/v1/queries/`)
- ✅ `GET/POST /` - Query list/create
- ✅ `GET /<str:task_id>/` - Query detail
- ✅ `POST /<str:task_id>/execute/` - Execute query
- ✅ `GET /<str:task_id>/export/<str:format>/` - Export query results

### Evaluation Module (`/api/v1/evaluation/`)
- ✅ `GET /scenarios/` - Evaluation scenarios
- ✅ `GET /runs/` - Evaluation runs
- ✅ `POST /runs/scenario/<str:scenario_id>/` - Run scenario evaluation
- ✅ `GET /batches/` - Evaluation batches
- ✅ `POST /batches/run/` - Run batch evaluation
- ✅ `GET /metrics/` - Evaluation metrics

### Security Module (`/api/v1/security/`)
- ✅ `GET/POST /prompts/` - Adversarial prompts
- ✅ `GET /tests/` - Security tests
- ✅ `POST /tests/run/` - Run security test
- ✅ `GET /test/<str:test_id>/` - Security test detail
- ✅ `GET /results/` - Security test results
- ✅ `GET /metrics/` - Security metrics

### Privacy Module (`/api/v1/privacy/`)
- ✅ `GET/POST /dp-config/` - DP configuration
- ✅ `POST /analysis/` - Privacy analysis

### Data Management Module (`/api/v1/data/`)
- ✅ `POST /upload/` - Data upload
- ✅ `GET /indices/` - List indices
- ✅ `DELETE /indices/<str:index_name>/` - Delete index
- ✅ `POST /cic-process/` - Process CIC data
- ✅ `GET /tasks/` - Data tasks

### System Admin Module (`/api/v1/system/`)
- ✅ `GET /health/` - System health
- ✅ `GET /indices/` - Available indices
- ✅ `GET /models/` - Available models
- ✅ `GET /status/` - System status
- ✅ `GET /metrics/` - System metrics
- ✅ `GET /analytics/` - System analytics
- ✅ `GET/POST /custom-metrics/` - Custom metrics
- ✅ `GET /analytics/export/` - Analytics export

## Frontend API Calls Analysis

### ✅ Working Connections (in api.ts)
1. `POST /queries/` - generateQuery ✅
2. `GET /queries/${taskId}/` - getQueryTask ✅
3. `POST /queries/${taskId}/execute/` - executeQuery ✅
4. `GET /system/health/` - getSystemHealth ✅
5. `GET /system/indices/` - getAvailableIndices ✅
6. `GET /system/metrics/` - getSystemMetrics ✅
7. `GET /data/tasks/` - getDataIngestionTasks ✅
8. `DELETE /data/indices/${indexName}/` - deleteIndex ✅
9. `GET /evaluation/scenarios/` - getEvaluationScenarios ✅
10. `POST /evaluation/runs/scenario/${scenarioId}/` - runEvaluation ✅
11. `GET /security/test/${testId}/` - getSecurityTestResults ✅

### ❌ BROKEN Connections (Frontend calling wrong endpoint)
1. `POST /security/test/` - runSecurityTest
   - **Frontend calls**: `/security/test/`
   - **Backend expects**: `/security/tests/run/`
   - **FIX NEEDED**: Update frontend to use correct endpoint

### ⚠️ Missing in api.ts but used in components
From fetch() calls in components:
1. `/api/admin/security-configuration/` - Used but should be `/api/v1/auth/admin/security-configuration/`
2. `/api/admin/security-events/` - Should be `/api/v1/auth/admin/security-events/`
3. `/api/admin/system-health/` - Should be `/api/v1/auth/admin/system-health/`
4. `/api/admin/system-stats/` - Should be `/api/v1/auth/admin/system-stats/`
5. `/api/admin/threat-analysis/` - Should be `/api/v1/auth/admin/threat-analysis/`
6. `/api/admin/metrics-history/` - Should be `/api/v1/auth/admin/metrics-history/`
7. `/api/admin/performance-metrics/` - Should be `/api/v1/auth/admin/performance-metrics/`
8. `/api/admin/maintenance/` - Should be `/api/v1/auth/admin/maintenance/`
9. `/api/admin/security/block-ip/` - Should be `/api/v1/auth/admin/security/block-ip/`
10. `/api/admin/security/unblock-ip/` - Should be `/api/v1/auth/admin/security/unblock-ip/`
11. `/api/auth/security-policies/` - Should be `/api/v1/auth/security-policies/`
12. `/api/auth/session-analytics/` - Should be `/api/v1/auth/session-analytics/`
13. `/api/auth/sessions/` - Should be `/api/v1/auth/sessions/`
14. `/api/auth/login/` - Should be `/api/v1/auth/login/`
15. `/api/auth/refresh/` - Should be `/api/v1/auth/refresh/`
16. `/api/auth/logout/` - Should be `/api/v1/auth/logout/`
17. `/api/auth/register/` - Should be `/api/v1/auth/register/`
18. `/api/auth/profile/` - Should be `/api/v1/auth/profile/`
19. `/api/auth/permissions/` - Should be `/api/v1/auth/permissions/`
20. `/api/auth/users/` - Should be `/api/v1/auth/users/`
21. `/api/auth/audit-logs/` - Should be `/api/v1/auth/audit-logs/`

### ⚠️ Monitoring Endpoints (Not found in backend)
1. `/api/monitoring/alert-rules/` - NOT FOUND
2. `/api/monitoring/alerts/` - NOT FOUND  
3. `/api/monitoring/health-checks/` - NOT FOUND
4. `/api/monitoring/metrics/recent/` - NOT FOUND
5. `/api/monitoring/notification-channels/` - NOT FOUND

These should likely use the analytics module endpoints:
- `/api/v1/analytics/alert-rules/`
- `/api/v1/analytics/alerts/`

### Missing Frontend Functions for Backend Endpoints
Backend endpoints that have no corresponding frontend function:
1. Privacy module - No frontend integration
2. Many auth admin endpoints - Not wrapped in api.ts
3. Analytics module - Not fully integrated
4. Evaluation batches - Not integrated
5. Security prompts management - Not integrated

## Summary of Issues

### Critical Issues to Fix:
1. ❌ **Security test endpoint mismatch** - Frontend calls wrong URL
2. ❌ **Missing /api/v1 prefix** - Many fetch() calls missing the API version prefix
3. ❌ **Monitoring endpoints don't exist** - Frontend calling non-existent endpoints

### Medium Priority:
1. ⚠️ Missing api.ts wrapper functions for auth admin endpoints
2. ⚠️ Missing integration for privacy module
3. ⚠️ Missing integration for analytics module

### Low Priority:
1. Some backend endpoints have no frontend usage (may be intentional)