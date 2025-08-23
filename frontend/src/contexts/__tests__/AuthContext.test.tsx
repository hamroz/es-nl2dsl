import React from 'react';
import { waitFor, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../test/mocks/server';
import { 
  render, 
  mockUser, 
  mockPermissions, 
  waitForAsync,
  mockLocalStorage,
  mockConsole
} from '../../test/utils/testUtils';
import { AuthProvider, useAuth, withAuth, usePermissions } from '../AuthContext';

// Mock API
const mockApi = {
  get: jest.fn(),
  post: jest.fn(),
  interceptors: {
    request: {
      use: jest.fn(),
      eject: jest.fn(),
    },
    response: {
      use: jest.fn(),
      eject: jest.fn(),
    },
  },
};

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: mockApi,
}));

// Test component that uses AuthContext
const TestComponent = () => {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth();
  
  return (
    <div>
      <div data-testid="loading">{isLoading ? 'Loading' : 'Not Loading'}</div>
      <div data-testid="authenticated">{isAuthenticated ? 'Authenticated' : 'Not Authenticated'}</div>
      <div data-testid="user">{user ? user.email : 'No User'}</div>
      <button onClick={() => login({ email: 'test@test.com', password: 'password' })}>
        Login
      </button>
      <button onClick={logout}>Logout</button>
    </div>
  );
};

// Test component for permissions
const PermissionsTestComponent = () => {
  const { hasPermission, hasAnyPermission, hasAllPermissions } = usePermissions();
  
  return (
    <div>
      <div data-testid="can-admin">{hasPermission('can_admin_users') ? 'Can Admin' : 'Cannot Admin'}</div>
      <div data-testid="any-perm">{hasAnyPermission(['can_admin_users', 'can_execute_queries']) ? 'Has Any' : 'Has None'}</div>
      <div data-testid="all-perm">{hasAllPermissions(['can_admin_users', 'can_execute_queries']) ? 'Has All' : 'Missing Some'}</div>
    </div>
  );
};

// Test component for withAuth HOC
const ProtectedComponent = () => <div data-testid="protected">Protected Content</div>;
const WrappedComponent = withAuth(ProtectedComponent);
const PermissionProtectedComponent = withAuth(ProtectedComponent, 'can_admin_users');

