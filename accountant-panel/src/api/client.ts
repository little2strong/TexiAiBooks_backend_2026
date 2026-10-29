import { session } from '../auth/session';
import type { Config, Dashboard, Overview, Receipt, Staff, TableQuery, TaxResult, VerifyResult, SavedView } from './types';

export class ApiError extends Error {
  constructor(public statusCode: number, message: string) { super(message); this.name = 'ApiError'; }
}

export const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
if (!baseUrl.startsWith('/') && !baseUrl.startsWith('https://')) throw new Error('Use a same-origin path or HTTPS API URL');

type RequestOptions = { method?: string; body?: unknown; signal?: AbortSignal; public?: boolean; binary?: boolean; idempotent?: boolean };
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers({ Accept: options.binary ? '*/*' : 'application/json' });
  const token = session.token();
  if (!options.public) {
    if (!token) throw new ApiError(401, 'Your session has ended. Sign in again.');
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (options.idempotent) headers.set('Idempotency-Key', crypto.randomUUID());
  const isForm = options.body instanceof FormData;
  if (options.body !== undefined && !isForm) headers.set('Content-Type', 'application/json');
  let response: Response;
  try {
    response = await fetch(baseUrl + path, {
      method: options.method || 'GET', headers, cache: 'no-store', credentials: 'omit',
      body: options.body === undefined ? undefined : isForm ? options.body as FormData : JSON.stringify(options.body),
      signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(30000)]) : AbortSignal.timeout(30000),
      referrerPolicy: 'no-referrer',
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError(0, 'Unable to reach the API. Check the connection and try again.');
  }
  if (!response.ok) {
    if (response.status === 401 && !options.public && session.token() === token) session.end();
    const messages: Record<number, string> = {
      401: 'Your credentials or authentication code are invalid or expired.',
      403: 'Your role does not allow this action.',
      404: 'This record is unavailable or outside your assigned drivers.',
      409: 'This record changed or its accounting period is locked. Refresh before continuing.',
      413: 'The file is larger than the server upload limit.',
      422: 'Check the supplied values. The server could not accept this operation.',
      429: 'Too many attempts. Wait before trying again.',
      503: 'This service is not configured or is temporarily unavailable.',
    };
    throw new ApiError(response.status, messages[response.status] || 'The request failed. Please try again.');
  }
  if (response.status === 204) return undefined as T;
  return (options.binary ? response.blob() : response.json()) as Promise<T>;
}

const post = <T>(path: string, body: unknown, signal?: AbortSignal) => request<T>(path, { method: 'POST', body, signal });
export const api = {
  login: (email: string, password: string) => request<{ challenge_id: string; expires_in: number }>('/staff/auth/login', { method: 'POST', body: { email, password }, public: true }),
  verify: (challenge_id: string, code: string) => request<VerifyResult>('/staff/auth/verify', { method: 'POST', body: { challenge_id, code }, public: true }),
  logout: () => request<void>('/staff/auth/logout', { method: 'POST' }),
  me: () => request<Staff>('/staff/me'),
  config: () => request<Config>('/staff/config'),
  dashboard: (tax_year: string, signal?: AbortSignal) => post<Dashboard>('/staff/dashboard', { tax_year }, signal),
  overview: (id: string, tax_year: string, signal?: AbortSignal) => post<Overview>(`/staff/drivers/${id}/overview`, { tax_year }, signal),
  tax: (id: string, tax_year: string, signal?: AbortSignal) => post<TaxResult>(`/staff/drivers/${id}/tax`, { tax_year }, signal),
  receipt: (id: string, receipt: string, signal?: AbortSignal) => request<Receipt>(`/staff/drivers/${id}/receipts/${receipt}`, { signal }),
  reveal: (id: string, body: { tax_year: string; field: 'utr' | 'ni_number'; reason: string }) => post<{ value: string; expires_in: number }>(`/staff/drivers/${id}/identifiers/reveal`, body),
  views: (resource: string) => post<{ items: SavedView[] }>('/staff/views/search', { resource }),
  saveView: (resource: string, name: string, query: TableQuery) => request<SavedView>('/staff/views', { method: 'POST', body: { resource, name, query }, idempotent: true }),
  deleteView: (id: string) => request<void>(`/staff/views/${id}`, { method: 'DELETE' }),
  mutate: <T>(path: string, body: unknown, method = 'POST') => request<T>(`/staff${path}`, { method, body, idempotent: true }),
  blob: (path: string, signal?: AbortSignal) => request<Blob>(`/staff${path}`, { binary: true, signal }),
};

export function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
