import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { ApiService } from './api.service';

describe('ApiService', () => {
  let service: ApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should GET the health endpoint', () => {
    service.health().subscribe((health) => {
      expect(health.tool).toBe('azuma');
      expect(health.database).toBe('ok');
    });

    const request = httpMock.expectOne('http://localhost:8030/api/health');
    expect(request.request.method).toBe('GET');
    request.flush({ status: 'ok', database: 'ok', version: '0.3.0', tool: 'azuma' });
  });

  it('should POST the form discovery payload', () => {
    service.discoverForms('example.com').subscribe();

    const request = httpMock.expectOne('http://localhost:8030/api/forms/discover');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ target: 'example.com' });
    request.flush({ analysis: { id: 1 }, form_count: 0 });
  });

  it('should build server-side export URLs', () => {
    expect(service.exportUrl(12, 'json')).toBe(
      'http://localhost:8030/api/analyses/12/export?format=json',
    );
    expect(service.exportUrl(12, 'csv')).toBe(
      'http://localhost:8030/api/analyses/12/export?format=csv',
    );
    expect(service.exportUrl(12)).toContain('format=json');
  });

  it('should build the live WebSocket URL with an encoded target', () => {
    const url = service.liveUrl('https://example.com/a b');
    expect(url).toBe('ws://localhost:8030/api/forms/live?target=https%3A%2F%2Fexample.com%2Fa%20b');
  });

  it('should list, fetch and delete analyses', () => {
    service.listAnalyses().subscribe((items) => expect(items).toEqual([]));
    httpMock.expectOne('http://localhost:8030/api/analyses').flush([]);

    service.getAnalysis('3').subscribe();
    httpMock.expectOne('http://localhost:8030/api/analyses/3').flush({ id: 3 });

    service.deleteAnalysis(3).subscribe();
    const deletion = httpMock.expectOne('http://localhost:8030/api/analyses/3');
    expect(deletion.request.method).toBe('DELETE');
    deletion.flush(null, { status: 204, statusText: 'No Content' });

    service.deleteAllAnalyses().subscribe();
    const deleteAll = httpMock.expectOne('http://localhost:8030/api/analyses');
    expect(deleteAll.request.method).toBe('DELETE');
    deleteAll.flush(null, { status: 204, statusText: 'No Content' });
  });
});
