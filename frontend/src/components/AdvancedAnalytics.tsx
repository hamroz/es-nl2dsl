import React, { useState, useEffect } from 'react';
import { 
  BarChart3, TrendingUp, Users, Database, Shield, Activity,
  Clock, Zap, AlertCircle, CheckCircle, Eye, Filter,
  Calendar, Download, RefreshCw, Settings, Target,
  PieChart, LineChart, ArrowUp, ArrowDown, Minus
} from 'lucide-react';
import { 
  LineChart as RechartsLineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  BarChart as RechartsBarChart, Bar, PieChart as RechartsPieChart, Cell, Pie,
  AreaChart, Area, ComposedChart
} from 'recharts';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

interface AnalyticsMetrics {
  user_metrics: {
    total_users: number;
    active_users_24h: number;
    new_users_7d: number;
    user_growth_rate: number;
    users_by_role: { role: string; count: number; percentage: number }[];
    user_activity_trend: { date: string; active_users: number }[];
  };
  query_metrics: {
    total_queries: number;
    queries_24h: number;
    avg_response_time: number;
    success_rate: number;
    queries_by_method: { method: string; count: number; avg_time: number }[];
    query_volume_trend: { date: string; count: number; avg_time: number }[];
  };
  security_metrics: {
    failed_logins_24h: number;
    locked_accounts: number;
    security_events: number;
    threat_level: 'low' | 'medium' | 'high';
    security_events_trend: { date: string; events: number; severity: string }[];
  };
  system_metrics: {
    uptime_percentage: number;
    avg_cpu_usage: number;
    memory_usage_gb: number;
    disk_usage_percentage: number;
    active_sessions: number;
    error_rate: number;
    performance_trend: { date: string; response_time: number; error_rate: number }[];
  };
  business_metrics: {
    tenant_count: number;
    workspace_count: number;
    data_processed_gb: number;
    export_count_24h: number;
    top_indices: { index: string; query_count: number; data_size_gb: number }[];
  };
}

interface CustomMetric {
  id: string;
  name: string;
  description: string;
  query: string;
  visualization_type: 'line' | 'bar' | 'pie' | 'number';
  refresh_interval: number;
  is_active: boolean;
  data?: any[];
  current_value?: number;
}

