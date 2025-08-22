import React, { useState, useEffect } from 'react';
import { 
  Building2, Plus, Users, Database, Settings, 
  Shield, Globe, Search, Filter, MoreVertical,
  Edit3, Trash2, UserCheck, Activity, Clock,
  AlertTriangle, CheckCircle, RefreshCw
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

interface Tenant {
  id: string;
  name: string;
  description: string;
  created_at: string;
  is_active: boolean;
  user_count: number;
  data_size_gb: number;
  last_activity?: string;
  settings: {
    max_users: number;
    max_storage_gb: number;
    features: string[];
    elasticsearch_indices: string[];
  };
}

interface Workspace {
  id: string;
  name: string;
  description: string;
  tenant_id: string;
  created_by: string;
  created_at: string;
  is_active: boolean;
  member_count: number;
  query_count: number;
  settings: {
    default_index: string;
    allowed_indices: string[];
    permissions: string[];
  };
}

interface TenantFormData {
  name: string;
  description: string;
  max_users: number;
  max_storage_gb: number;
  features: string[];
  elasticsearch_indices: string[];
}

interface WorkspaceFormData {
  name: string;
  description: string;
  default_index: string;
  allowed_indices: string[];
  permissions: string[];
}

const TenantManagement: React.FC = () => {
  const { user, permissions } = useAuth();
  const [activeTab, setActiveTab] = useState<'tenants' | 'workspaces'>('tenants');
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showTenantModal, setShowTenantModal] = useState(false);
  const [showWorkspaceModal, setShowWorkspaceModal] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');

  const [tenantFormData, setTenantFormData] = useState<TenantFormData>({
    name: '',
    description: '',
    max_users: 50,
    max_storage_gb: 100,
    features: ['query_generation', 'data_export', 'security_testing'],
    elasticsearch_indices: []
  });

  const [workspaceFormData, setWorkspaceFormData] = useState<WorkspaceFormData>({
    name: '',
    description: '',
    default_index: 'logs_net',
    allowed_indices: ['logs_net'],
    permissions: ['query_execute']
  });

  const availableFeatures = [
    'query_generation', 'data_export', 'security_testing', 
    'evaluation', 'privacy_analysis', 'advanced_analytics'
  ];

  const availablePermissions = [
    'query_execute', 'query_modify', 'data_export', 
    'workspace_admin', 'user_invite'
  ];

  useEffect(() => {
    if (permissions?.can_admin_users) {
      fetchTenants();
      fetchWorkspaces();
    }
  }, [permissions]);

  const fetchTenants = async () => {
    try {
      setLoading(true);
      const response = await api.get('/auth/tenants/');
      setTenants(response.data.results || response.data);
      setError('');
    } catch (err: any) {
      setError('Failed to fetch tenants: ' + (err.response?.data?.message || err.message));
    } finally {
      setLoading(false);
    }
  };

  const fetchWorkspaces = async () => {
    try {
      const response = await api.get('/auth/workspaces/');
      setWorkspaces(response.data.results || response.data);
    } catch (err: any) {
      setError('Failed to fetch workspaces: ' + (err.response?.data?.message || err.message));
    }
  };

  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/auth/tenants/', tenantFormData);
      setSuccess('Tenant created successfully');
      setShowTenantModal(false);
      setTenantFormData({
        name: '',
        description: '',
        max_users: 50,
        max_storage_gb: 100,
        features: ['query_generation', 'data_export'],
        elasticsearch_indices: []
      });
      fetchTenants();
    } catch (err: any) {
      setError('Failed to create tenant: ' + (err.response?.data?.message || err.message));
    }
  };

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/auth/workspaces/', {
        ...workspaceFormData,
        tenant_id: user?.tenant_id
      });
      setSuccess('Workspace created successfully');
      setShowWorkspaceModal(false);
      setWorkspaceFormData({
        name: '',
        description: '',
        default_index: 'logs_net',
        allowed_indices: ['logs_net'],
        permissions: ['query_execute']
      });
      fetchWorkspaces();
    } catch (err: any) {
      setError('Failed to create workspace: ' + (err.response?.data?.message || err.message));
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatBytes = (gb: number) => {
    return `${gb.toFixed(1)} GB`;
  };

  const filteredTenants = tenants.filter(tenant =>
    tenant.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    tenant.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredWorkspaces = workspaces.filter(workspace =>
    workspace.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    workspace.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (!permissions?.can_admin_users) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Shield className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600">You don't have permission to manage tenants and workspaces.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Multi-Tenant Management</h1>
          <p className="text-gray-600">Manage tenants, workspaces, and data isolation</p>
        </div>
        <div className="flex space-x-3">
          {activeTab === 'tenants' && (
            <button
              onClick={() => setShowTenantModal(true)}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center space-x-2"
            >
              <Plus className="w-4 h-4" />
              <span>New Tenant</span>
            </button>
          )}
          {activeTab === 'workspaces' && (
            <button
              onClick={() => setShowWorkspaceModal(true)}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg flex items-center space-x-2"
            >
              <Plus className="w-4 h-4" />
              <span>New Workspace</span>
            </button>
          )}
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg flex items-center">
          <AlertTriangle className="w-5 h-5 mr-2" />
          {error}
          <button onClick={() => setError('')} className="ml-auto text-red-500 hover:text-red-700">×</button>
        </div>
      )}

      {success && (
        <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded-lg flex items-center">
          <CheckCircle className="w-5 h-5 mr-2" />
          {success}
          <button onClick={() => setSuccess('')} className="ml-auto text-green-500 hover:text-green-700">×</button>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          <button
            onClick={() => setActiveTab('tenants')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'tenants'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center space-x-2">
              <Building2 className="w-4 h-4" />
              <span>Tenants ({tenants.length})</span>
            </div>
          </button>
          <button
            onClick={() => setActiveTab('workspaces')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'workspaces'
                ? 'border-green-500 text-green-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center space-x-2">
              <Globe className="w-4 h-4" />
              <span>Workspaces ({workspaces.length})</span>
            </div>
          </button>
        </nav>
      </div>

      {/* Search */}
      <div className="bg-white p-4 rounded-lg border border-gray-200 flex items-center justify-between">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder={`Search ${activeTab}...`}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10 pr-4 py-2 w-full border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <button
          onClick={activeTab === 'tenants' ? fetchTenants : fetchWorkspaces}
          disabled={loading}
          className="flex items-center space-x-2 px-4 py-2 text-gray-600 hover:text-gray-800"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Content */}
      {activeTab === 'tenants' ? (
        /* Tenants View */
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {loading ? (
            <div className="col-span-full text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-500">Loading tenants...</p>
            </div>
          ) : filteredTenants.length === 0 ? (
            <div className="col-span-full text-center py-8">
              <Building2 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500">No tenants found</p>
            </div>
          ) : (
            filteredTenants.map((tenant) => (
              <div key={tenant.id} className="bg-white rounded-lg border border-gray-200 p-6">
                <div className="flex justify-between items-start mb-4">
                  <div className="flex items-center space-x-3">
                    <div className="bg-blue-100 rounded-lg p-2">
                      <Building2 className="h-6 w-6 text-blue-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900">{tenant.name}</h3>
                      <p className="text-sm text-gray-500">{tenant.description}</p>
                    </div>
                  </div>
                  <div className="relative">
                    <button className="p-1 hover:bg-gray-100 rounded">
                      <MoreVertical className="h-4 w-4 text-gray-400" />
                    </button>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Status</span>
                    <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      tenant.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {tenant.is_active ? 'Active' : 'Inactive'}
                    </div>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Users</span>
                    <div className="flex items-center space-x-1">
                      <Users className="h-4 w-4 text-gray-400" />
                      <span className="text-sm font-medium">{tenant.user_count}/{tenant.settings.max_users}</span>
                    </div>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Storage</span>
                    <div className="flex items-center space-x-1">
                      <Database className="h-4 w-4 text-gray-400" />
                      <span className="text-sm font-medium">
                        {formatBytes(tenant.data_size_gb)}/{formatBytes(tenant.settings.max_storage_gb)}
                      </span>
                    </div>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Features</span>
                    <span className="text-sm font-medium">{tenant.settings.features.length}</span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Created</span>
                    <span className="text-xs text-gray-500">{formatDate(tenant.created_at)}</span>
                  </div>

                  {tenant.last_activity && (
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600">Last Activity</span>
                      <div className="flex items-center space-x-1">
                        <Clock className="h-3 w-3 text-gray-400" />
                        <span className="text-xs text-gray-500">{formatDate(tenant.last_activity)}</span>
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-4 pt-4 border-t border-gray-200">
                  <div className="flex space-x-2">
                    <button className="flex-1 bg-blue-50 hover:bg-blue-100 text-blue-700 px-3 py-2 rounded text-sm font-medium">
                      <Edit3 className="h-4 w-4 inline mr-1" />
                      Edit
                    </button>
                    <button className="flex-1 bg-gray-50 hover:bg-gray-100 text-gray-700 px-3 py-2 rounded text-sm font-medium">
                      <Users className="h-4 w-4 inline mr-1" />
                      Users
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        /* Workspaces View */
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {loading ? (
            <div className="col-span-full text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600 mx-auto mb-4"></div>
              <p className="text-gray-500">Loading workspaces...</p>
            </div>
          ) : filteredWorkspaces.length === 0 ? (
            <div className="col-span-full text-center py-8">
              <Globe className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500">No workspaces found</p>
            </div>
          ) : (
            filteredWorkspaces.map((workspace) => (
              <div key={workspace.id} className="bg-white rounded-lg border border-gray-200 p-6">
                <div className="flex justify-between items-start mb-4">
                  <div className="flex items-center space-x-3">
                    <div className="bg-green-100 rounded-lg p-2">
                      <Globe className="h-6 w-6 text-green-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900">{workspace.name}</h3>
                      <p className="text-sm text-gray-500">{workspace.description}</p>
                    </div>
                  </div>
                  <div className="relative">
                    <button className="p-1 hover:bg-gray-100 rounded">
                      <MoreVertical className="h-4 w-4 text-gray-400" />
                    </button>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Status</span>
                    <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      workspace.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {workspace.is_active ? 'Active' : 'Inactive'}
                    </div>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Members</span>
                    <div className="flex items-center space-x-1">
                      <UserCheck className="h-4 w-4 text-gray-400" />
                      <span className="text-sm font-medium">{workspace.member_count}</span>
                    </div>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Queries</span>
                    <div className="flex items-center space-x-1">
                      <Activity className="h-4 w-4 text-gray-400" />
                      <span className="text-sm font-medium">{workspace.query_count}</span>
                    </div>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Default Index</span>
                    <span className="text-sm font-medium font-mono text-gray-700">
                      {workspace.settings.default_index}
                    </span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Permissions</span>
                    <span className="text-sm font-medium">{workspace.settings.permissions.length}</span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Created</span>
                    <span className="text-xs text-gray-500">{formatDate(workspace.created_at)}</span>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-gray-200">
                  <div className="flex space-x-2">
                    <button className="flex-1 bg-green-50 hover:bg-green-100 text-green-700 px-3 py-2 rounded text-sm font-medium">
                      <Edit3 className="h-4 w-4 inline mr-1" />
                      Edit
                    </button>
                    <button className="flex-1 bg-gray-50 hover:bg-gray-100 text-gray-700 px-3 py-2 rounded text-sm font-medium">
                      <Settings className="h-4 w-4 inline mr-1" />
                      Settings
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Create Tenant Modal */}
      {showTenantModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md max-h-[80vh] overflow-y-auto">
            <h2 className="text-lg font-semibold mb-4">Create New Tenant</h2>
            <form onSubmit={handleCreateTenant}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                  <input
                    type="text"
                    required
                    value={tenantFormData.name}
                    onChange={(e) => setTenantFormData({...tenantFormData, name: e.target.value})}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                  <textarea
                    value={tenantFormData.description}
                    onChange={(e) => setTenantFormData({...tenantFormData, description: e.target.value})}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
                    rows={3}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Max Users</label>
                    <input
                      type="number"
                      min="1"
                      required
                      value={tenantFormData.max_users}
                      onChange={(e) => setTenantFormData({...tenantFormData, max_users: parseInt(e.target.value)})}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Max Storage (GB)</label>
                    <input
                      type="number"
                      min="1"
                      required
                      value={tenantFormData.max_storage_gb}
                      onChange={(e) => setTenantFormData({...tenantFormData, max_storage_gb: parseInt(e.target.value)})}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Features</label>
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {availableFeatures.map((feature) => (
                      <label key={feature} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={tenantFormData.features.includes(feature)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setTenantFormData({
                                ...tenantFormData,
                                features: [...tenantFormData.features, feature]
                              });
                            } else {
                              setTenantFormData({
                                ...tenantFormData,
                                features: tenantFormData.features.filter(f => f !== feature)
                              });
                            }
                          }}
                          className="rounded"
                        />
                        <span className="text-sm text-gray-700">{feature.replace('_', ' ')}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowTenantModal(false)}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg"
                >
                  Create Tenant
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Workspace Modal */}
      {showWorkspaceModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md max-h-[80vh] overflow-y-auto">
            <h2 className="text-lg font-semibold mb-4">Create New Workspace</h2>
            <form onSubmit={handleCreateWorkspace}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                  <input
                    type="text"
                    required
                    value={workspaceFormData.name}
                    onChange={(e) => setWorkspaceFormData({...workspaceFormData, name: e.target.value})}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-green-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                  <textarea
                    value={workspaceFormData.description}
                    onChange={(e) => setWorkspaceFormData({...workspaceFormData, description: e.target.value})}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-green-500"
                    rows={3}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Default Index</label>
                  <select
                    value={workspaceFormData.default_index}
                    onChange={(e) => setWorkspaceFormData({...workspaceFormData, default_index: e.target.value})}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-green-500"
                  >
                    <option value="logs_net">logs_net</option>
                    <option value="logs_cic_ids2017">logs_cic_ids2017</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Permissions</label>
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {availablePermissions.map((permission) => (
                      <label key={permission} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={workspaceFormData.permissions.includes(permission)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setWorkspaceFormData({
                                ...workspaceFormData,
                                permissions: [...workspaceFormData.permissions, permission]
                              });
                            } else {
                              setWorkspaceFormData({
                                ...workspaceFormData,
                                permissions: workspaceFormData.permissions.filter(p => p !== permission)
                              });
                            }
                          }}
                          className="rounded"
                        />
                        <span className="text-sm text-gray-700">{permission.replace('_', ' ')}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowWorkspaceModal(false)}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg"
                >
                  Create Workspace
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default TenantManagement;