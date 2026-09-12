import { Component, Input } from '@angular/core';

export interface DetailColumn {
  key: string;
  label: string;
}

/**
 * Flat data table shared by the detail views. Rows are plain objects and the
 * cell formatter renders — for empty values and YES/NO for booleans.
 */
@Component({
  selector: 'app-detail-table',
  standalone: true,
  template: `
    @if (rows.length > 0) {
      <table>
        <thead>
          <tr>
            @for (column of columns; track column.key) {
              <th class="t-label">{{ column.label }}</th>
            }
          </tr>
        </thead>
        <tbody>
          @for (row of rows; track trackRow($index, row)) {
            <tr>
              @for (column of columns; track column.key) {
                <td class="t-data" [class.url-cell]="isUrlColumn(column)">
                  {{ display(value(row, column.key)) }}
                </td>
              }
            </tr>
          }
        </tbody>
      </table>
    } @else {
      <div class="empty-state t-label">{{ emptyText }}</div>
    }
  `,
  styles: [
    `
      .url-cell {
        max-width: 420px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: var(--text-secondary);
      }
    `,
  ],
})
export class DetailTableComponent {
  @Input({ required: true }) columns: DetailColumn[] = [];
  @Input({ required: true }) rows: object[] = [];
  @Input() trackKey = 'id';
  @Input() emptyText = '[ NO DATA ]';

  protected value(row: object, key: string): unknown {
    return (row as Record<string, unknown>)[key];
  }

  protected display(value: unknown): string {
    if (value === null || value === undefined || value === '') {
      return '—';
    }
    if (typeof value === 'boolean') {
      return value ? 'YES' : 'NO';
    }
    return String(value);
  }

  protected isUrlColumn(column: DetailColumn): boolean {
    return column.key === 'url' || column.key === 'endpoint';
  }

  protected trackRow(index: number, row: object): unknown {
    const identifier = (row as Record<string, unknown>)[this.trackKey];
    return identifier ?? index;
  }
}
