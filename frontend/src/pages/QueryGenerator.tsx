import React, { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiService } from '../services/api';
import { PlayIcon, ArrowDownTrayIcon, ClockIcon } from '@heroicons/react/24/outline';

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
      setCurrentTask({ ...data, prompt, method, index: selectedIndex } as QueryTask);
      setQueryResult(null);
    }
  });

  // Poll for task completion
  const { data: taskDetails, refetch: refetchTask } = useQuery({
    queryKey: ['query-task', currentTask?.task_id],
    queryFn: () => apiService.getQueryTask(currentTask!.task_id),
    enabled: !!currentTask?.task_id && currentTask?.status !== 'completed' && currentTask?.status !== 'failed',
    refetchInterval: 2000,
    refetchIntervalInBackground: false
  });

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

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">🤖 Query Generator</h1>
        
        {/* Query Generation Form */}
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
                  href={`http://localhost:8001${queryResult.export_urls.csv}`}
                  className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700 flex items-center gap-1"
                >
                  <ArrowDownTrayIcon className="w-4 h-4" />
                  📊 Export CSV
                </a>
                <a
                  href={`http://localhost:8001${queryResult.export_urls.json}`}
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