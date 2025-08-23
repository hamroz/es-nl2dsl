import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '../../contexts/AuthContext';

// Mock user data for testing
export const mockUser = {
  id: '1',
  username: 'testuser',
  email: 'test@example.com',
  role: 'admin' as const,
  workspace: 'test-workspace',
  tenant_id: 'test-tenant'
};

export const mockPermissions = {
  can_admin_users: true,
  can_modify_queries: true,
  can_execute_queries: true,
  can_view_audit_logs: true,
  can_manage_system: true,
  can_export_data: true,
  is_read_only: false,
};

export const mockRestrictedPermissions = {
  can_admin_users: false,
  can_modify_queries: false,
  can_execute_queries: true,
  can_view_audit_logs: false,
  can_manage_system: false,
  can_export_data: false,
  is_read_only: true,
};

// Mock system health data
export const mockSystemHealth = {
  overall_status: 'healthy' as const,
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
};

// Mock query task data
export const mockQueryTask = {
  task_id: 'test-task-123',
  status: 'completed' as const,
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
    status: 'PASS' as const,
    errors: [],
  },
  metrics: {
    generation_time: 5.2,
    retry_count: 0,
  },
};

// Mock query results
export const mockQueryResults = {
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
};

// Mock evaluation scenarios
export const mockEvaluationScenarios = [
  {
    id: 'scan-001',
    name: 'Port Scan Detection',
    description: 'Detect port scanning activities',
    expected_query: { query: { term: { label: 'port_scan' } } },
  },
  {
    id: 'scan-002',
    name: 'Brute Force Detection',
    description: 'Detect brute force attacks',
    expected_query: { query: { term: { label: 'brute_force' } } },
  },
];

// Custom render function with providers
const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        {children}
      </AuthProvider>
    </QueryClientProvider>
  );
};

const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllTheProviders, ...options });

// Helper function to create a minimal render without providers
export const renderWithoutProviders = (ui: ReactElement, options?: RenderOptions) => 
  render(ui, options);

// Helper function to create a render with custom query client
export const renderWithQueryClient = (
  ui: ReactElement, 
  queryClient?: QueryClient,
  options?: Omit<RenderOptions, 'wrapper'>
) => {
  const testQueryClient = queryClient || new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={testQueryClient}>
      {children}
    </QueryClientProvider>
  );

  return render(ui, { wrapper: Wrapper, ...options });
};

// Helper function to wait for async operations
export const waitForAsync = () => new Promise(resolve => setTimeout(resolve, 0));

// Helper function to create mock WebSocket
export const createMockWebSocket = () => {
  const mockWs = {
    send: jest.fn(),
    close: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    onopen: null as ((event: Event) => void) | null,
    onclose: null as ((event: CloseEvent) => void) | null,
    onmessage: null as ((event: MessageEvent) => void) | null,
    onerror: null as ((event: Event) => void) | null,
    readyState: WebSocket.OPEN,
  };

  // Simulate successful connection
  setTimeout(() => {
    if (mockWs.onopen) {
      mockWs.onopen(new Event('open'));
    }
  }, 0);

  return mockWs;
};

// Helper to simulate WebSocket message
export const simulateWebSocketMessage = (ws: any, data: any) => {
  if (ws.onmessage) {
    const event = new MessageEvent('message', {
      data: JSON.stringify(data)
    });
    ws.onmessage(event);
  }
};

// Helper to create form data events
export const createChangeEvent = (name: string, value: string) => ({
  target: { name, value }
}) as React.ChangeEvent<HTMLInputElement>;

// Helper to create submit events
export const createSubmitEvent = () => ({
  preventDefault: jest.fn()
}) as unknown as React.FormEvent;

// Helper to wait for element to be removed
export const waitForElementToBeRemoved = async (element: HTMLElement) => {
  return new Promise<void>((resolve) => {
    const observer = new MutationObserver(() => {
      if (!document.body.contains(element)) {
        observer.disconnect();
        resolve();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  });
};

// Mock localStorage helpers
export const mockLocalStorage = () => {
  const store: { [key: string]: string } = {};
  
  return {
    getItem: jest.fn((key: string) => store[key] || null),
    setItem: jest.fn((key: string, value: string) => {
      store[key] = value.toString();
    }),
    removeItem: jest.fn((key: string) => {
      delete store[key];
    }),
    clear: jest.fn(() => {
      Object.keys(store).forEach(key => delete store[key]);
    }),
    store
  };
};

// Mock console methods for testing
export const mockConsole = () => {
  const originalConsole = { ...console };
  
  return {
    mockError: jest.spyOn(console, 'error').mockImplementation(() => {}),
    mockWarn: jest.spyOn(console, 'warn').mockImplementation(() => {}),
    mockLog: jest.spyOn(console, 'log').mockImplementation(() => {}),
    restore: () => {
      console.error = originalConsole.error;
      console.warn = originalConsole.warn;
      console.log = originalConsole.log;
    }
  };
};

// Re-export everything from testing library
export * from '@testing-library/react';
export { customRender as render };