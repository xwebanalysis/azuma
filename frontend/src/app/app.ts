import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

import { ApiService, Form } from './services/api.service';
import { ThemeService } from './services/theme.service';

@Component({
  selector: 'app-root',
  imports: [FormsModule, CommonModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  private readonly api = inject(ApiService);
  private readonly theme = inject(ThemeService);

  protected target = '';
  protected loading = false;
  protected error: string | null = null;
  protected backendOnline = false;
  protected forms: Form[] = [];
  protected analysisId: number | null = null;

  ngOnInit(): void {
    this.theme.initTheme();
    this.api.health().subscribe({
      next: () => (this.backendOnline = true),
      error: () => (this.backendOnline = false),
    });
  }

  toggleTheme(): void {
    this.theme.toggleTheme();
  }

  themeLabel(): string {
    return this.theme.nextThemeLabel();
  }

  discover(): void {
    const target = this.target.trim();
    if (!target || this.loading) {
      return;
    }
    this.loading = true;
    this.error = null;
    this.api.discoverForms(target).subscribe({
      next: (response) => {
        this.forms = response.analysis.forms;
        this.analysisId = response.analysis.id;
        this.loading = false;
      },
      error: (err) => {
        this.error = err.error?.detail ?? 'Failed to reach the backend.';
        this.loading = false;
      },
    });
  }
}
