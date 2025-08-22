import React, { useState, useEffect } from 'react';
import {
    Box,
    Grid,
    Card,
    CardContent,
    Typography,
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
    LinearProgress,
    Box as MuiBox,
    Accordion,
    AccordionSummary,
    AccordionDetails,
} from '@mui/material';
import {
    Shield,
    Security,
    Warning,
    Error,
    Block,
    VpnKey,
    Visibility,
    ExpandMore,
    Refresh,
    AccountCircle,
    Computer,
    AccessTime,
    LocationOn,
    CheckCircle,
    Cancel,
    Report,
} from '@mui/icons-material';
import { format } from 'date-fns';

interface SecurityOverviewProps {
    systemHealth: any;
    onRefresh: () => void;
}

interface SecurityEvent {
    id: string;
    event_type: string;
    severity: 'info' | 'warning' | 'error' | 'critical';
    description: string;
    user: {
        id: string;
        username: string;
        email: string;
        role: string;
    } | null;
    ip_address: string;
    user_agent: string;
    timestamp: string;
    metadata: any;
}

interface ThreatAnalysis {
    threat_level: 'low' | 'medium' | 'high' | 'critical';
    active_threats: number;
    blocked_attempts: number;
    suspicious_ips: string[];
    failed_login_patterns: {
        username: string;
        attempts: number;
        last_attempt: string;
        source_ips: string[];
    }[];
    policy_violations: {
        policy_name: string;
        violation_count: number;
        affected_users: number;
    }[];
    anomaly_detection: {
        unusual_login_times: number;
        new_locations: number;
        suspicious_user_agents: number;
    };
}

interface SecurityConfiguration {
    password_policy: {
        min_length: number;
        require_complexity: boolean;
        max_age_days: number;
    };
    session_policy: {
        max_concurrent_sessions: number;
        session_timeout_minutes: number;
        require_reauth_sensitive: boolean;
    };
    access_policy: {
        mfa_enabled: boolean;
        ip_whitelist_enabled: boolean;
        time_restrictions_enabled: boolean;
    };
    rate_limiting: {
        login_attempts_per_hour: number;
        api_requests_per_minute: number;
        failed_attempt_lockout_minutes: number;
    };
}

