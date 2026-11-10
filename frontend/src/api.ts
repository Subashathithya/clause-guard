import { Capacitor } from '@capacitor/core';
import type {
  AnalysisResult,
  AuthResponse,
  ChatMessage,
  ChatResponse,
  CompareResult,
  Contract,
  DriftResult,
  FairClausesResponse,
  Stats,
  User,
} from './types';

/**
 * Set this to your deployed FastAPI backend for the native app (must be HTTPS
 * for a real device). The web build keeps using REACT_APP_API_URL.
 */
export const MOBILE_API_URL = 'https://YOUR-DEPLOYED-BACKEND.example.com';

export const API_URL =
  Capacitor.isNativePlatform()
    ? process.env.REACT_APP_API_URL_MOBILE || MOBILE_API_URL
    : process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

const TOKEN_KEY = 'clauseguard_token';

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string | null): void => {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  },
};

/** Fired when the API receives a 401, so the app can clear the session. */
export const AUTH_EXPIRED_EVENT = 'clauseguard:auth-expired';
export function emitAuthExpired(): void {
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep default */
    }
    if (res.status === 401) emitAuthExpired();
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

function headers(withJson = true, extra?: Record<string, string>): Record<string, string> {
  const token = tokenStore.get();
  const h: Record<string, string> = {};
  if (withJson) h['Content-Type'] = 'application/json';
  if (token) h['Authorization'] = `Bearer ${token}`;
  if (extra) Object.assign(h, extra);
  return h;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { headers: headers(false) });
  return parse<T>(res);
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: headers(true),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return parse<T>(res);
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { method: 'DELETE', headers: headers(false) });
  return parse<T>(res);
}

export const api = {
  // ------------------------------------------------ auth
  async register(email: string, password: string, fullName: string): Promise<AuthResponse> {
    return post<AuthResponse>('/auth/register', { email, password, full_name: fullName });
  },
  async login(email: string, password: string): Promise<AuthResponse> {
    return post<AuthResponse>('/auth/login', { email, password });
  },
  async me(): Promise<User> {
    return get<User>('/auth/me');
  },

  // ------------------------------------------------ analysis
  async analyze(text: string, documentName: string): Promise<AnalysisResult> {
    return post<AnalysisResult>('/analyze', { text, document_name: documentName });
  },

  async upload(file: File, documentName: string): Promise<AnalysisResult> {
    const form = new FormData();
    form.append('file', file);
    form.append('document_name', documentName || file.name);
    const res = await fetch(`${API_URL}/upload`, {
      method: 'POST',
      headers: headers(false),
      body: form,
    });
    return parse<AnalysisResult>(res);
  },

  // ------------------------------------------------ contracts
  async contracts(): Promise<Contract[]> {
    const data = await get<{ contracts: Contract[] }>('/contracts');
    return data.contracts || [];
  },
  async getAnalysis(id: string): Promise<AnalysisResult> {
    return get<AnalysisResult>(`/contracts/${id}`);
  },
  async deleteContract(id: string): Promise<void> {
    await del<{ status: string }>(`/contracts/${id}`);
  },
  async history(): Promise<Contract[]> {
    const data = await get<{ count: number; analyses: Contract[] }>('/history');
    return data.analyses || [];
  },
  async stats(): Promise<Stats> {
    return get<Stats>('/stats');
  },

  // ------------------------------------------------ chat / compare
  async chat(
    question: string,
    documentIds: string[],
    history: ChatMessage[] = []
  ): Promise<ChatResponse> {
    return post<ChatResponse>('/chat', { question, document_ids: documentIds, history });
  },
  async compare(documentIds: string[]): Promise<CompareResult> {
    return post<CompareResult>('/compare', { document_ids: documentIds });
  },
  async drift(documentIds: string[]): Promise<DriftResult> {
    return post<DriftResult>('/drift', { document_ids: documentIds });
  },

  // ------------------------------------------------ knowledge
  async fairClauses(): Promise<FairClausesResponse> {
    return get<FairClausesResponse>('/fair-clauses?limit=5');
  },

  // ------------------------------------------------ system
  async health(): Promise<{
    status: string;
    version: string;
    model: string;
    auth_required: boolean;
    rag: { documents_indexed: number; fair_clauses: number };
  }> {
    return get('/health');
  },
};

export type Api = typeof api;