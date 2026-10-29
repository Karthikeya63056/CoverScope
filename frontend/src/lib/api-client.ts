import type {
  AuthResponse,
  AuthUser,
  ConversationHistoryResponse,
  PolicyDetailResponse,
  PolicyListResponse,
  PolicySummary,
  PolicyPageTextResponse,
  PolicyFactsResponse,
  AnswerResponse,
  ScenarioResponse,
  ComparisonResponse,
  DashboardSummaryResponse,
  ClaimRehearsalRequest,
  ClaimRehearsalResponse,
  ClaimRehearsalRecord,
  ScenarioRecord,
} from './types';

const BASE_HOST = import.meta.env.VITE_API_BASE_URL
  ? import.meta.env.VITE_API_BASE_URL.replace(/\/$/, '')
  : '';
const API_BASE_URL = `${BASE_HOST}/api/v1`;

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

function getAuthToken(): string | null {
  return localStorage.getItem('coverscope_token');
}

export function setAuthSession(token: string, user: AuthUser): void {
  localStorage.setItem('coverscope_token', token);
  localStorage.setItem('coverscope_user', JSON.stringify(user));
}

export function clearAuthSession(): void {
  localStorage.removeItem('coverscope_token');
  localStorage.removeItem('coverscope_user');
}

export function getStoredUser(): AuthUser | null {
  const raw = localStorage.getItem('coverscope_user');
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const token = getAuthToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
      credentials: options.credentials || 'include',
    });
  } catch (networkErr: any) {
    throw new ApiError(
      'Unable to connect to CoverScope backend server. Please verify that "python -m backend.main" is actively running on port 8000.',
      0
    );
  }

  if (response.status === 401) {
    // If unauthorized, clear invalid session
    if (!endpoint.includes('/auth/login') && !endpoint.includes('/auth/register')) {
      clearAuthSession();
      if (
        window.location.pathname !== '/login' &&
        window.location.pathname !== '/register' &&
        window.location.pathname !== '/'
      ) {
        window.location.href = '/login';
      }
    }
  }

  if (!response.ok) {
    let errorDetail = 'An unexpected server error occurred';
    let responseData = null;
    try {
      responseData = await response.json();
      if (responseData && responseData.detail) {
        errorDetail = Array.isArray(responseData.detail)
          ? responseData.detail.map((e: any) => e.msg).join(', ')
          : responseData.detail;
      } else if (responseData && responseData.message) {
        errorDetail = responseData.message;
      }
    } catch {
      if (response.status === 502 || response.status === 503 || response.status === 504) {
        errorDetail = 'Backend API is currently unreachable. Please make sure "python -m backend.main" is running on port 8000.';
      } else {
        errorDetail = `Server returned status ${response.status} (${response.statusText || 'Error'}).`;
      }
    }
    throw new ApiError(errorDetail, response.status, responseData);
  }

  return response.json();
}

export const api = {
  // Authentication
  async register(email: string, password: string, displayName?: string): Promise<AuthResponse> {
    const res = await request<any>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        display_name: displayName || undefined,
      }),
    });
    const token = res.access_token || res.token;
    if (!token) {
      throw new ApiError('The server did not return an authentication token.', 500, res);
    }
    setAuthSession(token, res.user);
    return res;
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    const res = await request<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    const token = res.access_token || res.token;
    if (!token) {
      throw new ApiError('The server did not return an authentication token.', 500, res);
    }
    setAuthSession(token, res.user);
    return res;
  },

  async me(): Promise<AuthUser> {
    return request<AuthUser>('/auth/me');
  },

  async logout(): Promise<void> {
    try {
      await request('/auth/logout', { method: 'POST' });
    } finally {
      clearAuthSession();
    }
  },

  // Document Library
  async listPolicies(): Promise<PolicyListResponse> {
    return request<PolicyListResponse>('/policies');
  },

  async getPolicy(id: string): Promise<PolicyDetailResponse> {
    return request<PolicyDetailResponse>(`/policies/${id}`);
  },

  async downloadPolicy(id: string): Promise<Blob> {
    const token = getAuthToken();
    const headers = new Headers();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const res = await fetch(`${API_BASE_URL}/policies/${id}/download`, {
      headers,
      credentials: 'include',
    });
    if (!res.ok) {
      throw new ApiError('Failed to download policy PDF document.', res.status);
    }
    return res.blob();
  },

  async uploadPolicy(file: File): Promise<PolicySummary> {
    const formData = new FormData();
    formData.append('file', file);
    return request<PolicySummary>('/policies/upload', {
      method: 'POST',
      body: formData,
    });
  },

  async deletePolicy(id: string): Promise<{ success: boolean; message: string }> {
    return request<{ success: boolean; message: string }>(`/policies/${id}`, {
      method: 'DELETE',
    });
  },

  async getPolicyPageText(id: string, pageNumber: number): Promise<PolicyPageTextResponse> {
    return request<PolicyPageTextResponse>(`/policies/${id}/pages/${pageNumber}`);
  },

  async getPolicyFacts(id: string): Promise<PolicyFactsResponse> {
    return request<PolicyFactsResponse>(`/policies/${id}/facts`);
  },

  // Q&A
  async askQuestion(policyId: string, question: string): Promise<AnswerResponse> {
    return request<AnswerResponse>('/qa/ask', {
      method: 'POST',
      body: JSON.stringify({
        policy_id: policyId,
        question,
      }),
    });
  },

  async getChatHistory(policyId: string): Promise<ConversationHistoryResponse> {
    return request<ConversationHistoryResponse>(`/qa/history/${policyId}`);
  },

  async clearChatHistory(policyId: string): Promise<{ success: boolean; deleted_conversations: number }> {
    return request<{ success: boolean; deleted_conversations: number }>(`/qa/history/${policyId}`, {
      method: 'DELETE',
    });
  },

  // Scenarios
  async evaluateScenario(params: {
    policy_id: string;
    ailment: string;
    elapsed_months: number;
    elapsed_days?: number;
    member_age: number;
    scenario_type: string;
  }): Promise<ScenarioResponse> {
    return request<ScenarioResponse>('/scenarios/evaluate', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async getScenarioHistory(policyId?: string): Promise<ScenarioRecord[]> {
    const query = policyId ? `?policy_id=${encodeURIComponent(policyId)}` : '';
    return request<ScenarioRecord[]>(`/scenarios/history${query}`);
  },

  // Comparison
  async comparePolicies(params: {
    policy_id_a: string;
    policy_id_b: string;
    continuous_months: number;
    member_age: number;
  }): Promise<ComparisonResponse> {
    return request<ComparisonResponse>('/comparison/compare', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  // Dashboard
  async getDashboardSummary(): Promise<DashboardSummaryResponse> {
    return request<DashboardSummaryResponse>('/dashboard/summary');
  },

  // Claim Rehearsal
  async rehearseClaim(params: ClaimRehearsalRequest): Promise<ClaimRehearsalResponse> {
    return request<ClaimRehearsalResponse>('/claim-rehearsal/rehearse', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async getClaimRehearsalHistory(policyId?: string): Promise<ClaimRehearsalRecord[]> {
    const query = policyId ? `?policy_id=${encodeURIComponent(policyId)}` : '';
    return request<ClaimRehearsalRecord[]>(`/claim-rehearsal/history${query}`);
  },
};
