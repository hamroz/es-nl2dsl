import React from 'react';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient } from '@tanstack/react-query';
import { rest } from 'msw';
import { server } from '../../test/mocks/server';
import { 
  render, 
  renderWithQueryClient,
  mockQueryTask, 
  mockQueryResults,
  createMockWebSocket,
  simulateWebSocketMessage,
  mockConsole,
  waitForAsync 
} from '../../test/utils/testUtils';
import QueryGenerator from '../QueryGenerator';

// Mock the QueryBuilder component
jest.mock('../../components/QueryBuilder', () => {
  return function MockQueryBuilder({ onExecute, onSave }: any) {
    return (
      <div data-testid="query-builder">
        <button 
          onClick={() => onExecute({ query: { match_all: {} } })}
        >
          Execute Visual Query
        </button>
        <button 
          onClick={() => onSave({ query: { match_all: {} } }, 'Test Query')}
        >
          Save Query
        </button>
      </div>
    );
  };
});

// Mock WebSocket
const mockWebSocket = createMockWebSocket();
global.WebSocket = jest.fn(() => mockWebSocket) as any;

describe('QueryGenerator Component', () => {
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
    jest.clearAllMocks();
  });

  afterEach(() => {
    consoleMock.restore();
  });

  it('should render query generator interface', () => {
    renderWithQueryClient(<QueryGenerator />, queryClient);

    expect(screen.getByText('🤖 Query Generator')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter your natural language query...')).toBeInTheDocument();
    expect(screen.getByText('Generate Query')).toBeInTheDocument();
  });

  it('should show tab navigation for natural language and visual query builder', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    expect(screen.getByText('Natural Language')).toBeInTheDocument();
    expect(screen.getByText('Visual Builder')).toBeInTheDocument();

    // Click on Visual Builder tab
    await user.click(screen.getByText('Visual Builder'));
    expect(screen.getByTestId('query-builder')).toBeInTheDocument();

    // Go back to Natural Language tab
    await user.click(screen.getByText('Natural Language'));
    expect(screen.getByPlaceholderText('Enter your natural language query...')).toBeInTheDocument();
  });

  it('should handle form input changes', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    await user.type(promptInput, 'Find malicious events');

    expect(promptInput).toHaveValue('Find malicious events');
  });

  it('should handle method selection', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const methodSelect = screen.getByDisplayValue('constrained');
    await user.selectOptions(methodSelect, 'rules');

    expect(methodSelect).toHaveValue('rules');
  });

  it('should handle index selection', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    await waitFor(() => {
      const indexSelect = screen.getByDisplayValue('logs_net');
      expect(indexSelect).toBeInTheDocument();
    });

    const indexSelect = screen.getByDisplayValue('logs_net');
    await user.selectOptions(indexSelect, 'logs_cic_ids2017');

    expect(indexSelect).toHaveValue('logs_cic_ids2017');
  });

  it('should submit query generation form', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    const generateButton = screen.getByText('Generate Query');

    await user.type(promptInput, 'Find malicious events');
    await user.click(generateButton);

    // Should show task progress
    await waitFor(() => {
      expect(screen.getByText('Query Generation in Progress')).toBeInTheDocument();
    });
  });

  it('should prevent submission with empty prompt', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const generateButton = screen.getByText('Generate Query');
    await user.click(generateButton);

    // Should not submit with empty prompt
    expect(screen.queryByText('Query Generation in Progress')).not.toBeInTheDocument();
  });

  it('should show WebSocket connection status', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    const generateButton = screen.getByText('Generate Query');

    await user.type(promptInput, 'Find malicious events');
    await user.click(generateButton);

    // WebSocket should be connected
    expect(consoleMock.mockLog).toHaveBeenCalledWith(
      'WebSocket connected for query generation:', 
      'mock-task-id-123'
    );
  });

  it('should handle WebSocket progress updates', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    const generateButton = screen.getByText('Generate Query');

    await user.type(promptInput, 'Find malicious events');
    await user.click(generateButton);

    // Simulate WebSocket progress update
    simulateWebSocketMessage(mockWebSocket, {
      type: 'progress_update',
      progress: 50
    });

    await waitFor(() => {
      expect(screen.getByText('Progress: 50%')).toBeInTheDocument();
    });
  });

  it('should handle WebSocket status updates', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    const generateButton = screen.getByText('Generate Query');

    await user.type(promptInput, 'Find malicious events');
    await user.click(generateButton);

    // Simulate status update to completed
    simulateWebSocketMessage(mockWebSocket, {
      type: 'status_update',
      status: 'completed'
    });

    await waitFor(() => {
      expect(screen.getByText('Query Generation Completed')).toBeInTheDocument();
    });
  });

  it('should handle WebSocket task updates', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    const generateButton = screen.getByText('Generate Query');

    await user.type(promptInput, 'Find malicious events');
    await user.click(generateButton);

    // Simulate full task update
    simulateWebSocketMessage(mockWebSocket, {
      type: 'task_update',
      task: {
        task_id: 'mock-task-id-123',
        status: 'completed',
        query: { query: { match_all: {} } }
      }
    });

    await waitFor(() => {
      expect(screen.getByText('Generated Query (JSON)')).toBeInTheDocument();
    });
  });

  it('should show generated query results', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    const generateButton = screen.getByText('Generate Query');

    await user.type(promptInput, 'Find malicious events');
    await user.click(generateButton);

    // Wait for completion
    await waitFor(() => {
      expect(screen.getByText('Query Generation Completed')).toBeInTheDocument();
    });

    // Should show generated query
    expect(screen.getByText('Generated Query (JSON)')).toBeInTheDocument();
    expect(screen.getByText('Validation: PASS')).toBeInTheDocument();
  });

  it('should handle query execution', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    const generateButton = screen.getByText('Generate Query');

    await user.type(promptInput, 'Find malicious events');
    await user.click(generateButton);

    // Wait for generation to complete
    await waitFor(() => {
      expect(screen.getByText('Execute Query')).toBeInTheDocument();
    });

    // Execute the query
    const executeButton = screen.getByText('Execute Query');
    await user.click(executeButton);

    // Should show execution results
    await waitFor(() => {
      expect(screen.getByText('Query Results')).toBeInTheDocument();
      expect(screen.getByText('Total: 150 hits')).toBeInTheDocument();
    });
  });

  it('should handle max size configuration', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const maxSizeInput = screen.getByDisplayValue('1000');
    await user.clear(maxSizeInput);
    await user.type(maxSizeInput, '500');

    expect(maxSizeInput).toHaveValue(500);
  });

  it('should display query execution results in table format', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    await user.type(promptInput, 'Find malicious events');
    await user.click(screen.getByText('Generate Query'));

    await waitFor(() => {
      expect(screen.getByText('Execute Query')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Execute Query'));

    await waitFor(() => {
      expect(screen.getByText('Query Results')).toBeInTheDocument();
      expect(screen.getByText('192.168.1.100')).toBeInTheDocument(); // Source IP from mock data
      expect(screen.getByText('10.0.0.1')).toBeInTheDocument(); // Destination IP from mock data
    });
  });

  it('should show export options for results', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    await user.type(promptInput, 'Find malicious events');
    await user.click(screen.getByText('Generate Query'));

    await waitFor(() => {
      expect(screen.getByText('Execute Query')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Execute Query'));

    await waitFor(() => {
      expect(screen.getByText('Export CSV')).toBeInTheDocument();
      expect(screen.getByText('Export JSON')).toBeInTheDocument();
    });
  });

  it('should handle visual query builder execution', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    // Switch to visual builder
    await user.click(screen.getByText('Visual Builder'));

    // Execute visual query
    await user.click(screen.getByText('Execute Visual Query'));

    // Should show execution results
    await waitFor(() => {
      expect(screen.getByText('Query Results')).toBeInTheDocument();
    });
  });

  it('should handle visual query saving', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    // Switch to visual builder
    await user.click(screen.getByText('Visual Builder'));

    // Save visual query
    await user.click(screen.getByText('Save Query'));

    // Should log the save action (mocked implementation)
    expect(consoleMock.mockLog).toHaveBeenCalledWith(
      'Saving query:', 
      'Test Query', 
      { query: { match_all: {} } }
    );
  });

  it('should handle WebSocket errors gracefully', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    const generateButton = screen.getByText('Generate Query');

    await user.type(promptInput, 'Find malicious events');
    await user.click(generateButton);

    // Simulate WebSocket error
    if (mockWebSocket.onerror) {
      mockWebSocket.onerror(new Event('error'));
    }

    expect(consoleMock.mockWarn).toHaveBeenCalledWith(
      'WebSocket error, falling back to polling:', 
      expect.any(Event)
    );
  });

  it('should clean up WebSocket on unmount', () => {
    const { unmount } = renderWithQueryClient(<QueryGenerator />, queryClient);

    // Component should mount and potentially create WebSocket
    unmount();

    // WebSocket close should be called during cleanup
    expect(mockWebSocket.close).toHaveBeenCalled();
  });

  it('should handle API errors during generation', async () => {
    server.use(
      rest.post('/api/v1/queries/', (req, res, ctx) => {
        return res(ctx.status(400), ctx.json({ error: 'Invalid prompt format' }));
      })
    );

    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    const generateButton = screen.getByText('Generate Query');

    await user.type(promptInput, 'invalid prompt');
    await user.click(generateButton);

    // Should handle the error gracefully
    await waitFor(() => {
      expect(screen.queryByText('Query Generation in Progress')).not.toBeInTheDocument();
    });
  });

  it('should handle API errors during execution', async () => {
    server.use(
      rest.post('/api/v1/queries/:taskId/execute/', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Execution failed' }));
      })
    );

    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    await user.type(promptInput, 'Find malicious events');
    await user.click(screen.getByText('Generate Query'));

    await waitFor(() => {
      expect(screen.getByText('Execute Query')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Execute Query'));

    // Should handle execution error gracefully
    await waitFor(() => {
      expect(screen.queryByText('Query Results')).not.toBeInTheDocument();
    });
  });

  it('should show validation errors for failed queries', async () => {
    server.use(
      rest.get('/api/v1/queries/:taskId', (req, res, ctx) => {
        return res(ctx.json({
          ...mockQueryTask,
          validation: {
            status: 'FAIL',
            errors: ['Time window too large', 'Invalid field used']
          }
        }));
      })
    );

    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    await user.type(promptInput, 'Find events from 2020 to 2023');
    await user.click(screen.getByText('Generate Query'));

    await waitFor(() => {
      expect(screen.getByText('Validation: FAIL')).toBeInTheDocument();
      expect(screen.getByText('Time window too large')).toBeInTheDocument();
      expect(screen.getByText('Invalid field used')).toBeInTheDocument();
    });
  });

  it('should disable execute button for failed validation', async () => {
    server.use(
      rest.get('/api/v1/queries/:taskId', (req, res, ctx) => {
        return res(ctx.json({
          ...mockQueryTask,
          validation: {
            status: 'FAIL',
            errors: ['Validation failed']
          }
        }));
      })
    );

    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    await user.type(promptInput, 'Invalid query');
    await user.click(screen.getByText('Generate Query'));

    await waitFor(() => {
      expect(screen.getByText('Validation: FAIL')).toBeInTheDocument();
    });

    // Execute button should be disabled
    const executeButton = screen.queryByText('Execute Query');
    expect(executeButton).toBeNull(); // Should not be available for failed validation
  });

  it('should show generation metrics', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const promptInput = screen.getByPlaceholderText('Enter your natural language query...');
    await user.type(promptInput, 'Find malicious events');
    await user.click(screen.getByText('Generate Query'));

    await waitFor(() => {
      expect(screen.getByText('Generation Time: 5.2s')).toBeInTheDocument();
      expect(screen.getByText('Retries: 0')).toBeInTheDocument();
    });
  });

  it('should handle advanced options toggle', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<QueryGenerator />, queryClient);

    const advancedToggle = screen.getByText('Advanced Options');
    await user.click(advancedToggle);

    // Should show model selection
    expect(screen.getByText('Model (Optional)')).toBeInTheDocument();
  });
});