import React, { useState, useEffect } from 'react';
import {
    Box,
    Grid,
    Card,
    CardContent,
    Typography,
    Tabs,
    Tab,
    Alert,
    CircularProgress,
    Chip,
    LinearProgress,
    IconButton,
    Tooltip,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    TextField,
    Switch,
    FormControlLabel,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    ListItemSecondaryAction,
    Divider,
    Badge,
} from '@mui/material';
import {
    Dashboard,
    TrendingUp,
    Warning,
    Error,
    CheckCircle,
    Refresh,
    Notifications,
    Settings,
    Timeline,
    Speed,
    Memory,
    Storage,
    NetworkCheck,
    Security,
    MonitorHeart,
    NotificationAdd,
    Edit,
    Delete,
    PlayArrow,
    Stop,
    Visibility,
    Assessment,
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
import { format } from 'date-fns';

interface PerformanceMetric {
    id: string;
    name: string;
    category: string;
    component: string;
    value: number;
    unit: string;
    timestamp: string;
    is_anomaly: boolean;
    tags: Record<string, any>;
}

interface Alert {
    id: string;
    title: string;
    description: string;
    severity: 'info' | 'warning' | 'error' | 'critical';
    status: 'open' | 'acknowledged' | 'resolved' | 'suppressed';
    component: string;
    metric_value: number;
    threshold_value: number;
    triggered_at: string;
    acknowledged_at?: string;
    resolved_at?: string;
    acknowledged_by?: string;
}

interface AlertRule {
    id: string;
    name: string;
    description: string;
    metric_name: string;
    metric_category: string;
    threshold_operator: string;
    threshold_value: number;
    severity: string;
    is_active: boolean;
    cooldown_period: number;
    last_triggered?: string;
}

interface HealthCheck {
    id: string;
    name: string;
    check_type: string;
    current_status: 'healthy' | 'warning' | 'critical' | 'unknown';
    last_check_time: string;
    response_time?: number;
    consecutive_failures: number;
    is_active: boolean;
}

interface NotificationChannel {
    id: string;
    name: string;
    channel_type: 'email' | 'slack' | 'webhook' | 'discord' | 'teams';
    is_active: boolean;
    last_used?: string;
}

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

function TabPanel(props: TabPanelProps) {
    const { children, value, index, ...other } = props;
    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`monitoring-tabpanel-${index}`}
            {...other}
        >
            {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
        </div>
    );
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];

