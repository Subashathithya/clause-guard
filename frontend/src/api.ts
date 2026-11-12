import { Capacitor } from '@capacitor/core';
import type {
  AnalysisResult,
  AuthResponse,
  Bookmark,
  ChatMessage,
  ChatResponse,
  ChecklistItem,
  CompareResult,
  Contract,
  ContractDate,
  ContractDateInput,
  DriftResult,
  FairClausesResponse,
  Reminder,
  Stats,
  User,
} from './types';
import { translateNow } from './i18n';

/**
 * Native builds talk to the deployed FastAPI backend (HTTPS is required on a
 * real device). Override per build with REACT_APP_API_URL_MOBILE; the web build
 * keeps using REACT_APP_API_URL.
 */
export const MOBILE_API_URL = 'https://clauseguard-api.onrender.com';

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

/** Friendly text for the failures a non-technical person can actually hit. */
function friendlyError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err ?? '');
  if (/failed to fetch|networkerror|load failed/i.test(raw)) {
    return translateNow('common.networkError');
  }
  if (/timeout/i.test(raw)) {
    return translateNow('common.timeoutError');
  }
  return raw;
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch (err) {
    // A dropped connection is the most common failure on a phone; it should
    // never look like a server error.
    throw new ApiError(0, friendlyError(err));
  }
  return parse<T>(res);
}

async function get<T>(path: string): Promise<T> {
  return request<T>(path, { headers: headers(false) });
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: headers(true),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

async function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE', headers: headers(false) });
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PATCH',
    headers: headers(true),
    body: JSON.stringify(body),
  });
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

  // ------------------------------------------------ tracking (Phase 4)
  async contractDates(id: string): Promise<ContractDate[]> {
    const data = await get<{ dates: ContractDate[] }>(`/contracts/${id}/dates`);
    return data.dates || [];
  },
  async addContractDate(id: string, input: ContractDateInput): Promise<ContractDate> {
    return post<ContractDate>(`/contracts/${id}/dates`, input);
  },
  async updateContractDate(
    id: string,
    dateId: string,
    input: Partial<ContractDateInput>
  ): Promise<ContractDate> {
    return patch<ContractDate>(`/contracts/${id}/dates/${dateId}`, input);
  },
  async deleteContractDate(id: string, dateId: string): Promise<void> {
    await del<{ status: string }>(`/contracts/${id}/dates/${dateId}`);
  },
  async reminders(days = 30): Promise<Reminder[]> {
    const data = await get<{ reminders: Reminder[] }>(`/reminders?days=${days}`);
    return data.reminders || [];
  },
  async bookmarks(id: string): Promise<Bookmark[]> {
    const data = await get<{ bookmarks: Bookmark[] }>(`/contracts/${id}/bookmarks`);
    return data.bookmarks || [];
  },
  async addBookmark(id: string, clauseIndex: string, note = ''): Promise<Bookmark> {
    return post<Bookmark>(`/contracts/${id}/bookmarks`, { clause_index: clauseIndex, note });
  },
  async deleteBookmark(id: string, bookmarkId: string): Promise<void> {
    await del<{ status: string }>(`/contracts/${id}/bookmarks/${bookmarkId}`);
  },
  async checklist(id: string): Promise<ChecklistItem[]> {
    const data = await get<{ items: ChecklistItem[] }>(`/contracts/${id}/checklist`);
    return data.items || [];
  },
  async addChecklistItem(id: string, text: string, clauseIndex?: string | null): Promise<ChecklistItem> {
    return post<ChecklistItem>(`/contracts/${id}/checklist`, {
      text,
      clause_index: clauseIndex ?? null,
    });
  },
  async generateChecklist(id: string): Promise<{ added: number; items: ChecklistItem[] }> {
    return post<{ added: number; items: ChecklistItem[] }>(`/contracts/${id}/checklist/generate`);
  },
  async updateChecklistItem(
    id: string,
    itemId: string,
    input: { text?: string; done?: boolean }
  ): Promise<ChecklistItem> {
    return patch<ChecklistItem>(`/contracts/${id}/checklist/${itemId}`, input);
  },
  async deleteChecklistItem(id: string, itemId: string): Promise<void> {
    await del<{ status: string }>(`/contracts/${id}/checklist/${itemId}`);
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