const SecurityOverview: React.FC<SecurityOverviewProps> = ({ 
    systemHealth, 
    onRefresh 
}) => {
    const [securityEvents, setSecurityEvents] = useState<SecurityEvent[]>([]);
    const [threatAnalysis, setThreatAnalysis] = useState<ThreatAnalysis | null>(null);
    const [securityConfig, setSecurityConfig] = useState<SecurityConfiguration | null>(null);
    const [loading, setLoading] = useState(false);
    const [showEventDetail, setShowEventDetail] = useState(false);
    const [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null);
    const [showThreatDetail, setShowThreatDetail] = useState(false);

    useEffect(() => {
        loadSecurityData();
        
        // Auto-refresh every 30 seconds
        const interval = setInterval(loadSecurityData, 30000);
        return () => clearInterval(interval);
    }, []);

    const loadSecurityData = async () => {
        setLoading(true);
        try {
            const [eventsResponse, analysisResponse, configResponse] = await Promise.all([
                fetch('/api/admin/security-events/?limit=50', {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
                }),
                fetch('/api/admin/threat-analysis/', {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
                }),
                fetch('/api/admin/security-configuration/', {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
                })
            ]);

            const [events, analysis, config] = await Promise.all([
                eventsResponse.ok ? eventsResponse.json() : { events: [] },
                analysisResponse.ok ? analysisResponse.json() : null,
                configResponse.ok ? configResponse.json() : null
            ]);

            setSecurityEvents(events.events || []);
            setThreatAnalysis(analysis);
            setSecurityConfig(config);
        } catch (err) {
            console.error('Failed to load security data:', err);
        } finally {
            setLoading(false);
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

    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case 'critical': return <Error color="error" />;
            case 'error': return <Error color="error" />;
            case 'warning': return <Warning color="warning" />;
            case 'info': return <CheckCircle color="info" />;
            default: return <Report />;
        }
    };

    const getThreatLevelColor = (level: string) => {
        switch (level) {
            case 'critical': return 'error';
            case 'high': return 'error';
            case 'medium': return 'warning';
            case 'low': return 'success';
            default: return 'default';
        }
    };

    const blockIP = async (ipAddress: string) => {
        try {
            const response = await fetch(`/api/admin/security/block-ip/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ ip_address: ipAddress }),
            });

            if (response.ok) {
                loadSecurityData();
            }
        } catch (err) {
            console.error('Failed to block IP:', err);
        }
    };

    const unblockIP = async (ipAddress: string) => {
        try {
            const response = await fetch(`/api/admin/security/unblock-ip/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ ip_address: ipAddress }),
            });

            if (response.ok) {
                loadSecurityData();
            }
        } catch (err) {
            console.error('Failed to unblock IP:', err);
        }
    };

    return (
        <Box>
            {/* Security Status Cards */}
            <Grid container spacing={3} sx={{ mb: 3 }}>
                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Shield color="primary" />
                                <Box>
                                    <Typography color="textSecondary" gutterBottom>
                                        Threat Level
                                    </Typography>
                                    <Chip
                                        label={threatAnalysis?.threat_level || 'unknown'}
                                        color={getThreatLevelColor(threatAnalysis?.threat_level || 'low') as any}
                                        variant="filled"
                                    />
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Block color="error" />
                                <Box>
                                    <Typography color="textSecondary" gutterBottom>
                                        Blocked Attempts
                                    </Typography>
                                    <Typography variant="h5" color="error">
                                        {threatAnalysis?.blocked_attempts || 0}
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
                                <Security color="warning" />
                                <Box>
                                    <Typography color="textSecondary" gutterBottom>
                                        Active Threats
                                    </Typography>
                                    <Typography variant="h5" color="warning">
                                        {threatAnalysis?.active_threats || 0}
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
                                <VpnKey color="success" />
                                <Box>
                                    <Typography color="textSecondary" gutterBottom>
                                        Active Policies
                                    </Typography>
                                    <Typography variant="h5">
                                        {systemHealth?.security?.active_policies || 0}
                                    </Typography>
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {loading && <LinearProgress sx={{ mb: 2 }} />}

            {/* Threat Analysis */}
            {threatAnalysis && (
                <Grid container spacing={3} sx={{ mb: 3 }}>
                    <Grid item xs={12} md={6}>
                        <Card>
                            <CardContent>
                                <Box sx={{ display: 'flex', justifyContent: 'between', alignItems: 'center', mb: 2 }}>
                                    <Typography variant="h6">Failed Login Patterns</Typography>
                                    <Button
                                        size="small"
                                        onClick={() => setShowThreatDetail(true)}
                                        startIcon={<Visibility />}
                                    >
                                        View Details
                                    </Button>
                                </Box>
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Username</TableCell>
                                                <TableCell>Attempts</TableCell>
                                                <TableCell>Last Attempt</TableCell>
                                                <TableCell>Actions</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {threatAnalysis.failed_login_patterns.slice(0, 5).map((pattern, index) => (
                                                <TableRow key={index}>
                                                    <TableCell>{pattern.username}</TableCell>
                                                    <TableCell>
                                                        <Chip
                                                            label={pattern.attempts}
                                                            color={pattern.attempts > 10 ? 'error' : 'warning'}
                                                            size="small"
                                                        />
                                                    </TableCell>
                                                    <TableCell>
                                                        {format(new Date(pattern.last_attempt), 'HH:mm:ss')}
                                                    </TableCell>
                                                    <TableCell>
                                                        <Tooltip title="Block IP">
                                                            <IconButton
                                                                size="small"
                                                                onClick={() => blockIP(pattern.source_ips[0])}
                                                            >
                                                                <Block fontSize="small" />
                                                            </IconButton>
                                                        </Tooltip>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </CardContent>
                        </Card>
                    </Grid>

                    <Grid item xs={12} md={6}>
                        <Card>
                            <CardContent>
                                <Typography variant="h6" gutterBottom>Anomaly Detection</Typography>
                                <List>
                                    <ListItem>
                                        <ListItemIcon>
                                            <AccessTime color={threatAnalysis.anomaly_detection.unusual_login_times > 0 ? 'warning' : 'success'} />
                                        </ListItemIcon>
                                        <ListItemText
                                            primary="Unusual Login Times"
                                            secondary={`${threatAnalysis.anomaly_detection.unusual_login_times} detected`}
                                        />
                                    </ListItem>
                                    <ListItem>
                                        <ListItemIcon>
                                            <LocationOn color={threatAnalysis.anomaly_detection.new_locations > 0 ? 'warning' : 'success'} />
                                        </ListItemIcon>
                                        <ListItemText
                                            primary="New Locations"
                                            secondary={`${threatAnalysis.anomaly_detection.new_locations} new locations`}
                                        />
                                    </ListItem>
                                    <ListItem>
                                        <ListItemIcon>
                                            <Computer color={threatAnalysis.anomaly_detection.suspicious_user_agents > 0 ? 'warning' : 'success'} />
                                        </ListItemIcon>
                                        <ListItemText
                                            primary="Suspicious User Agents"
                                            secondary={`${threatAnalysis.anomaly_detection.suspicious_user_agents} suspicious agents`}
                                        />
                                    </ListItem>
                                </List>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>
            )}

            {/* Security Configuration */}
            {securityConfig && (
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Typography variant="h6" gutterBottom>Security Configuration</Typography>
                        <Grid container spacing={2}>
                            <Grid item xs={12} md={6}>
                                <Accordion>
                                    <AccordionSummary expandIcon={<ExpandMore />}>
                                        <Typography>Password Policy</Typography>
                                    </AccordionSummary>
                                    <AccordionDetails>
                                        <List dense>
                                            <ListItem>
                                                <ListItemText
                                                    primary="Minimum Length"
                                                    secondary={`${securityConfig.password_policy.min_length} characters`}
                                                />
                                            </ListItem>
                                            <ListItem>
                                                <ListItemText
                                                    primary="Complexity Required"
                                                    secondary={securityConfig.password_policy.require_complexity ? 'Yes' : 'No'}
                                                />
                                            </ListItem>
                                            <ListItem>
                                                <ListItemText
                                                    primary="Password Expiry"
                                                    secondary={`${securityConfig.password_policy.max_age_days} days`}
                                                />
                                            </ListItem>
                                        </List>
                                    </AccordionDetails>
                                </Accordion>
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <Accordion>
                                    <AccordionSummary expandIcon={<ExpandMore />}>
                                        <Typography>Access Controls</Typography>
                                    </AccordionSummary>
                                    <AccordionDetails>
                                        <List dense>
                                            <ListItem>
                                                <ListItemIcon>
                                                    {securityConfig.access_policy.mfa_enabled ? 
                                                        <CheckCircle color="success" /> : 
                                                        <Cancel color="error" />
                                                    }
                                                </ListItemIcon>
                                                <ListItemText
                                                    primary="Multi-Factor Authentication"
                                                    secondary={securityConfig.access_policy.mfa_enabled ? 'Enabled' : 'Disabled'}
                                                />
                                            </ListItem>
                                            <ListItem>
                                                <ListItemIcon>
                                                    {securityConfig.access_policy.ip_whitelist_enabled ? 
                                                        <CheckCircle color="success" /> : 
                                                        <Cancel color="error" />
                                                    }
                                                </ListItemIcon>
                                                <ListItemText
                                                    primary="IP Whitelisting"
                                                    secondary={securityConfig.access_policy.ip_whitelist_enabled ? 'Enabled' : 'Disabled'}
                                                />
                                            </ListItem>
                                            <ListItem>
                                                <ListItemIcon>
                                                    {securityConfig.access_policy.time_restrictions_enabled ? 
                                                        <CheckCircle color="success" /> : 
                                                        <Cancel color="error" />
                                                    }
                                                </ListItemIcon>
                                                <ListItemText
                                                    primary="Time Restrictions"
                                                    secondary={securityConfig.access_policy.time_restrictions_enabled ? 'Enabled' : 'Disabled'}
                                                />
                                            </ListItem>
                                        </List>
                                    </AccordionDetails>
                                </Accordion>
                            </Grid>
                        </Grid>
                    </CardContent>
                </Card>
            )}

            {/* Recent Security Events */}
            <Card>
                <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6">Recent Security Events</Typography>
                        <Tooltip title="Refresh Events">
                            <IconButton onClick={loadSecurityData}>
                                <Refresh />
                            </IconButton>
                        </Tooltip>
                    </Box>
                    <TableContainer>
                        <Table>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Severity</TableCell>
                                    <TableCell>Event Type</TableCell>
                                    <TableCell>User</TableCell>
                                    <TableCell>IP Address</TableCell>
                                    <TableCell>Time</TableCell>
                                    <TableCell>Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {securityEvents.slice(0, 10).map((event) => (
                                    <TableRow key={event.id}>
                                        <TableCell>
                                            <Chip
                                                icon={getSeverityIcon(event.severity)}
                                                label={event.severity}
                                                color={getSeverityColor(event.severity) as any}
                                                size="small"
                                            />
                                        </TableCell>
                                        <TableCell>{event.event_type.replace('_', ' ')}</TableCell>
                                        <TableCell>
                                            {event.user ? (
                                                <Box>
                                                    <Typography variant="body2">
                                                        {event.user.username}
                                                    </Typography>
                                                    <Typography variant="caption" color="textSecondary">
                                                        {event.user.role}
                                                    </Typography>
                                                </Box>
                                            ) : (
                                                'System'
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" fontFamily="monospace">
                                                {event.ip_address}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            {format(new Date(event.timestamp), 'MMM dd, HH:mm:ss')}
                                        </TableCell>
                                        <TableCell>
                                            <Tooltip title="View Details">
                                                <IconButton
                                                    size="small"
                                                    onClick={() => {
                                                        setSelectedEvent(event);
                                                        setShowEventDetail(true);
                                                    }}
                                                >
                                                    <Visibility fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                            {event.severity !== 'info' && (
                                                <Tooltip title="Block IP">
                                                    <IconButton
                                                        size="small"
                                                        color="error"
                                                        onClick={() => blockIP(event.ip_address)}
                                                    >
                                                        <Block fontSize="small" />
                                                    </IconButton>
                                                </Tooltip>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </CardContent>
            </Card>

            {/* Event Detail Dialog */}
            <Dialog
                open={showEventDetail}
                onClose={() => setShowEventDetail(false)}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle>Security Event Details</DialogTitle>
                <DialogContent>
                    {selectedEvent && (
                        <Grid container spacing={2}>
                            <Grid item xs={12} md={6}>
                                <Typography variant="h6" gutterBottom>Event Information</Typography>
                                <Typography><strong>Type:</strong> {selectedEvent.event_type}</Typography>
                                <Typography><strong>Severity:</strong> {selectedEvent.severity}</Typography>
                                <Typography><strong>Description:</strong> {selectedEvent.description}</Typography>
                                <Typography><strong>Time:</strong> {format(new Date(selectedEvent.timestamp), 'yyyy-MM-dd HH:mm:ss')}</Typography>
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <Typography variant="h6" gutterBottom>Source Information</Typography>
                                <Typography><strong>IP Address:</strong> {selectedEvent.ip_address}</Typography>
                                <Typography><strong>User Agent:</strong> {selectedEvent.user_agent}</Typography>
                                {selectedEvent.user && (
                                    <>
                                        <Typography><strong>User:</strong> {selectedEvent.user.username}</Typography>
                                        <Typography><strong>Role:</strong> {selectedEvent.user.role}</Typography>
                                    </>
                                )}
                            </Grid>
                            {selectedEvent.metadata && Object.keys(selectedEvent.metadata).length > 0 && (
                                <Grid item xs={12}>
                                    <Typography variant="h6" gutterBottom>Additional Details</Typography>
                                    <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                                        <pre style={{ margin: 0, fontSize: '0.875rem' }}>
                                            {JSON.stringify(selectedEvent.metadata, null, 2)}
                                        </pre>
                                    </Paper>
                                </Grid>
                            )}
                        </Grid>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowEventDetail(false)}>Close</Button>
                    {selectedEvent && (
                        <Button
                            color="error"
                            onClick={() => {
                                blockIP(selectedEvent.ip_address);
                                setShowEventDetail(false);
                            }}
                        >
                            Block IP
                        </Button>
                    )}
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default SecurityOverview;