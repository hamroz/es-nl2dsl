import { http, HttpResponse } from 'msw';

// Mock API responses for testing
export const handlers = [
  // Authentication endpoints
  http.post('/api/v1/auth/login/', () => {
    return HttpResponse.json({
      access: 'mock-access-token',
      refresh: 'mock-refresh-token',
      session_token: 'mock-session-token',
    });
  }),

  http.get('/api/v1/auth/profile/', () => {
    return HttpResponse.json({
      id: '1',
      username: 'testuser',
      email: 'test@example.com',
      role: 'admin',
      workspace: 'test-workspace',
    });
  }),

  http.get('/api/v1/auth/permissions/', () => {
    return HttpResponse.json({
      permissions: {
        can_admin_users: true,
        can_modify_queries: true,
        can_execute_queries: true,
        can_view_audit_logs: true,
        can_manage_system: true,
        can_export_data: true,
        is_read_only: false,
      },
    });
  }),

  http.post('/api/v1/auth/refresh/', () => {
    return HttpResponse.json({
      access: 'new-mock-access-token',
      refresh: 'new-mock-refresh-token',
    });
  }),

  http.post('/api/v1/auth/logout/', () => {
    return HttpResponse.json({ message: 'Logged out successfully' });
  }),

  // Query generation endpoints
  http.post('/api/v1/queries/', () => {
    return HttpResponse.json({
      task_id: 'mock-task-id-123',
      status: 'pending',
    });
  }),

  http.get('/api/v1/queries/:taskId', ({ params }) => {
    return HttpResponse.json({
      task_id: params.taskId,
      status: 'completed',
      prompt: 'Find malicious events',
      method: 'constrained',
      index: 'logs_net',
      created_at: '2023-01-01T00:00:00Z',
      completed_at: '2023-01-01T00:00:05Z',
      query: {
        query: {
          bool: {
            must: [
              { term: { label: 'malicious' } }
            ],
            filter: [
              {
                range: {
                  '@timestamp': {
                    gte: '2023-01-01',
                    lte: '2023-01-31'
                  }
                }
              }
            ]
          }
        }
      },
      validation: {
        status: 'PASS',
        errors: [],
      },
      metrics: {
        generation_time: 5.2,
        retry_count: 0,
      },
    });
  }),

  http.post('/api/v1/queries/:taskId/execute/', () => {
    return HttpResponse.json({
      total_hits: 150,
      returned_hits: 10,
      took: 25,
      results: [
        {
          _id: '1',
          _source: {
            '@timestamp': '2023-01-01T10:00:00Z',
            src_ip: '192.168.1.100',
            dst_ip: '10.0.0.1',
            label: 'malicious',
            message: 'Suspicious activity detected',
          },
        },
        {
          _id: '2',
          _source: {
            '@timestamp': '2023-01-01T10:05:00Z',
            src_ip: '192.168.1.101',
            dst_ip: '10.0.0.2',
            label: 'malicious',
            message: 'Port scan detected',
          },
        },
      ],
      aggregations: {},
      export_urls: {
        csv: '/api/v1/exports/test-query-001_results.csv',
        json: '/api/v1/exports/test-query-001_results.json',
      },
    });
  }),

  // System admin endpoints
  http.get('/api/v1/system/health/', () => {
    return HttpResponse.json({
      overall_status: 'healthy',
      services: {
        elasticsearch: true,
        ollama: true,
        database: true,
        redis: true,
        celery_workers: true,
      },
      indices: ['logs_net', 'logs_cic_ids2017'],
      models: ['llama3.1:latest', 'deepseek-r1:14b'],
      last_check: '2023-01-01T00:00:00Z',
    });
  }),

  http.get('/api/v1/system/indices/', () => {
    return HttpResponse.json(['logs_net', 'logs_cic_ids2017', 'test_index']);
  }),

  http.get('/api/v1/system/metrics/', () => {
    return HttpResponse.json({
      cpu_usage: 45.2,
      memory_usage: 68.5,
      disk_usage: 32.1,
      elasticsearch_status: 'green',
      active_queries: 3,
    });
  }),

  http.get('/api/v1/data/tasks/', () => {
    return HttpResponse.json([
      {
        id: 'task-1',
        type: 'data_ingestion',
        status: 'completed',
        created_at: '2023-01-01T00:00:00Z',
        file_name: 'test_data.csv',
        records_processed: 1000,
      },
    ]);
  }),

  http.delete('/api/v1/data/indices/:indexName', ({ params }) => {
    return HttpResponse.json({ 
      message: `Index ${params.indexName} deleted successfully` 
    });
  }),

  // Evaluation endpoints
  http.get('/api/v1/evaluation/scenarios/', () => {
    return HttpResponse.json([
      {
        id: 'scan-001',
        name: 'Port Scan Detection',
        description: 'Detect port scanning activities',
        expected_query: { /* mock query */ },
      },
      {
        id: 'scan-002',
        name: 'Brute Force Detection',
        description: 'Detect brute force attacks',
        expected_query: { /* mock query */ },
      },
    ]);
  }),

  http.post('/api/v1/evaluation/runs/scenario/:scenarioId/', ({ params }) => {
    return HttpResponse.json({
      run_id: 'run-123',
      scenario_id: params.scenarioId,
      status: 'completed',
      metrics: {
        jaccard_similarity: 0.85,
        f1_score: 0.78,
        precision: 0.82,
        recall: 0.75,
      },
    });
  }),

  // Security testing endpoints
  http.post('/api/v1/security/tests/run/', () => {
    return HttpResponse.json({
      test_id: 'security-test-123',
      status: 'running',
      prompts_tested: 5,
    });
  }),

  http.get('/api/v1/security/test/:testId', () => {
    return HttpResponse.json({
      test_id: 'security-test-123',
      status: 'completed',
      results: {
        total_prompts: 5,
        blocked_prompts: 2,
        abstain_rate: 0.4,
        suspicious_patterns: ['injection attempt', 'data exfiltration'],
      },
    });
  }),

  // Generic error handlers for missing endpoints
  http.get('*', ({ request }) => {
    console.warn(`Unhandled GET request to ${request.url}`);
    return HttpResponse.json({ error: 'Not found' }, { status: 404 });
  }),

  http.post('*', ({ request }) => {
    console.warn(`Unhandled POST request to ${request.url}`);
    return HttpResponse.json({ error: 'Not found' }, { status: 404 });
  }),
];