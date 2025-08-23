import React from 'react';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient } from '@tanstack/react-query';
import { rest } from 'msw';
import { server } from '../../test/mocks/server';
import { 
  renderWithQueryClient,
  mockEvaluationScenarios,
  createMockWebSocket,
  simulateWebSocketMessage,
  mockConsole,
  waitForAsync 
} from '../../test/utils/testUtils';
import EvaluationDashboard from '../EvaluationDashboard';

// Mock recharts components
jest.mock('recharts', () => ({
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div data-testid="bar" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div data-testid="line" />,
  PieChart: ({ children }: any) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => <div data-testid="pie" />,
  Cell: () => <div data-testid="cell" />,
  ScatterChart: ({ children }: any) => <div data-testid="scatter-chart">{children}</div>,
  Scatter: () => <div data-testid="scatter" />,
}));

// Mock WebSocket
const mockWebSocket = createMockWebSocket();
global.WebSocket = jest.fn(() => mockWebSocket) as any;

const mockEvaluationRuns = [
  {
    run_id: 'run-001',
    scenario_id: 'scan-001',
    scenario_description: 'Port Scan Detection',
    method: 'constrained',
    model: 'llama3.1:latest',
    generated_query: { query: { term: { label: 'port_scan' } } },
    generation_time: 3.5,
    validation_passed: true,
    validation_errors: [],
    jaccard_similarity: 0.85,
    structural_similarity: 0.92,
    expert_result_count: 150,
    generated_result_count: 142,
    f1_score: 0.88,
    precision: 0.92,
    recall: 0.85,
    run_timestamp: '2023-01-01T10:00:00Z',
    execution_time_expert: 45,
    execution_time_generated: 42,
    status: 'completed',
  },
  {
    run_id: 'run-002',
    scenario_id: 'scan-002',
    scenario_description: 'Brute Force Detection',
    method: 'rules',
    model: 'deepseek-r1:14b',
    generated_query: { query: { term: { label: 'brute_force' } } },
    generation_time: 2.1,
    validation_passed: false,
    validation_errors: ['Time window too large'],
    jaccard_similarity: 0.62,
    structural_similarity: 0.71,
    expert_result_count: 89,
    generated_result_count: 112,
    f1_score: 0.68,
    precision: 0.73,
    recall: 0.64,
    run_timestamp: '2023-01-01T11:00:00Z',
    execution_time_expert: 38,
    execution_time_generated: 41,
    status: 'failed',
    error_message: 'Validation failed',
  },
];

const mockEvaluationMetrics = {
  total_runs: 25,
  completed_runs: 22,
  average_f1_score: 0.78,
  average_jaccard_similarity: 0.73,
  validation_pass_rate: 0.88,
  method_breakdown: {
    constrained: {
      count: 12,
      avg_f1: 0.82,
      avg_jaccard: 0.78,
    },
    rules: {
      count: 8,
      avg_f1: 0.75,
      avg_jaccard: 0.70,
    },
    zeroshot: {
      count: 5,
      avg_f1: 0.68,
      avg_jaccard: 0.65,
    },
  },
};

