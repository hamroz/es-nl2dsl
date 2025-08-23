import React, { useState, useEffect } from 'react';
import {
    Box,
    Grid,
    Card,
    CardContent,
    Typography,
    LinearProgress,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Chip,
    Alert,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    IconButton,
    Tooltip,
} from '@mui/material';
import {
    Computer,
    Storage,
    Memory,
    Speed,
    NetworkCheck,
    Database,
    Timeline,
    Warning,
    CheckCircle,
    Error,
    Refresh,
    TrendingUp,
    TrendingDown,
    Remove,
} from '@mui/icons-material';
import {
    LineChart,
    Line,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip as RechartsTooltip,
    ResponsiveContainer,
    BarChart,
    Bar,
    PieChart,
    Pie,
    Cell,
} from 'recharts';

interface SystemMetricsProps {
    systemHealth: any;
    systemStats: any;
    onRefresh: () => void;
}

interface MetricHistory {
    timestamp: string;
    cpu_usage: number;
    memory_usage: number;
    disk_usage: number;
    elasticsearch_response_time: number;
    active_sessions: number;
    requests_per_minute: number;
}

interface PerformanceMetrics {
    database_connections: number;
    query_cache_hit_rate: number;
    elasticsearch_health: {
        cluster_status: string;
        active_shards: number;
        relocating_shards: number;
        unassigned_shards: number;
    };
    api_response_times: {
        p50: number;
        p95: number;
        p99: number;
    };
    error_rates: {
        '2xx': number;
        '4xx': number;
        '5xx': number;
    };
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];

