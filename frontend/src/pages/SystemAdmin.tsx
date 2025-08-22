import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell
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
  Server, Database, HardDrive, Cpu, MemoryStick, Activity, 
  CheckCircle, XCircle, AlertTriangle, Upload, Trash2, 
  RefreshCw, Settings, Monitor, FileText, Users
} from 'lucide-react';

interface SystemHealth {
  elasticsearch: {
    status: 'healthy' | 'unhealthy' | 'unknown';
    cluster_health: 'green' | 'yellow' | 'red';
    nodes: number;
    indices_count: number;
    docs_count: number;
    store_size: string;
  };
  ollama: {
    status: 'healthy' | 'unhealthy' | 'unknown';
    models: string[];
    running_models: string[];
  };
  system: {
    cpu_usage: number;
    memory_usage: number;
    disk_usage: number;
    uptime: number;
    load_average: number[];
  };
  indices: Array<{
    name: string;
    health: 'green' | 'yellow' | 'red';
    docs_count: number;
    store_size: string;
    created_at: string;
  }>;
}

interface DataIngestionTask {
  task_id: string;
  task_name: string;
  source_file: string;
  target_index: string;
  dataset_type: string;
  status: string;
  total_records: number;
  processed_records: number;
  progress_percentage: number;
  created_at: string;
  processing_time_seconds: number;
}

interface SystemMetrics {
  total_queries_generated: number;
  total_evaluations_run: number;
  total_security_tests: number;
  total_data_ingested_gb: number;
  avg_query_generation_time: number;
  avg_evaluation_f1_score: number;
  security_pass_rate: number;
  system_uptime_hours: number;
}

const COLORS = ['#0088fe', '#00c49f', '#ffbb28', '#ff8042', '#8884d8'];

