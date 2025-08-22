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
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    Divider,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
} from '@mui/material';
import {
    Dashboard,
    People,
    Security,
    Analytics,
    Settings,
    Warning,
    CheckCircle,
    Error,
    Info,
    Refresh,
    Shield,
    Computer,
    Storage,
    NetworkCheck,
    Speed,
    Memory,
} from '@mui/icons-material';

import UserManagement from './UserManagement';
import SessionManagement from './SessionManagement';
import SystemMetrics from './SystemMetrics';
import SecurityOverview from './SecurityOverview';
import AuditLogViewer from './AuditLogViewer';

interface SystemHealth {
    elasticsearch: {
        status: 'healthy' | 'warning' | 'error';
        cluster_name: string;
        nodes: number;
        indices: number;
        documents: number;
        storage_size: string;
        response_time_ms: number;
    };
    database: {
        status: 'healthy' | 'warning' | 'error';
        connections: number;
        active_queries: number;
        response_time_ms: number;
    };
    authentication: {
        status: 'healthy' | 'warning' | 'error';
        active_sessions: number;
        failed_logins_24h: number;
        suspicious_activities: number;
    };
    system: {
        cpu_usage: number;
        memory_usage: number;
        disk_usage: number;
        uptime: string;
        load_average: number;
    };
    security: {
        active_policies: number;
        policy_violations_24h: number;
        blocked_ips: number;
        threat_level: 'low' | 'medium' | 'high' | 'critical';
    };
}

interface SystemStats {
    total_users: number;
    active_users_24h: number;
    total_sessions: number;
    queries_generated_24h: number;
    data_exported_24h: number;
    system_alerts: number;
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
            id={`admin-tabpanel-${index}`}
            aria-labelledby={`admin-tab-${index}`}
            {...other}
        >
            {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
        </div>
    );
}

