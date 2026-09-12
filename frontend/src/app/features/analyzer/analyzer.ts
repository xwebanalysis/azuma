import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, OnDestroy, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';

import {
  ApiService,
  FormAnalysis,
  ItemFoundPayload,
  LiveErrorPayload,
  LiveEvent,
  ProgressPayload,
  StartedPayload,
} from '../../core/api.service';
import { I18nService } from '../../core/i18n.service';
import { LiveService } from '../../core/live.service';
import { TerminalComponent } from '../../shared/terminal/terminal';
import { AnalysisDetailComponent } from '../history/detail';

type PhaseName = 'connect' | 'fetch' | 'forms' | 'oauth' | 'cookies' | 'complete';
type PhaseState = 'pending' | 'running' | 'done';

const PHASES: readonly PhaseName[] = ['connect', 'fetch', 'forms', 'oauth', 'cookies', 'complete'];

@Component({
  selector: 'app-analyzer',
  standalone: true,
  imports: [CommonModule, FormsModule, TerminalComponent, AnalysisDetailComponent],
  templateUrl: './analyzer.html',
  styleUrl: './analyzer.scss',
})
export class AnalyzerComponent implements OnDestroy {
  private readonly api = inject(ApiService);
  private readonly live = inject(LiveService);
  private readonly i18n = inject(I18nService);
  private readonly cdr = inject(ChangeDetectorRef);

  protected readonly phases = PHASES;

  protected target = '';
  protected loading = false;
  protected liveRunning = false;
  protected error: string | null = null;
  protected terminalLines: string[] = [];
  protected phaseState: Record<PhaseName, PhaseState> = this.emptyPhases();
  protected analysis: FormAnalysis | null = null;

  private subscription: Subscription | null = null;

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
  }

  protected t(key: string): string {
    return this.i18n.t(key);
  }

  protected canRun(): boolean {
    return !!this.target.trim() && !this.loading && !this.liveRunning;
  }

  /** REST run: single-shot synchronous discovery (fallback). */
  protected analyze(): void {
    const target = this.target.trim();
    if (!target || !this.canRun()) {
      return;
    }

    this.loading = true;
    this.error = null;
    this.appendLine(`START REST target=${target}`);

    this.api.discoverForms(target).subscribe({
      next: (response) => {
        this.analysis = response.analysis;
        this.phaseState = this.allPhasesDone();
        this.appendLine(
          `COMPLETED #${response.analysis.id} forms=${response.form_count} ` +
            `oauth=${response.oauth_flow_count} cookies=${response.session_cookie_count}`,
        );
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.error = this.errorMessage(err);
        this.appendLine(`[ERROR] ${this.error}`);
        this.loading = false;
        this.cdr.markForCheck();
      },
    });
  }

  /** WebSocket run: live xwa-sdk Events with terminal log. */
  protected runLive(): void {
    const target = this.target.trim();
    if (!target || !this.canRun()) {
      return;
    }

    this.liveRunning = true;
    this.error = null;
    this.analysis = null;
    this.terminalLines = [];
    this.phaseState = this.emptyPhases();
    this.appendLine(`OPEN /api/forms/live target=${target}`);

    this.subscription = this.live.connect(this.api.liveUrl(target)).subscribe({
      next: (event) => this.handleEvent(event),
      error: (err) => {
        this.error = err instanceof Error ? err.message : this.t('error.backend');
        this.appendLine(`[ERROR] ${this.error}`);
        this.liveRunning = false;
        this.cdr.markForCheck();
      },
      complete: () => {
        this.liveRunning = false;
        this.cdr.markForCheck();
      },
    });
  }

  protected cancel(): void {
    this.subscription?.unsubscribe();
    this.subscription = null;
    this.appendLine('[CANCELLED] client closed the stream');
    this.liveRunning = false;
    this.cdr.markForCheck();
  }

  private handleEvent(event: LiveEvent): void {
    switch (event.type) {
      case 'analysis_started': {
        const payload = event.payload as StartedPayload | null;
        this.markPhase('fetch');
        this.appendLine(`STARTED #${event.analysis_id} target=${payload?.target ?? ''}`);
        break;
      }
      case 'analysis_progress': {
        const payload = event.payload as ProgressPayload | null;
        this.markPhase('forms');
        this.appendLine(`PAGE ${payload?.page ?? ''} title=${payload?.title ?? 'n/a'}`);
        break;
      }
      case 'item_found': {
        const payload = event.payload as ItemFoundPayload | null;
        this.handleItem(payload);
        break;
      }
      case 'analysis_completed':
        this.phaseState = this.allPhasesDone();
        this.appendLine(`COMPLETED #${event.analysis_id}`);
        this.finishLive(event.analysis_id);
        break;
      case 'analysis_error': {
        const payload = event.payload as LiveErrorPayload | null;
        this.error = payload?.message ?? payload?.error?.message ?? 'Analysis failed.';
        this.appendLine(`[ERROR] ${this.error}`);
        this.liveRunning = false;
        break;
      }
      default:
        this.appendLine(`${event.type} #${event.seq}`);
    }
    this.cdr.markForCheck();
  }

  private handleItem(payload: ItemFoundPayload | null): void {
    const kind = String(payload?.kind ?? 'item');
    switch (kind) {
      case 'form':
        this.markPhase('forms');
        this.appendLine(
          `+ FORM ${payload?.method ?? ''} ${payload?.action ?? ''} ` +
            `fields=${payload?.fields ?? 0} csrf=${payload?.csrf ?? 0}`,
        );
        break;
      case 'oauth_flow':
        this.markPhase('oauth');
        this.appendLine(`+ OAUTH ${payload?.endpoint ?? ''} ${payload?.flow_type ?? ''}`.trimEnd());
        break;
      case 'session_cookie':
        this.markPhase('cookies');
        this.appendLine(
          `+ COOKIE ${payload?.name ?? ''} secure=${payload?.secure ? 'YES' : 'NO'}`,
        );
        break;
      default:
        this.appendLine(`+ ${kind.toUpperCase()}`);
    }
  }

  private finishLive(analysisId: string): void {
    this.api.getAnalysis(analysisId).subscribe({
      next: (analysis) => {
        this.analysis = analysis;
        this.liveRunning = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.liveRunning = false;
        this.cdr.markForCheck();
      },
    });
  }

  private errorMessage(err: unknown): string {
    const httpError = err as { error?: { error?: { message?: string }; detail?: string } };
    return (
      httpError?.error?.error?.message ??
      httpError?.error?.detail ??
      this.t('error.backend')
    );
  }

  private appendLine(line: string): void {
    const stamp = new Date().toISOString().slice(11, 19);
    this.terminalLines = [...this.terminalLines, `${stamp}  ${line}`];
  }

  private markPhase(phase: PhaseName): void {
    const index = PHASES.indexOf(phase);
    for (const [position, name] of PHASES.entries()) {
      if (position < index) {
        this.phaseState[name] = 'done';
      } else if (position === index) {
        this.phaseState[name] = 'running';
      }
    }
  }

  private emptyPhases(): Record<PhaseName, PhaseState> {
    return {
      connect: 'pending',
      fetch: 'pending',
      forms: 'pending',
      oauth: 'pending',
      cookies: 'pending',
      complete: 'pending',
    };
  }

  private allPhasesDone(): Record<PhaseName, PhaseState> {
    return {
      connect: 'done',
      fetch: 'done',
      forms: 'done',
      oauth: 'done',
      cookies: 'done',
      complete: 'done',
    };
  }
}
