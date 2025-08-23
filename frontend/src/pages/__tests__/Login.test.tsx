import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../test/mocks/server';
import { render, createChangeEvent } from '../../test/utils/testUtils';
import Login from '../Login';

// Mock the AuthContext
const mockLogin = jest.fn();
const mockAuthContext = {
  login: mockLogin,
  isLoading: false,
  isAuthenticated: false,
  user: null,
  permissions: null,
  logout: jest.fn(),
  refreshToken: jest.fn(),
  checkAuth: jest.fn(),
};

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => mockAuthContext,
}));

// Mock window.location
const mockLocationHref = jest.fn();
Object.defineProperty(window, 'location', {
  value: {
    href: '',
    get href() {
      return this._href || '';
    },
    set href(value) {
      this._href = value;
      mockLocationHref(value);
    },
  },
  writable: true,
});

describe('Login Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuthContext.isLoading = false;
    mockAuthContext.isAuthenticated = false;
  });

  it('should render login form', () => {
    render(<Login />);

    expect(screen.getByText('ES-NL2DSL')).toBeInTheDocument();
    expect(screen.getByText('Natural Language to Elasticsearch DSL')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Email address')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('should show system features and benefits', () => {
    render(<Login />);

    // Check for feature descriptions
    expect(screen.getByText('Natural Language Processing')).toBeInTheDocument();
    expect(screen.getByText('Real-time Query Generation')).toBeInTheDocument();
    expect(screen.getByText('Enterprise Security')).toBeInTheDocument();
    expect(screen.getByText('Advanced Analytics')).toBeInTheDocument();
  });

  it('should handle form input changes', async () => {
    const user = userEvent.setup();
    render(<Login />);

    const emailInput = screen.getByPlaceholderText('Email address');
    const passwordInput = screen.getByPlaceholderText('Password');

    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');

    expect(emailInput).toHaveValue('test@example.com');
    expect(passwordInput).toHaveValue('password123');
  });

  it('should toggle password visibility', async () => {
    const user = userEvent.setup();
    render(<Login />);

    const passwordInput = screen.getByPlaceholderText('Password');
    const toggleButton = screen.getByRole('button', { name: /toggle password visibility/i });

    // Initially password should be hidden
    expect(passwordInput).toHaveAttribute('type', 'password');

    // Click toggle button to show password
    await user.click(toggleButton);
    expect(passwordInput).toHaveAttribute('type', 'text');

    // Click toggle button again to hide password
    await user.click(toggleButton);
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  it('should submit login form with valid credentials', async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValue(undefined);
    
    render(<Login />);

    const emailInput = screen.getByPlaceholderText('Email address');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');
    await user.click(submitButton);

    expect(mockLogin).toHaveBeenCalledWith({
      email: 'test@example.com',
      password: 'password123'
    });
  });

  it('should prevent form submission with empty fields', async () => {
    const user = userEvent.setup();
    render(<Login />);

    const submitButton = screen.getByRole('button', { name: /sign in/i });
    await user.click(submitButton);

    // Login should not be called with empty credentials
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('should show loading state during submission', async () => {
    const user = userEvent.setup();
    let resolveLogin: (value: any) => void;
    const loginPromise = new Promise((resolve) => {
      resolveLogin = resolve;
    });
    mockLogin.mockReturnValue(loginPromise);
    
    render(<Login />);

    const emailInput = screen.getByPlaceholderText('Email address');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');
    await user.click(submitButton);

    // Should show loading state
    expect(screen.getByText('Signing in...')).toBeInTheDocument();
    expect(submitButton).toBeDisabled();

    // Resolve the promise
    resolveLogin!(undefined);
    
    await waitFor(() => {
      expect(screen.queryByText('Signing in...')).not.toBeInTheDocument();
    });
  });

  it('should display error message on login failure', async () => {
    const user = userEvent.setup();
    const errorMessage = 'Invalid credentials';
    mockLogin.mockRejectedValue(new Error(errorMessage));
    
    render(<Login />);

    const emailInput = screen.getByPlaceholderText('Email address');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'wrongpassword');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });

    // Error should be displayed with warning icon
    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('should clear error message on new input', async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValue(new Error('Invalid credentials'));
    
    render(<Login />);

    const emailInput = screen.getByPlaceholderText('Email address');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    // First login attempt with error
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'wrongpassword');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });

    // Change input should clear error
    await user.clear(emailInput);
    await user.type(emailInput, 'newemail@example.com');

    // Error should be cleared when typing in email field
    expect(screen.queryByText('Invalid credentials')).not.toBeInTheDocument();
  });

  it('should redirect if already authenticated', () => {
    mockAuthContext.isAuthenticated = true;
    
    render(<Login />);

    expect(mockLocationHref).toHaveBeenCalledWith('/');
  });

  it('should show loading spinner when auth is loading', () => {
    mockAuthContext.isLoading = true;
    
    render(<Login />);

    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(screen.getByText('Checking authentication...')).toBeInTheDocument();
  });

  it('should show demo credentials', () => {
    render(<Login />);

    expect(screen.getByText('Demo Credentials')).toBeInTheDocument();
    expect(screen.getByText('admin@es-nl2dsl.local')).toBeInTheDocument();
    expect(screen.getByText('admin123')).toBeInTheDocument();
  });

  it('should handle keyboard navigation', async () => {
    const user = userEvent.setup();
    render(<Login />);

    const emailInput = screen.getByPlaceholderText('Email address');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    // Tab navigation should work
    await user.tab();
    expect(emailInput).toHaveFocus();

    await user.tab();
    expect(passwordInput).toHaveFocus();

    await user.tab();
    expect(submitButton).toHaveFocus();
  });

  it('should submit form on Enter key press', async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValue(undefined);
    
    render(<Login />);

    const emailInput = screen.getByPlaceholderText('Email address');
    const passwordInput = screen.getByPlaceholderText('Password');

    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');
    
    // Press Enter in password field
    await user.keyboard('{Enter}');

    expect(mockLogin).toHaveBeenCalledWith({
      email: 'test@example.com',
      password: 'password123'
    });
  });

  it('should show forgot password link', () => {
    render(<Login />);

    const forgotPasswordLink = screen.getByText('Forgot your password?');
    expect(forgotPasswordLink).toBeInTheDocument();
    // In a real app, this might link to a reset password page
  });

  it('should display proper ARIA labels for accessibility', () => {
    render(<Login />);

    const emailInput = screen.getByPlaceholderText('Email address');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    expect(emailInput).toHaveAttribute('type', 'email');
    expect(passwordInput).toHaveAttribute('type', 'password');
    expect(submitButton).toHaveAttribute('type', 'submit');
  });

  it('should handle form validation', async () => {
    const user = userEvent.setup();
    render(<Login />);

    const emailInput = screen.getByPlaceholderText('Email address');
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    // Enter invalid email
    await user.type(emailInput, 'invalid-email');
    await user.click(submitButton);

    // Should not call login with invalid email
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('should show error for different error types', async () => {
    const user = userEvent.setup();
    
    render(<Login />);

    const emailInput = screen.getByPlaceholderText('Email address');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    // Test with error object without message
    mockLogin.mockRejectedValue(new Error());
    
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Login failed')).toBeInTheDocument();
    });

    // Test with string error
    mockLogin.mockRejectedValue('String error');
    
    await user.clear(emailInput);
    await user.type(emailInput, 'test2@example.com');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Login failed')).toBeInTheDocument();
    });
  });

  it('should prevent multiple submissions', async () => {
    const user = userEvent.setup();
    let resolveLogin: (value: any) => void;
    const loginPromise = new Promise((resolve) => {
      resolveLogin = resolve;
    });
    mockLogin.mockReturnValue(loginPromise);
    
    render(<Login />);

    const emailInput = screen.getByPlaceholderText('Email address');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');
    
    // First click
    await user.click(submitButton);
    expect(submitButton).toBeDisabled();
    
    // Second click should not trigger another call
    await user.click(submitButton);
    expect(mockLogin).toHaveBeenCalledTimes(1);

    // Resolve the first login
    resolveLogin!(undefined);
  });
});