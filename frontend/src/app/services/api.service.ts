import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface FormField {
  id: number;
  name: string | null;
  input_type: string | null;
  required: boolean;
  autocomplete: string | null;
  placeholder: string | null;
}

export interface Form {
  id: number;
  page_url: string | null;
  action: string | null;
  method: string;
  enctype: string | null;
  is_secure: boolean;
  fields: FormField[];
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
}

export interface DiscoverResponse {
  analysis: FormAnalysis;
  form_count: number;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = 'http://localhost:8000';

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
}