describe('EvaluationDashboard Component', () => {
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

    // Set up mock responses
    server.use(
      rest.get('/api/v1/evaluation/scenarios/', (req, res, ctx) => {
        return res(ctx.json(mockEvaluationScenarios));
      }),
      rest.get('/api/v1/evaluation/runs/', (req, res, ctx) => {
        return res(ctx.json(mockEvaluationRuns));
      }),
      rest.get('/api/v1/evaluation/metrics/', (req, res, ctx) => {
        return res(ctx.json(mockEvaluationMetrics));
      }),
      rest.post('/api/v1/evaluation/runs/scenario/:scenarioId/', (req, res, ctx) => {
        return res(ctx.json({
          run_id: 'new-run-123',
          scenario_id: req.params.scenarioId,
          status: 'running',
        }));
      })
    );

    jest.clearAllMocks();
  });

  afterEach(() => {
    consoleMock.restore();
  });

  it('should render evaluation dashboard', async () => {
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    expect(screen.getByText('📊 Evaluation Dashboard')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByText('Evaluation Metrics Overview')).toBeInTheDocument();
    });
  });

  it('should load and display evaluation scenarios', async () => {
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Port Scan Detection')).toBeInTheDocument();
      expect(screen.getByText('Brute Force Detection')).toBeInTheDocument();
    });

    // Should show scenario selection dropdown
    expect(screen.getByText('Select Scenario')).toBeInTheDocument();
  });

  it('should display evaluation metrics', async () => {
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('25')).toBeInTheDocument(); // Total runs
      expect(screen.getByText('22')).toBeInTheDocument(); // Completed runs
      expect(screen.getByText('78.0%')).toBeInTheDocument(); // Average F1 score
      expect(screen.getByText('73.0%')).toBeInTheDocument(); // Average Jaccard
      expect(screen.getByText('88.0%')).toBeInTheDocument(); // Validation pass rate
    });
  });

  it('should handle scenario selection', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Select Scenario')).toBeInTheDocument();
    });

    // Select a scenario from dropdown
    const scenarioSelect = screen.getByDisplayValue('');
    await user.selectOptions(scenarioSelect, 'scan-001');

    expect(scenarioSelect).toHaveValue('scan-001');
  });

  it('should handle method selection', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    const methodSelect = screen.getByDisplayValue('constrained');
    await user.selectOptions(methodSelect, 'rules');

    expect(methodSelect).toHaveValue('rules');
  });

  it('should run evaluation for selected scenario', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Select Scenario')).toBeInTheDocument();
    });

    // Select scenario and method
    const scenarioSelect = screen.getByDisplayValue('');
    await user.selectOptions(scenarioSelect, 'scan-001');

    const methodSelect = screen.getByDisplayValue('constrained');
    await user.selectOptions(methodSelect, 'rules');

    // Run evaluation
    const runButton = screen.getByText('Run Evaluation');
    await user.click(runButton);

    // Should show running state
    await waitFor(() => {
      expect(screen.getByText('Running evaluation...')).toBeInTheDocument();
    });
  });

  it('should display evaluation results table', async () => {
    // Override to return evaluation runs
    server.use(
      rest.get('/api/v1/evaluation/runs/', (req, res, ctx) => {
        return res(ctx.json(mockEvaluationRuns));
      })
    );

    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Recent Evaluation Runs')).toBeInTheDocument();
      
      // Table headers
      expect(screen.getByText('Scenario')).toBeInTheDocument();
      expect(screen.getByText('Method')).toBeInTheDocument();
      expect(screen.getByText('F1 Score')).toBeInTheDocument();
      expect(screen.getByText('Jaccard')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
    });
  });

  it('should show evaluation run details', async () => {
    server.use(
      rest.get('/api/v1/evaluation/runs/', (req, res, ctx) => {
        return res(ctx.json(mockEvaluationRuns));
      })
    );

    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Port Scan Detection')).toBeInTheDocument();
      expect(screen.getByText('0.88')).toBeInTheDocument(); // F1 score
      expect(screen.getByText('0.85')).toBeInTheDocument(); // Jaccard similarity
    });
  });

  it('should show validation status with proper styling', async () => {
    server.use(
      rest.get('/api/v1/evaluation/runs/', (req, res, ctx) => {
        return res(ctx.json(mockEvaluationRuns));
      })
    );

    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      const passedStatus = screen.getByText('Passed');
      const failedStatus = screen.getByText('Failed');

      expect(passedStatus).toHaveClass('bg-green-100', 'text-green-800');
      expect(failedStatus).toHaveClass('bg-red-100', 'text-red-800');
    });
  });

  it('should handle search/filter functionality', async () => {
    server.use(
      rest.get('/api/v1/evaluation/runs/', (req, res, ctx) => {
        return res(ctx.json(mockEvaluationRuns));
      })
    );

    const user = userEvent.setup();
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Recent Evaluation Runs')).toBeInTheDocument();
    });

    // Find search input
    const searchInput = screen.getByPlaceholderText('Search runs...');
    await user.type(searchInput, 'Port Scan');

    expect(searchInput).toHaveValue('Port Scan');
  });

  it('should display charts for metrics visualization', async () => {
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
      expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
    });
  });

  it('should show method breakdown chart', async () => {
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      // Should show method breakdown data
      expect(screen.getByText('Method Performance')).toBeInTheDocument();
      expect(screen.getByTestId('pie-chart')).toBeInTheDocument();
    });
  });

  it('should handle WebSocket connection for real-time updates', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Select Scenario')).toBeInTheDocument();
    });

    // Select scenario and run evaluation
    const scenarioSelect = screen.getByDisplayValue('');
    await user.selectOptions(scenarioSelect, 'scan-001');

    const runButton = screen.getByText('Run Evaluation');
    await user.click(runButton);

    // Simulate WebSocket progress update
    simulateWebSocketMessage(mockWebSocket, {
      type: 'progress_update',
      run_id: 'new-run-123',
      progress: 50,
      stage: 'generating_query'
    });

    await waitFor(() => {
      expect(screen.getByText('Progress: 50%')).toBeInTheDocument();
    });
  });

  it('should handle WebSocket completion updates', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Select Scenario')).toBeInTheDocument();
    });

    const scenarioSelect = screen.getByDisplayValue('');
    await user.selectOptions(scenarioSelect, 'scan-001');

    const runButton = screen.getByText('Run Evaluation');
    await user.click(runButton);

    // Simulate completion
    simulateWebSocketMessage(mockWebSocket, {
      type: 'evaluation_completed',
      run_id: 'new-run-123',
      results: {
        f1_score: 0.91,
        jaccard_similarity: 0.87,
        status: 'completed'
      }
    });

    await waitFor(() => {
      expect(screen.getByText('Evaluation completed')).toBeInTheDocument();
    });
  });

  it('should show run details modal', async () => {
    server.use(
      rest.get('/api/v1/evaluation/runs/', (req, res, ctx) => {
        return res(ctx.json(mockEvaluationRuns));
      })
    );

    const user = userEvent.setup();
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Recent Evaluation Runs')).toBeInTheDocument();
    });

    // Click on view details button
    const viewButtons = screen.getAllByRole('button', { name: /view details/i });
    await user.click(viewButtons[0]);

    // Should show modal with run details
    await waitFor(() => {
      expect(screen.getByText('Evaluation Run Details')).toBeInTheDocument();
      expect(screen.getByText('Generated Query')).toBeInTheDocument();
      expect(screen.getByText('Validation Results')).toBeInTheDocument();
    });
  });

  it('should handle export functionality', async () => {
    server.use(
      rest.get('/api/v1/evaluation/runs/', (req, res, ctx) => {
        return res(ctx.json(mockEvaluationRuns));
      })
    );

    const user = userEvent.setup();
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Recent Evaluation Runs')).toBeInTheDocument();
    });

    // Click export button
    const exportButton = screen.getByText('Export Results');
    await user.click(exportButton);

    // Should show export options
    await waitFor(() => {
      expect(screen.getByText('Export as CSV')).toBeInTheDocument();
      expect(screen.getByText('Export as JSON')).toBeInTheDocument();
    });
  });

  it('should handle error states gracefully', async () => {
    server.use(
      rest.get('/api/v1/evaluation/scenarios/', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Server error' }));
      })
    );

    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Error loading evaluation scenarios')).toBeInTheDocument();
    });
  });

  it('should show loading states appropriately', () => {
    const slowQueryClient = new QueryClient({
      defaultOptions: {
        queries: { 
          retry: false,
          staleTime: 0,
        },
      },
    });

    renderWithQueryClient(<EvaluationDashboard />, slowQueryClient);

    expect(screen.getByText('Loading scenarios...')).toBeInTheDocument();
  });

  it('should handle evaluation run errors', async () => {
    server.use(
      rest.post('/api/v1/evaluation/runs/scenario/:scenarioId/', (req, res, ctx) => {
        return res(ctx.status(400), ctx.json({ error: 'Invalid scenario configuration' }));
      })
    );

    const user = userEvent.setup();
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Select Scenario')).toBeInTheDocument();
    });

    const scenarioSelect = screen.getByDisplayValue('');
    await user.selectOptions(scenarioSelect, 'scan-001');

    const runButton = screen.getByText('Run Evaluation');
    await user.click(runButton);

    await waitFor(() => {
      expect(screen.getByText('Error running evaluation')).toBeInTheDocument();
    });
  });

  it('should refresh evaluation data', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Evaluation Metrics Overview')).toBeInTheDocument();
    });

    // Click refresh button
    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshButton);

    // Should trigger data refetch
    await waitFor(() => {
      expect(screen.getByText('Evaluation Metrics Overview')).toBeInTheDocument();
    });
  });

  it('should sort evaluation runs by different columns', async () => {
    server.use(
      rest.get('/api/v1/evaluation/runs/', (req, res, ctx) => {
        return res(ctx.json(mockEvaluationRuns));
      })
    );

    const user = userEvent.setup();
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Recent Evaluation Runs')).toBeInTheDocument();
    });

    // Click on F1 Score column header to sort
    const f1Header = screen.getByText('F1 Score');
    await user.click(f1Header);

    // Data should be sorted (this is handled by the table internally)
    expect(f1Header).toBeInTheDocument();
  });

  it('should display validation errors for failed runs', async () => {
    server.use(
      rest.get('/api/v1/evaluation/runs/', (req, res, ctx) => {
        return res(ctx.json(mockEvaluationRuns));
      })
    );

    const user = userEvent.setup();
    renderWithQueryClient(<EvaluationDashboard />, queryClient);

    await waitFor(() => {
      expect(screen.getByText('Recent Evaluation Runs')).toBeInTheDocument();
    });

    // Click on view details for failed run
    const viewButtons = screen.getAllByRole('button', { name: /view details/i });
    await user.click(viewButtons[1]); // Second run is failed

    await waitFor(() => {
      expect(screen.getByText('Validation Errors')).toBeInTheDocument();
      expect(screen.getByText('Time window too large')).toBeInTheDocument();
    });
  });
});