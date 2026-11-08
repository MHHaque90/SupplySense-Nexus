import type { DataSourceLabel } from "../api/types";

const LABEL_STYLE: Record<DataSourceLabel, { title: string; className: string; blurb: string }> = {
  derived: {
    title: "derived",
    className: "label-chip label-derived",
    blurb: "Derived metadata — computed from underlying synthetic data.",
  },
  forecast: {
    title: "forecast (estimated)",
    className: "label-chip label-forecast",
    blurb: "Forecast values are statistical estimates with uncertainty — never actuals.",
  },
  synthetic: {
    title: "synthetic data",
    className: "label-chip label-synthetic",
    blurb: "Computed over a rule-generated synthetic dataset — not real business data.",
  },
  simulated: {
    title: "simulated",
    className: "label-chip label-simulated",
    blurb: "Simulated scenario output — conditional modelling, never a prediction.",
  },
};

export function DataSourceLabelChip({ label }: { label: DataSourceLabel | string | undefined }) {
  if (!label) return null;
  const style = LABEL_STYLE[label as DataSourceLabel] ?? {
    title: label,
    className: "label-chip label-unknown",
    blurb: `Data-source label: ${label}.`,
  };
  return (
    <span className={style.className} title={style.blurb} aria-label={`Data source: ${style.title}`}>
      {style.title}
    </span>
  );
}

export function LabelLegend() {
  return (
    <div className="label-legend" aria-label="Data source label legend">
      <span className="legend-title">Data labels:</span>
      <DataSourceLabelChip label="derived" />
      <DataSourceLabelChip label="forecast" />
      <DataSourceLabelChip label="synthetic" />
      <DataSourceLabelChip label="simulated" />
    </div>
  );
}