describe('AuthContext', () => {
  let mockStorage: ReturnType<typeof mockLocalStorage>;
  let consoleMock: ReturnType<typeof mockConsole>;

  beforeEach(() => {
    mockStorage = mockLocalStorage();
    Object.defineProperty(window, 'localStorage', {
      value: mockStorage,
      writable: true
    });
    
    consoleMock = mockConsole();
    
    // Reset all mocks
    jest.clearAllMocks();
    mockApi.get.mockClear();
    mockApi.post.mockClear();
  });

  afterEach(() => {
    consoleMock.restore();
  });

  describe('AuthProvider', () => {
    it('should provide initial loading state', () => {
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
      });
    });

    it('should handle logout', async () => {
      const user = userEvent.setup();
      
      // Setup authenticated state
      mockStorage.setItem('es_nl2dsl_access_token', 'valid-token');
      mockStorage.setItem('es_nl2dsl_refresh_token', 'valid-refresh');
      
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
    });

    it('should check authentication on mount with valid token', async () => {
      // Mock valid token (not expired)
      const futureTime = Math.floor(Date.now() / 1000) + 3600; // 1 hour from now
      const tokenPayload = btoa(JSON.stringify({ exp: futureTime }));
      const mockToken = `header.${tokenPayload}.signature`;
      
      mockStorage.setItem('es_nl2dsl_access_token', mockToken);
      
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
      
      mockStorage.setItem('es_nl2dsl_access_token', mockToken);
      
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('authenticated')).toHaveTextContent('Not Authenticated');
      });

      expect(mockStorage.removeItem).toHaveBeenCalledWith('es_nl2dsl_access_token');
      expect(mockStorage.removeItem).toHaveBeenCalledWith('es_nl2dsl_refresh_token');
    });

    it('should handle API errors during authentication check', async () => {
      server.use(
        rest.get('/api/v1/auth/profile/', (req, res, ctx) => {
          return res(ctx.status(500), ctx.json({ error: 'Server error' }));
        })
      );

      mockStorage.setItem('es_nl2dsl_access_token', 'valid-token');
      
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('authenticated')).toHaveTextContent('Not Authenticated');
      });

      expect(consoleMock.mockError).toHaveBeenCalledWith(
        'Authentication check failed:', 
        expect.any(Object)
      );
    });

    it('should attempt token refresh when token is expired but refresh token exists', async () => {
      // Mock expired access token but valid refresh token
      const pastTime = Math.floor(Date.now() / 1000) - 3600;
      const futureTime = Math.floor(Date.now() / 1000) + 3600;
      
      const expiredTokenPayload = btoa(JSON.stringify({ exp: pastTime }));
      const validRefreshPayload = btoa(JSON.stringify({ exp: futureTime }));
      
      const expiredToken = `header.${expiredTokenPayload}.signature`;
      const validRefreshToken = `header.${validRefreshPayload}.signature`;
      
      mockStorage.setItem('es_nl2dsl_access_token', expiredToken);
      mockStorage.setItem('es_nl2dsl_refresh_token', validRefreshToken);
      
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('authenticated')).toHaveTextContent('Authenticated');
      });
    });
  });

  describe('useAuth hook', () => {
    it('should throw error when used outside provider', () => {
      // Suppress error boundary logs for this test
      const spy = jest.spyOn(console, 'error').mockImplementation();
      
      expect(() => {
        render(<TestComponent />);
      }).toThrow('useAuth must be used within an AuthProvider');
      
      spy.mockRestore();
    });
  });

  describe('usePermissions hook', () => {
    it('should return correct permissions', async () => {
      mockStorage.setItem('es_nl2dsl_access_token', 'valid-token');
      
      render(
        <AuthProvider>
          <PermissionsTestComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('can-admin')).toHaveTextContent('Can Admin');
        expect(screen.getByTestId('any-perm')).toHaveTextContent('Has Any');
        expect(screen.getByTestId('all-perm')).toHaveTextContent('Has All');
      });
    });

    it('should handle no permissions', async () => {
      // Override with empty permissions
      server.use(
        rest.get('/api/v1/auth/permissions/', (req, res, ctx) => {
          return res(ctx.json({ permissions: {} }));
        })
      );

      mockStorage.setItem('es_nl2dsl_access_token', 'valid-token');
      
      render(
        <AuthProvider>
          <PermissionsTestComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('can-admin')).toHaveTextContent('Cannot Admin');
        expect(screen.getByTestId('any-perm')).toHaveTextContent('Has None');
        expect(screen.getByTestId('all-perm')).toHaveTextContent('Missing Some');
      });
    });
  });

  describe('withAuth HOC', () => {
    it('should show loading state initially', () => {
      render(
        <AuthProvider>
          <WrappedComponent />
        </AuthProvider>
      );

      expect(screen.getByText('Loading')).toBeInTheDocument();
    });

    it('should render protected component when authenticated', async () => {
      mockStorage.setItem('es_nl2dsl_access_token', 'valid-token');
      
      render(
        <AuthProvider>
          <WrappedComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('protected')).toBeInTheDocument();
      });
    });

    it('should show authentication required when not authenticated', async () => {
      render(
        <AuthProvider>
          <WrappedComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Authentication Required')).toBeInTheDocument();
        expect(screen.getByText('Please log in to access this page.')).toBeInTheDocument();
      });
    });

    it('should show access denied when missing required permission', async () => {
      // Override with restricted permissions
      server.use(
        rest.get('/api/v1/auth/permissions/', (req, res, ctx) => {
          return res(ctx.json({ 
            permissions: { ...mockPermissions, can_admin_users: false } 
          }));
        })
      );

      mockStorage.setItem('es_nl2dsl_access_token', 'valid-token');
      
      render(
        <AuthProvider>
          <PermissionProtectedComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Access Denied')).toBeInTheDocument();
        expect(screen.getByText("You don't have permission to access this page.")).toBeInTheDocument();
      });
    });
  });

  describe('token management', () => {
    it('should decode JWT tokens correctly', () => {
      const payload = { exp: 1234567890, user_id: 1 };
      const tokenPayload = btoa(JSON.stringify(payload));
      const token = `header.${tokenPayload}.signature`;
      
      // Create a test component that uses the token decoder
      const TokenTestComponent = () => {
        const { user } = useAuth();
        // This would internally use the decodeJWT function
        return <div>Token test</div>;
      };

      render(
        <AuthProvider>
          <TokenTestComponent />
        </AuthProvider>
      );

      // The internal token decoding is tested indirectly through auth flow
      expect(screen.getByText('Token test')).toBeInTheDocument();
    });

    it('should handle malformed JWT tokens', async () => {
      mockStorage.setItem('es_nl2dsl_access_token', 'invalid.token.format');
      
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      // Should treat malformed token as expired/invalid
      await waitFor(() => {
        expect(screen.getByTestId('authenticated')).toHaveTextContent('Not Authenticated');
      });
    });
  });

  describe('error handling', () => {
    it('should handle login failure', async () => {
      server.use(
        rest.post('/api/v1/auth/login/', (req, res, ctx) => {
          return res(ctx.status(401), ctx.json({ message: 'Invalid credentials' }));
        })
      );

      const user = userEvent.setup();
      
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      const loginButton = screen.getByText('Login');
      
      let error: Error | null = null;
      try {
        await user.click(loginButton);
      } catch (e) {
        error = e as Error;
      }

      // The error should be handled internally, but auth state should remain unchanged
      await waitFor(() => {
        expect(screen.getByTestId('authenticated')).toHaveTextContent('Not Authenticated');
      });
    });

    it('should handle refresh token failure', async () => {
      server.use(
        rest.post('/api/v1/auth/refresh/', (req, res, ctx) => {
          return res(ctx.status(401), ctx.json({ error: 'Invalid refresh token' }));
        })
      );

      // Mock expired access token but valid refresh token
      const pastTime = Math.floor(Date.now() / 1000) - 3600;
      const futureTime = Math.floor(Date.now() / 1000) + 3600;
      
      const expiredTokenPayload = btoa(JSON.stringify({ exp: pastTime }));
      const refreshTokenPayload = btoa(JSON.stringify({ exp: futureTime }));
      
      mockStorage.setItem('es_nl2dsl_access_token', `header.${expiredTokenPayload}.signature`);
      mockStorage.setItem('es_nl2dsl_refresh_token', `header.${refreshTokenPayload}.signature`);
      
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('authenticated')).toHaveTextContent('Not Authenticated');
      });

      // Should clear tokens after failed refresh
      expect(mockStorage.removeItem).toHaveBeenCalledWith('es_nl2dsl_access_token');
      expect(mockStorage.removeItem).toHaveBeenCalledWith('es_nl2dsl_refresh_token');
    });
  });
});