const SystemAdmin: React.FC = () => {
  const [activeSection, setActiveSection] = useState<'dashboard' | 'indices' | 'ingestion' | 'logs'>('dashboard');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(30); // seconds
  const [autoRefresh, setAutoRefresh] = useState(true);

  const queryClient = useQueryClient();

  // System health data
  const { data: systemHealth, isLoading: healthLoading, refetch: refetchHealth } = useQuery<SystemHealth>({
    queryKey: ['system-health'],
    queryFn: async () => {
      const response = await fetch('/api/system/health/');
      if (!response.ok) throw new Error('Failed to fetch system health');
      return response.json();
    },
    refetchInterval: autoRefresh ? refreshInterval * 1000 : false,
  });

  // System metrics
  const { data: metrics, isLoading: metricsLoading } = useQuery<SystemMetrics>({
    queryKey: ['system-metrics'],
    queryFn: async () => {
      const response = await fetch('/api/system/metrics/');
      if (!response.ok) throw new Error('Failed to fetch system metrics');
      return response.json();
    },
    refetchInterval: autoRefresh ? refreshInterval * 1000 : false,
  });

  // Data ingestion tasks
  const { data: ingestionTasks = [], isLoading: tasksLoading, refetch: refetchTasks } = useQuery<DataIngestionTask[]>({
    queryKey: ['ingestion-tasks'],
    queryFn: async () => {
      const response = await fetch('/api/data/tasks/');
      if (!response.ok) throw new Error('Failed to fetch ingestion tasks');
      return response.json();
    },
  });

  // Delete index mutation
  const deleteIndexMutation = useMutation({
    mutationFn: async (indexName: string) => {
      const response = await fetch(`/api/data/indices/${indexName}/`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete index');
      return response.json();
    },
    onSuccess: () => {
      refetchHealth();
      queryClient.invalidateQueries({ queryKey: ['system-health'] });
    },
  });

  // Format bytes to human readable
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Format uptime
  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${days}d ${hours}h ${mins}m`;
  };

  // Table configuration for ingestion tasks
  const columnHelper = createColumnHelper<DataIngestionTask>();

  const taskColumns = [
    columnHelper.accessor('task_name', {
      header: 'Task Name',
      cell: info => (
        <div className="font-medium text-blue-600">
          {info.getValue()}
        </div>
      ),
    }),
    columnHelper.accessor('dataset_type', {
      header: 'Type',
      cell: info => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          info.getValue() === 'cic_ids2017' ? 'bg-purple-100 text-purple-800' :
          info.getValue() === 'general_csv' ? 'bg-blue-100 text-blue-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {info.getValue().replace('_', ' ')}
        </span>
      ),
    }),
    columnHelper.accessor('target_index', {
      header: 'Target Index',
      cell: info => (
        <code className="text-sm bg-gray-100 px-2 py-1 rounded">
          {info.getValue()}
        </code>
      ),
    }),
    columnHelper.accessor('status', {
      header: 'Status',
      cell: info => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          info.getValue() === 'completed' ? 'bg-green-100 text-green-800' :
          info.getValue() === 'processing' ? 'bg-blue-100 text-blue-800' :
          info.getValue() === 'failed' ? 'bg-red-100 text-red-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {info.getValue()}
        </span>
      ),
    }),
    columnHelper.accessor('progress_percentage', {
      header: 'Progress',
      cell: info => (
        <div className="w-24">
          <div className="bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full"
              style={{ width: `${info.getValue()}%` }}
            ></div>
          </div>
          <span className="text-xs text-gray-600">{info.getValue().toFixed(1)}%</span>
        </div>
      ),
    }),
    columnHelper.accessor('processed_records', {
      header: 'Records',
      cell: info => {
        const row = info.row.original;
        return (
          <div className="text-sm">
            {info.getValue()?.toLocaleString() || 0} / {row.total_records?.toLocaleString() || 0}
          </div>
        );
      },
    }),
  ];

  const taskTable = useReactTable({
    data: ingestionTasks,
    columns: taskColumns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  // Chart data preparation
  const systemUsageData = systemHealth ? [
    { name: 'CPU', usage: systemHealth.system.cpu_usage, color: '#8884d8' },
    { name: 'Memory', usage: systemHealth.system.memory_usage, color: '#82ca9d' },
    { name: 'Disk', usage: systemHealth.system.disk_usage, color: '#ffc658' },
  ] : [];

  const indexHealthData = systemHealth?.indices.map(index => ({
    name: index.name,
    docs: index.docs_count,
    size_mb: parseInt(index.store_size.replace(/[^0-9]/g, '')) || 0,
    health: index.health,
  })) || [];

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <Settings className="w-8 h-8 text-blue-600" />
            System Administration
          </h1>
          <p className="text-gray-600 mt-2">
            Comprehensive system monitoring and administration interface
          </p>
        </div>

        {/* Controls */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <div className="flex justify-between items-center">
            <div className="flex gap-4">
              <button
                onClick={() => setActiveSection('dashboard')}
                className={`px-4 py-2 rounded-md text-sm font-medium ${
                  activeSection === 'dashboard'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <Monitor className="w-4 h-4 inline mr-2" />
                Dashboard
              </button>
              <button
                onClick={() => setActiveSection('indices')}
                className={`px-4 py-2 rounded-md text-sm font-medium ${
                  activeSection === 'indices'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <Database className="w-4 h-4 inline mr-2" />
                Indices
              </button>
              <button
                onClick={() => setActiveSection('ingestion')}
                className={`px-4 py-2 rounded-md text-sm font-medium ${
                  activeSection === 'ingestion'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <Upload className="w-4 h-4 inline mr-2" />
                Data Ingestion
              </button>
              <button
                onClick={() => setActiveSection('logs')}
                className={`px-4 py-2 rounded-md text-sm font-medium ${
                  activeSection === 'logs'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <FileText className="w-4 h-4 inline mr-2" />
                System Logs
              </button>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="autoRefresh"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded"
                />
                <label htmlFor="autoRefresh" className="text-sm text-gray-700">
                  Auto-refresh ({refreshInterval}s)
                </label>
              </div>
              <button
                onClick={() => {
                  refetchHealth();
                  refetchTasks();
                  queryClient.invalidateQueries({ queryKey: ['system-metrics'] });
                }}
                className="flex items-center gap-1 px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
            </div>
          </div>
        </div>

        {activeSection === 'dashboard' && (
          <>
            {/* System Health Overview */}
            {systemHealth && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-600">Elasticsearch</p>
                      <p className="text-2xl font-bold text-gray-900 capitalize">
                        {systemHealth.elasticsearch.status}
                      </p>
                    </div>
                    <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                      {systemHealth.elasticsearch.status === 'healthy' ? (
                        <CheckCircle className="w-4 h-4 text-green-600" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-600" />
                      )}
                    </div>
                  </div>
                  <p className="text-sm text-gray-500 mt-1">
                    {systemHealth.elasticsearch.docs_count.toLocaleString()} docs, {systemHealth.elasticsearch.indices_count} indices
                  </p>
                </div>

                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-600">Ollama</p>
                      <p className="text-2xl font-bold text-gray-900 capitalize">
                        {systemHealth.ollama.status}
                      </p>
                    </div>
                    <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
                      {systemHealth.ollama.status === 'healthy' ? (
                        <CheckCircle className="w-4 h-4 text-purple-600" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-600" />
                      )}
                    </div>
                  </div>
                  <p className="text-sm text-gray-500 mt-1">
                    {systemHealth.ollama.running_models.length} running, {systemHealth.ollama.models.length} total models
                  </p>
                </div>

                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-600">System Load</p>
                      <p className="text-2xl font-bold text-gray-900">
                        {systemHealth.system.load_average[0]?.toFixed(2)}
                      </p>
                    </div>
                    <div className="w-8 h-8 bg-orange-100 rounded-full flex items-center justify-center">
                      <Activity className="w-4 h-4 text-orange-600" />
                    </div>
                  </div>
                  <p className="text-sm text-gray-500 mt-1">
                    Uptime: {formatUptime(systemHealth.system.uptime)}
                  </p>
                </div>

                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-600">Storage</p>
                      <p className="text-2xl font-bold text-gray-900">
                        {systemHealth.elasticsearch.store_size}
                      </p>
                    </div>
                    <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                      <HardDrive className="w-4 h-4 text-blue-600" />
                    </div>
                  </div>
                  <p className="text-sm text-gray-500 mt-1">
                    {systemHealth.system.disk_usage.toFixed(1)}% disk usage
                  </p>
                </div>
              </div>
            )}

            {/* System Metrics */}
            {metrics && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-600">Queries Generated</p>
                      <p className="text-2xl font-bold text-blue-600">
                        {metrics.total_queries_generated.toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-600">Evaluations Run</p>
                      <p className="text-2xl font-bold text-green-600">
                        {metrics.total_evaluations_run.toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-600">Security Tests</p>
                      <p className="text-2xl font-bold text-red-600">
                        {metrics.total_security_tests.toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-600">Data Ingested</p>
                      <p className="text-2xl font-bold text-purple-600">
                        {metrics.total_data_ingested_gb.toFixed(2)} GB
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              {/* System Resource Usage */}
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">System Resource Usage</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={systemUsageData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Bar dataKey="usage" fill="#8884d8" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Index Health Overview */}
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Index Document Counts</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={indexHealthData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="docs" fill="#82ca9d" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </>
        )}

        {activeSection === 'indices' && systemHealth && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Elasticsearch Indices</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Index Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Health
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Documents
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Size
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {systemHealth.indices.map((index, i) => (
                    <tr key={index.name} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <code className="text-sm font-medium text-blue-600">
                          {index.name}
                        </code>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          index.health === 'green' ? 'bg-green-100 text-green-800' :
                          index.health === 'yellow' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {index.health}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {index.docs_count.toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {index.store_size}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(index.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <button
                          onClick={() => {
                            if (confirm(`Are you sure you want to delete index "${index.name}"?`)) {
                              deleteIndexMutation.mutate(index.name);
                            }
                          }}
                          className="text-red-600 hover:text-red-900 flex items-center gap-1"
                        >
                          <Trash2 className="w-4 h-4" />
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeSection === 'ingestion' && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold text-gray-900">Data Ingestion Tasks</h3>
                <button
                  onClick={() => setShowUploadModal(true)}
                  className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center gap-2"
                >
                  <Upload className="w-4 h-4" />
                  Upload Data
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  {taskTable.getHeaderGroups().map(headerGroup => (
                    <tr key={headerGroup.id}>
                      {headerGroup.headers.map(header => (
                        <th
                          key={header.id}
                          className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                        >
                          {header.isPlaceholder
                            ? null
                            : flexRender(
                                header.column.columnDef.header,
                                header.getContext()
                              )}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {taskTable.getRowModel().rows.map(row => (
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
          </div>
        )}

        {activeSection === 'logs' && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">System Logs</h3>
            <div className="bg-gray-900 text-green-400 p-4 rounded font-mono text-sm h-96 overflow-y-auto">
              <div className="space-y-1">
                <div>[2024-08-22 17:15:23] INFO: Elasticsearch cluster healthy</div>
                <div>[2024-08-22 17:15:23] INFO: Ollama service running</div>
                <div>[2024-08-22 17:15:24] INFO: Query generation completed successfully</div>
                <div>[2024-08-22 17:15:25] INFO: Evaluation run started for scenario scan-001</div>
                <div>[2024-08-22 17:15:26] INFO: Security test completed with 95% abstain rate</div>
                <div>[2024-08-22 17:15:27] INFO: Data ingestion task completed: 10,000 records</div>
                <div>[2024-08-22 17:15:28] INFO: System health check passed</div>
              </div>
            </div>
          </div>
        )}

        {/* Upload Modal */}
        {showUploadModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg max-w-md w-full p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload Data File</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Select File
                  </label>
                  <input
                    type="file"
                    accept=".csv,.json,.jsonl"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Dataset Type
                  </label>
                  <select className="w-full px-3 py-2 border border-gray-300 rounded-md">
                    <option value="general_csv">General CSV</option>
                    <option value="cic_ids2017">CIC-IDS2017 Dataset</option>
                    <option value="network_logs">Network Logs</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-4 mt-6">
                <button
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
                  Upload
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SystemAdmin;