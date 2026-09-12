import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { App } from './app';
import { ApiService } from './core/api.service';

const apiStub = {
  health: () => of({ status: 'ok', database: 'ok', version: '0.3.0', tool: 'azuma' }),
};

describe('App', () => {
  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([]), { provide: ApiService, useValue: apiStub }],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should render the app shell with the side navigation', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.brand h1')?.textContent).toContain('AZUMA');
    expect(compiled.querySelector('.status-label')?.textContent).toContain('BACKEND ONLINE');
    const links = Array.from(compiled.querySelectorAll('.nav-link')).map((link) =>
      link.textContent?.replace(/\s+/g, ' ').trim(),
    );
    expect(links).toEqual(['[ ANALYZER ]', '[ HISTORY ]', '[ EXPORTS ]']);
  });
});
