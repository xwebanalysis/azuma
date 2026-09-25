import { Injectable, signal } from '@angular/core';

export type Locale = 'en' | 'es';

const TRANSLATIONS: Record<Locale, Record<string, string>> = {
  en: {
    'app.tagline': 'XWA - MODULE',
    'nav.analyzer': 'ANALYZER',
    'nav.history': 'HISTORY',
    'nav.exports': 'EXPORTS',
    'dashboard.title': 'FORM & AUTH ANALYSIS',
    'dashboard.subtitle': 'FORM DISCOVERY / OAUTH MAPPING / SESSION ANALYSIS',
    'target.label': 'TARGET',
    'target.placeholder': 'https://example.com',
    'action.analyze': 'ANALYZE',
    'action.live': 'LIVE STREAM',
    'action.cancel': 'CANCEL',
    'action.analyzing': 'ANALYZING...',
    'action.delete': 'DELETE',
    'action.delete_all': 'DELETE ALL',
    'action.back': 'BACK',
    'error.backend': 'FAILED TO REACH THE BACKEND',
    'terminal.title': 'LIVE LOG',
    'terminal.empty': '[ NO EVENTS YET ]',
    'phase.connect': 'CONNECT',
    'phase.fetch': 'FETCH',
    'phase.forms': 'FORMS',
    'phase.oauth': 'OAUTH',
    'phase.cookies': 'COOKIES',
    'phase.complete': 'COMPLETE',
    'metric.forms': 'FORMS',
    'metric.fields': 'FIELDS',
    'metric.oauth': 'OAUTH FLOWS',
    'metric.cookies': 'COOKIES',
    'history.title': 'HISTORY',
    'history.subtitle': 'RECENT ANALYSES',
    'history.empty': '[ NO ANALYSES YET ]',
    'detail.loading': '[ LOADING... ]',
    'detail.forms': 'FORMS',
    'detail.oauth': 'OAUTH FLOWS',
    'detail.cookies': 'SESSION COOKIES',
    'detail.no_forms': '[ NO FORMS DISCOVERED ]',
    'detail.no_oauth': '[ NO OAUTH FLOWS DETECTED ]',
    'detail.no_cookies': '[ NO SESSION COOKIES PROFILED ]',
    'detail.fields': 'FIELD(S)',
    'detail.csrf': 'CSRF',
    'detail.redirect': 'REDIRECT CHAIN',
    'detail.no_action': '(NO ACTION)',
    'detail.findings': 'SESSION FINDINGS',
    'detail.no_findings': '[ NO SESSION FINDINGS ]',
    'chart.fields_per_form': 'FIELDS PER FORM',
    'chart.cookie_flags': 'COOKIE FLAGS PRESENT',
    'chart.weakness_severity': 'WEAKNESS SEVERITY',
    'chart.scans_per_day': 'SCANS PER DAY',
    'chart.status': 'STATUS',
    'exports.title': 'EXPORTS',
    'exports.subtitle': 'SERVER-SIDE AND CLIENT-SIDE DOWNLOADS',
    'exports.empty': '[ NO ANALYSES YET ]',
    'exports.server_json': 'SERVER JSON',
    'exports.server_csv': 'SERVER CSV',
    'exports.client_json': 'CLIENT JSON',
    'exports.client_pdf': 'CLIENT PDF',
  },
  es: {
    'app.tagline': 'XWA - MODULO',
    'nav.analyzer': 'ANALIZADOR',
    'nav.history': 'HISTORIAL',
    'nav.exports': 'EXPORTAR',
    'dashboard.title': 'ANALISIS DE FORMULARIOS Y AUTH',
    'dashboard.subtitle': 'DESCUBRIMIENTO DE FORMULARIOS / OAUTH / SESIONES',
    'target.label': 'OBJETIVO',
    'target.placeholder': 'https://ejemplo.com',
    'action.analyze': 'ANALIZAR',
    'action.live': 'STREAM EN VIVO',
    'action.cancel': 'CANCELAR',
    'action.analyzing': 'ANALIZANDO...',
    'action.delete': 'BORRAR',
    'action.delete_all': 'BORRAR TODO',
    'action.back': 'VOLVER',
    'error.backend': 'NO SE PUDO ALCANZAR EL BACKEND',
    'terminal.title': 'LOG EN VIVO',
    'terminal.empty': '[ SIN EVENTOS TODAVIA ]',
    'phase.connect': 'CONEXION',
    'phase.fetch': 'DESCARGA',
    'phase.forms': 'FORMULARIOS',
    'phase.oauth': 'OAUTH',
    'phase.cookies': 'COOKIES',
    'phase.complete': 'COMPLETO',
    'metric.forms': 'FORMULARIOS',
    'metric.fields': 'CAMPOS',
    'metric.oauth': 'FLUJOS OAUTH',
    'metric.cookies': 'COOKIES',
    'history.title': 'HISTORIAL',
    'history.subtitle': 'ANALISIS RECIENTES',
    'history.empty': '[ SIN ANALISIS TODAVIA ]',
    'detail.loading': '[ CARGANDO... ]',
    'detail.forms': 'FORMULARIOS',
    'detail.oauth': 'FLUJOS OAUTH',
    'detail.cookies': 'COOKIES DE SESION',
    'detail.no_forms': '[ SIN FORMULARIOS ]',
    'detail.no_oauth': '[ SIN FLUJOS OAUTH DETECTADOS ]',
    'detail.no_cookies': '[ SIN COOKIES DE SESION ]',
    'detail.fields': 'CAMPO(S)',
    'detail.csrf': 'CSRF',
    'detail.redirect': 'CADENA DE REDIRECCION',
    'detail.no_action': '(SIN ACTION)',
    'detail.findings': 'HALLAZGOS DE SESION',
    'detail.no_findings': '[ SIN HALLAZGOS DE SESION ]',
    'chart.fields_per_form': 'CAMPOS POR FORMULARIO',
    'chart.cookie_flags': 'FLAGS DE COOKIES PRESENTES',
    'chart.weakness_severity': 'SEVERIDAD DE DEBILIDADES',
    'chart.scans_per_day': 'ANALISIS POR DIA',
    'chart.status': 'ESTADO',
    'exports.title': 'EXPORTAR',
    'exports.subtitle': 'DESCARGAS DEL SERVIDOR Y DEL CLIENTE',
    'exports.empty': '[ SIN ANALISIS TODAVIA ]',
    'exports.server_json': 'JSON SERVIDOR',
    'exports.server_csv': 'CSV SERVIDOR',
    'exports.client_json': 'JSON CLIENTE',
    'exports.client_pdf': 'PDF CLIENTE',
  },
};

@Injectable({ providedIn: 'root' })
export class I18nService {
  private readonly storageKey = 'azuma-locale';
  readonly locale = signal<Locale>(this.readStoredLocale());

  t(key: string): string {
    return TRANSLATIONS[this.locale()][key] ?? key;
  }

  toggle(): void {
    this.setLocale(this.locale() === 'en' ? 'es' : 'en');
  }

  setLocale(locale: Locale): void {
    this.locale.set(locale);
    localStorage.setItem(this.storageKey, locale);
  }

  private readStoredLocale(): Locale {
    const stored = localStorage.getItem(this.storageKey);
    return stored === 'es' ? 'es' : 'en';
  }
}