const AdvancedAnalytics: React.FC = () => {
  const { permissions } = useAuth();
  const [metrics, setMetrics] = useState<AnalyticsMetrics | null>(null);
  const [customMetrics, setCustomMetrics] = useState<CustomMetric[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTimeRange, setSelectedTimeRange] = useState('7d');
  const [selectedCategory, setSelectedCategory] = useState('overview');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const timeRanges = [
    { value: '1h', label: 'Last Hour' },
    { value: '24h', label: 'Last 24 Hours' },
    { value: '7d', label: 'Last 7 Days' },
    { value: '30d', label: 'Last 30 Days' },
    { value: '90d', label: 'Last 90 Days' }
  ];

  const categories = [
    { value: 'overview', label: 'Overview', icon: BarChart3 },
    { value: 'users', label: 'Users', icon: Users },
    { value: 'queries', label: 'Queries', icon: Database },
    { value: 'security', label: 'Security', icon: Shield },
    { value: 'system', label: 'System', icon: Activity },
    { value: 'business', label: 'Business', icon: Target }
  ];

  const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4'];

  useEffect(() => {
    if (permissions?.can_view_audit_logs) {
      fetchAnalytics();
      fetchCustomMetrics();
    }
  }, [selectedTimeRange, permissions]);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchAnalytics, 30000); // Refresh every 30 seconds
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

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/system/analytics/?range=${selectedTimeRange}`);
      setMetrics(response.data);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchCustomMetrics = async () => {
    try {
      const response = await api.get('/system/custom-metrics/');
      setCustomMetrics(response.data);
    } catch (error) {
      console.error('Failed to fetch custom metrics:', error);
    }
  };

  const exportAnalytics = async (format: 'csv' | 'pdf') => {
    try {
      const response = await api.get(`/system/analytics/export?format=${format}&range=${selectedTimeRange}`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `analytics-${selectedTimeRange}.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Export failed:', error);
    }
  };

  const MetricCard: React.FC<{
    title: string;
    value: string | number;
    change?: number;
    icon: React.ComponentType<any>;
    color: string;
    suffix?: string;
  }> = ({ title, value, change, icon: Icon, color, suffix = '' }) => (
    <div className="bg-white rounded-lg p-6 border border-gray-200">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900">
            {typeof value === 'number' ? value.toLocaleString() : value}{suffix}
          </p>
          {change !== undefined && (
            <div className={`flex items-center mt-1 text-sm ${
              change > 0 ? 'text-green-600' : change < 0 ? 'text-red-600' : 'text-gray-600'
            }`}>
              {change > 0 ? <ArrowUp className="w-4 h-4 mr-1" /> : 
               change < 0 ? <ArrowDown className="w-4 h-4 mr-1" /> : 
               <Minus className="w-4 h-4 mr-1" />}
              {Math.abs(change).toFixed(1)}%
            </div>
          )}
        </div>
        <div className={`p-3 rounded-full ${color}`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  );

  const renderOverviewDashboard = () => {
    if (!metrics) return null;

    return (
      <div className="space-y-6">
        {/* Key Metrics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricCard
            title="Active Users"
            value={metrics.user_metrics.active_users_24h}
            change={metrics.user_metrics.user_growth_rate}
            icon={Users}
            color="bg-blue-500"
          />
          <MetricCard
            title="Queries Today"
            value={metrics.query_metrics.queries_24h}
            icon={Database}
            color="bg-green-500"
          />
          <MetricCard
            title="Success Rate"
            value={metrics.query_metrics.success_rate}
            icon={CheckCircle}
            color="bg-emerald-500"
            suffix="%"
          />
          <MetricCard
            title="Avg Response Time"
            value={metrics.query_metrics.avg_response_time}
            icon={Zap}
            color="bg-yellow-500"
            suffix="ms"
          />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* User Activity Trend */}
          <div className="bg-white p-6 rounded-lg border border-gray-200">
            <h3 className="text-lg font-semibold mb-4">User Activity Trend</h3>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={metrics.user_metrics.user_activity_trend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Area type="monotone" dataKey="active_users" stroke="#3B82F6" fill="#93C5FD" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Query Volume Trend */}
          <div className="bg-white p-6 rounded-lg border border-gray-200">
            <h3 className="text-lg font-semibold mb-4">Query Performance</h3>
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={metrics.query_metrics.query_volume_trend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis yAxisId="left" />
                <YAxis yAxisId="right" orientation="right" />
                <Tooltip />
                <Bar yAxisId="left" dataKey="count" fill="#10B981" name="Query Count" />
                <Line yAxisId="right" type="monotone" dataKey="avg_time" stroke="#F59E0B" name="Avg Time (ms)" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Users by Role & Query Methods */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white p-6 rounded-lg border border-gray-200">
            <h3 className="text-lg font-semibold mb-4">Users by Role</h3>
            <ResponsiveContainer width="100%" height={250}>
              <RechartsPieChart>
                <Pie
                  data={metrics.user_metrics.users_by_role}
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="count"
                  label={({ role, percentage }) => `${role} (${percentage}%)`}
                >
                  {metrics.user_metrics.users_by_role.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </RechartsPieChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white p-6 rounded-lg border border-gray-200">
            <h3 className="text-lg font-semibold mb-4">Query Methods Performance</h3>
            <ResponsiveContainer width="100%" height={250}>
              <RechartsBarChart data={metrics.query_metrics.queries_by_method}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="method" />
                <YAxis yAxisId="left" />
                <YAxis yAxisId="right" orientation="right" />
                <Tooltip />
                <Bar yAxisId="left" dataKey="count" fill="#3B82F6" name="Count" />
                <Line yAxisId="right" dataKey="avg_time" stroke="#EF4444" name="Avg Time (ms)" />
              </RechartsBarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    );
  };

  const renderSecurityDashboard = () => {
    if (!metrics) return null;

    const getThreatLevelColor = (level: string) => {
      switch (level) {
        case 'high': return 'bg-red-500';
        case 'medium': return 'bg-yellow-500';
        case 'low': return 'bg-green-500';
        default: return 'bg-gray-500';
      }
    };

    return (
      <div className="space-y-6">
        {/* Security Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricCard
            title="Failed Logins (24h)"
            value={metrics.security_metrics.failed_logins_24h}
            icon={Shield}
            color="bg-red-500"
          />
          <MetricCard
            title="Locked Accounts"
            value={metrics.security_metrics.locked_accounts}
            icon={AlertCircle}
            color="bg-orange-500"
          />
          <MetricCard
            title="Security Events"
            value={metrics.security_metrics.security_events}
            icon={Eye}
            color="bg-purple-500"
          />
          <div className="bg-white rounded-lg p-6 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Threat Level</p>
                <p className="text-2xl font-bold text-gray-900 capitalize">
                  {metrics.security_metrics.threat_level}
                </p>
              </div>
              <div className={`p-3 rounded-full ${getThreatLevelColor(metrics.security_metrics.threat_level)}`}>
                <Shield className="w-6 h-6 text-white" />
              </div>
            </div>
          </div>
        </div>

        {/* Security Events Trend */}
        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold mb-4">Security Events Timeline</h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={metrics.security_metrics.security_events_trend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Area type="monotone" dataKey="events" stroke="#EF4444" fill="#FCA5A5" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  };

  const renderSystemDashboard = () => {
    if (!metrics) return null;

    return (
      <div className="space-y-6">
        {/* System Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricCard
            title="Uptime"
            value={metrics.system_metrics.uptime_percentage}
            icon={Activity}
            color="bg-green-500"
            suffix="%"
          />
          <MetricCard
            title="CPU Usage"
            value={metrics.system_metrics.avg_cpu_usage}
            icon={Zap}
            color="bg-blue-500"
            suffix="%"
          />
          <MetricCard
            title="Memory Usage"
            value={metrics.system_metrics.memory_usage_gb}
            icon={Database}
            color="bg-purple-500"
            suffix=" GB"
          />
          <MetricCard
            title="Active Sessions"
            value={metrics.system_metrics.active_sessions}
            icon={Users}
            color="bg-indigo-500"
          />
        </div>

        {/* Performance Trend */}
        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold mb-4">System Performance</h3>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={metrics.system_metrics.performance_trend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis yAxisId="left" />
              <YAxis yAxisId="right" orientation="right" />
              <Tooltip />
              <Area yAxisId="left" type="monotone" dataKey="response_time" stroke="#3B82F6" fill="#93C5FD" name="Response Time (ms)" />
              <Line yAxisId="right" type="monotone" dataKey="error_rate" stroke="#EF4444" name="Error Rate %" />
            </ComposedChart>
          </ResponsiveContainer>
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
          <p className="text-gray-600">You don't have permission to view analytics.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Advanced Analytics</h1>
          <p className="text-gray-600">
            Real-time insights and performance metrics
            {lastUpdated && (
              <span className="ml-2 text-sm text-gray-400">
                • Last updated: {lastUpdated.toLocaleTimeString()}
              </span>
            )}
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
            onClick={fetchAnalytics}
            disabled={loading}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <div className="relative">
            <button className="flex items-center space-x-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">
              <Download className="w-4 h-4" />
              <span>Export</span>
            </button>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white p-4 rounded-lg border border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            {/* Time Range Selector */}
            <div className="flex items-center space-x-2">
              <Calendar className="w-4 h-4 text-gray-400" />
              <select
                value={selectedTimeRange}
                onChange={(e) => setSelectedTimeRange(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-1 text-sm focus:ring-2 focus:ring-blue-500"
              >
                {timeRanges.map(range => (
                  <option key={range.value} value={range.value}>{range.label}</option>
                ))}
              </select>
            </div>

            {/* Category Selector */}
            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-gray-400" />
              <div className="flex space-x-1">
                {categories.map(category => {
                  const Icon = category.icon;
                  return (
                    <button
                      key={category.value}
                      onClick={() => setSelectedCategory(category.value)}
                      className={`flex items-center space-x-1 px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                        selectedCategory === category.value
                          ? 'bg-blue-100 text-blue-700'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span>{category.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Dashboard Content */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-500">Loading analytics...</p>
          </div>
        </div>
      ) : (
        <div>
          {selectedCategory === 'overview' && renderOverviewDashboard()}
          {selectedCategory === 'security' && renderSecurityDashboard()}
          {selectedCategory === 'system' && renderSystemDashboard()}
          {selectedCategory === 'users' && renderOverviewDashboard()} {/* Could be separate */}
          {selectedCategory === 'queries' && renderOverviewDashboard()} {/* Could be separate */}
          {selectedCategory === 'business' && renderOverviewDashboard()} {/* Could be separate */}
        </div>
      )}

      {/* Custom Metrics Section */}
      {customMetrics.length > 0 && (
        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold mb-4">Custom Metrics</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {customMetrics.filter(m => m.is_active).map(metric => (
              <div key={metric.id} className="p-4 border border-gray-200 rounded-lg">
                <h4 className="font-medium text-gray-900">{metric.name}</h4>
                <p className="text-sm text-gray-600 mb-2">{metric.description}</p>
                <div className="text-2xl font-bold text-blue-600">
                  {metric.current_value?.toLocaleString() || 'N/A'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdvancedAnalytics;