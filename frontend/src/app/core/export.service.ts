import { Injectable } from '@angular/core';

import { Form, FormAnalysis } from './api.service';

const CSV_HEADER = [
  'kind',
  'analysis_id',
  'target',
  'page_url',
  'method',
  'action',
  'enctype',
  'is_secure',
  'field_name',
  'field_type',
  'field_required',
  'field_csrf',
  'field_autocomplete',
  'endpoint',
  'flow_type',
  'client_id',
  'redirect_uri',
  'scope',
  'uses_state',
  'weakness',
  'cookie_name',
  'cookie_domain',
  'cookie_path',
  'http_only',
  'secure',
  'same_site',
  'max_age',
];

/** Build the client-side CSV export for a form analysis. */
export function analysisToCsv(analysis: FormAnalysis): string {
  const rows: (string | number)[][] = [[...CSV_HEADER]];
  const base = [analysis.id, analysis.target];

  for (const form of analysis.forms) {
    const formBase = [
      'form',
      ...base,
      form.page_url ?? '',
      form.method ?? '',
      form.action ?? '',
      form.enctype ?? '',
      form.is_secure ? 1 : 0,
    ];
    if (form.fields.length === 0) {
      rows.push(formBase);
    }
    for (const field of form.fields) {
      rows.push([
        ...formBase,
        field.name ?? '',
        field.input_type ?? '',
        field.required ? 1 : 0,
        field.is_csrf ? 1 : 0,
        field.autocomplete ?? '',
      ]);
    }
  }

  for (const flow of analysis.oauth_flows) {
    rows.push([
      'oauth_flow',
      ...base,
      '', '', '', '', '',
      '', '', '', '', '',
      flow.endpoint ?? '',
      flow.flow_type ?? '',
      flow.client_id ?? '',
      flow.redirect_uri ?? '',
      flow.scope ?? '',
      flow.uses_state ? 1 : 0,
      flow.weakness ?? '',
    ]);
  }

  for (const cookie of analysis.session_cookies) {
    rows.push([
      'session_cookie',
      ...base,
      '', '', '', '', '',
      '', '', '', '', '',
      '', '', '', '', '', '',
      '',
      cookie.name ?? '',
      cookie.domain ?? '',
      cookie.path ?? '',
      cookie.http_only ? 1 : 0,
      cookie.secure ? 1 : 0,
      cookie.same_site ?? '',
      cookie.max_age ?? '',
    ]);
  }

  return rows.map((row) => row.map((cell) => escapeCsv(cell)).join(',')).join('\n');
}

function escapeCsv(value: string | number): string {
  const text = String(value ?? '');
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

/**
 * Client-side exports: JSON/CSV blobs and a jsPDF report. The PDF dependency is
 * loaded lazily so the initial bundle stays lean and tests never need jsPDF.
 */
@Injectable({ providedIn: 'root' })
export class ExportService {
  downloadJson(analysis: FormAnalysis): void {
    const blob = new Blob([JSON.stringify(analysis, null, 2)], {
      type: 'application/json;charset=utf-8',
    });
    this.download(blob, `azuma-analysis-${analysis.id}.json`);
  }

  downloadCsv(analysis: FormAnalysis): void {
    this.download(
      new Blob([analysisToCsv(analysis)], { type: 'text/csv;charset=utf-8' }),
      `azuma-analysis-${analysis.id}.csv`,
    );
  }

  async downloadPdf(analysis: FormAnalysis): Promise<void> {
    const { jsPDF } = await import('jspdf');
    const doc = new jsPDF({ unit: 'pt', format: 'a4' });
    const margin = 48;
    let y = margin;

    const line = (text: string, size = 9, style: 'normal' | 'bold' = 'normal', gap = 14) => {
      doc.setFont('courier', style);
      doc.setFontSize(size);
      const wrapped = doc.splitTextToSize(text, 595 - margin * 2) as string[];
      for (const chunk of wrapped) {
        if (y > 800) {
          doc.addPage();
          y = margin;
        }
        doc.text(chunk, margin, y);
        y += gap;
      }
    };

    line('AZUMA / FORM & AUTH FLOW ANALYSIS', 16, 'bold', 20);
    line(`ANALYSIS #${analysis.id}`, 11, 'bold');
    line(`TARGET:   ${analysis.target}`);
    line(`STATUS:   ${analysis.status}`);
    line(`CREATED:  ${analysis.created_at}`);
    y += 8;

    const fieldCount = analysis.forms.reduce((total, form) => total + form.fields.length, 0);
    line('SUMMARY', 11, 'bold');
    line(`FORMS:        ${analysis.forms.length}`);
    line(`FIELDS:       ${fieldCount}`);
    line(`OAUTH FLOWS:  ${analysis.oauth_flows.length}`);
    line(`COOKIES:      ${analysis.session_cookies.length}`);
    y += 8;

    line('FORMS', 11, 'bold');
    for (const form of analysis.forms) {
      line(
        `- ${form.method} ${form.action ?? '(no action)'} ` +
          `[${form.is_secure ? 'HTTPS' : 'HTTP'}] fields=${form.fields.length} ` +
          `csrf=${form.fields.filter((field) => field.is_csrf).length}`,
      );
      if (form.page_url) {
        line(`  page: ${form.page_url}`, 8, 'normal', 12);
      }
      for (const field of form.fields) {
        line(
          `  ${field.input_type ?? 'text'} ${field.name ?? '(unnamed)'}` +
            `${field.required ? ' required' : ''}${field.is_csrf ? ' csrf' : ''}`,
          8,
          'normal',
          12,
        );
      }
    }
    y += 4;

    line('OAUTH FLOWS', 11, 'bold');
    for (const flow of analysis.oauth_flows) {
      line(
        `- ${flow.endpoint ?? 'n/a'} [${flow.flow_type ?? 'unknown'}] ` +
          `state=${flow.uses_state ? 'yes' : 'no'}${flow.weakness ? ` weakness=${flow.weakness}` : ''}`,
      );
    }
    y += 4;

    line('SESSION COOKIES', 11, 'bold');
    for (const cookie of analysis.session_cookies) {
      line(
        `- ${cookie.name ?? 'unnamed'} [${cookie.http_only ? 'httponly' : 'no-httponly'} / ` +
          `${cookie.secure ? 'secure' : 'no-secure'} / samesite=${cookie.same_site ?? 'n/a'}]`,
      );
    }

    doc.save(`azuma-analysis-${analysis.id}.pdf`);
  }

  /** GET redirect chain summary for a form (`status url -> status url`). */
  redirectSummary(form: Form): string {
    if (!form.redirect_chain) {
      return '';
    }
    try {
      const chain = JSON.parse(form.redirect_chain) as { url: string; status: number }[];
      return chain.map((hop) => `${hop.status} ${hop.url}`).join(' → ');
    } catch {
      return '';
    }
  }

  private download(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.rel = 'noopener';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }
}
