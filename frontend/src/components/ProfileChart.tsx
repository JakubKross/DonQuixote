import { KeyboardEvent, PointerEvent, useId, useState } from "react";

import { formatDateTime, formatNumber } from "../format";

export interface ChartSeries {
  name: string;
  values: number[];
  /** CSS color, normally one of the `--series-N` custom properties. */
  color: string;
}

interface ProfileChartProps {
  title: string;
  timestamps: string[];
  series: ChartSeries[];
  unit: string;
  /** Horizontal threshold drawn as a dashed line, e.g. the grid connection limit. */
  reference?: { label: string; value: number };
  digits?: number;
}

const WIDTH = 720;
const HEIGHT = 240;
const MARGIN = { top: 12, right: 16, bottom: 28, left: 56 };
const INNER_WIDTH = WIDTH - MARGIN.left - MARGIN.right;
const INNER_HEIGHT = HEIGHT - MARGIN.top - MARGIN.bottom;

function niceStep(rough: number): number {
  if (rough <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const residual = rough / magnitude;
  const nice = residual <= 1 ? 1 : residual <= 2 ? 2 : residual <= 5 ? 5 : 10;
  return nice * magnitude;
}

/**
 * Hourly time-series line chart: one shared y-axis, 2px lines, crosshair with a
 * tooltip listing every series at the hovered hour (also reachable with arrow keys),
 * a legend for two or more series and a table view of the same data.
 */
export default function ProfileChart({
  title,
  timestamps,
  series,
  unit,
  reference,
  digits = 3,
}: ProfileChartProps) {
  const titleId = useId();
  const [active, setActive] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);

  const count = timestamps.length;
  if (count === 0) return null;

  const dataMax = Math.max(0, ...series.flatMap((s) => s.values), reference?.value ?? 0);
  const step = niceStep(dataMax / 4);
  const yMax = Math.max(step, Math.ceil(dataMax / step) * step);
  const ticks = Array.from({ length: Math.round(yMax / step) + 1 }, (_, i) => i * step);

  const x = (index: number) => MARGIN.left + (count === 1 ? INNER_WIDTH / 2 : (index / (count - 1)) * INNER_WIDTH);
  const y = (value: number) => MARGIN.top + INNER_HEIGHT - (value / yMax) * INNER_HEIGHT;
  const path = (values: number[]) =>
    values.map((value, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(value).toFixed(1)}`).join("");

  const xLabelIndexes = count === 1 ? [0] : [...new Set([0, Math.floor((count - 1) / 2), count - 1])];

  function indexFromPointer(event: PointerEvent<SVGSVGElement>): number {
    const rect = event.currentTarget.getBoundingClientRect();
    const svgX = ((event.clientX - rect.left) / rect.width) * WIDTH;
    const ratio = (svgX - MARGIN.left) / INNER_WIDTH;
    return Math.min(count - 1, Math.max(0, Math.round(ratio * (count - 1))));
  }

  function handleKey(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const delta = event.key === "ArrowLeft" ? -1 : 1;
    setActive((current) => Math.min(count - 1, Math.max(0, (current ?? 0) + delta)));
  }

  const tooltipLeft = active == null ? 0 : (x(active) / WIDTH) * 100;

  return (
    <figure className="profile-chart">
      <figcaption id={titleId} className="profile-chart__title">
        {title} <span className="profile-chart__unit">[{unit}]</span>
      </figcaption>

      {(series.length > 1 || reference) && (
        <ul className="chart-legend">
          {series.map((s) => (
            <li key={s.name}>
              <span className="chart-legend__key" style={{ borderColor: s.color }} />
              {s.name}
            </li>
          ))}
          {reference && (
            <li>
              <span className="chart-legend__key chart-legend__key--dashed" />
              {reference.label}
            </li>
          )}
        </ul>
      )}

      <div className="profile-chart__plot">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-labelledby={titleId}
          tabIndex={0}
          onPointerMove={(event) => setActive(indexFromPointer(event))}
          onPointerLeave={() => setActive(null)}
          onKeyDown={handleKey}
          onBlur={() => setActive(null)}
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                className="chart-grid"
                x1={MARGIN.left}
                x2={WIDTH - MARGIN.right}
                y1={y(tick)}
                y2={y(tick)}
              />
              <text className="chart-axis-label" x={MARGIN.left - 8} y={y(tick)} textAnchor="end" dominantBaseline="middle">
                {formatNumber(tick, step < 1 ? 2 : 0)}
              </text>
            </g>
          ))}
          {xLabelIndexes.map((index, i) => (
            <text
              key={index}
              className="chart-axis-label"
              x={x(index)}
              y={HEIGHT - 8}
              textAnchor={i === 0 ? "start" : i === xLabelIndexes.length - 1 ? "end" : "middle"}
            >
              {formatDateTime(timestamps[index])}
            </text>
          ))}

          {reference && (
            <line
              className="chart-reference"
              x1={MARGIN.left}
              x2={WIDTH - MARGIN.right}
              y1={y(reference.value)}
              y2={y(reference.value)}
            />
          )}
          {series.map((s) => (
            <path key={s.name} d={path(s.values)} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" />
          ))}

          {active != null && (
            <g>
              <line className="chart-crosshair" x1={x(active)} x2={x(active)} y1={MARGIN.top} y2={MARGIN.top + INNER_HEIGHT} />
              {series.map((s) => (
                <circle
                  key={s.name}
                  cx={x(active)}
                  cy={y(s.values[active] ?? 0)}
                  r={4}
                  fill={s.color}
                  className="chart-marker"
                />
              ))}
            </g>
          )}
        </svg>

        {active != null && (
          <div
            className={`chart-tooltip${tooltipLeft > 60 ? " chart-tooltip--left" : ""}`}
            style={{ left: `${tooltipLeft}%` }}
          >
            <div className="chart-tooltip__date">{formatDateTime(timestamps[active])}</div>
            {series.map((s) => (
              <div key={s.name} className="chart-tooltip__row">
                <span className="chart-legend__key" style={{ borderColor: s.color }} />
                <strong>
                  {formatNumber(s.values[active], digits)} {unit}
                </strong>
                <span className="chart-tooltip__name">{s.name}</span>
              </div>
            ))}
            {reference && (
              <div className="chart-tooltip__row">
                <span className="chart-legend__key chart-legend__key--dashed" />
                <strong>
                  {formatNumber(reference.value, digits)} {unit}
                </strong>
                <span className="chart-tooltip__name">{reference.label}</span>
              </div>
            )}
          </div>
        )}
      </div>

      <button type="button" className="link-button" onClick={() => setShowTable((value) => !value)}>
        {showTable ? "Ukryj tabelę" : "Pokaż tabelę"}
      </button>
      {showTable && (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Godzina</th>
                {series.map((s) => (
                  <th key={s.name}>
                    {s.name} [{unit}]
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {timestamps.map((timestamp, index) => (
                <tr key={timestamp}>
                  <td>{formatDateTime(timestamp)}</td>
                  {series.map((s) => (
                    <td key={s.name} className="numeric">
                      {formatNumber(s.values[index], digits)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </figure>
  );
}
