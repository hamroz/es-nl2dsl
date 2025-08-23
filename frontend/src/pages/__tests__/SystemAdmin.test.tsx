import React from 'react';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient } from '@tanstack/react-query';
import { rest } from 'msw';
import { server } from '../../test/mocks/server';
import { 
  renderWithQueryClient,
  mockSystemHealth,
  mockConsole,
  waitForAsync 
} from '../../test/utils/testUtils';
import SystemAdmin from '../SystemAdmin';

// Mock recharts components
jest.mock('recharts', () => ({
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div data-testid="line" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  AreaChart: ({ children }: any) => <div data-testid="area-chart">{children}</div>,
  Area: () => <div data-testid="area" />,
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div data-testid="bar" />,
  PieChart: ({ children }: any) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => <div data-testid="pie" />,
  Cell: () => <div data-testid="cell" />,
}));

// Mock enhanced system health data for testing
const mockEnhancedSystemHealth = {
  elasticsearch: {
    status: 'healthy' as const,
    cluster_health: 'green' as const,
    nodes: 3,
    indices_count: 5,
    docs_count: 250000,
    store_size: '1.2 GB',
  },
  ollama: {
    status: 'healthy' as const,
    models: ['llama3.1:latest', 'deepseek-r1:14b'],
    running_models: ['llama3.1:latest'],
  },
  system: {
    cpu_usage: 45.2,
    memory_usage: 68.5,
    disk_usage: 32.1,
    uptime: 86400,
    load_average: [1.2, 1.5, 1.8],
  },
  indices: [
    {
      name: 'logs_net',
      health: 'green' as const,
      docs_count: 50000,
      store_size: '250 MB',
      created_at: '2023-01-01T00:00:00Z',
    },
    {
      name: 'logs_cic_ids2017',
      health: 'yellow' as const,
      docs_count: 200000,
      store_size: '1.0 GB',
      created_at: '2023-01-02T00:00:00Z',
    },
  ],
};

const mockSystemMetrics = {
  total_queries_generated: 1250,
  total_evaluations_run: 85,
  total_security_tests: 15,
  total_data_ingested_gb: 5.8,
  avg_query_generation_time: 3.2,
  avg_evaluation_f1_score: 0.85,
  security_pass_rate: 0.92,
  system_uptime_hours: 240,
};

const mockIngestionTasks = [
  {
    task_id: 'task-001',
    task_name: 'CIC-IDS2017 Monday Data',
    source_file: 'Monday-WorkingHours.csv',
    target_index: 'logs_cic_ids2017',
    dataset_type: 'cic_ids2017',
    status: 'completed',
    total_records: 100000,
    processed_records: 100000,
    progress_percentage: 100,
    created_at: '2023-01-01T10:00:00Z',
    processing_time_seconds: 300,
  },
  {
    task_id: 'task-002',
    task_name: 'General Network Logs',
    source_file: 'network_logs.csv',
    target_index: 'logs_net',
    dataset_type: 'general_csv',
    status: 'processing',
    total_records: 50000,
    processed_records: 25000,
    progress_percentage: 50,
    created_at: '2023-01-01T11:00:00Z',
    processing_time_seconds: 150,
  },
];

