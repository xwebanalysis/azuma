import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';

export type ExportFormat = 'json' | 'csv';

export interface FormField {
  id: number;
  name: string | null;
  input_type: string | null;
  value: string | null;
  required: boolean;
  autocomplete: string | null;
  placeholder: string | null;
  is_csrf: boolean;
}

export interface Form {
  id: number;
  page_url: string | null;
  action: string | null;
  method: string;
  enctype: string | null;
  is_secure: boolean;
  redirect_chain: string | null;
  fields: FormField[];
}

export interface OAuthFlow {
  id: number;
  endpoint: string | null;
  flow_type: string | null;
  client_id: string | null;
  redirect_uri: string | null;
  scope: string | null;
  uses_state: boolean;
  weakness: string | null;
}

export interface SessionCookie {
  id: number;
  name: string | null;
  value_preview: string | null;
  domain: string | null;
  path: string | null;
  http_only: boolean;
  secure: boolean;
  same_site: string | null;
  max_age: string | null;
}

export interface FormAnalysis {
  id: number;
  target: string;
  status: string;
  analysis_type: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  forms: Form[];
  oauth_flows: OAuthFlow[];
  session_cookies: SessionCookie[];
}

export interface AnalysisListItem {
  id: number;
  target: string;
  status: string;
  analysis_type: string;
  created_at: string;
  form_count: number;
  oauth_flow_count: number;
  session_cookie_count: number;
}

export interface DiscoverResponse {
  analysis: FormAnalysis;
  form_count: number;
  oauth_flow_count: number;
  session_cookie_count: number;
}

export interface HealthResponse {
  status: string;
  database: string;
  version: string;
  tool: string;
}

/** xwa-sdk Event envelope as received over the WebSocket. */
export interface LiveEvent {
  seq: number;
  type: string;
  tool: string;
  analysis_id: string;
  ts: string;
  payload: unknown;
}

/** Payload shapes emitted by the azuma live stream. */
export interface StartedPayload {
  target?: string;
}

export interface ProgressPayload {
  page?: string;
  title?: string | null;
}

export interface ItemFoundPayload {
  kind?: string;
  method?: string;
  action?: string | null;
  fields?: number;
  csrf?: number;
  endpoint?: string | null;
  flow_type?: string | null;
  name?: string | null;
  secure?: boolean;
}

export interface LiveErrorPayload {
  /** xwa-sdk Error object emitted top-level by the backend. */
  code?: string;
  message?: string;
  retryable?: boolean;
  /** Also tolerate a nested REST-style `{ error: { message } }` payload. */
  error?: {
    code?: string;
    message?: string;
    retryable?: boolean;
  };
}

/** Known live event types of the xwa-sdk Event contract. */
export const LIVE_EVENT_TYPES = [
  'analysis_started',
  'analysis_progress',
  'item_found',
  'analysis_completed',
  'analysis_error',
] as const;

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiBaseUrl;
  private readonly wsUrl = environment.wsBaseUrl;

  health(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${this.apiUrl}/api/health`);
  }

  /** Synchronous REST fallback (the live WebSocket is the preferred path). */
  discoverForms(target: string): Observable<DiscoverResponse> {
    return this.http.post<DiscoverResponse>(`${this.apiUrl}/api/forms/discover`, {
      target,
    });
  }

  listAnalyses(): Observable<AnalysisListItem[]> {
    return this.http.get<AnalysisListItem[]>(`${this.apiUrl}/api/analyses`);
  }

  getAnalysis(id: number | string): Observable<FormAnalysis> {
    return this.http.get<FormAnalysis>(`${this.apiUrl}/api/analyses/${id}`);
  }

  deleteAnalysis(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/api/analyses/${id}`);
  }

  deleteAllAnalyses(): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/api/analyses`);
  }

  /** Server-side export URL (Content-Disposition attachment). */
  exportUrl(id: number, format: ExportFormat = 'json'): string {
    return `${this.apiUrl}/api/analyses/${id}/export?format=${format}`;
  }

  /** Live WebSocket endpoint (target URL-encoded). */
  liveUrl(target: string): string {
    return `${this.wsUrl}/api/forms/live?target=${encodeURIComponent(target)}`;
  }
}
