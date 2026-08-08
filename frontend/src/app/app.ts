import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

import { ApiService, Form } from './services/api.service';

@Component({
  selector: 'app-root',
  imports: [FormsModule, CommonModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  private readonly api = inject(ApiService);

  protected target = '';
  protected loading = false;
  protected error: string | null = null;
  protected backendOnline = false;
  protected forms: Form[] = [];
  protected analysisId: number | null = null;
  protected expandedForm: number | null = null;

  ngOnInit(): void {
    this.api.health().subscribe({
      next: () => (this.backendOnline = true),
      error: () => (this.backendOnline = false),
    });
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

  toggleForm(id: number): void {
    this.expandedForm = this.expandedForm === id ? null : id;
  }
}
