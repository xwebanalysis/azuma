import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./features/analyzer/analyzer').then((module) => module.AnalyzerComponent),
    title: 'Azuma — Analyzer',
  },
  {
    path: 'history',
    loadComponent: () =>
      import('./features/history/history').then((module) => module.HistoryComponent),
    title: 'Azuma — History',
  },
  {
    path: 'history/:id',
    loadComponent: () =>
      import('./features/history/detail').then((module) => module.AnalysisDetailComponent),
    title: 'Azuma — Analysis',
  },
  {
    path: 'exports',
    loadComponent: () =>
      import('./features/exports/exports').then((module) => module.ExportsComponent),
    title: 'Azuma — Exports',
  },
  { path: '**', redirectTo: '' },
];
