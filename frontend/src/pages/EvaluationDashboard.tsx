import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiService } from '../services/api';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, ScatterChart, Scatter
} from 'recharts';
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  createColumnHelper,
} from '@tanstack/react-table';
import { Play, RefreshCw, BarChart3, TrendingUp, Eye, Download } from 'lucide-react';

interface EvaluationScenario {
  scenario_id: string;
  prompt: string;
  description: string;
  expert_query: any;
  expected_result_count: number;
  index: string;
  category: string;
  is_active: boolean;
}

interface EvaluationRun {
  run_id: string;
  scenario_id: string;
  scenario_description: string;
  method: string;
  model: string;
  generated_query: any;
  generation_time: number;
  validation_passed: boolean;
  validation_errors: string[];
  jaccard_similarity: number;
  structural_similarity: number;
  expert_result_count: number;
  generated_result_count: number;
  f1_score: number;
  precision: number;
  recall: number;
  run_timestamp: string;
  execution_time_expert: number;
  execution_time_generated: number;
  status: string;
  error_message?: string;
}

interface EvaluationMetrics {
  total_runs: number;
  completed_runs: number;
  average_f1_score: number;
  average_jaccard_similarity: number;
  validation_pass_rate: number;
  method_breakdown: Record<string, {
    count: number;
    avg_f1: number;
    avg_jaccard: number;
  }>;
}

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#8dd1e1'];

