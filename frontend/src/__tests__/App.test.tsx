import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { render, mockUser, mockPermissions } from '../test/utils/testUtils';
import App from '../App';

// Mock all page components
jest.mock('../pages/QueryGenerator', () => {
  return function MockQueryGenerator() {
    return <div data-testid="query-generator">Query Generator Page</div>;
  };
});

jest.mock('../pages/EvaluationDashboard', () => {
  return function MockEvaluationDashboard() {
    return <div data-testid="evaluation-dashboard">Evaluation Dashboard Page</div>;
  };
});

jest.mock('../pages/SecurityTesting', () => {
  return function MockSecurityTesting() {
    return <div data-testid="security-testing">Security Testing Page</div>;
  };
});

jest.mock('../pages/PrivacyAnalysis', () => {
  return function MockPrivacyAnalysis() {
    return <div data-testid="privacy-analysis">Privacy Analysis Page</div>;
  };
});

jest.mock('../pages/SystemAdmin', () => {
  return function MockSystemAdmin() {
    return <div data-testid="system-admin">System Admin Page</div>;
  };
});

jest.mock('../pages/Login', () => {
  return function MockLogin() {
    return <div data-testid="login-page">Login Page</div>;
  };
});

// Mock AuthContext
const mockLogout = jest.fn();
const mockAuthContext = {
  isAuthenticated: true,
  isLoading: false,
  user: mockUser,
  permissions: mockPermissions,
  login: jest.fn(),
  logout: mockLogout,
  refreshToken: jest.fn(),
  checkAuth: jest.fn(),
};

jest.mock('../contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useAuth: () => mockAuthContext,
}));

// Wrapper component for testing with router
const AppWithRouter = ({ initialEntries = ['/'] }: { initialEntries?: string[] }) => (
  <MemoryRouter initialEntries={initialEntries}>
    <App />
  </MemoryRouter>
);

