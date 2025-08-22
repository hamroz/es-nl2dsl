import axios from 'axios';

const API_BASE_URL = 'http://localhost:8001/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Types for API responses
export interface QueryTask {
  task_id: string;
  prompt: string;
  method: string;
  index: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  created_at: string;
  completed_at?: string;
}

export interface GeneratedQuery {
  task_id: string;
  status: string;
  query: Record<string, any>;
  validation: {
    status: 'PASS' | 'FAIL';
    errors: string[];
  };
  metrics: {
    generation_time: number;
    retry_count: number;
  };
}

export interface SystemHealth {
  overall_status: 'healthy' | 'unhealthy';
  services: {
    elasticsearch: boolean;
    ollama: boolean;
    database: boolean;
    redis: boolean;
    celery_workers: boolean;
  };
  indices: string[];
  models: string[];
  last_check: string;
}

// API functions
export const apiService = {
  // Query generation
  generateQuery: async (data: {
    prompt: string;
    method: 'constrained' | 'rules' | 'zeroshot';
    index?: string;
    model?: string;
  }): Promise<{ task_id: string; status: string }> => {
    const response = await api.post('/queries/', data);
    return response.data;
  },

  getQueryTask: async (taskId: string): Promise<GeneratedQuery> => {
    const response = await api.get(`/queries/${taskId}/`);
    return response.data;
  },

  executeQuery: async (taskId: string, maxSize = 1000) => {
    const response = await api.post(`/queries/${taskId}/execute/`, {
      max_size: maxSize,
    });
    return response.data;
  },

  // System admin
  getSystemHealth: async (): Promise<SystemHealth> => {
    const response = await api.get('/system/health/');
    return response.data;
  },

  getAvailableIndices: async (): Promise<string[]> => {
    const response = await api.get('/system/indices/');
    return response.data;
  },

  // Evaluation
  getEvaluationScenarios: async () => {
    const response = await api.get('/evaluation/scenarios/');
    return response.data;
  },

  runEvaluation: async (scenarioId: string, method: string) => {
    const response = await api.post(`/evaluation/scenarios/${scenarioId}/run/`, {
      method,
    });
    return response.data;
  },

  // Security testing
  runSecurityTest: async (prompts: string[], testName = 'security_test') => {
    const response = await api.post('/security/test/', {
      prompts,
      test_name: testName,
    });
    return response.data;
  },

  getSecurityTestResults: async (testId: string) => {
    const response = await api.get(`/security/test/${testId}/`);
    return response.data;
  },
};

export default api;