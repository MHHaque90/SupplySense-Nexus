import { useMemo, useState, type ReactNode } from "react";

export interface Column<T> {
  header: string;
  render: (row: T) => ReactNode;
  width?: string;
}

export function DataTable<T>({
  columns,
  rows,
  emptyHint,
}: {
  columns: Column<T>[];
  rows: T[];
  emptyHint?: string;
}) {
  if (rows.length === 0) {
    return emptyHint ? <EmptyTable hint={emptyHint} /> : null;
  }
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.header} style={column.width ? { width: column.width } : undefined}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column.header}>{column.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EmptyTable({ hint }: { hint: string }) {
  return <p className="table-empty">{hint}</p>;
}

export function Pagination({
  page,
  pageSize,
  total,
  hasNext,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  hasNext: boolean;
  onPage: (page: number) => void;
}) {
  const pages = useMemo(() => Math.ceil(total / Math.max(pageSize, 1)), [total, pageSize]);
  return (
    <nav className="pagination" aria-label="Table pagination">
      <span className="muted" aria-live="polite">
        Page {page} of {pages || 1} · {total} row{total === 1 ? "" : "s"}
      </span>
      <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        ‹ Prev
      </button>
      <button type="button" className="btn btn-sm" disabled={!hasNext} onClick={() => onPage(page + 1)}>
        Next ›
      </button>
    </nav>
  );
}

export function usePager(): [number, (page: number) => void] {
  const [page, setPage] = useState(1);
  return [page, (next) => setPage(Math.max(1, next))];
}
