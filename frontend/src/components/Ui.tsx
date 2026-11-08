import type { ReactNode } from "react";
import type { KpiMetric } from "../api/types";

export function KpiCard({
  title,
  value,
  unit,
  note,
  formula,
}: {
  title: string;
  value: number | null;
  unit: string;
  note?: string;
  formula?: string;
}) {
  return (
    <div className="kpi-card">
      <p className="kpi-title">{title}</p>
      <p className="kpi-value">
        {value === null ? <span className="muted">n/a</span> : formatNumber(value)}
        {value !== null && unit ? <span className="kpi-unit"> {unit}</span> : null}
      </p>
      {formula ? <p className="kpi-formula" title={formula}>{formula}</p> : null}
      {note ? <p className="kpi-note">{note}</p> : null}
    </div>
  );
}

export function KpiCardFromMetric({ metric }: { metric: KpiMetric }) {
  return (
    <KpiCard
      title={metric.metric_name}
      value={metric.value}
      unit={metric.unit}
      note={metric.notes || undefined}
      formula={metric.formula || undefined}
    />
  );
}

export function MetricGroupTable({ metrics }: { metrics: KpiMetric[] }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Value</th>
            <th>Unit</th>
            <th>Numerator</th>
            <th>Denominator</th>
            <th>Formula</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric, index) => (
            <tr key={index}>
              <td>{metric.metric_name}</td>
              <td>{metric.value === null ? <span className="muted">n/a</span> : formatNumber(metric.value)}</td>
              <td>{metric.unit}</td>
              <td>{metric.numerator === null ? <span className="muted">n/a</span> : formatNumber(metric.numerator)}</td>
              <td>{metric.denominator === null ? <span className="muted">n/a</span> : formatNumber(metric.denominator)}</td>
              <td className="mono small">{metric.formula}</td>
              <td className="small">{metric.notes}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return String(value);
  const abs = Math.abs(value);
  if (abs >= 100000) return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (abs >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (abs >= 10) return value.toFixed(1);
  if (abs >= 1) return value.toFixed(2);
  return value.toPrecision(3);
}

export function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function DateChip({ date }: { date: string | undefined }) {
  if (!date) return null;
  return <span className="date-chip">{date}</span>;
}

export function Section({
  title,
  children,
  actions,
  subtitle,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>{title}</h2>
        {actions ? <div className="panel-actions">{actions}</div> : null}
      </div>
      {subtitle ? <p className="panel-subtitle">{subtitle}</p> : null}
      {children}
    </section>
  );
}

export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="filter-bar">{children}</div>;
}

export function TextInput({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </label>
  );
}

export function NumberInput({
  label,
  value,
  onChange,
  min,
  max,
  step,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        min={min}
        max={max}
        step={step ?? 1}
      />
    </label>
  );
}

export function SelectInput<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: readonly T[] | readonly { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  type Opt = { value: T; label: string };
  const normalized: Opt[] = (options as readonly (T | Opt)[]).map((option) =>
    typeof option === "string" ? ({ value: option as T, label: option } as Opt) : option,
  );
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value as T)}>
        {normalized.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function ShortId({ id }: { id: string }) {
  if (!id) return <span className="muted">—</span>;
  return (
    <code className="short-id" title={id}>
      {id.length > 12 ? `${id.slice(0, 8)}…` : id}
    </code>
  );
}

export function SeverityChip({ severity }: { severity: string }) {
  const level = severity.toLowerCase().replace(/_/g, " ");
  const tone =
    ["high", "critical", "stockout"].includes(level) ? "chip-bad"
    : ["moderate", "monitor", "at_risk", "elevated"].includes(level) ? "chip-warn"
    : ["low", "healthy", "no_signal"].includes(level) ? "chip-good"
    : "chip-neutral";
  return <span className={`chip ${tone}`}>{level.toUpperCase()}</span>;
}
