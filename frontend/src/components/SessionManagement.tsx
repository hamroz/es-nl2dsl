import React, { useState, useEffect } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Button,
    Chip,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Grid,
    Alert,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Paper,
    LinearProgress,
    Tooltip,
    IconButton,
    Switch,
    FormControlLabel,
} from '@mui/material';
import {
    Computer,
    LocationOn,
    Security,
    Warning,
    Logout,
    Visibility,
    Refresh,
    FilterList,
    Download,
    Block,
    CheckCircle,
    ErrorOutline,
    Info,
} from '@mui/icons-material';
import { format } from 'date-fns';

interface UserSession {
    id: string;
    session_id: string;
    user: {
        id: string;
        username: string;
        email: string;
        role: string;
    };
    ip_address: string;
    user_agent: string;
    browser: string;
    os: string;
    device: string;
    location_country: string;
    location_city: string;
    security_level: 'low' | 'medium' | 'high' | 'critical';
    risk_score: number;
    is_suspicious: boolean;
    request_count: number;
    created_at: string;
    last_activity: string;
    expires_at: string;
    is_terminated: boolean;
    terminated_at?: string;
    termination_reason?: string;
    session_duration?: string;
}

interface SessionAnalytics {
    total_sessions: number;
    active_sessions: number;
    suspicious_sessions: number;
    avg_session_duration: string;
    top_locations: Array<{ location: string; count: number }>;
    device_breakdown: Record<string, number>;
    security_level_distribution: Record<string, number>;
    termination_reasons: Record<string, number>;
}