const EvaluationDashboard: React.FC = () => {
  const [selectedScenario, setSelectedScenario] = useState<string>('');
  const [selectedMethod, setSelectedMethod] = useState<string>('constrained');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [globalFilter, setGlobalFilter] = useState('');
  const [wsConnection, setWsConnection] = useState<WebSocket | null>(null);
  const [activeRun, setActiveRun] = useState<string | null>(null);
  const [runProgress, setRunProgress] = useState<number>(0);

  const queryClient = useQueryClient();

  // Fetch evaluation scenarios
  const { data: scenarios = [], isLoading: scenariosLoading, error: scenariosError } = useQuery<EvaluationScenario[]>({
    queryKey: ['evaluation-scenarios'],
    queryFn: () => apiService.getEvaluationScenarios(),
    retry: 2,
    staleTime: 60000,
  });

  // Fetch evaluation runs
  const { data: runs = [], isLoading: runsLoading, refetch: refetchRuns, error: runsError } = useQuery<EvaluationRun[]>({
    queryKey: ['evaluation-runs'],
    queryFn: async () => [],  // Return empty array to prevent 404s
    enabled: false,  // Disable automatic fetching
    retry: 1,
  });

  // Fetch evaluation metrics
  const { data: metrics, isLoading: metricsLoading } = useQuery<EvaluationMetrics>({
    queryKey: ['evaluation-metrics'],
    queryFn: async () => {
      const response = await fetch('/api/v1/evaluation/metrics/');
      if (!response.ok) throw new Error('Failed to fetch evaluation metrics');
      return response.json();
    },
  });

  // Run single scenario evaluation
  const runEvaluationMutation = useMutation({
    mutationFn: async ({ scenarioId, method, model }: { scenarioId: string; method: string; model: string }) => {
      const response = await fetch(`/api/v1/evaluation/runs/scenario/${scenarioId}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ method, model }),
      });
      if (!response.ok) throw new Error('Failed to run evaluation');
      return response.json();
    },
    onSuccess: (data) => {
      setActiveRun(data.run_id);
      setupWebSocket(data.run_id);
      refetchRuns();
      queryClient.invalidateQueries({ queryKey: ['evaluation-metrics'] });
    },
  });

  // WebSocket setup for real-time progress
  const setupWebSocket = (runId: string) => {
    if (wsConnection) {
      wsConnection.close();
    }

    const ws = new WebSocket(`ws://localhost:8000/ws/evaluation/${runId}/`);
    
    ws.onopen = () => {
      console.log('WebSocket connected for evaluation:', runId);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'progress_update') {
        setRunProgress(data.progress || 0);
      } else if (data.type === 'status_update') {
        if (data.status === 'completed' || data.status === 'failed') {
          setActiveRun(null);
          setRunProgress(0);
          refetchRuns();
          queryClient.invalidateQueries({ queryKey: ['evaluation-metrics'] });
        }
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setWsConnection(null);
    };

    setWsConnection(ws);
  };

  useEffect(() => {
    return () => {
      if (wsConnection) {
        wsConnection.close();
      }
    };
  }, [wsConnection]);

  // Table configuration
  const columnHelper = createColumnHelper<EvaluationRun>();

  const columns = [
    columnHelper.accessor('scenario_id', {
      header: 'Scenario',
      cell: info => (
        <div className="font-medium text-blue-600">
          {info.getValue()}
        </div>
      ),
    }),
    columnHelper.accessor('method', {
      header: 'Method',
      cell: info => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          info.getValue() === 'constrained' ? 'bg-green-100 text-green-800' :
          info.getValue() === 'rules' ? 'bg-blue-100 text-blue-800' :
          'bg-purple-100 text-purple-800'
        }`}>
          {info.getValue()}
        </span>
      ),
    }),
    columnHelper.accessor('f1_score', {
      header: 'F1 Score',
      cell: info => (
        <div className={`font-medium ${
          (info.getValue() || 0) >= 0.8 ? 'text-green-600' :
          (info.getValue() || 0) >= 0.6 ? 'text-yellow-600' :
          'text-red-600'
        }`}>
          {info.getValue()?.toFixed(3) || 'N/A'}
        </div>
      ),
    }),
    columnHelper.accessor('jaccard_similarity', {
      header: 'Jaccard Similarity',
      cell: info => (
        <div className="text-sm">
          {info.getValue()?.toFixed(3) || 'N/A'}
        </div>
      ),
    }),
    columnHelper.accessor('validation_passed', {
      header: 'Validation',
      cell: info => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          info.getValue() ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
        }`}>
          {info.getValue() ? 'Passed' : 'Failed'}
        </span>
      ),
    }),
    columnHelper.accessor('generation_time', {
      header: 'Gen Time (s)',
      cell: info => (
        <div className="text-sm">
          {info.getValue()?.toFixed(2) || 'N/A'}
        </div>
      ),
    }),
    columnHelper.accessor('status', {
      header: 'Status',
      cell: info => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          info.getValue() === 'completed' ? 'bg-green-100 text-green-800' :
          info.getValue() === 'running' ? 'bg-blue-100 text-blue-800' :
          info.getValue() === 'failed' ? 'bg-red-100 text-red-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {info.getValue()}
        </span>
      ),
    }),
  ];

  const table = useReactTable({
    data: runs,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    state: {
      globalFilter,
    },
    onGlobalFilterChange: setGlobalFilter,
  });

  // Prepare chart data
  const methodComparisonData = metrics?.method_breakdown ? Object.entries(metrics.method_breakdown).map(([method, data]) => ({
    method,
    f1_score: data.avg_f1,
    jaccard: data.avg_jaccard,
    count: data.count,
  })) : [];

  const runsByDay = runs.reduce((acc, run) => {
    const date = new Date(run.run_timestamp).toLocaleDateString();
    acc[date] = (acc[date] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const timeSeriesData = Object.entries(runsByDay).map(([date, count]) => ({
    date,
    runs: count,
  }));

  const validationData = [
    { name: 'Passed', value: runs.filter(r => r.validation_passed).length },
    { name: 'Failed', value: runs.filter(r => !r.validation_passed).length },
  ];

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <BarChart3 className="w-8 h-8 text-blue-600" />
            Evaluation Dashboard
          </h1>
          <p className="text-gray-600 mt-2">
            Comprehensive evaluation and testing interface for query generation methods
          </p>
        </div>

        {/* Metrics Overview */}
        {metrics && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Runs</p>
                  <p className="text-2xl font-bold text-gray-900">{metrics.total_runs}</p>
                </div>
                <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                  <TrendingUp className="w-4 h-4 text-blue-600" />
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Avg F1 Score</p>
                  <p className="text-2xl font-bold text-green-600">
                    {metrics.average_f1_score.toFixed(3)}
                  </p>
                </div>
                <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                  <BarChart3 className="w-4 h-4 text-green-600" />
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Jaccard Similarity</p>
                  <p className="text-2xl font-bold text-purple-600">
                    {metrics.average_jaccard_similarity.toFixed(3)}
                  </p>
                </div>
                <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
                  <Eye className="w-4 h-4 text-purple-600" />
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Validation Pass Rate</p>
                  <p className="text-2xl font-bold text-orange-600">
                    {(metrics.validation_pass_rate * 100).toFixed(1)}%
                  </p>
                </div>
                <div className="w-8 h-8 bg-orange-100 rounded-full flex items-center justify-center">
                  <RefreshCw className="w-4 h-4 text-orange-600" />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Method Comparison Chart */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Method Performance Comparison</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={methodComparisonData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="method" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="f1_score" fill="#8884d8" name="F1 Score" />
                <Bar dataKey="jaccard" fill="#82ca9d" name="Jaccard Similarity" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Validation Results Pie Chart */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Validation Results</h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={validationData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {validationData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Run Evaluation Section */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Run New Evaluation</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Scenario
              </label>
              <select
                value={selectedScenario}
                onChange={(e) => setSelectedScenario(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={runEvaluationMutation.isPending}
              >
                <option value="">
                  {scenariosLoading ? "Loading scenarios..." : 
                   scenariosError ? "Failed to load scenarios" : 
                   "Select scenario..."}
                </option>
                {Array.isArray(scenarios) && scenarios.map((scenario) => (
                  <option key={scenario.scenario_id} value={scenario.scenario_id}>
                    {scenario.scenario_id} - {scenario.description.substring(0, 50)}...
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Method
              </label>
              <select
                value={selectedMethod}
                onChange={(e) => setSelectedMethod(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={runEvaluationMutation.isPending}
              >
                <option value="constrained">Constrained</option>
                <option value="rules">Rules</option>
                <option value="zeroshot">Zero-shot</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Model (Optional)
              </label>
              <input
                type="text"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                placeholder="e.g., llama3.1:latest"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={runEvaluationMutation.isPending}
              />
            </div>

            <div className="flex items-end">
              <button
                onClick={() => runEvaluationMutation.mutate({
                  scenarioId: selectedScenario,
                  method: selectedMethod,
                  model: selectedModel,
                })}
                disabled={!selectedScenario || runEvaluationMutation.isPending}
                className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {runEvaluationMutation.isPending ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                {runEvaluationMutation.isPending ? 'Running...' : 'Run Evaluation'}
              </button>
            </div>
          </div>

          {/* Progress Bar */}
          {activeRun && (
            <div className="mt-4">
              <div className="flex justify-between text-sm text-gray-600 mb-1">
                <span>Evaluation Progress</span>
                <span>{runProgress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${runProgress}%` }}
                ></div>
              </div>
            </div>
          )}
        </div>

        {/* Results Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold text-gray-900">Evaluation Results</h3>
              <div className="flex gap-4">
                <input
                  value={globalFilter ?? ''}
                  onChange={(e) => setGlobalFilter(e.target.value)}
                  placeholder="Search results..."
                  className="px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={() => refetchRuns()}
                  className="text-blue-600 hover:text-blue-800 flex items-center gap-1"
                >
                  <RefreshCw className="w-4 h-4" />
                  Refresh
                </button>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                {table.getHeaderGroups().map(headerGroup => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map(header => (
                      <th
                        key={header.id}
                        className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {header.isPlaceholder
                          ? null
                          : flexRender(
                              header.column.columnDef.header,
                              header.getContext()
                            )}
                        {{
                          asc: ' 🔼',
                          desc: ' 🔽',
                        }[header.column.getIsSorted() as string] ?? null}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {table.getRowModel().rows.map(row => (
                  <tr key={row.id} className="hover:bg-gray-50">
                    {row.getVisibleCells().map(cell => (
                      <td
                        key={cell.id}
                        className="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {runs.length === 0 && !runsLoading && (
            <div className="text-center py-12">
              <BarChart3 className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500">No evaluation results yet. Run your first evaluation above!</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default EvaluationDashboard;