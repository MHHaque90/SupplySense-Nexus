import type { ForecastRow, OutcomeDistribution } from "../api/types";

function scale(value: number, min: number, max: number, size: number): number {
  if (max === min) return size / 2;
  return ((value - min) / (max - min)) * size;
}

function niceBounds(lower: number[], upper: number[], points: number[]): [number, number] {
  const all = [...lower, ...upper, ...points].filter((n) => Number.isFinite(n));
  if (all.length === 0) return [0, 1];
  const min = Math.min(...all);
  const max = Math.max(...all);
  const pad = (max - min) * 0.08 || Math.abs(max) * 0.05 || 1;
  return [min - pad, max + pad];
}

export function ForecastChart({ row }: { row: ForecastRow }) {
  const W = 640;
  const H = 220;
  const PAD = { x: 44, y: 14 };
  const dates = row.forecast_dates;
  const points = row.point;
  const lower = row.lower;
  const upper = row.upper;
  const [lo, hi] = niceBounds(lower, upper, points);

  const x = (index: number) => PAD.x + (dates.length <= 1 ? 0 : (index / (dates.length - 1)) * (W - PAD.x * 2));
  const y = (v: number) => H - PAD.y - ((v - lo) / (hi - lo)) * (H - PAD.y * 2);

  const bandPath =
    dates.length > 1
      ? `M ${upper.map((v, i) => `${x(i)},${y(v)}`).join(" L ")} L ` +
        `${[...lower].reverse().map((v, i) => `${x(lower.length - 1 - i)},${y(v)}`).join(" L ")} Z`
      : "";

  return (
    <figure className="chart-figure">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Forecast series with ${Math.round(row.confidence_level * 100)}% prediction interval between lower and upper bounds`} className="chart-svg">
        <polygon points={bandPath} className="chart-band" />
        <polyline points={points.map((v, i) => `${x(i)},${y(v)}`).join(" ")} className="chart-line" fill="none" />
        {dates.map((date, i) => (
          <text key={i} x={x(i)} y={H - 2} textAnchor="middle" className="chart-tick">
            {date.slice(5)}
          </text>
        ))}
        <text x={4} y={PAD.y + 8} className="chart-tick">{hi.toFixed(0)}</text>
        <text x={4} y={H - PAD.y} className="chart-tick">{lo.toFixed(0)}</text>
      </svg>
      <figcaption className="chart-caption">
        Forecast points with prediction-interval band (lower–upper). Estimated values, not actuals.
      </figcaption>
    </figure>
  );
}

export function DistributionChart({ title, dist }: { title: string; dist: OutcomeDistribution }) {
  const W = 640;
  const H = 120;
  const PAD = 16;
  const [lo, hi] = niceBounds([dist.min], [dist.p99 ?? dist.max], [dist.mean]);
  const x = (v: number) => PAD + scale(v, lo - 0, hi + 0, W - PAD * 2);
  const q = (v: number) => x(v);

  return (
    <figure className="chart-figure">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}: distribution summary box`} className="chart-svg chart-box">
        <line x1={x(dist.min)} x2={x(dist.max)} y1={H / 2} y2={H / 2} className="chart-whisker" />
        <line x1={x(dist.min)} x2={x(dist.min)} y1={H / 2 - 10} y2={H / 2 + 10} className="chart-whisker" />
        <line x1={x(dist.max)} x2={x(dist.max)} y1={H / 2 - 10} y2={H / 2 + 10} className="chart-whisker" />
        <rect x={q(dist.p25)} width={Math.max(q(dist.p75) - q(dist.p25), 2)} y={H / 2 - 18} height={36} className="chart-iqr" />
        <line x1={q(dist.p50)} x2={q(dist.p50)} y1={H / 2 - 22} y2={H / 2 + 22} className="chart-median" />
        <circle cx={q(dist.mean)} cy={H / 2} r={4} className="chart-mean" />
        <text x={PAD} y={12} className="chart-tick">{title}</text>
        <text x={x(dist.min)} y={H - 4} textAnchor="middle" className="chart-tick">min {dist.min.toFixed(1)}</text>
        <text x={q(dist.p50)} y={H - 4} textAnchor="middle" className="chart-tick">p50 {dist.p50.toFixed(1)}</text>
        <text x={W - PAD} y={H - 4} textAnchor="end" className="chart-tick">max {dist.max.toFixed(1)}</text>
      </svg>
      <figcaption className="chart-caption">
        min · p05–p75 quartiles · median line · mean dot · max — summary of simulated draws, not a fitted distribution.
      </figcaption>
    </figure>
  );
}