describe('SystemAdmin Component', () => {
  let queryClient: QueryClient;
  let consoleMock: ReturnType<typeof mockConsole>;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    consoleMock = mockConsole();

    // Set up enhanced mock responses
    server.use(
      rest.get('/api/v1/system/health/', (req, res, ctx) => {
        return res(ctx.json(mockEnhancedSystemHealth));
      }),
      rest.get('/api/v1/system/metrics/', (req, res, ctx) => {
        return res(ctx.json(mockSystemMetrics));
      }),
      rest.get('/api/v1/data/tasks/', (req, res, ctx) => {
        return res(ctx.json(mockIngestionTasks));
      })
    );

    jest.clearAllMocks();
  });

  afterEach(() => {
    consoleMock.restore();
  });

  it('should render system admin dashboard', async () => {
    renderWithQueryClient(<SystemAdmin />, queryClient);

    expect(screen.getByText('⚙️ System Administration')).toBeInTheDocument();
    
    // Navigation should be visible
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Indices')).toBeInTheDocument();
    expect(screen.getByText('Data Ingestion')).toBeInTheDocument();
    expect(screen.getByText('System Logs')).toBeInTheDocument();

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('System Health Overview')).toBeInTheDocument();
    });
  });

  it('should display system health information', async () => {
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await waitFor(() => {
      // Elasticsearch status
      expect(screen.getByText('Elasticsearch')).toBeInTheDocument();
      expect(screen.getByText('Healthy')).toBeInTheDocument();
      expect(screen.getByText('3 nodes')).toBeInTheDocument();

      // Ollama status
      expect(screen.getByText('Ollama')).toBeInTheDocument();
      expect(screen.getByText('2 models')).toBeInTheDocument();

      // System metrics
      expect(screen.getByText('45.2%')).toBeInTheDocument(); // CPU usage
      expect(screen.getByText('68.5%')).toBeInTheDocument(); // Memory usage
    });
  });

  it('should display system metrics correctly', async () => {
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('1,250')).toBeInTheDocument(); // Total queries
      expect(screen.getByText('85')).toBeInTheDocument(); // Total evaluations
      expect(screen.getByText('15')).toBeInTheDocument(); // Security tests
      expect(screen.getByText('5.8 GB')).toBeInTheDocument(); // Data ingested
    });
  });

  it('should switch between different sections', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemAdmin />, queryClient);

    // Initially on dashboard
    await waitFor(() => {
      expect(screen.getByText('System Health Overview')).toBeInTheDocument();
    });

    // Switch to indices section
    await user.click(screen.getByText('Indices'));
    
    await waitFor(() => {
      expect(screen.getByText('Elasticsearch Indices')).toBeInTheDocument();
      expect(screen.getByText('logs_net')).toBeInTheDocument();
      expect(screen.getByText('logs_cic_ids2017')).toBeInTheDocument();
    });

    // Switch to data ingestion section
    await user.click(screen.getByText('Data Ingestion'));
    
    await waitFor(() => {
      expect(screen.getByText('Data Ingestion Tasks')).toBeInTheDocument();
      expect(screen.getByText('CIC-IDS2017 Monday Data')).toBeInTheDocument();
    });
  });

  it('should display indices with correct health status', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await user.click(screen.getByText('Indices'));

    await waitFor(() => {
      const indicesSection = screen.getByText('Elasticsearch Indices').closest('div');
      expect(within(indicesSection!).getByText('logs_net')).toBeInTheDocument();
      expect(within(indicesSection!).getByText('50,000')).toBeInTheDocument(); // docs count
      expect(within(indicesSection!).getByText('250 MB')).toBeInTheDocument(); // store size
    });
  });

  it('should handle index deletion', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await user.click(screen.getByText('Indices'));

    await waitFor(() => {
      const deleteButtons = screen.getAllByText('Delete');
      expect(deleteButtons.length).toBeGreaterThan(0);
    });

    // Click first delete button
    const deleteButtons = screen.getAllByText('Delete');
    await user.click(deleteButtons[0]);

    // Should show confirmation dialog
    expect(screen.getByText('Confirm Deletion')).toBeInTheDocument();
    expect(screen.getByText('Are you sure you want to delete this index?')).toBeInTheDocument();

    // Confirm deletion
    const confirmButton = screen.getByText('Delete Index');
    await user.click(confirmButton);

    // Should call the delete API
    await waitFor(() => {
      expect(screen.queryByText('Confirm Deletion')).not.toBeInTheDocument();
    });
  });

  it('should display data ingestion tasks table', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await user.click(screen.getByText('Data Ingestion'));

    await waitFor(() => {
      expect(screen.getByText('Data Ingestion Tasks')).toBeInTheDocument();
      
      // Table headers
      expect(screen.getByText('Task Name')).toBeInTheDocument();
      expect(screen.getByText('Type')).toBeInTheDocument();
      expect(screen.getByText('Target Index')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('Progress')).toBeInTheDocument();

      // Task data
      expect(screen.getByText('CIC-IDS2017 Monday Data')).toBeInTheDocument();
      expect(screen.getByText('General Network Logs')).toBeInTheDocument();
    });
  });

  it('should show progress bars for ingestion tasks', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await user.click(screen.getByText('Data Ingestion'));

    await waitFor(() => {
      // Should show progress percentages
      expect(screen.getByText('100.0%')).toBeInTheDocument();
      expect(screen.getByText('50.0%')).toBeInTheDocument();
    });
  });

  it('should display task status badges with correct colors', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await user.click(screen.getByText('Data Ingestion'));

    await waitFor(() => {
      const completedStatus = screen.getByText('completed');
      const processingStatus = screen.getByText('processing');

      expect(completedStatus).toHaveClass('bg-green-100', 'text-green-800');
      expect(processingStatus).toHaveClass('bg-blue-100', 'text-blue-800');
    });
  });

  it('should handle auto refresh toggle', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemAdmin />, queryClient);

    // Find and click auto refresh toggle
    const autoRefreshToggle = screen.getByRole('checkbox');
    await user.click(autoRefreshToggle);

    // Should enable auto refresh
    expect(autoRefreshToggle).toBeChecked();
  });

  it('should handle refresh interval change', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemAdmin />, queryClient);

    // Find refresh interval input
    const intervalInput = screen.getByDisplayValue('60');
    await user.clear(intervalInput);
    await user.type(intervalInput, '30');

    expect(intervalInput).toHaveValue(30);
  });

  it('should handle manual refresh', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('System Health Overview')).toBeInTheDocument();
    });

    // Find and click refresh button
    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshButton);

    // Should trigger a refetch of data
    await waitFor(() => {
      expect(screen.getByText('System Health Overview')).toBeInTheDocument();
    });
  });

  it('should format bytes correctly', async () => {
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('1.2 GB')).toBeInTheDocument(); // Elasticsearch store size
    });
  });

  it('should format uptime correctly', async () => {
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('1d 0h 0m')).toBeInTheDocument(); // 86400 seconds = 1 day
    });
  });

  it('should handle loading states', () => {
    // Create a query client that doesn't resolve immediately
    const slowQueryClient = new QueryClient({
      defaultOptions: {
        queries: { 
          retry: false,
          staleTime: 0,
        },
      },
    });

    renderWithQueryClient(<SystemAdmin />, slowQueryClient);

    // Should show loading indicators
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('should handle error states', async () => {
    server.use(
      rest.get('/api/v1/system/health/', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Server error' }));
      })
    );

    renderWithQueryClient(<SystemAdmin />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Error loading system health')).toBeInTheDocument();
    });
  });

  it('should show unhealthy system status', async () => {
    server.use(
      rest.get('/api/v1/system/health/', (req, res, ctx) => {
        return res(ctx.json({
          ...mockEnhancedSystemHealth,
          elasticsearch: {
            ...mockEnhancedSystemHealth.elasticsearch,
            status: 'unhealthy',
            cluster_health: 'red',
          }
        }));
      })
    );

    renderWithQueryClient(<SystemAdmin />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Unhealthy')).toBeInTheDocument();
    });
  });

  it('should display charts in dashboard', async () => {
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await waitFor(() => {
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
      expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    });
  });

  it('should handle upload modal', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await user.click(screen.getByText('Data Ingestion'));

    // Look for upload button
    const uploadButton = screen.getByText('Upload Data');
    await user.click(uploadButton);

    // Should show upload modal
    await waitFor(() => {
      expect(screen.getByText('Upload Dataset')).toBeInTheDocument();
    });
  });

  it('should show system logs section', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await user.click(screen.getByText('System Logs'));

    await waitFor(() => {
      expect(screen.getByText('System Logs')).toBeInTheDocument();
    });
  });

  it('should handle network errors gracefully', async () => {
    server.use(
      rest.get('/api/v1/system/health/', (req, res) => {
        return res.networkError('Network connection failed');
      })
    );

    renderWithQueryClient(<SystemAdmin />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Error loading system health')).toBeInTheDocument();
    });
  });

  it('should show correct metric calculations', async () => {
    renderWithQueryClient(<SystemAdmin />, queryClient);

    await waitFor(() => {
      // Average generation time should be formatted
      expect(screen.getByText('3.2s')).toBeInTheDocument();
      
      // F1 score should be formatted as percentage
      expect(screen.getByText('85.0%')).toBeInTheDocument();
      
      // Pass rate should be formatted as percentage
      expect(screen.getByText('92.0%')).toBeInTheDocument();
    });
  });
});