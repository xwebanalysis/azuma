import { FormAnalysis } from './api.service';
import { analysisToCsv } from './export.service';

const analysis = {
  id: 5,
  target: 'https://example.com',
  status: 'COMPLETED',
  analysis_type: 'form_scan',
  created_at: '2026-09-12T10:00:00',
  started_at: null,
  finished_at: null,
  error_message: null,
  forms: [
    {
      id: 1,
      page_url: 'https://example.com/login',
      action: '/login',
      method: 'POST',
      enctype: 'application/x-www-form-urlencoded',
      is_secure: true,
      redirect_chain: JSON.stringify([
        { url: 'https://example.com/login', status: 302 },
        { url: 'https://example.com/', status: 200 },
      ]),
      fields: [
        {
          id: 1,
          name: 'email',
          input_type: 'email',
          value: null,
          required: true,
          autocomplete: 'email',
          placeholder: null,
          is_csrf: false,
        },
        {
          id: 2,
          name: 'csrf_token',
          input_type: 'hidden',
          value: 'abc',
          required: false,
          autocomplete: null,
          placeholder: null,
          is_csrf: true,
        },
      ],
    },
  ],
  oauth_flows: [
    {
      id: 1,
      endpoint: 'https://accounts.example.com/oauth/authorize',
      flow_type: 'authorization_code',
      client_id: 'client-1',
      redirect_uri: 'https://example.com/callback',
      scope: 'openid',
      uses_state: true,
      weakness: null,
    },
  ],
  session_cookies: [
    {
      id: 1,
      name: 'sessionid',
      value_preview: 'abc123',
      domain: 'example.com',
      path: '/',
      http_only: true,
      secure: true,
      same_site: 'Lax',
      max_age: '3600',
    },
  ],
} as unknown as FormAnalysis;

describe('analysisToCsv', () => {
  it('should emit one row per field plus OAuth and cookie rows', () => {
    const lines = analysisToCsv(analysis).split('\n');
    expect(lines).toHaveLength(5);
    expect(lines[0]).toContain('kind,analysis_id,target,page_url,method,action');
    expect(lines[1]).toContain('form,5,https://example.com,https://example.com/login,POST,/login');
    expect(lines[1]).toContain('email,email,1,0,email');
    expect(lines[2]).toContain('csrf_token,hidden,0,1');
    expect(lines[3]).toContain('oauth_flow,5,https://example.com');
    expect(lines[3]).toContain('authorization_code,client-1');
    expect(lines[4]).toContain('session_cookie,5,https://example.com');
    expect(lines[4]).toContain('sessionid,example.com,/,1,1,Lax,3600');
  });

  it('should emit a form row even when the form has no fields', () => {
    const lines = analysisToCsv({
      ...analysis,
      forms: [{ ...analysis.forms[0], fields: [] }],
      oauth_flows: [],
      session_cookies: [],
    }).split('\n');
    expect(lines).toHaveLength(2);
    expect(lines[1]).toContain('form,5,https://example.com');
  });
});