const AdminDashboard: React.FC = () => {
    const [currentTab, setCurrentTab] = useState(0);
    const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
    const [systemStats, setSystemStats] = useState<SystemStats | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
    const [showMaintenanceDialog, setShowMaintenanceDialog] = useState(false);

    useEffect(() => {
        loadDashboardData();
        
        // Auto-refresh every 30 seconds
        const interval = setInterval(loadDashboardData, 30000);
        return () => clearInterval(interval);
    }, []);

    const loadDashboardData = async () => {
        setLoading(true);
        try {
            const [healthResponse, statsResponse] = await Promise.all([
                fetch('/api/admin/system-health/', {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
                }),
                fetch('/api/admin/system-stats/', {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
                })
            ]);

            if (healthResponse.ok && statsResponse.ok) {
                const [health, stats] = await Promise.all([
                    healthResponse.json(),
                    statsResponse.json()
                ]);
                
                setSystemHealth(health);
                setSystemStats(stats);
                setLastRefresh(new Date());
            } else {
                setError('Failed to load dashboard data');
            }
        } catch (err) {
            setError('Network error loading dashboard');
        } finally {
            setLoading(false);
        }
    };

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setCurrentTab(newValue);
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'healthy': return 'success';
            case 'warning': return 'warning';
            case 'error': return 'error';
            default: return 'default';
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'healthy': return <CheckCircle />;
            case 'warning': return <Warning />;
            case 'error': return <Error />;
            default: return <Info />;
        }
    };

    const getThreatLevelColor = (level: string) => {
        switch (level) {
            case 'low': return 'success';
            case 'medium': return 'info';
            case 'high': return 'warning';
            case 'critical': return 'error';
            default: return 'default';
        }
    };

    const formatBytes = (bytes: number) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const performMaintenanceAction = async (action: string) => {
        try {
            const response = await fetch(`/api/admin/maintenance/${action}/`, {
                method: 'POST',
                headers: { 
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                setShowMaintenanceDialog(false);
                loadDashboardData();
            } else {
                setError(`Failed to perform ${action}`);
            }
        } catch (err) {
            setError(`Error performing ${action}`);
        }
    };

    return (
        <Box sx={{ width: '100%' }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1">
                    System Administration
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                    <Typography variant="body2" color="textSecondary">
                        Last updated: {lastRefresh.toLocaleTimeString()}
                    </Typography>
                    <Tooltip title="Refresh Dashboard">
                        <IconButton onClick={loadDashboardData} disabled={loading}>
                            <Refresh />
                        </IconButton>
                    </Tooltip>
                    <Button
                        variant="outlined"
                        startIcon={<Settings />}
                        onClick={() => setShowMaintenanceDialog(true)}
                    >
                        Maintenance
                    </Button>
                </Box>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {/* Loading indicator */}
            {loading && <LinearProgress sx={{ mb: 2 }} />}

            {/* System Overview Cards */}
            {systemHealth && systemStats && (
                <Grid container spacing={3} sx={{ mb: 3 }}>
                    {/* System Health Cards */}
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                    <Computer color="primary" />
                                    <Box>
                                        <Typography color="textSecondary" gutterBottom>
                                            System Health
                                        </Typography>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            {getStatusIcon(systemHealth.database.status)}
                                            <Typography variant="h6">
                                                Overall Status
                                            </Typography>
                                        </Box>
                                        <Typography variant="body2" color="textSecondary">
                                            CPU: {systemHealth.system.cpu_usage}% | 
                                            RAM: {systemHealth.system.memory_usage}%
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
                                    <Storage color="primary" />
                                    <Box>
                                        <Typography color="textSecondary" gutterBottom>
                                            Elasticsearch
                                        </Typography>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Chip
                                                icon={getStatusIcon(systemHealth.elasticsearch.status)}
                                                label={systemHealth.elasticsearch.status}
                                                color={getStatusColor(systemHealth.elasticsearch.status) as any}
                                                size="small"
                                            />
                                        </Box>
                                        <Typography variant="body2" color="textSecondary">
                                            {systemHealth.elasticsearch.indices} indices | 
                                            {systemHealth.elasticsearch.documents.toLocaleString()} docs
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
                                    <Shield color="primary" />
                                    <Box>
                                        <Typography color="textSecondary" gutterBottom>
                                            Security
                                        </Typography>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Chip
                                                label={systemHealth.security.threat_level}
                                                color={getThreatLevelColor(systemHealth.security.threat_level) as any}
                                                size="small"
                                            />
                                        </Box>
                                        <Typography variant="body2" color="textSecondary">
                                            {systemHealth.security.active_policies} policies active
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
                                    <People color="primary" />
                                    <Box>
                                        <Typography color="textSecondary" gutterBottom>
                                            Users & Sessions
                                        </Typography>
                                        <Typography variant="h6">
                                            {systemStats.total_users} users
                                        </Typography>
                                        <Typography variant="body2" color="textSecondary">
                                            {systemStats.active_users_24h} active today | 
                                            {systemStats.total_sessions} sessions
                                        </Typography>
                                    </Box>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>
            )}

            {/* Quick Alerts */}
            {systemHealth && (
                <Paper sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
                    <Typography variant="h6" gutterBottom>
                        System Alerts
                    </Typography>
                    <List dense>
                        {systemHealth.authentication.failed_logins_24h > 10 && (
                            <ListItem>
                                <ListItemIcon>
                                    <Warning color="warning" />
                                </ListItemIcon>
                                <ListItemText 
                                    primary="High Failed Login Rate"
                                    secondary={`${systemHealth.authentication.failed_logins_24h} failed logins in last 24h`}
                                />
                            </ListItem>
                        )}
                        {systemHealth.security.policy_violations_24h > 0 && (
                            <ListItem>
                                <ListItemIcon>
                                    <Error color="error" />
                                </ListItemIcon>
                                <ListItemText 
                                    primary="Security Policy Violations"
                                    secondary={`${systemHealth.security.policy_violations_24h} violations in last 24h`}
                                />
                            </ListItem>
                        )}
                        {systemHealth.system.disk_usage > 80 && (
                            <ListItem>
                                <ListItemIcon>
                                    <Warning color="warning" />
                                </ListItemIcon>
                                <ListItemText 
                                    primary="High Disk Usage"
                                    secondary={`Disk usage at ${systemHealth.system.disk_usage}%`}
                                />
                            </ListItem>
                        )}
                        {systemHealth.elasticsearch.response_time_ms > 1000 && (
                            <ListItem>
                                <ListItemIcon>
                                    <Speed color="warning" />
                                </ListItemIcon>
                                <ListItemText 
                                    primary="Slow Elasticsearch Response"
                                    secondary={`Average response time: ${systemHealth.elasticsearch.response_time_ms}ms`}
                                />
                            </ListItem>
                        )}
                    </List>
                </Paper>
            )}

            {/* Navigation Tabs */}
            <Paper sx={{ borderBottom: 1, borderColor: 'divider' }}>
                <Tabs 
                    value={currentTab} 
                    onChange={handleTabChange}
                    variant="scrollable"
                    scrollButtons="auto"
                >
                    <Tab 
                        icon={<Dashboard />} 
                        label="Overview" 
                        id="admin-tab-0"
                    />
                    <Tab 
                        icon={<People />} 
                        label="User Management" 
                        id="admin-tab-1"
                    />
                    <Tab 
                        icon={<Security />} 
                        label="Session Security" 
                        id="admin-tab-2"
                    />
                    <Tab 
                        icon={<Analytics />} 
                        label="System Metrics" 
                        id="admin-tab-3"
                    />
                    <Tab 
                        icon={<Shield />} 
                        label="Security Overview" 
                        id="admin-tab-4"
                    />
                    <Tab 
                        icon={<Settings />} 
                        label="Audit Logs" 
                        id="admin-tab-5"
                    />
                </Tabs>
            </Paper>

            {/* Tab Content */}
            <TabPanel value={currentTab} index={0}>
                <SystemMetrics 
                    systemHealth={systemHealth}
                    systemStats={systemStats}
                    onRefresh={loadDashboardData}
                />
            </TabPanel>

            <TabPanel value={currentTab} index={1}>
                <UserManagement />
            </TabPanel>

            <TabPanel value={currentTab} index={2}>
                <SessionManagement />
            </TabPanel>

            <TabPanel value={currentTab} index={3}>
                <SystemMetrics 
                    systemHealth={systemHealth}
                    systemStats={systemStats}
                    onRefresh={loadDashboardData}
                />
            </TabPanel>

            <TabPanel value={currentTab} index={4}>
                <SecurityOverview 
                    systemHealth={systemHealth}
                    onRefresh={loadDashboardData}
                />
            </TabPanel>

            <TabPanel value={currentTab} index={5}>
                <AuditLogViewer />
            </TabPanel>

            {/* Maintenance Dialog */}
            <Dialog
                open={showMaintenanceDialog}
                onClose={() => setShowMaintenanceDialog(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle>System Maintenance</DialogTitle>
                <DialogContent>
                    <Typography paragraph>
                        Select a maintenance action to perform:
                    </Typography>
                    <List>
                        <ListItem button onClick={() => performMaintenanceAction('cleanup-sessions')}>
                            <ListItemText 
                                primary="Cleanup Expired Sessions"
                                secondary="Remove expired and terminated sessions"
                            />
                        </ListItem>
                        <Divider />
                        <ListItem button onClick={() => performMaintenanceAction('cleanup-logs')}>
                            <ListItemText 
                                primary="Cleanup Old Logs"
                                secondary="Archive audit logs older than 90 days"
                            />
                        </ListItem>
                        <Divider />
                        <ListItem button onClick={() => performMaintenanceAction('optimize-indices')}>
                            <ListItemText 
                                primary="Optimize Elasticsearch Indices"
                                secondary="Optimize and refresh Elasticsearch indices"
                            />
                        </ListItem>
                        <Divider />
                        <ListItem button onClick={() => performMaintenanceAction('update-analytics')}>
                            <ListItemText 
                                primary="Refresh Analytics"
                                secondary="Recalculate system analytics and metrics"
                            />
                        </ListItem>
                    </List>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowMaintenanceDialog(false)}>
                        Cancel
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default AdminDashboard;