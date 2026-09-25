import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, Input, OnInit, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { ApiService, Form, FormAnalysis } from '../../core/api.service';
import { ExportService } from '../../core/export.service';
import { I18nService } from '../../core/i18n.service';
import {
  XwaChartColorKey,
  XwaChartComponent,
  XwaChartDatum,
} from '../../shared/charts/xwa-chart.component';
import { DetailColumn, DetailTableComponent } from '../../shared/detail-table/detail-table';
import { ExportActionsComponent } from '../../shared/export-actions/export-actions';
import { MetricCardComponent } from '../../shared/metric-card/metric-card';
import { StatusBadgeComponent } from '../../shared/status-badge/status-badge';

/** xwa-sdk severity → chart color (CHART-SPEC: medium uses neutral-strong). */
const SEVERITY_COLORS: Record<string, XwaChartColorKey> = {
  critical: 'critical',
  high: 'high',
  medium: 'neutral-strong',
  low: 'low',
  info: 'info',
};

/** Weakness severities only (informational observations excluded from the donut). */
const WEAKNESS_SEVERITIES: readonly XwaChartColorKey[] = ['critical', 'high', 'medium', 'low'];

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
    XwaChartComponent,
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

  protected readonly findingColumns: DetailColumn[] = [
    { key: 'kind', label: 'KIND' },
    { key: 'severity', label: 'SEVERITY' },
    { key: 'title', label: 'TITLE' },
    { key: 'description', label: 'DESCRIPTION' },
    { key: 'method', label: 'METHOD' },
    { key: 'csrf_present', label: 'CSRF' },
    { key: 'target_url', label: 'TARGET' },
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

  protected findingCount(): number {
    return this.analysis?.session_findings.length ?? 0;
  }

  /** CHART-SPEC azuma: one h-bar per discovered form, sized by field count. */
  protected fieldsPerFormData(): XwaChartDatum[] {
    return (this.analysis?.forms ?? []).map((form, index) => ({
      label: form.action ?? `FORM #${index + 1}`,
      value: form.fields.length,
    }));
  }

  /** CHART-SPEC azuma: cookie flag present counts (HttpOnly/Secure/SameSite). */
  protected cookieFlagsData(): XwaChartDatum[] {
    const cookies = this.analysis?.session_cookies ?? [];
    return [
      {
        label: 'HTTPONLY',
        value: cookies.filter((cookie) => cookie.http_only).length,
        color: 'interactive' as XwaChartColorKey,
      },
      {
        label: 'SECURE',
        value: cookies.filter((cookie) => cookie.secure).length,
        color: 'success' as XwaChartColorKey,
      },
      {
        label: 'SAMESITE',
        value: cookies.filter((cookie) => !!cookie.same_site).length,
        color: 'warning' as XwaChartColorKey,
      },
    ];
  }

  /** CHART-SPEC azuma: weakness severity donut (xwa-sdk severities, no info). */
  protected weaknessSeverityData(): XwaChartDatum[] {
    const counts = new Map<string, number>();
    for (const finding of this.analysis?.session_findings ?? []) {
      const severity = String(finding.severity ?? '').toLowerCase();
      if (WEAKNESS_SEVERITIES.includes(severity as XwaChartColorKey)) {
        counts.set(severity, (counts.get(severity) ?? 0) + 1);
      }
    }
    return WEAKNESS_SEVERITIES.filter((severity) => counts.has(severity)).map((severity) => ({
      label: severity.toUpperCase(),
      value: counts.get(severity) ?? 0,
      color: SEVERITY_COLORS[severity],
    }));
  }
}
