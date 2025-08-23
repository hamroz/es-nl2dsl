// Mock API
const mockApi = {
  get: jest.fn(),
  post: jest.fn(),
  interceptors: {
    request: {
      use: jest.fn(() => 1),
      eject: jest.fn(),
    },
    response: {
      use: jest.fn(() => 1),
      eject: jest.fn(),
    },
  },
};

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: mockApi,
}));

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider, useAuth } from '../AuthContext';

// Test component that uses AuthContext
const TestComponent = () => {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth();
  
  const handleLogin = async () => {
    try {
      await login({ email: 'test@test.com', password: 'password' });
    } catch (error) {
      // Handle login errors gracefully in test
      console.log('Login failed:', error);
    }
  };
  
  return (
    <div>
      <div data-testid="loading">{isLoading ? 'Loading' : 'Not Loading'}</div>
      <div data-testid="authenticated">{isAuthenticated ? 'Authenticated' : 'Not Authenticated'}</div>
      <div data-testid="user">{user ? user.email : 'No User'}</div>
      <button onClick={handleLogin}>
        Login
      </button>
      <button onClick={logout}>Logout</button>
    </div>
  );
};

describe('AuthContext (Simple)', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    jest.clearAllMocks();
    
    // Reset API mocks
    mockApi.get.mockReset();
    mockApi.post.mockReset();
  });

  it('should provide initial state', () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('loading')).toHaveTextContent('Loading');
    expect(screen.getByTestId('authenticated')).toHaveTextContent('Not Authenticated');
    expect(screen.getByTestId('user')).toHaveTextContent('No User');
  });

  it('should handle successful login', async () => {
    const user = userEvent.setup();
    
    // Mock successful login and profile responses
    mockApi.post.mockImplementation((url) => {
      if (url === '/auth/login/') {
        return Promise.resolve({
          data: {
            access: 'access-token',
            refresh: 'refresh-token',
            session_token: 'session-token'
          }
        });
      }
      return Promise.reject(new Error('Not found'));
    });

    mockApi.get.mockImplementation((url) => {
      if (url === '/auth/profile/') {
        return Promise.resolve({
          data: {
            id: '1',
            username: 'testuser',
            email: 'test@example.com',
            role: 'admin',
            workspace: 'test-workspace'
          }
        });
      }
      if (url === '/auth/permissions/') {
        return Promise.resolve({
          data: {
            permissions: {
              can_admin_users: true,
              can_modify_queries: true,
              can_execute_queries: true,
              can_view_audit_logs: true,
              can_manage_system: true,
              can_export_data: true,
              is_read_only: false,
            }
          }
        });
      }
      return Promise.reject(new Error('Not found'));
    });
    
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const loginButton = screen.getByText('Login');
    await user.click(loginButton);

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('Authenticated');
      expect(screen.getByTestId('user')).toHaveTextContent('test@example.com');
    }, { timeout: 3000 });
  });

  it('should handle logout', async () => {
    const user = userEvent.setup();
    
    // Set up authenticated state
    localStorage.setItem('es_nl2dsl_access_token', 'valid-token');
    localStorage.setItem('es_nl2dsl_refresh_token', 'valid-refresh');
    
    // Mock profile response for initial auth check
    mockApi.get.mockImplementation((url) => {
      if (url === '/auth/profile/') {
        return Promise.resolve({
          data: {
            id: '1',
            username: 'testuser',
            email: 'test@example.com',
            role: 'admin',
            workspace: 'test-workspace'
          }
        });
      }
      if (url === '/auth/permissions/') {
        return Promise.resolve({
          data: {
            permissions: {
              can_admin_users: true,
              can_modify_queries: true,
              can_execute_queries: true,
              can_view_audit_logs: true,
              can_manage_system: true,
              can_export_data: true,
              is_read_only: false,
            }
          }
        });
      }
      return Promise.reject(new Error('Not found'));
    });

    mockApi.post.mockImplementation((url) => {
      if (url === '/auth/logout/') {
        return Promise.resolve({ data: { message: 'Logged out' } });
      }
      return Promise.reject(new Error('Not found'));
    });
    
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    // Wait for auth check to complete
    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('Authenticated');
    });

    const logoutButton = screen.getByText('Logout');
    await user.click(logoutButton);

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('Not Authenticated');
      expect(screen.getByTestId('user')).toHaveTextContent('No User');
    });
    
    // Check that tokens are cleared
    expect(localStorage.getItem('es_nl2dsl_access_token')).toBeNull();
    expect(localStorage.getItem('es_nl2dsl_refresh_token')).toBeNull();
  });

  it('should check authentication on mount with valid token', async () => {
    // Mock valid token (not expired)
    const futureTime = Math.floor(Date.now() / 1000) + 3600; // 1 hour from now
    const tokenPayload = btoa(JSON.stringify({ exp: futureTime }));
    const mockToken = `header.${tokenPayload}.signature`;
    
    localStorage.setItem('es_nl2dsl_access_token', mockToken);
    
    mockApi.get.mockImplementation((url) => {
      if (url === '/auth/profile/') {
        return Promise.resolve({
          data: {
            id: '1',
            username: 'testuser',
            email: 'test@example.com',
            role: 'admin',
            workspace: 'test-workspace'
          }
        });
      }
      if (url === '/auth/permissions/') {
        return Promise.resolve({
          data: {
            permissions: {
              can_admin_users: true,
              can_modify_queries: true,
              can_execute_queries: true,
              can_view_audit_logs: true,
              can_manage_system: true,
              can_export_data: true,
              is_read_only: false,
            }
          }
        });
      }
      return Promise.reject(new Error('Not found'));
    });
    
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('Authenticated');
    });
  });

  it('should clear expired tokens on mount', async () => {
    // Mock expired token
    const pastTime = Math.floor(Date.now() / 1000) - 3600; // 1 hour ago
    const tokenPayload = btoa(JSON.stringify({ exp: pastTime }));
    const mockToken = `header.${tokenPayload}.signature`;
    
    localStorage.setItem('es_nl2dsl_access_token', mockToken);
    
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('Not Authenticated');
    });

    expect(localStorage.getItem('es_nl2dsl_access_token')).toBeNull();
    expect(localStorage.getItem('es_nl2dsl_refresh_token')).toBeNull();
  });

  it('should handle API errors during authentication check', async () => {
    localStorage.setItem('es_nl2dsl_access_token', 'valid-token');
    
    mockApi.get.mockRejectedValue(new Error('Server error'));
    
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('Not Authenticated');
    });
  });

  it('should throw error when useAuth is used outside provider', () => {
    // Suppress error boundary logs for this test
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    
    expect(() => {
      render(<TestComponent />);
    }).toThrow('useAuth must be used within an AuthProvider');
    
    spy.mockRestore();
  });

  it('should handle token refresh', async () => {
    // Mock expired access token but valid refresh token
    const pastTime = Math.floor(Date.now() / 1000) - 3600;
    const futureTime = Math.floor(Date.now() / 1000) + 3600;
    
    const expiredTokenPayload = btoa(JSON.stringify({ exp: pastTime }));
    const validRefreshPayload = btoa(JSON.stringify({ exp: futureTime }));
    
    const expiredToken = `header.${expiredTokenPayload}.signature`;
    const validRefreshToken = `header.${validRefreshPayload}.signature`;
    
    localStorage.setItem('es_nl2dsl_access_token', expiredToken);
    localStorage.setItem('es_nl2dsl_refresh_token', validRefreshToken);
    
    mockApi.post.mockImplementation((url) => {
      if (url === '/auth/refresh/') {
        return Promise.resolve({
          data: {
            access: 'new-access-token',
            refresh: 'new-refresh-token'
          }
        });
      }
      return Promise.reject(new Error('Not found'));
    });

    mockApi.get.mockImplementation((url) => {
      if (url === '/auth/profile/') {
        return Promise.resolve({
          data: {
            id: '1',
            username: 'testuser',
            email: 'test@example.com',
            role: 'admin',
            workspace: 'test-workspace'
          }
        });
      }
      if (url === '/auth/permissions/') {
        return Promise.resolve({
          data: {
            permissions: {
              can_admin_users: true,
              can_modify_queries: true,
              can_execute_queries: true,
              can_view_audit_logs: true,
              can_manage_system: true,
              can_export_data: true,
              is_read_only: false,
            }
          }
        });
      }
      return Promise.reject(new Error('Not found'));
    });
    
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('Authenticated');
    });
    
    // Check that new tokens are stored
    expect(localStorage.getItem('es_nl2dsl_access_token')).toBe('new-access-token');
    expect(localStorage.getItem('es_nl2dsl_refresh_token')).toBe('new-refresh-token');
  });

  it('should handle login failure', async () => {
    const user = userEvent.setup();
    
    mockApi.post.mockRejectedValue(new Error('Invalid credentials'));
    
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const loginButton = screen.getByText('Login');
    
    // Click the login button - this will throw an error internally
    await user.click(loginButton);

    // The login should fail and the user should remain unauthenticated
    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('Not Authenticated');
    });
    
    // The error should be logged but not crash the app
    expect(mockApi.post).toHaveBeenCalledWith('/auth/login/', {
      email: 'test@test.com',
      password: 'password'
    });
  });
});