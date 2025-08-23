import React, { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiService } from '../services/api';
import { PlayIcon, ArrowDownTrayIcon, ClockIcon } from '@heroicons/react/24/outline';
import QueryBuilder from '../components/QueryBuilder';

interface QueryTask {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  prompt: string;
  method: string;
  index: string;
  created_at: string;
  completed_at?: string;
  error_message?: string;
  query?: any;
  validation?: {
    status: 'PASS' | 'FAIL';
    errors: string[];
  };
  metrics?: {
    generation_time: number;
    retry_count: number;
  };
}

interface QueryResult {
  total_hits: number;
  returned_hits: number;
  took: number;
  results: any[];
  aggregations: any;
  export_urls?: {
    csv: string;
    json: string;
  };
}

const QueryGenerator: React.FC = () => {
  const [prompt, setPrompt] = useState('');
  const [method, setMethod] = useState<'constrained' | 'rules' | 'zeroshot'>('constrained');
  const [selectedIndex, setSelectedIndex] = useState('logs_net');
  const [model, setModel] = useState('');
  const [currentTask, setCurrentTask] = useState<QueryTask | null>(null);
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [maxSize, setMaxSize] = useState(1000);
  const [activeTab, setActiveTab] = useState<'natural' | 'visual'>('natural');
  const [visualQuery, setVisualQuery] = useState<any>(null);
  const [wsConnection, setWsConnection] = useState<WebSocket | null>(null);
  const [taskProgress, setTaskProgress] = useState<number>(0);

  // Get available indices
  const { data: availableIndices } = useQuery({
    queryKey: ['indices'],
    queryFn: () => apiService.getAvailableIndices(),
    initialData: ['logs_net']
  });

  // Generate query mutation
  const generateMutation = useMutation({
    mutationFn: (params: { prompt: string; method: string; index?: string; model?: string }) =>
      apiService.generateQuery(params),
    onSuccess: (data) => {
      const newTask = { ...data, prompt, method, index: selectedIndex } as QueryTask;
      setCurrentTask(newTask);
      setQueryResult(null);
      setTaskProgress(0);
      // Set up WebSocket connection for real-time updates
      setupWebSocket(newTask.task_id);
    }
  });

  // Poll for task completion (fallback if WebSocket fails)
  const { data: taskDetails, refetch: refetchTask } = useQuery({
    queryKey: ['query-task', currentTask?.task_id],
    queryFn: () => apiService.getQueryTask(currentTask!.task_id),
    enabled: !!currentTask?.task_id && currentTask?.status !== 'completed' && currentTask?.status !== 'failed' && !wsConnection,
    refetchInterval: 3000, // Slower polling as fallback
    refetchIntervalInBackground: false
  });

  // WebSocket setup for real-time progress updates
  const setupWebSocket = (taskId: string) => {
    // Close existing connection
    if (wsConnection) {
      wsConnection.close();
    }

    const ws = new WebSocket(`ws://localhost:8000/ws/queries/${taskId}/`);
    
    ws.onopen = () => {
      console.log('WebSocket connected for query generation:', taskId);
      setWsConnection(ws);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'progress_update') {
        setTaskProgress(data.progress || 0);
      } else if (data.type === 'status_update') {
        // Update task status in real-time
        setCurrentTask(prev => prev ? { ...prev, status: data.status } : null);
        
        if (data.status === 'completed' || data.status === 'failed') {
          setTaskProgress(100);
          // Fetch final task details
          refetchTask();
          // Close WebSocket connection
          ws.close();
        }
      } else if (data.type === 'task_update') {
        // Full task data update
        setCurrentTask(prev => prev ? { ...prev, ...data.task } : data.task);
      }
    };

    ws.onerror = (error) => {
      console.warn('WebSocket error, falling back to polling:', error);
      setWsConnection(null);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected for query generation');
      setWsConnection(null);
    };
  };

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsConnection) {
        wsConnection.close();
      }
    };
  }, [wsConnection]);

  // Execute query mutation
  const executeMutation = useMutation({
    mutationFn: (params: { taskId: string; maxSize: number }) =>
      apiService.executeQuery(params.taskId, params.maxSize),
    onSuccess: (data) => {
      setQueryResult(data);
    }
  });

  // Update current task when poll data changes
  useEffect(() => {
    if (taskDetails && currentTask) {
      setCurrentTask(taskDetails);
    }
  }, [taskDetails, currentTask?.task_id]);

  const handleGenerate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    generateMutation.mutate({
      prompt: prompt.trim(),
      method,
      index: selectedIndex,
      model: model || undefined
    });
  };

  const handleExecute = () => {
    if (!currentTask?.task_id) return;
    executeMutation.mutate({
      taskId: currentTask.task_id,
      maxSize
    });
  };

  const canExecute = currentTask?.status === 'completed' && 
                    currentTask?.validation?.status === 'PASS';

  const handleVisualQueryExecute = (query: any) => {
    setVisualQuery(query);
    // For visual queries, we can execute them directly
    executeMutation.mutate({
      taskId: 'visual-query', // Special handling for visual queries
      maxSize
    });
  };

  const handleVisualQuerySave = (query: any, name: string) => {
    console.log('Saving query:', name, query);
    // TODO: Implement query saving functionality
  };

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">🤖 Query Generator</h1>
        
        {/* Tab Navigation */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('natural')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'natural'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Natural Language
            </button>
            <button
              onClick={() => setActiveTab('visual')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'visual'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Visual Query Builder
            </button>
          </nav>
        </div>

        {activeTab === 'natural' ? (
          /* Natural Language Query Generation Form */
          <form onSubmit={handleGenerate} className="space-y-4">
          <div>
            <label htmlFor="prompt" className="block text-sm font-medium text-gray-700 mb-1">
              Natural Language Query
            </label>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g., Find malicious events from IP 192.168.1.1 in the last 24 hours"
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              rows={3}
              required
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label htmlFor="method" className="block text-sm font-medium text-gray-700 mb-1">
                Generation Method
              </label>
              <select
                id="method"
                value={method}
                onChange={(e) => setMethod(e.target.value as any)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="constrained">Constrained Generation</option>
                <option value="rules">Rule-based</option>
                <option value="zeroshot">Zero-shot</option>
              </select>
            </div>

            <div>
              <label htmlFor="index" className="block text-sm font-medium text-gray-700 mb-1">
                Target Index
              </label>
              <select
                id="index"
                value={selectedIndex}
                onChange={(e) => setSelectedIndex(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {availableIndices?.map(index => (
                  <option key={index} value={index}>{index}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="model" className="block text-sm font-medium text-gray-700 mb-1">
                Model (Optional)
              </label>
              <input
                id="model"
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="llama3.1:latest"
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={generateMutation.isPending || !prompt.trim()}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {generateMutation.isPending ? (
              <>
                <ClockIcon className="w-4 h-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                🚀 Generate Query
              </>
            )}
          </button>
        </form>
        ) : (
          /* Visual Query Builder */
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label htmlFor="visual-index" className="block text-sm font-medium text-gray-700 mb-1">
                  Target Index
                </label>
                <select
                  id="visual-index"
                  value={selectedIndex}
                  onChange={(e) => setSelectedIndex(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  {availableIndices?.map(index => (
                    <option key={index} value={index}>{index}</option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="visual-max-size" className="block text-sm font-medium text-gray-700 mb-1">
                  Max Results
                </label>
                <input
                  id="visual-max-size"
                  type="number"
                  value={maxSize}
                  onChange={(e) => setMaxSize(parseInt(e.target.value))}
                  min="10"
                  max="10000"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div className="flex items-end">
                <div className="text-sm text-gray-600">
                  Build your query visually using the interface below, then execute it directly.
                </div>
              </div>
            </div>

            <QueryBuilder
              onQueryChange={setVisualQuery}
              onExecute={handleVisualQueryExecute}
              onSave={handleVisualQuerySave}
              availableFields={availableIndices?.includes(selectedIndex) ? 
                (selectedIndex.includes('cic') ? 
                  ['@timestamp', 'src_ip', 'dst_ip', 'src_port', 'dst_port', 'protocol', 'bytes_in', 'bytes_out', 'label', 'attack_type', 'flow_duration', 'total_packets'] :
                  ['@timestamp', 'src_ip', 'dst_ip', 'src_port', 'dst_port', 'protocol', 'bytes_in', 'bytes_out', 'label', 'message']
                ) : undefined
              }
            />
          </div>
        )}
      </div>

      {/* Query Status and Results */}
      {currentTask && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Query Status</h2>
          
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-medium text-gray-600">Task ID:</span>
              <code className="text-sm bg-gray-100 px-2 py-1 rounded">{currentTask.task_id}</code>
              <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                currentTask.status === 'completed' ? 'bg-green-100 text-green-800' :
                currentTask.status === 'running' ? 'bg-yellow-100 text-yellow-800' :
                currentTask.status === 'failed' ? 'bg-red-100 text-red-800' :
                'bg-gray-100 text-gray-800'
              }`}>
                {currentTask.status}
              </span>
            </div>
            <p className="text-sm text-gray-600">{currentTask.prompt}</p>
          </div>

          {/* WebSocket Progress Bar */}
          {currentTask.status === 'running' && wsConnection && (
            <div className="mb-4">
              <div className="flex justify-between text-sm text-gray-600 mb-1">
                <span>Generation Progress</span>
                <span>{taskProgress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                  style={{ width: `${taskProgress}%` }}
                ></div>
              </div>
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>{wsConnection ? '🔗 Real-time updates' : '🔄 Polling for updates'}</span>
                <span>Task: {currentTask.task_id.slice(-8)}</span>
              </div>
            </div>
          )}

          {currentTask.status === 'completed' && currentTask.query && (
            <div className="space-y-4">
              <div>
                <h3 className="font-medium text-gray-900 mb-2">Generated Query</h3>
                <pre className="bg-gray-50 p-3 rounded text-sm overflow-x-auto">
                  {JSON.stringify(currentTask.query, null, 2)}
                </pre>
              </div>

              {currentTask.validation && (
                <div>
                  <h3 className="font-medium text-gray-900 mb-2">Validation</h3>
                  <div className={`p-3 rounded ${
                    currentTask.validation.status === 'PASS' 
                      ? 'bg-green-50 text-green-800' 
                      : 'bg-red-50 text-red-800'
                  }`}>
                    <p className="font-medium">{currentTask.validation.status}</p>
                    {currentTask.validation.errors.length > 0 && (
                      <ul className="mt-1 list-disc list-inside text-sm">
                        {currentTask.validation.errors.map((error, i) => (
                          <li key={i}>{error}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              )}

              {canExecute && (
                <div className="border-t pt-4">
                  <div className="flex items-center gap-4 mb-4">
                    <label htmlFor="maxSize" className="text-sm font-medium text-gray-700">
                      Max Results:
                    </label>
                    <input
                      id="maxSize"
                      type="number"
                      value={maxSize}
                      onChange={(e) => setMaxSize(parseInt(e.target.value))}
                      min="10"
                      max="10000"
                      className="w-20 px-2 py-1 border border-gray-300 rounded"
                    />
                    <button
                      onClick={handleExecute}
                      disabled={executeMutation.isPending}
                      className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:opacity-50 flex items-center gap-2"
                    >
                      <PlayIcon className="w-4 h-4" />
                      {executeMutation.isPending ? 'Executing...' : '🚀 Execute Query'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {currentTask.error_message && (
            <div className="bg-red-50 text-red-800 p-3 rounded">
              <p className="font-medium">Error:</p>
              <p className="text-sm">{currentTask.error_message}</p>
            </div>
          )}
        </div>
      )}

      {/* Query Results */}
      {queryResult && (
        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Query Results</h2>
            {queryResult.export_urls && (
              <div className="flex gap-2">
                <a
                  href={`http://localhost:8000${queryResult.export_urls.csv}`}
                  className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700 flex items-center gap-1"
                >
                  <ArrowDownTrayIcon className="w-4 h-4" />
                  📊 Export CSV
                </a>
                <a
                  href={`http://localhost:8000${queryResult.export_urls.json}`}
                  className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700 flex items-center gap-1"
                >
                  <ArrowDownTrayIcon className="w-4 h-4" />
                  📋 Export JSON
                </a>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div className="bg-blue-50 p-3 rounded">
              <p className="text-sm text-blue-600 font-medium">Total Hits</p>
              <p className="text-2xl font-bold text-blue-900">{queryResult.total_hits}</p>
            </div>
            <div className="bg-green-50 p-3 rounded">
              <p className="text-sm text-green-600 font-medium">Returned</p>
              <p className="text-2xl font-bold text-green-900">{queryResult.returned_hits}</p>
            </div>
            <div className="bg-purple-50 p-3 rounded">
              <p className="text-sm text-purple-600 font-medium">Execution Time</p>
              <p className="text-2xl font-bold text-purple-900">{queryResult.took}ms</p>
            </div>
          </div>

          {queryResult.results.length > 0 && (
            <div>
              <h3 className="font-medium text-gray-900 mb-2">Sample Results</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full border border-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      {Object.keys(queryResult.results[0]).slice(0, 6).map(key => (
                        <th key={key} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b">
                          {key}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {queryResult.results.slice(0, 5).map((result, i) => (
                      <tr key={i}>
                        {Object.keys(result).slice(0, 6).map(key => (
                          <td key={key} className="px-4 py-2 text-sm text-gray-900 border-b">
                            <div className="max-w-xs truncate">
                              {typeof result[key] === 'object' ? JSON.stringify(result[key]) : String(result[key])}
                            </div>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {queryResult.results.length > 5 && (
                <p className="text-sm text-gray-600 mt-2">
                  Showing first 5 of {queryResult.results.length} results. Use export for full data.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default QueryGenerator;