const SystemMetrics: React.FC<SystemMetricsProps> = ({ 
    systemHealth, 
    systemStats, 
    onRefresh 
}) => {
    const [metricsHistory, setMetricsHistory] = useState<MetricHistory[]>([]);
    const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetrics | null>(null);
    const [showDetailDialog, setShowDetailDialog] = useState(false);
    const [selectedMetric, setSelectedMetric] = useState<string>('');
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadMetricsHistory();
        loadPerformanceMetrics();
        
        // Auto-refresh every 60 seconds for metrics
        const interval = setInterval(() => {
            loadMetricsHistory();
            loadPerformanceMetrics();
        }, 60000);
        
        return () => clearInterval(interval);
    }, []);

    const loadMetricsHistory = async () => {
        try {
            const response = await fetch('/api/v1/auth/admin/metrics-history/?hours=24', {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}` }
            });
            
            if (response.ok) {
                const data = await response.json();
                setMetricsHistory(data.metrics || []);
            }
        } catch (err) {
            console.error('Failed to load metrics history:', err);
        }
    };

    const loadPerformanceMetrics = async () => {
        try {
            const response = await fetch('/api/v1/auth/admin/performance-metrics/', {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}` }
            });
            
            if (response.ok) {
                const data = await response.json();
                setPerformanceMetrics(data);
            }
        } catch (err) {
            console.error('Failed to load performance metrics:', err);
        }
    };

    const getUsageColor = (usage: number) => {
        if (usage > 90) return 'error';
        if (usage > 70) return 'warning';
        return 'success';
    };

    const getTrendIcon = (current: number, previous: number) => {
        if (current > previous) return <TrendingUp color="error" fontSize="small" />;
        if (current < previous) return <TrendingDown color="success" fontSize="small" />;
        return <Remove color="action" fontSize="small" />;
    };

    const formatBytes = (bytes: number) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const formatDuration = (seconds: number) => {
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        
        if (days > 0) return `${days}d ${hours}h ${minutes}m`;
        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
    };

    const chartData = metricsHistory.map(metric => ({
        time: new Date(metric.timestamp).toLocaleTimeString(),
        CPU: metric.cpu_usage,
        Memory: metric.memory_usage,
        Disk: metric.disk_usage,
        'ES Response': metric.elasticsearch_response_time,
        Sessions: metric.active_sessions,
        'Requests/min': metric.requests_per_minute,
    }));

    const errorRateData = performanceMetrics ? [
        { name: '2xx Success', value: performanceMetrics.error_rates['2xx'], color: COLORS[0] },
        { name: '4xx Client Error', value: performanceMetrics.error_rates['4xx'], color: COLORS[1] },
        { name: '5xx Server Error', value: performanceMetrics.error_rates['5xx'], color: COLORS[2] },
    ] : [];

    return (
        <Box>
            {/* Resource Usage Cards */}
            <Grid container spacing={3} sx={{ mb: 3 }}>
                <Grid item xs={12} md={4}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                                <Computer color="primary" />
                                <Typography variant="h6">CPU Usage</Typography>
                                {systemHealth && getTrendIcon(
                                    systemHealth.system.cpu_usage,
                                    metricsHistory[metricsHistory.length - 2]?.cpu_usage || 0
                                )}
                            </Box>
                            {systemHealth && (
                                <>
                                    <LinearProgress
                                        variant="determinate"
                                        value={systemHealth.system.cpu_usage}
                                        color={getUsageColor(systemHealth.system.cpu_usage)}
                                        sx={{ height: 8, borderRadius: 1, mb: 1 }}
                                    />
                                    <Typography variant="h4" color={getUsageColor(systemHealth.system.cpu_usage) === 'error' ? 'error' : 'textPrimary'}>
                                        {systemHealth.system.cpu_usage}%
                                    </Typography>
                                    <Typography variant="body2" color="textSecondary">
                                        Load Average: {systemHealth.system.load_average}
                                    </Typography>
                                </>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} md={4}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                                <Memory color="primary" />
                                <Typography variant="h6">Memory Usage</Typography>
                                {systemHealth && getTrendIcon(
                                    systemHealth.system.memory_usage,
                                    metricsHistory[metricsHistory.length - 2]?.memory_usage || 0
                                )}
                            </Box>
                            {systemHealth && (
                                <>
                                    <LinearProgress
                                        variant="determinate"
                                        value={systemHealth.system.memory_usage}
                                        color={getUsageColor(systemHealth.system.memory_usage)}
                                        sx={{ height: 8, borderRadius: 1, mb: 1 }}
                                    />
                                    <Typography variant="h4" color={getUsageColor(systemHealth.system.memory_usage) === 'error' ? 'error' : 'textPrimary'}>
                                        {systemHealth.system.memory_usage}%
                                    </Typography>
                                    <Typography variant="body2" color="textSecondary">
                                        Available RAM
                                    </Typography>
                                </>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} md={4}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                                <Storage color="primary" />
                                <Typography variant="h6">Disk Usage</Typography>
                                {systemHealth && getTrendIcon(
                                    systemHealth.system.disk_usage,
                                    metricsHistory[metricsHistory.length - 2]?.disk_usage || 0
                                )}
                            </Box>
                            {systemHealth && (
                                <>
                                    <LinearProgress
                                        variant="determinate"
                                        value={systemHealth.system.disk_usage}
                                        color={getUsageColor(systemHealth.system.disk_usage)}
                                        sx={{ height: 8, borderRadius: 1, mb: 1 }}
                                    />
                                    <Typography variant="h4" color={getUsageColor(systemHealth.system.disk_usage) === 'error' ? 'error' : 'textPrimary'}>
                                        {systemHealth.system.disk_usage}%
                                    </Typography>
                                    <Typography variant="body2" color="textSecondary">
                                        Disk Space Used
                                    </Typography>
                                </>
                            )}
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* Performance Charts */}
            <Grid container spacing={3} sx={{ mb: 3 }}>
                <Grid item xs={12} lg={8}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'between', alignItems: 'center', mb: 2 }}>
                                <Typography variant="h6">System Performance (24h)</Typography>
                                <Tooltip title="Refresh Data">
                                    <IconButton onClick={() => { loadMetricsHistory(); onRefresh(); }} size="small">
                                        <Refresh />
                                    </IconButton>
                                </Tooltip>
                            </Box>
                            <ResponsiveContainer width="100%" height={300}>
                                <LineChart data={chartData}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="time" />
                                    <YAxis />
                                    <RechartsTooltip />
                                    <Line type="monotone" dataKey="CPU" stroke={COLORS[0]} strokeWidth={2} />
                                    <Line type="monotone" dataKey="Memory" stroke={COLORS[1]} strokeWidth={2} />
                                    <Line type="monotone" dataKey="Sessions" stroke={COLORS[2]} strokeWidth={2} />
                                </LineChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} lg={4}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>API Response Distribution</Typography>
                            {errorRateData.length > 0 && (
                                <ResponsiveContainer width="100%" height={250}>
                                    <PieChart>
                                        <Pie
                                            data={errorRateData}
                                            cx="50%"
                                            cy="50%"
                                            outerRadius={80}
                                            dataKey="value"
                                            label={({ name, value }) => `${name}: ${value}%`}
                                        >
                                            {errorRateData.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={entry.color} />
                                            ))}
                                        </Pie>
                                        <RechartsTooltip />
                                    </PieChart>
                                </ResponsiveContainer>
                            )}
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* System Components Status */}
            <Grid container spacing={3} sx={{ mb: 3 }}>
                <Grid item xs={12} md={6}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Elasticsearch Cluster
                            </Typography>
                            {systemHealth && (
                                <TableContainer>
                                    <Table size="small">
                                        <TableBody>
                                            <TableRow>
                                                <TableCell>Cluster Status</TableCell>
                                                <TableCell>
                                                    <Chip
                                                        label={systemHealth.elasticsearch.status}
                                                        color={systemHealth.elasticsearch.status === 'healthy' ? 'success' : 'error'}
                                                        size="small"
                                                    />
                                                </TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell>Nodes</TableCell>
                                                <TableCell>{systemHealth.elasticsearch.nodes}</TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell>Indices</TableCell>
                                                <TableCell>{systemHealth.elasticsearch.indices}</TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell>Documents</TableCell>
                                                <TableCell>{systemHealth.elasticsearch.documents.toLocaleString()}</TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell>Storage Size</TableCell>
                                                <TableCell>{systemHealth.elasticsearch.storage_size}</TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell>Avg Response Time</TableCell>
                                                <TableCell>
                                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                        {systemHealth.elasticsearch.response_time_ms}ms
                                                        {systemHealth.elasticsearch.response_time_ms > 1000 && (
                                                            <Warning color="warning" fontSize="small" />
                                                        )}
                                                    </Box>
                                                </TableCell>
                                            </TableRow>
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} md={6}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Database Performance
                            </Typography>
                            {systemHealth && performanceMetrics && (
                                <TableContainer>
                                    <Table size="small">
                                        <TableBody>
                                            <TableRow>
                                                <TableCell>Connection Status</TableCell>
                                                <TableCell>
                                                    <Chip
                                                        label={systemHealth.database.status}
                                                        color={systemHealth.database.status === 'healthy' ? 'success' : 'error'}
                                                        size="small"
                                                    />
                                                </TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell>Active Connections</TableCell>
                                                <TableCell>{performanceMetrics.database_connections}</TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell>Active Queries</TableCell>
                                                <TableCell>{systemHealth.database.active_queries}</TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell>Cache Hit Rate</TableCell>
                                                <TableCell>{performanceMetrics.query_cache_hit_rate}%</TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell>Avg Response Time</TableCell>
                                                <TableCell>
                                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                        {systemHealth.database.response_time_ms}ms
                                                        {systemHealth.database.response_time_ms > 500 && (
                                                            <Warning color="warning" fontSize="small" />
                                                        )}
                                                    </Box>
                                                </TableCell>
                                            </TableRow>
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            )}
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* API Performance Metrics */}
            {performanceMetrics && (
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Typography variant="h6" gutterBottom>
                            API Performance Metrics
                        </Typography>
                        <Grid container spacing={3}>
                            <Grid item xs={12} md={4}>
                                <Typography variant="subtitle2" gutterBottom>Response Time Percentiles</Typography>
                                <List dense>
                                    <ListItem>
                                        <ListItemIcon><Speed fontSize="small" /></ListItemIcon>
                                        <ListItemText 
                                            primary="P50 (median)" 
                                            secondary={`${performanceMetrics.api_response_times.p50}ms`}
                                        />
                                    </ListItem>
                                    <ListItem>
                                        <ListItemIcon><Speed fontSize="small" /></ListItemIcon>
                                        <ListItemText 
                                            primary="P95" 
                                            secondary={`${performanceMetrics.api_response_times.p95}ms`}
                                        />
                                    </ListItem>
                                    <ListItem>
                                        <ListItemIcon><Speed fontSize="small" /></ListItemIcon>
                                        <ListItemText 
                                            primary="P99" 
                                            secondary={`${performanceMetrics.api_response_times.p99}ms`}
                                        />
                                    </ListItem>
                                </List>
                            </Grid>
                            <Grid item xs={12} md={4}>
                                <Typography variant="subtitle2" gutterBottom>Elasticsearch Health</Typography>
                                <List dense>
                                    <ListItem>
                                        <ListItemIcon>
                                            {performanceMetrics.elasticsearch_health.cluster_status === 'green' ? 
                                                <CheckCircle color="success" fontSize="small" /> :
                                                <Warning color="warning" fontSize="small" />
                                            }
                                        </ListItemIcon>
                                        <ListItemText 
                                            primary="Cluster Status" 
                                            secondary={performanceMetrics.elasticsearch_health.cluster_status}
                                        />
                                    </ListItem>
                                    <ListItem>
                                        <ListItemIcon><Database fontSize="small" /></ListItemIcon>
                                        <ListItemText 
                                            primary="Active Shards" 
                                            secondary={performanceMetrics.elasticsearch_health.active_shards}
                                        />
                                    </ListItem>
                                    <ListItem>
                                        <ListItemIcon><Database fontSize="small" /></ListItemIcon>
                                        <ListItemText 
                                            primary="Unassigned Shards" 
                                            secondary={performanceMetrics.elasticsearch_health.unassigned_shards}
                                        />
                                    </ListItem>
                                </List>
                            </Grid>
                            <Grid item xs={12} md={4}>
                                <Typography variant="subtitle2" gutterBottom>Error Rates (24h)</Typography>
                                <List dense>
                                    <ListItem>
                                        <ListItemIcon><CheckCircle color="success" fontSize="small" /></ListItemIcon>
                                        <ListItemText 
                                            primary="Success (2xx)" 
                                            secondary={`${performanceMetrics.error_rates['2xx']}%`}
                                        />
                                    </ListItem>
                                    <ListItem>
                                        <ListItemIcon><Warning color="warning" fontSize="small" /></ListItemIcon>
                                        <ListItemText 
                                            primary="Client Errors (4xx)" 
                                            secondary={`${performanceMetrics.error_rates['4xx']}%`}
                                        />
                                    </ListItem>
                                    <ListItem>
                                        <ListItemIcon><Error color="error" fontSize="small" /></ListItemIcon>
                                        <ListItemText 
                                            primary="Server Errors (5xx)" 
                                            secondary={`${performanceMetrics.error_rates['5xx']}%`}
                                        />
                                    </ListItem>
                                </List>
                            </Grid>
                        </Grid>
                    </CardContent>
                </Card>
            )}
        </Box>
    );
};

export default SystemMetrics;