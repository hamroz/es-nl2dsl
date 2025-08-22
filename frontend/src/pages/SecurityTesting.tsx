import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  LineChart, Line
} from 'recharts';
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  createColumnHelper,
} from '@tanstack/react-table';
import { 
  Shield, ShieldAlert, Play, RefreshCw, AlertTriangle, Eye, Plus, 
  Filter, Search, Target, TrendingUp, AlertCircle 
} from 'lucide-react';

interface AdversarialPrompt {
  prompt_id: string;
  prompt_text: string;
  category: string;
  severity: string;
  description: string;
  expected_behavior: string;
  created_at: string;
  is_active: boolean;
}

interface SecurityTest {
  test_id: string;
  test_name: string;
  description: string;
  method: string;
  model: string;
  total_prompts: number;
  abstain_count: number;
  malicious_count: number;
  valid_count: number;
  abstain_rate: number;
  security_pass_rate: number;
  started_at: string;
  completed_at: string;
  status: string;
}

interface SecurityTestResult {
  result_id: string;
  prompt_id: string;
  prompt_category: string;
  prompt_severity: string;
  generated_query: any;
  generation_time: number;
  abstained: boolean;
  validation_passed: boolean;
  validation_errors: string[];
  is_malicious: boolean;
  security_risk_level: string;
  security_notes: string;
  tested_at: string;
  status: string;
  error_message?: string;
}

interface SecurityMetrics {
  total_tests: number;
  completed_tests: number;
  total_prompts_tested: number;
  overall_abstain_rate: number;
  overall_malicious_rate: number;
  average_security_pass_rate: number;
  method_breakdown: Record<string, {
    test_count: number;
    prompt_count: number;
    abstain_rate: number;
    avg_security_pass_rate: number;
  }>;
}

const COLORS = ['#10b981', '#ef4444', '#f59e0b', '#8b5cf6', '#06b6d4'];
const SEVERITY_COLORS = {
  low: '#10b981',
  medium: '#f59e0b',
  high: '#ef4444',
  critical: '#7c2d12'
};

