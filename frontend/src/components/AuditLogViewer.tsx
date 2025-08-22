import React, { useState, useEffect } from 'react';
import { 
  Search, Filter, Calendar, Download, RefreshCw, Eye, AlertTriangle,
  User, Shield, Database, Activity, Clock, MapPin, Smartphone,
  ChevronDown, ChevronRight, ExternalLink, Info, Warning, 
  AlertCircle, XCircle, CheckCircle, Zap
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

interface AuditLogEntry {
  id: string;
  user_email?: string;
  user_username?: string;
  action: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  description: string;
  ip_address?: string;
  user_agent?: string;
  endpoint?: string;
  resource_type?: string;
  resource_id?: string;
  metadata: Record<string, any>;
  timestamp: string;
}

interface AuditFilters {
  search: string;
  user_id: string;
  action: string;
  severity: string;
  start_date: string;
  end_date: string;
  ip_address: string;
  resource_type: string;
}

const AuditLogViewer: React.FC = () => {
  const { permissions } = useAuth();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [selectedLogs, setSelectedLogs] = useState<Set<string>>(new Set());
  const [showFilters, setShowFilters] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);

  const [filters, setFilters] = useState<AuditFilters>({
    search: '',
    user_id: '',
    action: '',
    severity: '',
    start_date: '',
    end_date: '',
    ip_address: '',
    resource_type: ''
  });

  const severityColors = {
    info: 'bg-blue-100 text-blue-800',
    warning: 'bg-yellow-100 text-yellow-800',
    error: 'bg-red-100 text-red-800',
    critical: 'bg-red-200 text-red-900'
  };

  const severityIcons = {
    info: Info,
    warning: Warning,
    error: AlertCircle,
    critical: XCircle
  };

  const actionIcons = {
    login: User,
    logout: User,
    query_generate: Database,
    query_execute: Database,
    security_event: Shield,
    user_create: User,
    user_modify: User,
    data_export: Download,
    system_config: Activity
  };

  const actionCategories = [
    'login', 'logout', 'query_generate', 'query_execute', 'data_export',
    'user_create', 'user_modify', 'user_delete', 'role_change',
    'security_event', 'system_config', 'api_access'
  ];

  useEffect(() => {
    if (permissions?.can_view_audit_logs) {
      fetchAuditLogs();
    }
  }, [currentPage, pageSize, permissions]);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchAuditLogs, 30000); // Refresh every 30 seconds
      setRefreshInterval(interval);
    } else {
      if (refreshInterval) {
        clearInterval(refreshInterval);
        setRefreshInterval(null);
      }
    }

    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval);
      }
    };
  }, [autoRefresh]);

  const fetchAuditLogs = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      
      // Pagination
      params.append('page', currentPage.toString());
      params.append('page_size', pageSize.toString());
      
      // Filters
      Object.entries(filters).forEach(([key, value]) => {
        if (value) {
          params.append(key, value);
        }
      });

      const response = await api.get(`/auth/audit-logs/?${params}`);
      setLogs(response.data.results);
      setTotalCount(response.data.count);
    } catch (error) {
      console.error('Failed to fetch audit logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key: keyof AuditFilters, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const applyFilters = () => {
    setCurrentPage(1);
    fetchAuditLogs();
  };

  const clearFilters = () => {
    setFilters({
      search: '',
      user_id: '',
      action: '',
      severity: '',
      start_date: '',
      end_date: '',
      ip_address: '',
      resource_type: ''
    });
    setCurrentPage(1);
    fetchAuditLogs();
  };

  const toggleRowExpansion = (logId: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(logId)) {
      newExpanded.delete(logId);
    } else {
      newExpanded.add(logId);
    }
    setExpandedRows(newExpanded);
  };

  const toggleLogSelection = (logId: string) => {
    const newSelected = new Set(selectedLogs);
    if (newSelected.has(logId)) {
      newSelected.delete(logId);
    } else {
      newSelected.add(logId);
    }
    setSelectedLogs(newSelected);
  };

  const selectAllLogs = () => {
    if (selectedLogs.size === logs.length) {
      setSelectedLogs(new Set());
    } else {
      setSelectedLogs(new Set(logs.map(log => log.id)));
    }
  };

  const exportLogs = async (format: 'csv' | 'json') => {
    try {
      const params = new URLSearchParams();
      params.append('format', format);
      
      // Apply current filters to export
      Object.entries(filters).forEach(([key, value]) => {
        if (value) {
          params.append(key, value);
        }
      });

      const response = await api.get(`/auth/audit-logs/export/?${params}`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `audit-logs.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Export failed:', error);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const formatUserAgent = (userAgent: string) => {
    if (!userAgent) return 'Unknown';
    
    // Extract browser and OS info
    const browserMatch = userAgent.match(/(Chrome|Firefox|Safari|Edge)\/[\d\.]+/);
    const osMatch = userAgent.match(/(Windows|Mac|Linux|Android|iOS)/);
    
    const browser = browserMatch ? browserMatch[1] : 'Unknown Browser';
    const os = osMatch ? osMatch[1] : 'Unknown OS';
    
    return `${browser} on ${os}`;
  };

  const getActionIcon = (action: string) => {
    const Icon = actionIcons[action as keyof typeof actionIcons] || Activity;
    return <Icon className="w-4 h-4" />;
  };

  const getSeverityIcon = (severity: string) => {
    const Icon = severityIcons[severity as keyof typeof severityIcons] || Info;
    return <Icon className="w-4 h-4" />;
  };

  const renderMetadata = (metadata: Record<string, any>) => {
    return (
      <div className="bg-gray-50 p-3 rounded-lg mt-2">
        <h4 className="text-sm font-medium text-gray-700 mb-2">Additional Details</h4>
        <div className="space-y-1 text-sm">
          {Object.entries(metadata).map(([key, value]) => (
            <div key={key} className="flex">
              <span className="font-medium text-gray-600 w-32 flex-shrink-0">
                {key.replace('_', ' ')}:
              </span>
              <span className="text-gray-800">
                {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  if (!permissions?.can_view_audit_logs) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Shield className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600">You don't have permission to view audit logs.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Log Viewer</h1>
          <p className="text-gray-600">
            View and analyze system audit logs • {totalCount.toLocaleString()} total entries
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <label className="text-sm text-gray-600">Auto Refresh:</label>
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                autoRefresh ? 'bg-blue-600' : 'bg-gray-200'
              }`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                autoRefresh ? 'translate-x-6' : 'translate-x-1'
              }`} />
            </button>
          </div>
          <button
            onClick={fetchAuditLogs}
            disabled={loading}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white p-4 rounded-lg border border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-4">
            {/* Search */}
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search logs..."
                value={filters.search}
                onChange={(e) => handleFilterChange('search', e.target.value)}
                className="pl-10 pr-4 py-2 w-80 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Quick Filters */}
            <select
              value={filters.severity}
              onChange={(e) => handleFilterChange('severity', e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Severities</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
              <option value="critical">Critical</option>
            </select>

            <select
              value={filters.action}
              onChange={(e) => handleFilterChange('action', e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Actions</option>
              {actionCategories.map(action => (
                <option key={action} value={action}>{action.replace('_', ' ')}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center space-x-2 px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
            >
              <Filter className="w-4 h-4" />
              <span>Advanced Filters</span>
              {showFilters ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>

            <button
              onClick={applyFilters}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Apply
            </button>

            <button
              onClick={clearFilters}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
            >
              Clear
            </button>

            <div className="relative">
              <button className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                <Download className="w-4 h-4" />
                <span>Export</span>
              </button>
              {/* Export dropdown would go here */}
            </div>
          </div>
        </div>

        {/* Advanced Filters */}
        {showFilters && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-gray-200">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
              <input
                type="datetime-local"
                value={filters.start_date}
                onChange={(e) => handleFilterChange('start_date', e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
              <input
                type="datetime-local"
                value={filters.end_date}
                onChange={(e) => handleFilterChange('end_date', e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">IP Address</label>
              <input
                type="text"
                placeholder="192.168.1.1"
                value={filters.ip_address}
                onChange={(e) => handleFilterChange('ip_address', e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Resource Type</label>
              <input
                type="text"
                placeholder="user, query, etc."
                value={filters.resource_type}
                onChange={(e) => handleFilterChange('resource_type', e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        )}
      </div>

      {/* Bulk Actions */}
      {selectedLogs.size > 0 && (
        <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-blue-800">
              {selectedLogs.size} log{selectedLogs.size !== 1 ? 's' : ''} selected
            </span>
            <div className="flex space-x-2">
              <button
                onClick={() => exportLogs('csv')}
                className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
              >
                Export Selected as CSV
              </button>
              <button
                onClick={() => exportLogs('json')}
                className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
              >
                Export Selected as JSON
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Logs Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={selectedLogs.size === logs.length && logs.length > 0}
                    onChange={selectAllLogs}
                    className="rounded"
                  />
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  User
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Action
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Severity
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Description
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Location
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-6 py-8 text-center text-gray-500">
                    <div className="flex items-center justify-center">
                      <RefreshCw className="w-6 h-6 animate-spin mr-2" />
                      Loading audit logs...
                    </div>
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-8 text-center text-gray-500">
                    No audit logs found matching your criteria
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <React.Fragment key={log.id}>
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-4">
                        <input
                          type="checkbox"
                          checked={selectedLogs.has(log.id)}
                          onChange={() => toggleLogSelection(log.id)}
                          className="rounded"
                        />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        <div className="flex items-center space-x-1">
                          <Clock className="w-4 h-4 text-gray-400" />
                          <span>{formatDate(log.timestamp)}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm">
                          <div className="font-medium text-gray-900">
                            {log.user_username || 'System'}
                          </div>
                          {log.user_email && (
                            <div className="text-gray-500">{log.user_email}</div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center space-x-2">
                          {getActionIcon(log.action)}
                          <span className="text-sm font-medium text-gray-900">
                            {log.action.replace('_', ' ')}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          severityColors[log.severity]
                        }`}>
                          {getSeverityIcon(log.severity)}
                          <span className="ml-1 capitalize">{log.severity}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-900 max-w-md truncate">
                          {log.description}
                        </div>
                        {log.resource_type && (
                          <div className="text-xs text-gray-500">
                            {log.resource_type}: {log.resource_id}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {log.ip_address && (
                          <div className="flex items-center space-x-1">
                            <MapPin className="w-3 h-3" />
                            <span>{log.ip_address}</span>
                          </div>
                        )}
                        {log.user_agent && (
                          <div className="flex items-center space-x-1 mt-1">
                            <Smartphone className="w-3 h-3" />
                            <span className="truncate max-w-32">
                              {formatUserAgent(log.user_agent)}
                            </span>
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => toggleRowExpansion(log.id)}
                          className="text-blue-600 hover:text-blue-900"
                        >
                          {expandedRows.has(log.id) ? (
                            <ChevronDown className="w-4 h-4" />
                          ) : (
                            <ChevronRight className="w-4 h-4" />
                          )}
                        </button>
                      </td>
                    </tr>
                    {expandedRows.has(log.id) && (
                      <tr>
                        <td colSpan={8} className="px-6 py-4 bg-gray-50">
                          <div className="space-y-3">
                            {/* Full description */}
                            <div>
                              <h4 className="text-sm font-medium text-gray-700">Full Description</h4>
                              <p className="text-sm text-gray-900 mt-1">{log.description}</p>
                            </div>

                            {/* Endpoint */}
                            {log.endpoint && (
                              <div>
                                <h4 className="text-sm font-medium text-gray-700">Endpoint</h4>
                                <p className="text-sm text-gray-900 mt-1 font-mono">{log.endpoint}</p>
                              </div>
                            )}

                            {/* User Agent */}
                            {log.user_agent && (
                              <div>
                                <h4 className="text-sm font-medium text-gray-700">User Agent</h4>
                                <p className="text-sm text-gray-900 mt-1 break-all">{log.user_agent}</p>
                              </div>
                            )}

                            {/* Metadata */}
                            {log.metadata && Object.keys(log.metadata).length > 0 && (
                              renderMetadata(log.metadata)
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
          <div className="flex-1 flex justify-between sm:hidden">
            <button
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
            >
              Previous
            </button>
            <button
              onClick={() => setCurrentPage(currentPage + 1)}
              disabled={currentPage * pageSize >= totalCount}
              className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
            >
              Next
            </button>
          </div>
          <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-gray-700">
                Showing{' '}
                <span className="font-medium">{(currentPage - 1) * pageSize + 1}</span>
                {' '}to{' '}
                <span className="font-medium">
                  {Math.min(currentPage * pageSize, totalCount)}
                </span>
                {' '}of{' '}
                <span className="font-medium">{totalCount}</span>
                {' '}results
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <select
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
                className="border border-gray-300 rounded px-3 py-1 text-sm"
              >
                <option value={25}>25 per page</option>
                <option value={50}>50 per page</option>
                <option value={100}>100 per page</option>
              </select>

              <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                <button
                  onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                  disabled={currentPage === 1}
                  className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setCurrentPage(currentPage + 1)}
                  disabled={currentPage * pageSize >= totalCount}
                  className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                >
                  Next
                </button>
              </nav>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuditLogViewer;