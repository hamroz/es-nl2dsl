import { setupServer } from 'msw/node';
import { handlers } from './handlers';

// Setup mock server for API requests
export const server = setupServer(...handlers);