import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, Input, OnInit, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { ApiService, Form, FormAnalysis } from '../../core/api.service';
import { ExportService } from '../../core/export.service';
import { I18nService } from '../../core/i18n.service';
import { DetailColumn, DetailTableComponent } from '../../shared/detail-table/detail-table';
import { ExportActionsComponent } from '../../shared/export-actions/export-actions';
import { MetricCardComponent } from '../../shared/metric-card/metric-card';
import { StatusBadgeComponent } from '../../shared/status-badge/status-badge';

@Component({
  selector: 'app-analysis-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    DetailTableComponent,
    ExportActionsComponent,
    MetricCardComponent,
    StatusBadgeComponent,
  ],
  templateUrl: './detail.html',
  styleUrl: './detail.scss',
})
export class AnalysisDetailComponent implements OnInit {
  @Input() analysis: FormAnalysis | null = null;

  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ApiService);
  private readonly i18n = inject(I18nService);
  private readonly exporter = inject(ExportService);
  private readonly cdr = inject(ChangeDetectorRef);

  protected loading = false;
  protected error: string | null = null;
  protected routeView = false;

  protected readonly fieldColumns: DetailColumn[] = [
    { key: 'input_type', label: 'TYPE' },
    { key: 'name', label: 'NAME' },
    { key: 'required', label: 'REQUIRED' },
    { key: 'is_csrf', label: 'CSRF' },
    { key: 'autocomplete', label: 'AUTOCOMPLETE' },
  ];

  protected readonly oauthColumns: DetailColumn[] = [
    { key: 'endpoint', label: 'ENDPOINT' },
    { key: 'flow_type', label: 'FLOW' },
    { key: 'client_id', label: 'CLIENT' },
    { key: 'redirect_uri', label: 'REDIRECT URI' },
    { key: 'scope', label: 'SCOPE' },
    { key: 'uses_state', label: 'STATE' },
    { key: 'weakness', label: 'WEAKNESS' },
  ];

  protected readonly cookieColumns: DetailColumn[] = [
    { key: 'name', label: 'NAME' },
    { key: 'value_preview', label: 'VALUE' },
    { key: 'domain', label: 'DOMAIN' },
    { key: 'path', label: 'PATH' },
    { key: 'http_only', label: 'HTTPONLY' },
    { key: 'secure', label: 'SECURE' },
    { key: 'same_site', label: 'SAMESITE' },
    { key: 'max_age', label: 'MAX-AGE' },
  ];

  ngOnInit(): void {
    if (this.analysis) {
      return;
    }
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) {
      return;
    }
    this.routeView = true;
    this.loading = true;
    this.error = null;
    this.api.getAnalysis(id).subscribe({
      next: (analysis) => {
        this.analysis = analysis;
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.error = this.i18n.t('error.backend');
        this.loading = false;
        this.cdr.markForCheck();
      },
    });
  }

  protected t(key: string): string {
    return this.i18n.t(key);
  }

  protected csrfCount(form: Form): number {
    return form.fields.filter((field) => field.is_csrf).length;
  }

  protected redirectSummary(form: Form): string {
    return this.exporter.redirectSummary(form);
  }

  protected fieldCount(): number {
    return this.analysis?.forms.reduce((total, form) => total + form.fields.length, 0) ?? 0;
  }

  protected counts(): { forms: number; fields: number; oauth: number; cookies: number } {
    return {
      forms: this.analysis?.forms.length ?? 0,
      fields: this.fieldCount(),
      oauth: this.analysis?.oauth_flows.length ?? 0,
      cookies: this.analysis?.session_cookies.length ?? 0,
    };
  }
}