const MonitoringDashboard: React.FC = () => {
    const [currentTab, setCurrentTab] = useState(0);
    const [metrics, setMetrics] = useState<PerformanceMetric[]>([]);
    const [alerts, setAlerts] = useState<Alert[]>([]);
    const [alertRules, setAlertRules] = useState<AlertRule[]>([]);
    const [healthChecks, setHealthChecks] = useState<HealthCheck[]>([]);
    const [notificationChannels, setNotificationChannels] = useState<NotificationChannel[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

    // Dialog states
    const [showAlertRuleDialog, setShowAlertRuleDialog] = useState(false);
    const [showChannelDialog, setShowChannelDialog] = useState(false);
    const [showAlertDetail, setShowAlertDetail] = useState(false);
    const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
    const [selectedRule, setSelectedRule] = useState<AlertRule | null>(null);

    useEffect(() => {
        loadMonitoringData();
        
        // Auto-refresh every 30 seconds
        const interval = setInterval(loadMonitoringData, 30000);
        return () => clearInterval(interval);
    }, []);

    const loadMonitoringData = async () => {
        setLoading(true);
        try {
            const [
                metricsResponse,
                alertsResponse,
                rulesResponse,
                healthResponse,
                channelsResponse
            ] = await Promise.all([
                fetch('/api/v1/analytics/', {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}` }
                }),
                fetch('/api/v1/analytics/alerts/', {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}` }
                }),
                fetch('/api/v1/analytics/alert-rules/', {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}` }
                }),
                fetch('/api/v1/system/health/', {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}` }
                }),
                fetch('/api/v1/analytics/alerts/', {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}` }
                })
            ]);

            const [metricsData, alertsData, rulesData, healthData, channelsData] = await Promise.all([
                metricsResponse.ok ? metricsResponse.json() : { metrics: [] },
                alertsResponse.ok ? alertsResponse.json() : { alerts: [] },
                rulesResponse.ok ? rulesResponse.json() : { rules: [] },
                healthResponse.ok ? healthResponse.json() : { checks: [] },
                channelsResponse.ok ? channelsResponse.json() : { channels: [] }
            ]);

            setMetrics(metricsData.metrics || []);
            setAlerts(alertsData.alerts || []);
            setAlertRules(rulesData.rules || []);
            setHealthChecks(healthData.checks || []);
            setNotificationChannels(channelsData.channels || []);
            setLastRefresh(new Date());

        } catch (err) {
            setError('Failed to load monitoring data');
        } finally {
            setLoading(false);
        }
    };

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setCurrentTab(newValue);
    };

    const acknowledgeAlert = async (alertId: string) => {
        try {
            const response = await fetch(`/api/v1/analytics/alerts/${alertId}/acknowledge/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ comment: 'Acknowledged from dashboard' }),
            });

            if (response.ok) {
                loadMonitoringData();
            }
        } catch (err) {
            console.error('Failed to acknowledge alert:', err);
        }
    };

    const resolveAlert = async (alertId: string) => {
        try {
            const response = await fetch(`/api/v1/analytics/alerts/${alertId}/resolve/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ comment: 'Resolved from dashboard' }),
            });

            if (response.ok) {
                loadMonitoringData();
            }
        } catch (err) {
            console.error('Failed to resolve alert:', err);
        }
    };

    const toggleAlertRule = async (ruleId: string, isActive: boolean) => {
        try {
            const response = await fetch(`/api/v1/analytics/alert-rules/${ruleId}/`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ is_active: isActive }),
            });

            if (response.ok) {
                loadMonitoringData();
            }
        } catch (err) {
            console.error('Failed to toggle alert rule:', err);
        }
    };

    const runHealthCheck = async (checkId: string) => {
        try {
            const response = await fetch(`/api/v1/system/health/`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}` }
            });

            if (response.ok) {
                loadMonitoringData();
            }
        } catch (err) {
            console.error('Failed to run health check:', err);
        }
    };

    const getSeverityColor = (severity: string) => {
        switch (severity) {
            case 'critical': return 'error';
            case 'error': return 'error';
            case 'warning': return 'warning';
            case 'info': return 'info';
            default: return 'default';
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'healthy': return 'success';
            case 'warning': return 'warning';
            case 'critical': return 'error';
            default: return 'default';
        }
    };

    const getMetricChartData = () => {
        const last24Hours = metrics.filter(m => {
            const metricTime = new Date(m.timestamp);
            const twentyFourHoursAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
            return metricTime > twentyFourHoursAgo;
        });

        const groupedData = last24Hours.reduce((acc, metric) => {
            const hour = new Date(metric.timestamp).toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
            
            if (!acc[hour]) {
                acc[hour] = { time: hour };
            }
            
            acc[hour][metric.name] = metric.value;
            return acc;
        }, {} as any);

        return Object.values(groupedData).slice(-24); // Last 24 data points
    };

    const alertsByStatus = alerts.reduce((acc, alert) => {
        acc[alert.status] = (acc[alert.status] || 0) + 1;
        return acc;
    }, {} as Record<string, number>);

    const alertStatusData = Object.entries(alertsByStatus).map(([status, count], index) => ({
        name: status.charAt(0).toUpperCase() + status.slice(1),
        value: count,
        color: COLORS[index % COLORS.length]
    }));

    return (
        <Box sx={{ width: '100%' }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1">
                    Performance Monitoring & Alerting
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                    <Typography variant="body2" color="textSecondary">
                        Last updated: {lastRefresh.toLocaleTimeString()}
                    </Typography>
                    <Tooltip title="Refresh Data">
                        <IconButton onClick={loadMonitoringData} disabled={loading}>
                            <Refresh />
                        </IconButton>
                    </Tooltip>
                </Box>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {loading && <LinearProgress sx={{ mb: 2 }} />}

            {/* Summary Cards */}
            <Grid container spacing={3} sx={{ mb: 3 }}>
                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Assessment color="primary" />
                                <Box>
                                    <Typography color="textSecondary" gutterBottom>
                                        Total Metrics
                                    </Typography>
                                    <Typography variant="h5">
                                        {metrics.length.toLocaleString()}
                                    </Typography>
                                    <Typography variant="body2" color="textSecondary">
                                        {metrics.filter(m => m.is_anomaly).length} anomalies
                                    </Typography>
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Warning color="warning" />
                                <Box>
                                    <Typography color="textSecondary" gutterBottom>
                                        Active Alerts
                                    </Typography>
                                    <Typography variant="h5" color="warning.main">
                                        {alerts.filter(a => a.status === 'open').length}
                                    </Typography>
                                    <Typography variant="body2" color="textSecondary">
                                        {alerts.filter(a => a.severity === 'critical').length} critical
                                    </Typography>
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <MonitorHeart color="success" />
                                <Box>
                                    <Typography color="textSecondary" gutterBottom>
                                        Health Checks
                                    </Typography>
                                    <Typography variant="h5">
                                        {healthChecks.filter(h => h.current_status === 'healthy').length}/
                                        {healthChecks.length}
                                    </Typography>
                                    <Typography variant="body2" color="textSecondary">
                                        healthy
                                    </Typography>
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Notifications color="info" />
                                <Box>
                                    <Typography color="textSecondary" gutterBottom>
                                        Alert Rules
                                    </Typography>
                                    <Typography variant="h5">
                                        {alertRules.filter(r => r.is_active).length}
                                    </Typography>
                                    <Typography variant="body2" color="textSecondary">
                                        active rules
                                    </Typography>
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* Navigation Tabs */}
            <Paper sx={{ borderBottom: 1, borderColor: 'divider' }}>
                <Tabs 
                    value={currentTab} 
                    onChange={handleTabChange}
                    variant="scrollable"
                    scrollButtons="auto"
                >
                    <Tab icon={<Dashboard />} label="Overview" />
                    <Tab icon={<Timeline />} label="Metrics" />
                    <Tab icon={<Warning />} label="Alerts" />
                    <Tab icon={<Settings />} label="Alert Rules" />
                    <Tab icon={<MonitorHeart />} label="Health Checks" />
                    <Tab icon={<Notifications />} label="Notifications" />
                </Tabs>
            </Paper>

            {/* Tab Content */}
            <TabPanel value={currentTab} index={0}>
                {/* Overview Dashboard */}
                <Grid container spacing={3}>
                    <Grid item xs={12} lg={8}>
                        <Card>
                            <CardContent>
                                <Typography variant="h6" gutterBottom>
                                    Performance Metrics Trend (24h)
                                </Typography>
                                <ResponsiveContainer width="100%" height={350}>
                                    <LineChart data={getMetricChartData()}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis dataKey="time" />
                                        <YAxis />
                                        <RechartsTooltip />
                                        <Line type="monotone" dataKey="cpu_usage_percent" stroke={COLORS[0]} name="CPU %" />
                                        <Line type="monotone" dataKey="memory_usage_percent" stroke={COLORS[1]} name="Memory %" />
                                        <Line type="monotone" dataKey="disk_usage_percent" stroke={COLORS[2]} name="Disk %" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>
                    </Grid>

                    <Grid item xs={12} lg={4}>
                        <Card>
                            <CardContent>
                                <Typography variant="h6" gutterBottom>
                                    Alert Status Distribution
                                </Typography>
                                <ResponsiveContainer width="100%" height={300}>
                                    <PieChart>
                                        <Pie
                                            data={alertStatusData}
                                            cx="50%"
                                            cy="50%"
                                            outerRadius={80}
                                            dataKey="value"
                                            label={({ name, value }) => `${name}: ${value}`}
                                        >
                                            {alertStatusData.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={entry.color} />
                                            ))}
                                        </Pie>
                                        <RechartsTooltip />
                                    </PieChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>
            </TabPanel>

            <TabPanel value={currentTab} index={1}>
                {/* Metrics Tab */}
                <Card>
                    <CardContent>
                        <Typography variant="h6" gutterBottom>
                            Recent Performance Metrics
                        </Typography>
                        <TableContainer>
                            <Table>
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Metric</TableCell>
                                        <TableCell>Component</TableCell>
                                        <TableCell>Value</TableCell>
                                        <TableCell>Timestamp</TableCell>
                                        <TableCell>Status</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {metrics.slice(0, 20).map((metric) => (
                                        <TableRow key={metric.id}>
                                            <TableCell>
                                                <Typography variant="body2">
                                                    {metric.name}
                                                </Typography>
                                                <Typography variant="caption" color="textSecondary">
                                                    {metric.category}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>{metric.component}</TableCell>
                                            <TableCell>
                                                <Typography variant="body2">
                                                    {metric.value} {metric.unit}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                {format(new Date(metric.timestamp), 'MMM dd, HH:mm:ss')}
                                            </TableCell>
                                            <TableCell>
                                                {metric.is_anomaly ? (
                                                    <Chip
                                                        label="Anomaly"
                                                        color="warning"
                                                        size="small"
                                                        icon={<Warning />}
                                                    />
                                                ) : (
                                                    <Chip
                                                        label="Normal"
                                                        color="success"
                                                        size="small"
                                                        icon={<CheckCircle />}
                                                    />
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </CardContent>
                </Card>
            </TabPanel>

            <TabPanel value={currentTab} index={2}>
                {/* Alerts Tab */}
                <Card>
                    <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'between', alignItems: 'center', mb: 2 }}>
                            <Typography variant="h6">Active Alerts</Typography>
                            <Button
                                variant="outlined"
                                onClick={() => setShowAlertDetail(true)}
                                disabled={alerts.filter(a => a.status === 'open').length === 0}
                            >
                                Bulk Actions
                            </Button>
                        </Box>
                        <TableContainer>
                            <Table>
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Severity</TableCell>
                                        <TableCell>Title</TableCell>
                                        <TableCell>Component</TableCell>
                                        <TableCell>Value</TableCell>
                                        <TableCell>Triggered</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell>Actions</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {alerts.map((alert) => (
                                        <TableRow key={alert.id}>
                                            <TableCell>
                                                <Chip
                                                    label={alert.severity}
                                                    color={getSeverityColor(alert.severity) as any}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="body2">
                                                    {alert.title}
                                                </Typography>
                                                <Typography variant="caption" color="textSecondary">
                                                    {alert.description.substring(0, 100)}...
                                                </Typography>
                                            </TableCell>
                                            <TableCell>{alert.component}</TableCell>
                                            <TableCell>
                                                {alert.metric_value} / {alert.threshold_value}
                                            </TableCell>
                                            <TableCell>
                                                {format(new Date(alert.triggered_at), 'MMM dd, HH:mm')}
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={alert.status}
                                                    color={alert.status === 'open' ? 'error' : 'default'}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Box sx={{ display: 'flex', gap: 0.5 }}>
                                                    {alert.status === 'open' && (
                                                        <>
                                                            <Tooltip title="Acknowledge">
                                                                <IconButton
                                                                    size="small"
                                                                    onClick={() => acknowledgeAlert(alert.id)}
                                                                >
                                                                    <CheckCircle fontSize="small" />
                                                                </IconButton>
                                                            </Tooltip>
                                                            <Tooltip title="Resolve">
                                                                <IconButton
                                                                    size="small"
                                                                    color="success"
                                                                    onClick={() => resolveAlert(alert.id)}
                                                                >
                                                                    <CheckCircle fontSize="small" />
                                                                </IconButton>
                                                            </Tooltip>
                                                        </>
                                                    )}
                                                    <Tooltip title="View Details">
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => {
                                                                setSelectedAlert(alert);
                                                                setShowAlertDetail(true);
                                                            }}
                                                        >
                                                            <Visibility fontSize="small" />
                                                        </IconButton>
                                                    </Tooltip>
                                                </Box>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </CardContent>
                </Card>
            </TabPanel>

            <TabPanel value={currentTab} index={3}>
                {/* Alert Rules Tab */}
                <Card>
                    <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'between', alignItems: 'center', mb: 2 }}>
                            <Typography variant="h6">Alert Rules</Typography>
                            <Button
                                variant="contained"
                                startIcon={<NotificationAdd />}
                                onClick={() => setShowAlertRuleDialog(true)}
                            >
                                Create Rule
                            </Button>
                        </Box>
                        <TableContainer>
                            <Table>
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Name</TableCell>
                                        <TableCell>Metric</TableCell>
                                        <TableCell>Condition</TableCell>
                                        <TableCell>Severity</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell>Last Triggered</TableCell>
                                        <TableCell>Actions</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {alertRules.map((rule) => (
                                        <TableRow key={rule.id}>
                                            <TableCell>
                                                <Typography variant="body2">
                                                    {rule.name}
                                                </Typography>
                                                <Typography variant="caption" color="textSecondary">
                                                    {rule.description}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>{rule.metric_name}</TableCell>
                                            <TableCell>
                                                {rule.threshold_operator} {rule.threshold_value}
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={rule.severity}
                                                    color={getSeverityColor(rule.severity) as any}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Switch
                                                    checked={rule.is_active}
                                                    onChange={(e) => toggleAlertRule(rule.id, e.target.checked)}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                {rule.last_triggered 
                                                    ? format(new Date(rule.last_triggered), 'MMM dd, HH:mm')
                                                    : 'Never'
                                                }
                                            </TableCell>
                                            <TableCell>
                                                <Box sx={{ display: 'flex', gap: 0.5 }}>
                                                    <Tooltip title="Edit Rule">
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => {
                                                                setSelectedRule(rule);
                                                                setShowAlertRuleDialog(true);
                                                            }}
                                                        >
                                                            <Edit fontSize="small" />
                                                        </IconButton>
                                                    </Tooltip>
                                                </Box>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </CardContent>
                </Card>
            </TabPanel>

            <TabPanel value={currentTab} index={4}>
                {/* Health Checks Tab */}
                <Card>
                    <CardContent>
                        <Typography variant="h6" gutterBottom>
                            System Health Checks
                        </Typography>
                        <TableContainer>
                            <Table>
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Check Name</TableCell>
                                        <TableCell>Type</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell>Last Check</TableCell>
                                        <TableCell>Response Time</TableCell>
                                        <TableCell>Failures</TableCell>
                                        <TableCell>Actions</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {healthChecks.map((check) => (
                                        <TableRow key={check.id}>
                                            <TableCell>{check.name}</TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={check.check_type}
                                                    variant="outlined"
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={check.current_status}
                                                    color={getStatusColor(check.current_status) as any}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                {format(new Date(check.last_check_time), 'MMM dd, HH:mm:ss')}
                                            </TableCell>
                                            <TableCell>
                                                {check.response_time ? `${check.response_time.toFixed(0)}ms` : 'N/A'}
                                            </TableCell>
                                            <TableCell>
                                                <Badge
                                                    badgeContent={check.consecutive_failures}
                                                    color={check.consecutive_failures > 0 ? 'error' : 'default'}
                                                >
                                                    <Typography variant="body2">failures</Typography>
                                                </Badge>
                                            </TableCell>
                                            <TableCell>
                                                <Box sx={{ display: 'flex', gap: 0.5 }}>
                                                    <Tooltip title="Run Check">
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => runHealthCheck(check.id)}
                                                        >
                                                            <PlayArrow fontSize="small" />
                                                        </IconButton>
                                                    </Tooltip>
                                                </Box>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </CardContent>
                </Card>
            </TabPanel>

            <TabPanel value={currentTab} index={5}>
                {/* Notification Channels Tab */}
                <Card>
                    <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'between', alignItems: 'center', mb: 2 }}>
                            <Typography variant="h6">Notification Channels</Typography>
                            <Button
                                variant="contained"
                                startIcon={<NotificationAdd />}
                                onClick={() => setShowChannelDialog(true)}
                            >
                                Add Channel
                            </Button>
                        </Box>
                        <List>
                            {notificationChannels.map((channel, index) => (
                                <React.Fragment key={channel.id}>
                                    <ListItem>
                                        <ListItemIcon>
                                            <Notifications color={channel.is_active ? 'primary' : 'disabled'} />
                                        </ListItemIcon>
                                        <ListItemText
                                            primary={channel.name}
                                            secondary={
                                                <Box>
                                                    <Typography variant="caption">
                                                        Type: {channel.channel_type}
                                                    </Typography>
                                                    {channel.last_used && (
                                                        <Typography variant="caption" display="block">
                                                            Last used: {format(new Date(channel.last_used), 'MMM dd, HH:mm')}
                                                        </Typography>
                                                    )}
                                                </Box>
                                            }
                                        />
                                        <ListItemSecondaryAction>
                                            <Switch
                                                checked={channel.is_active}
                                                onChange={() => {/* Handle toggle */}}
                                                size="small"
                                            />
                                        </ListItemSecondaryAction>
                                    </ListItem>
                                    {index < notificationChannels.length - 1 && <Divider />}
                                </React.Fragment>
                            ))}
                        </List>
                    </CardContent>
                </Card>
            </TabPanel>

            {/* Alert Detail Dialog */}
            <Dialog
                open={showAlertDetail}
                onClose={() => setShowAlertDetail(false)}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle>Alert Details</DialogTitle>
                <DialogContent>
                    {selectedAlert && (
                        <Box>
                            <Typography variant="h6" gutterBottom>
                                {selectedAlert.title}
                            </Typography>
                            <Typography paragraph>
                                {selectedAlert.description}
                            </Typography>
                            <Grid container spacing={2}>
                                <Grid item xs={6}>
                                    <Typography><strong>Severity:</strong> {selectedAlert.severity}</Typography>
                                    <Typography><strong>Status:</strong> {selectedAlert.status}</Typography>
                                    <Typography><strong>Component:</strong> {selectedAlert.component}</Typography>
                                </Grid>
                                <Grid item xs={6}>
                                    <Typography><strong>Current Value:</strong> {selectedAlert.metric_value}</Typography>
                                    <Typography><strong>Threshold:</strong> {selectedAlert.threshold_value}</Typography>
                                    <Typography><strong>Triggered:</strong> {format(new Date(selectedAlert.triggered_at), 'yyyy-MM-dd HH:mm:ss')}</Typography>
                                </Grid>
                            </Grid>
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowAlertDetail(false)}>Close</Button>
                    {selectedAlert?.status === 'open' && (
                        <>
                            <Button
                                onClick={() => {
                                    acknowledgeAlert(selectedAlert.id);
                                    setShowAlertDetail(false);
                                }}
                                color="warning"
                            >
                                Acknowledge
                            </Button>
                            <Button
                                onClick={() => {
                                    resolveAlert(selectedAlert.id);
                                    setShowAlertDetail(false);
                                }}
                                color="success"
                                variant="contained"
                            >
                                Resolve
                            </Button>
                        </>
                    )}
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default MonitoringDashboard;