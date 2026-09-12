import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';

import { AnalysisListItem, ApiService, FormAnalysis } from '../../core/api.service';
import { ExportService } from '../../core/export.service';
import { I18nService } from '../../core/i18n.service';
import { StatusBadgeComponent } from '../../shared/status-badge/status-badge';

@Component({
  selector: 'app-exports',
  standalone: true,
  imports: [CommonModule, StatusBadgeComponent],
  templateUrl: './exports.html',
  styleUrl: './exports.scss',
})
export class ExportsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly exporter = inject(ExportService);
  private readonly i18n = inject(I18nService);
  private readonly cdr = inject(ChangeDetectorRef);

  protected history: AnalysisListItem[] = [];
  protected loading = false;
  protected error: string | null = null;
  protected notice: string | null = null;
  protected busyId: number | null = null;

  ngOnInit(): void {
    this.load();
  }

  protected t(key: string): string {
    return this.i18n.t(key);
  }

  protected load(): void {
    this.loading = true;
    this.error = null;
    this.api.listAnalyses().subscribe({
      next: (items) => {
        this.history = items;
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.error = this.t('error.backend');
        this.loading = false;
        this.cdr.markForCheck();
      },
    });
  }

  protected serverJsonUrl(id: number): string {
    return this.api.exportUrl(id, 'json');
  }

  protected serverCsvUrl(id: number): string {
    return this.api.exportUrl(id, 'csv');
  }

  protected clientJson(item: AnalysisListItem): void {
    this.withAnalysis(item, (analysis) => {
      this.exporter.downloadJson(analysis);
      this.notice = `[DOWNLOADED #${analysis.id} JSON]`;
    });
  }

  protected clientPdf(item: AnalysisListItem): void {
    this.withAnalysis(item, async (analysis) => {
      await this.exporter.downloadPdf(analysis);
      this.notice = `[DOWNLOADED #${analysis.id} PDF]`;
    });
  }

  private withAnalysis(
    item: AnalysisListItem,
    action: (analysis: FormAnalysis) => void | Promise<void>,
  ): void {
    if (this.busyId !== null) {
      return;
    }
    this.busyId = item.id;
    this.error = null;
    this.api.getAnalysis(item.id).subscribe({
      next: (analysis) => {
        void Promise.resolve(action(analysis)).finally(() => {
          this.busyId = null;
          this.cdr.markForCheck();
        });
      },
      error: () => {
        this.error = this.t('error.backend');
        this.busyId = null;
        this.cdr.markForCheck();
      },
    });
  }
}
