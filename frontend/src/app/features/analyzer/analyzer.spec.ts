import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { ApiService, FormAnalysis } from '../../core/api.service';
import { LiveService } from '../../core/live.service';
import { AnalyzerComponent } from './analyzer';

const analysis = {
  id: 9,
  target: 'https://example.com',
  status: 'COMPLETED',
  analysis_type: 'form_scan',
  created_at: '2026-09-12T10:00:00',
  started_at: null,
  finished_at: null,
  error_message: null,
  forms: [],
  oauth_flows: [],
  session_cookies: [],
} as unknown as FormAnalysis;

describe('AnalyzerComponent', () => {
  let fixture: ComponentFixture<AnalyzerComponent>;
  let component: any;
  const apiStub = {
    discoverForms: vi.fn(),
    getAnalysis: vi.fn(),
    liveUrl: vi.fn((target: string) => `ws://test/api/forms/live?target=${target}`),
  };
  const liveStub = { connect: vi.fn() };

  beforeEach(async () => {
    localStorage.clear();
    apiStub.discoverForms.mockReset();
    apiStub.getAnalysis.mockReset();
    liveStub.connect.mockReset();

    await TestBed.configureTestingModule({
      imports: [AnalyzerComponent],
      providers: [
        provideRouter([]),
        { provide: ApiService, useValue: apiStub },
        { provide: LiveService, useValue: liveStub },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(AnalyzerComponent);
    component = fixture.componentInstance;
  });

  it('should run the synchronous REST fallback and load the analysis', () => {
    apiStub.discoverForms.mockReturnValue(
      of({
        analysis,
        form_count: 2,
        oauth_flow_count: 1,
        session_cookie_count: 3,
      }),
    );

    component.target = 'example.com';
    component.analyze();

    expect(apiStub.discoverForms).toHaveBeenCalledWith('example.com');
    expect(component.analysis?.id).toBe(9);
    expect(component.loading).toBe(false);
    expect(component.terminalLines.some((line: string) => line.includes('START REST'))).toBe(true);
  });

  it('should consume live xwa-sdk events and load the persisted analysis', () => {
    apiStub.getAnalysis.mockReturnValue(of(analysis));
    liveStub.connect.mockReturnValue(
      of(
        {
          seq: 1,
          type: 'analysis_started',
          tool: 'azuma',
          analysis_id: '9',
          ts: '2026-09-12T10:00:00Z',
          payload: { target: 'example.com' },
        },
        {
          seq: 2,
          type: 'analysis_progress',
          tool: 'azuma',
          analysis_id: '9',
          ts: '2026-09-12T10:00:01Z',
          payload: { page: 'https://example.com/', title: 'Example' },
        },
        {
          seq: 3,
          type: 'item_found',
          tool: 'azuma',
          analysis_id: '9',
          ts: '2026-09-12T10:00:02Z',
          payload: { kind: 'form', method: 'POST', action: '/login', fields: 2, csrf: 1 },
        },
        {
          seq: 4,
          type: 'item_found',
          tool: 'azuma',
          analysis_id: '9',
          ts: '2026-09-12T10:00:03Z',
          payload: { kind: 'oauth_flow', endpoint: '/oauth/authorize', flow_type: 'code' },
        },
        {
          seq: 5,
          type: 'item_found',
          tool: 'azuma',
          analysis_id: '9',
          ts: '2026-09-12T10:00:04Z',
          payload: { kind: 'session_cookie', name: 'sessionid', secure: true },
        },
        {
          seq: 6,
          type: 'analysis_completed',
          tool: 'azuma',
          analysis_id: '9',
          ts: '2026-09-12T10:00:05Z',
          payload: { form_count: 1 },
        },
      ),
    );

    component.target = 'example.com';
    component.runLive();

    expect(liveStub.connect).toHaveBeenCalledWith('ws://test/api/forms/live?target=example.com');
    expect(
      component.terminalLines.some((line: string) => line.includes('+ FORM POST /login')),
    ).toBe(true);
    expect(
      component.terminalLines.some((line: string) => line.includes('+ OAUTH /oauth/authorize')),
    ).toBe(true);
    expect(
      component.terminalLines.some((line: string) => line.includes('+ COOKIE sessionid secure=YES')),
    ).toBe(true);
    expect(component.analysis?.id).toBe(9);
    expect(component.liveRunning).toBe(false);
    expect(component.phaseState.cookies).toBe('done');
  });

  it('should surface analysis_error events inline (top-level xwa-sdk Error payload)', () => {
    liveStub.connect.mockReturnValue(
      of({
        seq: 2,
        type: 'analysis_error',
        tool: 'azuma',
        analysis_id: '9',
        ts: '2026-09-12T10:00:00Z',
        payload: { code: 'TARGET_ERROR', message: 'TLS handshake failed', retryable: true },
      }),
    );

    component.target = 'bad.example';
    component.runLive();

    expect(component.error).toContain('TLS handshake failed');
    expect(component.liveRunning).toBe(false);
  });

  it('should also tolerate a nested REST-style error payload', () => {
    liveStub.connect.mockReturnValue(
      of({
        seq: 2,
        type: 'analysis_error',
        tool: 'azuma',
        analysis_id: '9',
        ts: '2026-09-12T10:00:00Z',
        payload: { error: { code: 'TARGET_ERROR', message: 'nested failure' } },
      }),
    );

    component.target = 'bad.example';
    component.runLive();

    expect(component.error).toContain('nested failure');
  });
});