interface SecurityPolicy {
    id: string;
    name: string;
    description: string;
    policy_type: string;
    user_role: string;
    priority: number;
    policy_config: any;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

const SessionManagement: React.FC = () => {
    const [sessions, setSessions] = useState<UserSession[]>([]);
    const [analytics, setAnalytics] = useState<SessionAnalytics | null>(null);
    const [policies, setPolicies] = useState<SecurityPolicy[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedSession, setSelectedSession] = useState<UserSession | null>(null);
    const [showTerminateDialog, setShowTerminateDialog] = useState(false);
    const [showSessionDetail, setShowSessionDetail] = useState(false);
    const [showPolicies, setShowPolicies] = useState(false);
    
    // Filters
    const [filters, setFilters] = useState({
        user_role: '',
        security_level: '',
        is_suspicious: false,
        show_terminated: false,
    });

    useEffect(() => {
        loadSessions();
        loadAnalytics();
        loadPolicies();
        
        // Auto-refresh every 30 seconds
        const interval = setInterval(() => {
            loadSessions();
            loadAnalytics();
        }, 30000);
        
        return () => clearInterval(interval);
    }, [filters]);

    const loadSessions = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (filters.user_role) params.append('role', filters.user_role);
            if (filters.security_level) params.append('security_level', filters.security_level);
            if (filters.is_suspicious) params.append('suspicious_only', 'true');
            if (filters.show_terminated) params.append('include_terminated', 'true');

            const response = await fetch(`/api/v1/auth/sessions/?${params}`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}` }
            });
            
            if (response.ok) {
                const data = await response.json();
                setSessions(data.sessions || []);
            } else {
                setError('Failed to load sessions');
            }
        } catch (err) {
            setError('Network error loading sessions');
        } finally {
            setLoading(false);
        }
    };

    const loadAnalytics = async () => {
        try {
            const response = await fetch('/api/v1/auth/session-analytics/', {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}` }
            });
            
            if (response.ok) {
                const data = await response.json();
                setAnalytics(data);
            }
        } catch (err) {
            console.error('Failed to load analytics:', err);
        }
    };

    const loadPolicies = async () => {
        try {
            const response = await fetch('/api/v1/auth/security-policies/', {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}` }
            });
            
            if (response.ok) {
                const data = await response.json();
                setPolicies(data.policies || []);
            }
        } catch (err) {
            console.error('Failed to load policies:', err);
        }
    };

    const terminateSession = async (sessionId: string, reason: string) => {
        try {
            const response = await fetch(`/api/v1/auth/sessions/${sessionId}/terminate/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ reason }),
            });

            if (response.ok) {
                setShowTerminateDialog(false);
                setSelectedSession(null);
                loadSessions();
            } else {
                setError('Failed to terminate session');
            }
        } catch (err) {
            setError('Network error terminating session');
        }
    };

    const terminateAllUserSessions = async (userId: string) => {
        try {
            const response = await fetch(`/api/v1/auth/users/${userId}/terminate-sessions/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ reason: 'admin_action' }),
            });

            if (response.ok) {
                loadSessions();
            } else {
                setError('Failed to terminate user sessions');
            }
        } catch (err) {
            setError('Network error terminating sessions');
        }
    };

    const togglePolicyStatus = async (policyId: string, isActive: boolean) => {
        try {
            const response = await fetch(`/api/v1/auth/security-policies/${policyId}/`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('es_nl2dsl_access_token')}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ is_active: isActive }),
            });

            if (response.ok) {
                loadPolicies();
            } else {
                setError('Failed to update policy');
            }
        } catch (err) {
            setError('Network error updating policy');
        }
    };

    const getSecurityLevelColor = (level: string) => {
        switch (level) {
            case 'low': return 'success';
            case 'medium': return 'warning';
            case 'high': return 'error';
            case 'critical': return 'error';
            default: return 'default';
        }
    };

    const getSecurityLevelIcon = (level: string) => {
        switch (level) {
            case 'low': return <CheckCircle fontSize="small" />;
            case 'medium': return <Info fontSize="small" />;
            case 'high': return <Warning fontSize="small" />;
            case 'critical': return <ErrorOutline fontSize="small" />;
            default: return <Security fontSize="small" />;
        }
    };

    const formatDuration = (duration: string) => {
        if (!duration) return 'N/A';
        return duration.replace(/\d+:\d+:\d+\.\d+/, (match) => {
            const [hours, minutes] = match.split(':');
            return `${hours}h ${minutes}m`;
        });
    };

    const exportSessions = () => {
        const csvData = sessions.map(session => ({
            user: session.user.username,
            email: session.user.email,
            role: session.user.role,
            ip_address: session.ip_address,
            location: `${session.location_city || 'Unknown'}, ${session.location_country || 'Unknown'}`,
            device: `${session.browser} on ${session.os}`,
            security_level: session.security_level,
            risk_score: session.risk_score,
            is_suspicious: session.is_suspicious ? 'Yes' : 'No',
            created_at: format(new Date(session.created_at), 'yyyy-MM-dd HH:mm:ss'),
            last_activity: session.last_activity ? format(new Date(session.last_activity), 'yyyy-MM-dd HH:mm:ss') : 'N/A',
            is_terminated: session.is_terminated ? 'Yes' : 'No',
            termination_reason: session.termination_reason || 'N/A'
        }));

        const csv = [
            Object.keys(csvData[0] || {}).join(','),
            ...csvData.map(row => Object.values(row).join(','))
        ].join('\n');

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sessions_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <Box sx={{ p: 3 }}>
            <Typography variant="h4" gutterBottom>
                Session Management & Security Policies
            </Typography>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {/* Analytics Cards */}
            {analytics && (
                <Grid container spacing={3} sx={{ mb: 3 }}>
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom>
                                    Total Sessions
                                </Typography>
                                <Typography variant="h5">
                                    {analytics.total_sessions}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom>
                                    Active Sessions
                                </Typography>
                                <Typography variant="h5" color="primary">
                                    {analytics.active_sessions}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom>
                                    Suspicious Sessions
                                </Typography>
                                <Typography variant="h5" color="error">
                                    {analytics.suspicious_sessions}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom>
                                    Avg Duration
                                </Typography>
                                <Typography variant="h5">
                                    {formatDuration(analytics.avg_session_duration)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>
            )}

            {/* Action Buttons */}
            <Box sx={{ mb: 3, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                <Button
                    startIcon={<Refresh />}
                    onClick={loadSessions}
                    disabled={loading}
                >
                    Refresh
                </Button>
                <Button
                    startIcon={<Download />}
                    onClick={exportSessions}
                    variant="outlined"
                >
                    Export CSV
                </Button>
                <Button
                    startIcon={<Security />}
                    onClick={() => setShowPolicies(!showPolicies)}
                    variant="outlined"
                >
                    {showPolicies ? 'Hide' : 'Show'} Policies
                </Button>
                
                {/* Filters */}
                <FormControl size="small" sx={{ minWidth: 120 }}>
                    <InputLabel>Role</InputLabel>
                    <Select
                        value={filters.user_role}
                        onChange={(e) => setFilters(prev => ({ ...prev, user_role: e.target.value }))}
                        label="Role"
                    >
                        <MenuItem value="">All Roles</MenuItem>
                        <MenuItem value="admin">Admin</MenuItem>
                        <MenuItem value="analyst">Analyst</MenuItem>
                        <MenuItem value="viewer">Viewer</MenuItem>
                    </Select>
                </FormControl>
                
                <FormControl size="small" sx={{ minWidth: 120 }}>
                    <InputLabel>Security Level</InputLabel>
                    <Select
                        value={filters.security_level}
                        onChange={(e) => setFilters(prev => ({ ...prev, security_level: e.target.value }))}
                        label="Security Level"
                    >
                        <MenuItem value="">All Levels</MenuItem>
                        <MenuItem value="low">Low</MenuItem>
                        <MenuItem value="medium">Medium</MenuItem>
                        <MenuItem value="high">High</MenuItem>
                        <MenuItem value="critical">Critical</MenuItem>
                    </Select>
                </FormControl>
                
                <FormControlLabel
                    control={
                        <Switch
                            checked={filters.is_suspicious}
                            onChange={(e) => setFilters(prev => ({ ...prev, is_suspicious: e.target.checked }))}
                        />
                    }
                    label="Suspicious Only"
                />
                
                <FormControlLabel
                    control={
                        <Switch
                            checked={filters.show_terminated}
                            onChange={(e) => setFilters(prev => ({ ...prev, show_terminated: e.target.checked }))}
                        />
                    }
                    label="Include Terminated"
                />
            </Box>

            {loading && <LinearProgress sx={{ mb: 2 }} />}

            {/* Security Policies Panel */}
            {showPolicies && (
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Typography variant="h6" gutterBottom>
                            Security Policies
                        </Typography>
                        <TableContainer>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Name</TableCell>
                                        <TableCell>Type</TableCell>
                                        <TableCell>Role</TableCell>
                                        <TableCell>Priority</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell>Actions</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {policies.map((policy) => (
                                        <TableRow key={policy.id}>
                                            <TableCell>
                                                <Typography variant="subtitle2">
                                                    {policy.name}
                                                </Typography>
                                                <Typography variant="caption" color="textSecondary">
                                                    {policy.description}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={policy.policy_type}
                                                    size="small"
                                                    variant="outlined"
                                                />
                                            </TableCell>
                                            <TableCell>{policy.user_role}</TableCell>
                                            <TableCell>{policy.priority}</TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={policy.is_active ? 'Active' : 'Inactive'}
                                                    color={policy.is_active ? 'success' : 'default'}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Switch
                                                    checked={policy.is_active}
                                                    onChange={(e) => togglePolicyStatus(policy.id, e.target.checked)}
                                                    size="small"
                                                />
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </CardContent>
                </Card>
            )}

            {/* Sessions Table */}
            <Card>
                <CardContent>
                    <Typography variant="h6" gutterBottom>
                        Active Sessions ({sessions.length})
                    </Typography>
                    <TableContainer>
                        <Table>
                            <TableHead>
                                <TableRow>
                                    <TableCell>User</TableCell>
                                    <TableCell>Location & Device</TableCell>
                                    <TableCell>Security</TableCell>
                                    <TableCell>Activity</TableCell>
                                    <TableCell>Duration</TableCell>
                                    <TableCell>Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {sessions.map((session) => (
                                    <TableRow key={session.id}>
                                        <TableCell>
                                            <Box>
                                                <Typography variant="subtitle2">
                                                    {session.user.username}
                                                </Typography>
                                                <Typography variant="caption" color="textSecondary">
                                                    {session.user.email}
                                                </Typography>
                                                <br />
                                                <Chip
                                                    label={session.user.role}
                                                    size="small"
                                                    variant="outlined"
                                                />
                                            </Box>
                                        </TableCell>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                <LocationOn fontSize="small" color="action" />
                                                <Box>
                                                    <Typography variant="body2">
                                                        {session.location_city || 'Unknown'}, {session.location_country || 'XX'}
                                                    </Typography>
                                                    <Typography variant="caption" color="textSecondary">
                                                        {session.ip_address}
                                                    </Typography>
                                                </Box>
                                            </Box>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                                                <Computer fontSize="small" color="action" />
                                                <Typography variant="caption">
                                                    {session.browser} on {session.os}
                                                </Typography>
                                            </Box>
                                        </TableCell>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                <Chip
                                                    icon={getSecurityLevelIcon(session.security_level)}
                                                    label={session.security_level}
                                                    color={getSecurityLevelColor(session.security_level) as any}
                                                    size="small"
                                                />
                                                {session.is_suspicious && (
                                                    <Chip
                                                        label="Suspicious"
                                                        color="error"
                                                        size="small"
                                                        variant="outlined"
                                                    />
                                                )}
                                            </Box>
                                            <Typography variant="caption" color="textSecondary">
                                                Risk: {(session.risk_score * 100).toFixed(0)}%
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2">
                                                {session.request_count} requests
                                            </Typography>
                                            <Typography variant="caption" color="textSecondary">
                                                Last: {session.last_activity 
                                                    ? format(new Date(session.last_activity), 'HH:mm:ss')
                                                    : 'Never'
                                                }
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2">
                                                {formatDuration(session.session_duration || '')}
                                            </Typography>
                                            <Typography variant="caption" color="textSecondary">
                                                Started: {format(new Date(session.created_at), 'HH:mm')}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', gap: 0.5 }}>
                                                <Tooltip title="View Details">
                                                    <IconButton
                                                        size="small"
                                                        onClick={() => {
                                                            setSelectedSession(session);
                                                            setShowSessionDetail(true);
                                                        }}
                                                    >
                                                        <Visibility fontSize="small" />
                                                    </IconButton>
                                                </Tooltip>
                                                {!session.is_terminated && (
                                                    <Tooltip title="Terminate Session">
                                                        <IconButton
                                                            size="small"
                                                            color="error"
                                                            onClick={() => {
                                                                setSelectedSession(session);
                                                                setShowTerminateDialog(true);
                                                            }}
                                                        >
                                                            <Block fontSize="small" />
                                                        </IconButton>
                                                    </Tooltip>
                                                )}
                                                <Tooltip title="Terminate All User Sessions">
                                                    <IconButton
                                                        size="small"
                                                        color="warning"
                                                        onClick={() => terminateAllUserSessions(session.user.id)}
                                                    >
                                                        <Logout fontSize="small" />
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

            {/* Terminate Session Dialog */}
            <Dialog
                open={showTerminateDialog}
                onClose={() => setShowTerminateDialog(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle>Terminate Session</DialogTitle>
                <DialogContent>
                    <Typography paragraph>
                        Are you sure you want to terminate this session for {selectedSession?.user.username}?
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                        This will immediately log out the user and invalidate their authentication token.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowTerminateDialog(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={() => selectedSession && terminateSession(selectedSession.session_id, 'admin_terminated')}
                        color="error"
                        variant="contained"
                    >
                        Terminate Session
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Session Detail Dialog */}
            <Dialog
                open={showSessionDetail}
                onClose={() => setShowSessionDetail(false)}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle>Session Details</DialogTitle>
                <DialogContent>
                    {selectedSession && (
                        <Grid container spacing={2}>
                            <Grid item xs={12} md={6}>
                                <Typography variant="h6" gutterBottom>User Information</Typography>
                                <Typography><strong>Username:</strong> {selectedSession.user.username}</Typography>
                                <Typography><strong>Email:</strong> {selectedSession.user.email}</Typography>
                                <Typography><strong>Role:</strong> {selectedSession.user.role}</Typography>
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <Typography variant="h6" gutterBottom>Session Information</Typography>
                                <Typography><strong>Session ID:</strong> {selectedSession.session_id}</Typography>
                                <Typography><strong>Created:</strong> {format(new Date(selectedSession.created_at), 'yyyy-MM-dd HH:mm:ss')}</Typography>
                                <Typography><strong>Last Activity:</strong> {selectedSession.last_activity ? format(new Date(selectedSession.last_activity), 'yyyy-MM-dd HH:mm:ss') : 'Never'}</Typography>
                                <Typography><strong>Expires:</strong> {format(new Date(selectedSession.expires_at), 'yyyy-MM-dd HH:mm:ss')}</Typography>
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <Typography variant="h6" gutterBottom>Location & Device</Typography>
                                <Typography><strong>IP Address:</strong> {selectedSession.ip_address}</Typography>
                                <Typography><strong>Location:</strong> {selectedSession.location_city || 'Unknown'}, {selectedSession.location_country || 'Unknown'}</Typography>
                                <Typography><strong>Browser:</strong> {selectedSession.browser}</Typography>
                                <Typography><strong>OS:</strong> {selectedSession.os}</Typography>
                                <Typography><strong>Device:</strong> {selectedSession.device}</Typography>
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <Typography variant="h6" gutterBottom>Security Analysis</Typography>
                                <Typography><strong>Security Level:</strong> {selectedSession.security_level}</Typography>
                                <Typography><strong>Risk Score:</strong> {(selectedSession.risk_score * 100).toFixed(1)}%</Typography>
                                <Typography><strong>Suspicious:</strong> {selectedSession.is_suspicious ? 'Yes' : 'No'}</Typography>
                                <Typography><strong>Request Count:</strong> {selectedSession.request_count}</Typography>
                            </Grid>
                        </Grid>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowSessionDetail(false)}>Close</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default SessionManagement;