describe('App Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuthContext.isAuthenticated = true;
    mockAuthContext.isLoading = false;
  });

  it('should render loading state when authentication is loading', () => {
    mockAuthContext.isLoading = true;
    
    render(<AppWithRouter />);

    expect(screen.getByRole('status')).toBeInTheDocument(); // Loading spinner
  });

  it('should render login page when user is not authenticated', () => {
    mockAuthContext.isAuthenticated = false;
    mockAuthContext.isLoading = false;
    
    render(<AppWithRouter />);

    expect(screen.getByTestId('login-page')).toBeInTheDocument();
  });

  it('should render main app layout when user is authenticated', () => {
    render(<AppWithRouter />);

    expect(screen.getByText('ES-NL2DSL')).toBeInTheDocument();
    expect(screen.getByText('Query Generator')).toBeInTheDocument();
    expect(screen.getByText('Evaluation')).toBeInTheDocument();
    expect(screen.getByText('Security Testing')).toBeInTheDocument();
    expect(screen.getByText('Privacy Analysis')).toBeInTheDocument();
    expect(screen.getByText('System Admin')).toBeInTheDocument();
  });

  it('should display user information in sidebar', () => {
    render(<AppWithRouter />);

    expect(screen.getByText('test@example.com')).toBeInTheDocument();
    expect(screen.getByText('admin')).toBeInTheDocument();
  });

  it('should render QueryGenerator page by default (root route)', () => {
    render(<AppWithRouter initialEntries={['/']} />);

    expect(screen.getByTestId('query-generator')).toBeInTheDocument();
  });

  it('should render EvaluationDashboard page on /evaluation route', () => {
    render(<AppWithRouter initialEntries={['/evaluation']} />);

    expect(screen.getByTestId('evaluation-dashboard')).toBeInTheDocument();
  });

  it('should render SecurityTesting page on /security route', () => {
    render(<AppWithRouter initialEntries={['/security']} />);

    expect(screen.getByTestId('security-testing')).toBeInTheDocument();
  });

  it('should render PrivacyAnalysis page on /privacy route', () => {
    render(<AppWithRouter initialEntries={['/privacy']} />);

    expect(screen.getByTestId('privacy-analysis')).toBeInTheDocument();
  });

  it('should render SystemAdmin page on /admin route', () => {
    render(<AppWithRouter initialEntries={['/admin']} />);

    expect(screen.getByTestId('system-admin')).toBeInTheDocument();
  });

  it('should handle navigation between pages', async () => {
    const user = userEvent.setup();
    render(<AppWithRouter />);

    // Start on Query Generator (default)
    expect(screen.getByTestId('query-generator')).toBeInTheDocument();

    // Navigate to Evaluation
    await user.click(screen.getByText('Evaluation'));
    expect(screen.getByTestId('evaluation-dashboard')).toBeInTheDocument();

    // Navigate to Security Testing
    await user.click(screen.getByText('Security Testing'));
    expect(screen.getByTestId('security-testing')).toBeInTheDocument();

    // Navigate to System Admin
    await user.click(screen.getByText('System Admin'));
    expect(screen.getByTestId('system-admin')).toBeInTheDocument();
  });

  it('should handle logout functionality', async () => {
    const user = userEvent.setup();
    render(<AppWithRouter />);

    const logoutButton = screen.getByText('Logout');
    await user.click(logoutButton);

    expect(mockLogout).toHaveBeenCalled();
  });

  it('should display navigation icons', () => {
    render(<AppWithRouter />);

    // Check that navigation items have their associated icons
    // Icons are rendered as SVG elements from Heroicons
    const navigationLinks = screen.getAllByRole('link');
    expect(navigationLinks.length).toBeGreaterThan(0);
  });

  it('should apply hover styles to navigation links', async () => {
    const user = userEvent.setup();
    render(<AppWithRouter />);

    const evaluationLink = screen.getByText('Evaluation');
    
    // Check that the link has hover classes
    expect(evaluationLink.closest('a')).toHaveClass('hover:bg-gray-700', 'hover:text-white');
  });

  it('should display logo and branding', () => {
    render(<AppWithRouter />);

    expect(screen.getByText('ES-NL2DSL')).toBeInTheDocument();
  });

  it('should handle unknown routes gracefully', () => {
    render(<AppWithRouter initialEntries={['/unknown-route']} />);

    // Should still render the app layout (navigation will handle unknown routes)
    expect(screen.getByText('ES-NL2DSL')).toBeInTheDocument();
  });

  it('should maintain responsive design classes', () => {
    render(<AppWithRouter />);

    const sidebar = screen.getByText('ES-NL2DSL').closest('div');
    expect(sidebar?.parentElement).toHaveClass('fixed', 'inset-y-0', 'left-0', 'z-50', 'w-64');

    const mainContent = screen.getByTestId('query-generator').closest('div');
    expect(mainContent?.parentElement).toHaveClass('ml-64', 'flex-1');
  });

  it('should handle authentication state changes', async () => {
    mockAuthContext.isAuthenticated = true;
    const { rerender } = render(<AppWithRouter />);

    // Should show authenticated app
    expect(screen.getByText('ES-NL2DSL')).toBeInTheDocument();

    // Change to unauthenticated
    mockAuthContext.isAuthenticated = false;
    rerender(<AppWithRouter />);

    expect(screen.getByTestId('login-page')).toBeInTheDocument();
  });

  it('should display user role badge with correct styling', () => {
    render(<AppWithRouter />);

    const roleElement = screen.getByText('admin');
    expect(roleElement).toHaveClass('text-xs', 'text-gray-400');
  });

  it('should render with proper semantic HTML structure', () => {
    render(<AppWithRouter />);

    // Should have main navigation
    expect(screen.getByRole('navigation')).toBeInTheDocument();
    
    // Should have proper link elements
    const links = screen.getAllByRole('link');
    expect(links.length).toBeGreaterThanOrEqual(5); // At least 5 navigation links
  });

  it('should handle query client configuration', () => {
    render(<AppWithRouter />);

    // Should render without query client errors
    expect(screen.getByText('ES-NL2DSL')).toBeInTheDocument();
  });

  it('should display sidebar with proper dark theme styling', () => {
    render(<AppWithRouter />);

    const sidebar = screen.getByText('Query Generator').closest('nav')?.parentElement;
    expect(sidebar).toHaveClass('bg-gray-900');
  });

  it('should handle accessibility features', () => {
    render(<AppWithRouter />);

    // Check that navigation links are keyboard accessible
    const navLinks = screen.getAllByRole('link');
    navLinks.forEach(link => {
      expect(link).toHaveAttribute('href');
    });
  });
});