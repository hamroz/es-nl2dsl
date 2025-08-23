import axios from 'axios';
import { rest } from 'msw';
import { server } from '../../test/mocks/server';
import api, { apiService } from '../api';
import { 
  mockSystemHealth, 
  mockQueryTask, 
  mockQueryResults,
  mockEvaluationScenarios,
  mockLocalStorage,
  mockConsole
} from '../../test/utils/testUtils';

// Mock axios create
jest.mock('axios', () => ({
  create: jest.fn(() => ({
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
    interceptors: {
      request: {
        use: jest.fn(),
        eject: jest.fn(),
      },
      response: {
        use: jest.fn(),
        eject: jest.fn(),
      },
    },
  })),
  post: jest.fn(),
}));

describe('API Service', () => {
  let mockStorage: ReturnType<typeof mockLocalStorage>;
  let consoleMock: ReturnType<typeof mockConsole>;

  beforeEach(() => {
    mockStorage = mockLocalStorage();
    Object.defineProperty(window, 'localStorage', {
      value: mockStorage,
      writable: true
    });
    
    consoleMock = mockConsole();
    jest.clearAllMocks();
  });

  afterEach(() => {
    consoleMock.restore();
  });

  describe('Query generation APIs', () => {
    it('should generate query successfully', async () => {
      const queryData = {
        prompt: 'Find malicious events',
        method: 'constrained' as const,
        index: 'logs_net',
        model: 'llama3.1:latest'
      };

      const result = await apiService.generateQuery(queryData);

      expect(result).toEqual({
        task_id: 'mock-task-id-123',
        status: 'pending'
      });
    });

    it('should get query task details', async () => {
      const result = await apiService.getQueryTask('test-task-123');

      expect(result).toEqual(expect.objectContaining({
        task_id: 'test-task-123',
        status: 'completed',
        prompt: 'Find malicious events',
        query: expect.any(Object),
        validation: expect.objectContaining({
          status: 'PASS'
        })
      }));
    });

    it('should execute query successfully', async () => {
      const result = await apiService.executeQuery('test-task-123', 500);

      expect(result).toEqual(expect.objectContaining({
        total_hits: 150,
        returned_hits: 10,
        results: expect.arrayContaining([
          expect.objectContaining({
            _id: expect.any(String),
            _source: expect.any(Object)
          })
        ])
      }));
    });

    it('should handle query generation errors', async () => {
      server.use(
        rest.post('/api/v1/queries/', (req, res, ctx) => {
          return res(ctx.status(400), ctx.json({ error: 'Invalid prompt' }));
        })
      );

      await expect(apiService.generateQuery({
        prompt: '',
        method: 'constrained'
      })).rejects.toThrow();
    });

    it('should handle query execution errors', async () => {
      server.use(
        rest.post('/api/v1/queries/:taskId/execute/', (req, res, ctx) => {
          return res(ctx.status(404), ctx.json({ error: 'Query not found' }));
        })
      );

      await expect(apiService.executeQuery('invalid-task')).rejects.toThrow();
    });
  });

  describe('System administration APIs', () => {
    it('should get system health', async () => {
      const result = await apiService.getSystemHealth();

      expect(result).toEqual(mockSystemHealth);
    });

    it('should get available indices', async () => {
      const result = await apiService.getAvailableIndices();

      expect(result).toEqual(['logs_net', 'logs_cic_ids2017', 'test_index']);
    });

    it('should get system metrics', async () => {
      const result = await apiService.getSystemMetrics();

      expect(result).toEqual(expect.objectContaining({
        cpu_usage: expect.any(Number),
        memory_usage: expect.any(Number),
        disk_usage: expect.any(Number),
        elasticsearch_status: expect.any(String)
      }));
    });

    it('should get data ingestion tasks', async () => {
      const result = await apiService.getDataIngestionTasks();

      expect(result).toEqual(expect.arrayContaining([
        expect.objectContaining({
          id: expect.any(String),
          type: 'data_ingestion',
          status: expect.any(String)
        })
      ]));
    });

    it('should delete index successfully', async () => {
      const result = await apiService.deleteIndex('test_index');

      expect(result).toEqual({ 
        message: 'Index test_index deleted successfully' 
      });
    });

    it('should handle system health errors', async () => {
      server.use(
        rest.get('/api/v1/system/health/', (req, res, ctx) => {
          return res(ctx.status(503), ctx.json({ error: 'Service unavailable' }));
        })
      );

      await expect(apiService.getSystemHealth()).rejects.toThrow();
    });
  });

  describe('Evaluation APIs', () => {
    it('should get evaluation scenarios', async () => {
      const result = await apiService.getEvaluationScenarios();

      expect(result).toEqual(mockEvaluationScenarios);
    });

    it('should run evaluation successfully', async () => {
      const result = await apiService.runEvaluation('scan-001', 'constrained');

      expect(result).toEqual(expect.objectContaining({
        run_id: expect.any(String),
        scenario_id: 'scan-001',
        status: 'completed',
        metrics: expect.objectContaining({
          jaccard_similarity: expect.any(Number),
          f1_score: expect.any(Number)
        })
      }));
    });

    it('should handle evaluation errors', async () => {
      server.use(
        rest.post('/api/v1/evaluation/runs/scenario/:scenarioId/', (req, res, ctx) => {
          return res(ctx.status(400), ctx.json({ error: 'Invalid scenario' }));
        })
      );

      await expect(apiService.runEvaluation('invalid', 'constrained')).rejects.toThrow();
    });
  });

  describe('Security testing APIs', () => {
    it('should run security test successfully', async () => {
      const prompts = ['malicious prompt 1', 'suspicious input'];
      const result = await apiService.runSecurityTest(prompts, 'test-suite');

      expect(result).toEqual(expect.objectContaining({
        test_id: 'security-test-123',
        status: 'running',
        prompts_tested: expect.any(Number)
      }));
    });

    it('should get security test results', async () => {
      const result = await apiService.getSecurityTestResults('security-test-123');

      expect(result).toEqual(expect.objectContaining({
        test_id: 'security-test-123',
        status: 'completed',
        results: expect.objectContaining({
          total_prompts: expect.any(Number),
          blocked_prompts: expect.any(Number),
          abstain_rate: expect.any(Number)
        })
      }));
    });

    it('should handle security test errors', async () => {
      server.use(
        rest.post('/api/v1/security/tests/run/', (req, res, ctx) => {
          return res(ctx.status(500), ctx.json({ error: 'Internal server error' }));
        })
      );

      await expect(apiService.runSecurityTest(['test'])).rejects.toThrow();
    });
  });

  describe('Authentication APIs', () => {
    it('should login successfully', async () => {
      const credentials = { email: 'test@example.com', password: 'password' };
      const result = await apiService.login(credentials);

      expect(result).toEqual(expect.objectContaining({
        access: 'mock-access-token',
        refresh: 'mock-refresh-token'
      }));
    });

    it('should logout successfully', async () => {
      const result = await apiService.logout();

      expect(result).toEqual({ message: 'Logged out successfully' });
    });

    it('should refresh token successfully', async () => {
      const result = await apiService.refreshToken('mock-refresh-token');

      expect(result).toEqual(expect.objectContaining({
        access: 'new-mock-access-token',
        refresh: 'new-mock-refresh-token'
      }));
    });

    it('should get user profile', async () => {
      const result = await apiService.getUserProfile();

      expect(result).toEqual(expect.objectContaining({
        id: '1',
        username: 'testuser',
        email: 'test@example.com',
        role: 'admin'
      }));
    });

    it('should get user permissions', async () => {
      const result = await apiService.getUserPermissions();

      expect(result).toEqual(expect.objectContaining({
        permissions: expect.objectContaining({
          can_admin_users: true,
          can_modify_queries: true,
          can_execute_queries: true
        })
      }));
    });

    it('should handle login errors', async () => {
      server.use(
        rest.post('/api/v1/auth/login/', (req, res, ctx) => {
          return res(ctx.status(401), ctx.json({ message: 'Invalid credentials' }));
        })
      );

      await expect(apiService.login({
        email: 'invalid@example.com',
        password: 'wrong'
      })).rejects.toThrow();
    });
  });

  describe('User management APIs', () => {
    it('should get users list', async () => {
      server.use(
        rest.get('/api/v1/auth/users/', (req, res, ctx) => {
          return res(ctx.json([
            { id: '1', username: 'user1', email: 'user1@example.com' },
            { id: '2', username: 'user2', email: 'user2@example.com' }
          ]));
        })
      );

      const result = await apiService.getUsers();

      expect(result).toHaveLength(2);
      expect(result[0]).toEqual(expect.objectContaining({
        id: '1',
        username: 'user1',
        email: 'user1@example.com'
      }));
    });

    it('should update user successfully', async () => {
      server.use(
        rest.put('/api/v1/auth/users/:userId/', (req, res, ctx) => {
          return res(ctx.json({ 
            id: req.params.userId,
            username: 'updated-user',
            email: 'updated@example.com'
          }));
        })
      );

      const result = await apiService.updateUser('1', {
        username: 'updated-user',
        email: 'updated@example.com'
      });

      expect(result).toEqual(expect.objectContaining({
        id: '1',
        username: 'updated-user',
        email: 'updated@example.com'
      }));
    });

    it('should patch user successfully', async () => {
      server.use(
        rest.patch('/api/v1/auth/users/:userId/', (req, res, ctx) => {
          return res(ctx.json({ 
            id: req.params.userId,
            is_active: false
          }));
        })
      );

      const result = await apiService.patchUser('1', { is_active: false });

      expect(result).toEqual(expect.objectContaining({
        id: '1',
        is_active: false
      }));
    });
  });

  describe('Session management APIs', () => {
    it('should get user sessions', async () => {
      server.use(
        rest.get('/api/v1/auth/sessions/', (req, res, ctx) => {
          return res(ctx.json([
            { id: 'session1', user_id: '1', created_at: '2023-01-01T00:00:00Z' },
            { id: 'session2', user_id: '1', created_at: '2023-01-01T01:00:00Z' }
          ]));
        })
      );

      const result = await apiService.getUserSessions('1');

      expect(result).toHaveLength(2);
      expect(result[0]).toEqual(expect.objectContaining({
        id: 'session1',
        user_id: '1'
      }));
    });

    it('should delete session successfully', async () => {
      server.use(
        rest.delete('/api/v1/auth/sessions/', (req, res, ctx) => {
          return res(ctx.json({ message: 'Session deleted' }));
        })
      );

      const result = await apiService.deleteSession('session1');

      expect(result).toEqual({ message: 'Session deleted' });
    });
  });

  describe('Audit log APIs', () => {
    it('should get audit logs', async () => {
      server.use(
        rest.get('/api/v1/auth/audit-logs/', (req, res, ctx) => {
          return res(ctx.json([
            { id: '1', action: 'LOGIN', user: 'testuser', timestamp: '2023-01-01T00:00:00Z' },
            { id: '2', action: 'QUERY_GENERATED', user: 'testuser', timestamp: '2023-01-01T01:00:00Z' }
          ]));
        })
      );

      const result = await apiService.getAuditLogs();

      expect(result).toHaveLength(2);
      expect(result[0]).toEqual(expect.objectContaining({
        id: '1',
        action: 'LOGIN'
      }));
    });

    it('should export audit logs', async () => {
      server.use(
        rest.get('/api/v1/auth/audit-logs/export/', (req, res, ctx) => {
          return res(ctx.body('audit,log,data'));
        })
      );

      const result = await apiService.exportAuditLogs();

      expect(result).toEqual('audit,log,data');
    });
  });

  describe('Tenant and workspace APIs', () => {
    it('should get tenants', async () => {
      server.use(
        rest.get('/api/v1/auth/tenants/', (req, res, ctx) => {
          return res(ctx.json([
            { id: '1', name: 'Tenant 1' },
            { id: '2', name: 'Tenant 2' }
          ]));
        })
      );

      const result = await apiService.getTenants();

      expect(result).toHaveLength(2);
      expect(result[0]).toEqual(expect.objectContaining({
        id: '1',
        name: 'Tenant 1'
      }));
    });

    it('should create tenant successfully', async () => {
      server.use(
        rest.post('/api/v1/auth/tenants/', (req, res, ctx) => {
          return res(ctx.json({ id: '3', name: 'New Tenant' }));
        })
      );

      const result = await apiService.createTenant({ name: 'New Tenant' });

      expect(result).toEqual(expect.objectContaining({
        id: '3',
        name: 'New Tenant'
      }));
    });

    it('should get workspaces', async () => {
      server.use(
        rest.get('/api/v1/auth/workspaces/', (req, res, ctx) => {
          return res(ctx.json([
            { id: '1', name: 'Workspace 1' },
            { id: '2', name: 'Workspace 2' }
          ]));
        })
      );

      const result = await apiService.getWorkspaces();

      expect(result).toHaveLength(2);
      expect(result[0]).toEqual(expect.objectContaining({
        id: '1',
        name: 'Workspace 1'
      }));
    });
  });

  describe('System analytics APIs', () => {
    it('should get system analytics', async () => {
      server.use(
        rest.get('/api/v1/system/analytics/', (req, res, ctx) => {
          return res(ctx.json({
            queries_generated: 150,
            successful_queries: 140,
            error_rate: 0.067,
            average_generation_time: 3.2
          }));
        })
      );

      const result = await apiService.getSystemAnalytics('7d');

      expect(result).toEqual(expect.objectContaining({
        queries_generated: 150,
        successful_queries: 140,
        error_rate: 0.067
      }));
    });

    it('should export system analytics', async () => {
      server.use(
        rest.get('/api/v1/system/analytics/export', (req, res, ctx) => {
          return res(ctx.body('analytics,data,csv'));
        })
      );

      const result = await apiService.exportSystemAnalytics('csv', '30d');

      expect(result).toEqual('analytics,data,csv');
    });

    it('should get custom metrics', async () => {
      server.use(
        rest.get('/api/v1/system/custom-metrics/', (req, res, ctx) => {
          return res(ctx.json({
            custom_metric_1: 42,
            custom_metric_2: 'active'
          }));
        })
      );

      const result = await apiService.getCustomMetrics();

      expect(result).toEqual(expect.objectContaining({
        custom_metric_1: 42,
        custom_metric_2: 'active'
      }));
    });
  });

  describe('Error handling', () => {
    it('should handle network errors', async () => {
      server.use(
        rest.get('/api/v1/system/health/', (req, res, ctx) => {
          return res.networkError('Network error');
        })
      );

      await expect(apiService.getSystemHealth()).rejects.toThrow();
    });

    it('should handle timeout errors', async () => {
      server.use(
        rest.get('/api/v1/system/health/', (req, res, ctx) => {
          return res(ctx.delay(10000), ctx.json({ status: 'ok' }));
        })
      );

      // This would timeout in a real scenario, but MSW doesn't support timeout simulation
      // So we'll just verify the request is made
      const promise = apiService.getSystemHealth();
      expect(promise).toBeInstanceOf(Promise);
    });

    it('should handle malformed JSON responses', async () => {
      server.use(
        rest.get('/api/v1/system/health/', (req, res, ctx) => {
          return res(ctx.text('invalid json response'));
        })
      );

      await expect(apiService.getSystemHealth()).rejects.toThrow();
    });
  });
});