const SecurityTesting: React.FC = () => {
  const [selectedMethod, setSelectedMethod] = useState<string>('constrained');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [testName, setTestName] = useState<string>('');
  const [testDescription, setTestDescription] = useState<string>('');
  const [globalFilter, setGlobalFilter] = useState('');
  const [wsConnection, setWsConnection] = useState<WebSocket | null>(null);
  const [activeTest, setActiveTest] = useState<string | null>(null);
  const [testProgress, setTestProgress] = useState<number>(0);
  const [showCreatePrompt, setShowCreatePrompt] = useState<boolean>(false);

  const queryClient = useQueryClient();

  // Fetch adversarial prompts
  const { data: prompts = [], isLoading: promptsLoading, refetch: refetchPrompts } = useQuery<AdversarialPrompt[]>({
    queryKey: ['adversarial-prompts'],
    queryFn: async () => {
      const response = await fetch('/api/security/prompts/');
      if (!response.ok) throw new Error('Failed to fetch prompts');
      return response.json();
    },
  });

  // Fetch security tests
  const { data: tests = [], isLoading: testsLoading, refetch: refetchTests } = useQuery<SecurityTest[]>({
    queryKey: ['security-tests'],
    queryFn: async () => {
      const response = await fetch('/api/security/tests/');
      if (!response.ok) throw new Error('Failed to fetch security tests');
      return response.json();
    },
  });

  // Fetch security test results
  const { data: results = [], isLoading: resultsLoading, refetch: refetchResults } = useQuery<SecurityTestResult[]>({
    queryKey: ['security-test-results'],
    queryFn: async () => {
      const response = await fetch('/api/security/results/');
      if (!response.ok) throw new Error('Failed to fetch test results');
      return response.json();
    },
  });

  // Fetch security metrics
  const { data: metrics, isLoading: metricsLoading } = useQuery<SecurityMetrics>({
    queryKey: ['security-metrics'],
    queryFn: async () => {
      const response = await fetch('/api/security/metrics/');
      if (!response.ok) throw new Error('Failed to fetch security metrics');
      return response.json();
    },
  });

  // Run security test mutation
  const runSecurityTestMutation = useMutation({
    mutationFn: async (testData: {
      test_name: string;
      description: string;
      method: string;
      model: string;
      categories: string[];
    }) => {
      const response = await fetch('/api/security/tests/run/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(testData),
      });
      if (!response.ok) throw new Error('Failed to run security test');
      return response.json();
    },
    onSuccess: (data) => {
      setActiveTest(data.test_id);
      setupWebSocket(data.test_id);
      refetchTests();
      queryClient.invalidateQueries({ queryKey: ['security-metrics'] });
    },
  });

  // Create adversarial prompt mutation
  const createPromptMutation = useMutation({
    mutationFn: async (promptData: {
      prompt_id: string;
      prompt_text: string;
      category: string;
      severity: string;
      description: string;
      expected_behavior: string;
    }) => {
      const response = await fetch('/api/security/prompts/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(promptData),
      });
      if (!response.ok) throw new Error('Failed to create prompt');
      return response.json();
    },
    onSuccess: () => {
      refetchPrompts();
      setShowCreatePrompt(false);
    },
  });

  // WebSocket setup for real-time progress
  const setupWebSocket = (testId: string) => {
    if (wsConnection) {
      wsConnection.close();
    }

    const ws = new WebSocket(`ws://localhost:8001/ws/security/${testId}/`);
    
    ws.onopen = () => {
      console.log('WebSocket connected for security test:', testId);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'progress_update') {
        setTestProgress(data.progress || 0);
      } else if (data.type === 'status_update') {
        if (data.status === 'completed' || data.status === 'failed') {
          setActiveTest(null);
          setTestProgress(0);
          refetchTests();
          refetchResults();
          queryClient.invalidateQueries({ queryKey: ['security-metrics'] });
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

  // Table configuration for results
  const columnHelper = createColumnHelper<SecurityTestResult>();

  const columns = [
    columnHelper.accessor('prompt_id', {
      header: 'Prompt ID',
      cell: info => (
        <div className="font-medium text-blue-600">
          {info.getValue()}
        </div>
      ),
    }),
    columnHelper.accessor('prompt_category', {
      header: 'Category',
      cell: info => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          info.getValue() === 'injection' ? 'bg-red-100 text-red-800' :
          info.getValue() === 'bypass' ? 'bg-orange-100 text-orange-800' :
          info.getValue() === 'extraction' ? 'bg-purple-100 text-purple-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {info.getValue()}
        </span>
      ),
    }),
    columnHelper.accessor('prompt_severity', {
      header: 'Severity',
      cell: info => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          info.getValue() === 'critical' ? 'bg-red-900 text-red-100' :
          info.getValue() === 'high' ? 'bg-red-100 text-red-800' :
          info.getValue() === 'medium' ? 'bg-yellow-100 text-yellow-800' :
          'bg-green-100 text-green-800'
        }`}>
          {info.getValue()}
        </span>
      ),
    }),
    columnHelper.accessor('abstained', {
      header: 'Abstained',
      cell: info => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          info.getValue() ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
        }`}>
          {info.getValue() ? 'Yes' : 'No'}
        </span>
      ),
    }),
    columnHelper.accessor('is_malicious', {
      header: 'Malicious',
      cell: info => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          info.getValue() ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
        }`}>
          {info.getValue() ? 'Yes' : 'No'}
        </span>
      ),
    }),
    columnHelper.accessor('security_risk_level', {
      header: 'Risk Level',
      cell: info => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          info.getValue() === 'critical' ? 'bg-red-900 text-red-100' :
          info.getValue() === 'high' ? 'bg-red-100 text-red-800' :
          info.getValue() === 'medium' ? 'bg-yellow-100 text-yellow-800' :
          info.getValue() === 'low' ? 'bg-blue-100 text-blue-800' :
          'bg-green-100 text-green-800'
        }`}>
          {info.getValue() || 'none'}
        </span>
      ),
    }),
    columnHelper.accessor('generation_time', {
      header: 'Time (s)',
      cell: info => (
        <div className="text-sm">
          {info.getValue()?.toFixed(2) || 'N/A'}
        </div>
      ),
    }),
  ];

  const table = useReactTable({
    data: results,
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
  const categoryData = prompts.reduce((acc, prompt) => {
    acc[prompt.category] = (acc[prompt.category] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const categoryChartData = Object.entries(categoryData).map(([category, count]) => ({
    category,
    count,
  }));

  const severityData = prompts.reduce((acc, prompt) => {
    acc[prompt.severity] = (acc[prompt.severity] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const severityChartData = Object.entries(severityData).map(([severity, count]) => ({
    severity,
    count,
    fill: SEVERITY_COLORS[severity as keyof typeof SEVERITY_COLORS] || '#gray',
  }));

  const abstainRateData = results.reduce((acc, result) => {
    const category = result.prompt_category;
    if (!acc[category]) {
      acc[category] = { total: 0, abstained: 0 };
    }
    acc[category].total++;
    if (result.abstained) {
      acc[category].abstained++;
    }
    return acc;
  }, {} as Record<string, { total: number; abstained: number }>);

  const abstainChartData = Object.entries(abstainRateData).map(([category, data]) => ({
    category,
    abstain_rate: data.total > 0 ? (data.abstained / data.total) * 100 : 0,
  }));

  const categories = [...new Set(prompts.map(p => p.category))];

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="w-8 h-8 text-red-600" />
            Security Testing
          </h1>
          <p className="text-gray-600 mt-2">
            Red team testing and security validation interface for adversarial prompt detection
          </p>
        </div>

        {/* Metrics Overview */}
        {metrics && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Tests</p>
                  <p className="text-2xl font-bold text-gray-900">{metrics.total_tests}</p>
                </div>
                <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                  <Target className="w-4 h-4 text-blue-600" />
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Abstain Rate</p>
                  <p className="text-2xl font-bold text-green-600">
                    {(metrics.overall_abstain_rate * 100).toFixed(1)}%
                  </p>
                </div>
                <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                  <Shield className="w-4 h-4 text-green-600" />
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Malicious Rate</p>
                  <p className="text-2xl font-bold text-red-600">
                    {(metrics.overall_malicious_rate * 100).toFixed(1)}%
                  </p>
                </div>
                <div className="w-8 h-8 bg-red-100 rounded-full flex items-center justify-center">
                  <ShieldAlert className="w-4 h-4 text-red-600" />
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Security Pass Rate</p>
                  <p className="text-2xl font-bold text-purple-600">
                    {(metrics.average_security_pass_rate * 100).toFixed(1)}%
                  </p>
                </div>
                <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
                  <TrendingUp className="w-4 h-4 text-purple-600" />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Category Distribution */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Prompt Categories</h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={categoryChartData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ category, percent }) => `${category} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="count"
                >
                  {categoryChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Severity Distribution */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Severity Levels</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={severityChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="severity" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#8884d8" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Abstain Rate by Category */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Abstain Rate by Category</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={abstainChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="category" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="abstain_rate" fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Run Security Test Section */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Run Security Test</h3>
            <button
              onClick={() => setShowCreatePrompt(true)}
              className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Create Prompt
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Test Name
              </label>
              <input
                type="text"
                value={testName}
                onChange={(e) => setTestName(e.target.value)}
                placeholder="e.g., Injection Test v1"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={runSecurityTestMutation.isPending}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Method
              </label>
              <select
                value={selectedMethod}
                onChange={(e) => setSelectedMethod(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={runSecurityTestMutation.isPending}
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
                disabled={runSecurityTestMutation.isPending}
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Categories (Optional)
              </label>
              <div className="flex flex-wrap gap-2">
                {categories.map(category => (
                  <label key={category} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={selectedCategories.includes(category)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedCategories([...selectedCategories, category]);
                        } else {
                          setSelectedCategories(selectedCategories.filter(c => c !== category));
                        }
                      }}
                      className="mr-2"
                      disabled={runSecurityTestMutation.isPending}
                    />
                    <span className="text-sm">{category}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Description
              </label>
              <textarea
                value={testDescription}
                onChange={(e) => setTestDescription(e.target.value)}
                placeholder="Test description..."
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={runSecurityTestMutation.isPending}
              />
            </div>
          </div>

          <div className="flex justify-between items-center">
            <button
              onClick={() => runSecurityTestMutation.mutate({
                test_name: testName,
                description: testDescription,
                method: selectedMethod,
                model: selectedModel,
                categories: selectedCategories,
              })}
              disabled={!testName || runSecurityTestMutation.isPending}
              className="bg-red-600 text-white px-6 py-2 rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {runSecurityTestMutation.isPending ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              {runSecurityTestMutation.isPending ? 'Running Test...' : 'Run Security Test'}
            </button>
          </div>

          {/* Progress Bar */}
          {activeTest && (
            <div className="mt-4">
              <div className="flex justify-between text-sm text-gray-600 mb-1">
                <span>Security Test Progress</span>
                <span>{testProgress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-red-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${testProgress}%` }}
                ></div>
              </div>
            </div>
          )}
        </div>

        {/* Results Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold text-gray-900">Test Results</h3>
              <div className="flex gap-4">
                <input
                  value={globalFilter ?? ''}
                  onChange={(e) => setGlobalFilter(e.target.value)}
                  placeholder="Search results..."
                  className="px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={() => refetchResults()}
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

          {results.length === 0 && !resultsLoading && (
            <div className="text-center py-12">
              <ShieldAlert className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500">No security test results yet. Run your first test above!</p>
            </div>
          )}
        </div>

        {/* Create Prompt Modal */}
        {showCreatePrompt && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg max-w-2xl w-full max-h-screen overflow-y-auto">
              <div className="p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Create Adversarial Prompt</h3>
                {/* Add form fields for creating new prompts */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Prompt ID</label>
                    <input 
                      type="text" 
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder="e.g., injection-001"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Prompt Text</label>
                    <textarea 
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      rows={3}
                      placeholder="Enter the adversarial prompt..."
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Category</label>
                      <select className="w-full px-3 py-2 border border-gray-300 rounded-md">
                        <option value="injection">Prompt Injection</option>
                        <option value="bypass">Security Bypass</option>
                        <option value="extraction">Data Extraction</option>
                        <option value="manipulation">Query Manipulation</option>
                        <option value="escalation">Privilege Escalation</option>
                        <option value="other">Other</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Severity</label>
                      <select className="w-full px-3 py-2 border border-gray-300 rounded-md">
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="critical">Critical</option>
                      </select>
                    </div>
                  </div>
                </div>
                <div className="flex justify-end gap-4 mt-6">
                  <button
                    onClick={() => setShowCreatePrompt(false)}
                    className="px-4 py-2 text-gray-600 hover:text-gray-800"
                  >
                    Cancel
                  </button>
                  <button
                    className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
                  >
                    Create Prompt
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SecurityTesting;