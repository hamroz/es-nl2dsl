import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import api from '../services/api';

interface User {
  id: string;
  username: string;
  email: string;
  role: 'admin' | 'analyst' | 'viewer';
  workspace: string;
  tenant_id?: string;
}

interface UserPermissions {
  can_admin_users: boolean;
  can_modify_queries: boolean;
  can_execute_queries: boolean;
  can_view_audit_logs: boolean;
  can_manage_system: boolean;
  can_export_data: boolean;
  is_read_only: boolean;
}

interface LoginCredentials {
  email: string;
  password: string;
}

interface AuthContextType {
  user: User | null;
  permissions: UserPermissions | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Token management utilities
const TOKEN_STORAGE_KEY = 'es_nl2dsl_access_token';
const REFRESH_TOKEN_STORAGE_KEY = 'es_nl2dsl_refresh_token';
const SESSION_TOKEN_STORAGE_KEY = 'es_nl2dsl_session_token';

const getStoredToken = () => localStorage.getItem(TOKEN_STORAGE_KEY);
const getStoredRefreshToken = () => localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
const getStoredSessionToken = () => localStorage.getItem(SESSION_TOKEN_STORAGE_KEY);

const setTokens = (accessToken: string, refreshToken: string, sessionToken?: string) => {
  localStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, refreshToken);
  if (sessionToken) {
    localStorage.setItem(SESSION_TOKEN_STORAGE_KEY, sessionToken);
  }
};

const clearTokens = () => {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
  localStorage.removeItem(SESSION_TOKEN_STORAGE_KEY);
};

// JWT token decoder
const decodeJWT = (token: string) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
      return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    return JSON.parse(jsonPayload);
  } catch (error) {
    return null;
  }
};

// Check if token is expired
const isTokenExpired = (token: string): boolean => {
  const decoded = decodeJWT(token);
  if (!decoded || !decoded.exp) return true;
  
  const currentTime = Date.now() / 1000;
  return decoded.exp < currentTime;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<UserPermissions | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Setup axios interceptor for token management
  useEffect(() => {
    const requestInterceptor = api.interceptors.request.use(
      (config) => {
        const token = getStoredToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        
        const sessionToken = getStoredSessionToken();
        if (sessionToken) {
          config.headers['X-Session-Token'] = sessionToken;
        }
        
        return config;
      },
      (error) => Promise.reject(error)
    );

    const responseInterceptor = api.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;
        
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;
          
          try {
            await refreshToken();
            const newToken = getStoredToken();
            if (newToken) {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
              return api(originalRequest);
            }
          } catch (refreshError) {
            // Refresh failed, logout user
            logout();
          }
        }
        
        return Promise.reject(error);
      }
    );

    return () => {
      api.interceptors.request.eject(requestInterceptor);
      api.interceptors.response.eject(responseInterceptor);
    };
  }, []);

  // Check authentication status on mount
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      setIsLoading(true);
      const token = getStoredToken();
      
      if (!token || isTokenExpired(token)) {
        // Try to refresh token
        const refreshTokenValue = getStoredRefreshToken();
        if (refreshTokenValue && !isTokenExpired(refreshTokenValue)) {
          try {
            await refreshToken();
            return;
          } catch (error) {
            clearTokens();
            setIsAuthenticated(false);
            setUser(null);
            setPermissions(null);
            return;
          }
        } else {
          clearTokens();
          setIsAuthenticated(false);
          setUser(null);
          setPermissions(null);
          return;
        }
      }

      // Fetch user profile and permissions
      const [profileResponse, permissionsResponse] = await Promise.all([
        api.get('/auth/profile/'),
        api.get('/auth/permissions/')
      ]);

      setUser(profileResponse.data);
      setPermissions(permissionsResponse.data.permissions);
      setIsAuthenticated(true);

    } catch (error) {
      console.error('Authentication check failed:', error);
      clearTokens();
      setIsAuthenticated(false);
      setUser(null);
      setPermissions(null);
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (credentials: LoginCredentials) => {
    try {
      setIsLoading(true);
      const response = await api.post('/auth/login/', credentials);
      
      const { access, refresh, session_token } = response.data;
      setTokens(access, refresh, session_token);
      
      // Fetch user profile and permissions
      const [profileResponse, permissionsResponse] = await Promise.all([
        api.get('/auth/profile/'),
        api.get('/auth/permissions/')
      ]);

      setUser(profileResponse.data);
      setPermissions(permissionsResponse.data.permissions);
      setIsAuthenticated(true);

    } catch (error: any) {
      clearTokens();
      throw new Error(error.response?.data?.message || 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      const refreshTokenValue = getStoredRefreshToken();
      const sessionToken = getStoredSessionToken();
      
      if (refreshTokenValue || sessionToken) {
        await api.post('/auth/logout/', {
          refresh_token: refreshTokenValue,
          session_token: sessionToken
        });
      }
    } catch (error) {
      console.error('Logout API call failed:', error);
    } finally {
      clearTokens();
      setUser(null);
      setPermissions(null);
      setIsAuthenticated(false);
    }
  };

  const refreshToken = async () => {
    try {
      const refreshTokenValue = getStoredRefreshToken();
      if (!refreshTokenValue) {
        throw new Error('No refresh token available');
      }

      const response = await api.post('/auth/refresh/', {
        refresh: refreshTokenValue
      });

      const { access, refresh } = response.data;
      setTokens(access, refresh, getStoredSessionToken());

      return access;
    } catch (error) {
      clearTokens();
      setIsAuthenticated(false);
      setUser(null);
      setPermissions(null);
      throw error;
    }
  };

  const contextValue: AuthContextType = {
    user,
    permissions,
    isAuthenticated,
    isLoading,
    login,
    logout,
    refreshToken,
    checkAuth
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Higher-order component for protected routes
export const withAuth = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  requiredPermission?: keyof UserPermissions
) => {
  return (props: P) => {
    const { isAuthenticated, isLoading, permissions } = useAuth();
    
    if (isLoading) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
        </div>
      );
    }
    
    if (!isAuthenticated) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Authentication Required</h2>
            <p className="text-gray-600 mb-4">Please log in to access this page.</p>
          </div>
        </div>
      );
    }
    
    if (requiredPermission && permissions && !permissions[requiredPermission]) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Access Denied</h2>
            <p className="text-gray-600 mb-4">You don't have permission to access this page.</p>
          </div>
        </div>
      );
    }
    
    return <WrappedComponent {...props} />;
  };
};

// Custom hook for permission checking
export const usePermissions = () => {
  const { permissions } = useAuth();
  
  const hasPermission = (permission: keyof UserPermissions): boolean => {
    return permissions ? permissions[permission] : false;
  };
  
  const hasAnyPermission = (requiredPermissions: (keyof UserPermissions)[]): boolean => {
    return requiredPermissions.some(permission => hasPermission(permission));
  };
  
  const hasAllPermissions = (requiredPermissions: (keyof UserPermissions)[]): boolean => {
    return requiredPermissions.every(permission => hasPermission(permission));
  };
  
  return {
    permissions,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions
  };
};

export default AuthContext;