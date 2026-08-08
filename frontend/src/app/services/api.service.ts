import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

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

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `http://${window.location.hostname}:8000`;

  health(): Observable<{ status: string; database: string; version: string }> {
    return this.http.get<{ status: string; database: string; version: string }>(
      `${this.apiUrl}/api/health`,
    );
  }

  discoverForms(target: string): Observable<DiscoverResponse> {
    return this.http.post<DiscoverResponse>(
      `${this.apiUrl}/api/forms/discover`,
      { target },
    );
  }

  listAnalyses(): Observable<AnalysisListItem[]> {
    return this.http.get<AnalysisListItem[]>(`${this.apiUrl}/api/analyses`);
  }

  getAnalysis(id: number): Observable<FormAnalysis> {
    return this.http.get<FormAnalysis>(`${this.apiUrl}/api/analyses/${id}`);
  }
}
