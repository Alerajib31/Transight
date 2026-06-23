const METRICS = [
  {
    key: "eta",
    label: "ETA Trend",
    yAxisLabel: "Predicted ETA",
    xAxisLabel: "Sample time",
    accent: {
      dark: "#60a5fa",
      light: "#2563eb",
    },
    unit: "min",
    axisUnit: "minutes",
  },
  {
    key: "delay_minutes",
    label: "Delay Trend",
    yAxisLabel: "Schedule delay",
    xAxisLabel: "Sample time",
    accent: {
      dark: "#f87171",
      light: "#dc2626",
    },
    unit: "min",
    axisUnit: "minutes",
  },
  {
    key: "passenger_count",
    label: "Passenger Trend",
    yAxisLabel: "Passenger count",
    xAxisLabel: "Sample time",
    accent: {
      dark: "#34d399",
      light: "#059669",
    },
    unit: "pax",
    axisUnit: "people",
  },
  {
    key: "traffic_delay",
    label: "Traffic Trend",
    yAxisLabel: "Traffic delay",
    xAxisLabel: "Sample time",
    accent: {
      dark: "#fbbf24",
      light: "#d97706",
    },
    unit: "sec",
    axisUnit: "seconds",
  },
];

function isNumericValue(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function formatMetricValue(unit, value) {
  if (!isNumericValue(value)) {
    return "--";
  }

  const rounded = unit === "pax" ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded}${unit === "pax" ? "" : ` ${unit}`}`;
}

function formatAxisValue(unit, value) {
  if (!isNumericValue(value)) {
    return "--";
  }

  if (unit === "pax") {
    return `${Math.round(value)}`;
  }

  const rounded = Math.abs(value) >= 10 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded}`;
}

function formatHistoryTime(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "--";
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function buildTrendPoints(points, metricKey, width = 360, height = 180) {
  const chart = {
    left: 58,
    right: 18,
    top: 16,
    bottom: 42,
  };
  const chartWidth = width - chart.left - chart.right;
  const chartHeight = height - chart.top - chart.bottom;
  const metricPoints = points
    .map((point) => ({
      timestamp: point.timestamp,
      value: point[metricKey],
    }))
    .filter((point) => isNumericValue(point.value));

  if (metricPoints.length === 0) {
    return { path: "", points: [], minValue: null, midValue: null, maxValue: null, chart, width, height };
  }

  const values = metricPoints.map((point) => point.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const span = maxValue - minValue || 1;
  const midValue = minValue + span / 2;

  const svgPoints = metricPoints.map((point, index) => {
    const x =
      metricPoints.length === 1
        ? chart.left + chartWidth / 2
        : chart.left + (index / (metricPoints.length - 1)) * chartWidth;
    const normalized = (point.value - minValue) / span;
    const y = chart.top + chartHeight - normalized * chartHeight;
    return {
      ...point,
      x,
      y,
    };
  });

  const path = svgPoints
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");

  return { path, points: svgPoints, minValue, midValue, maxValue, chart, width, height };
}

function MetricTrendCard({ metric, history, theme }) {
  const accent = theme === "dark" ? metric.accent.dark : metric.accent.light;
  const stat = history.stats?.[metric.key] ?? null;
  const trend = buildTrendPoints(history.points ?? [], metric.key);
  const latestPoint = history.points?.[history.points.length - 1] ?? null;
  const earliestPoint = history.points?.[0] ?? null;

  return (
    <div className="rounded-2xl border border-border bg-bg-card-hover/40 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-text-secondary">
            {metric.label}
          </p>
          <p className="mt-1 text-2xl font-bold text-text-primary">
            {formatMetricValue(metric.unit, stat?.latest)}
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            X-axis: {metric.xAxisLabel} | Y-axis: {metric.yAxisLabel} ({metric.axisUnit})
          </p>
        </div>
        <div className="text-right text-xs text-text-secondary">
          <p>Avg {formatMetricValue(metric.unit, stat?.average)}</p>
          <p>Peak {formatMetricValue(metric.unit, stat?.max)}</p>
        </div>
      </div>

      {trend.points.length > 0 ? (
        <svg
          viewBox={`0 0 ${trend.width} ${trend.height}`}
          className="h-44 w-full overflow-visible"
          role="img"
          aria-label={`${metric.label}: x-axis is sample time; y-axis is ${metric.yAxisLabel.toLowerCase()} in ${metric.axisUnit}.`}
        >
          <title>
            {`${metric.label}: X-axis sample time, Y-axis ${metric.yAxisLabel} in ${metric.axisUnit}`}
          </title>
          <line
            x1={trend.chart.left}
            y1={trend.chart.top}
            x2={trend.chart.left}
            y2={trend.height - trend.chart.bottom}
            stroke="rgba(148, 163, 184, 0.45)"
          />
          <line
            x1={trend.chart.left}
            y1={trend.height - trend.chart.bottom}
            x2={trend.width - trend.chart.right}
            y2={trend.height - trend.chart.bottom}
            stroke="rgba(148, 163, 184, 0.45)"
          />
          <line x1={trend.chart.left} y1={trend.chart.top} x2={trend.width - trend.chart.right} y2={trend.chart.top} stroke="rgba(148, 163, 184, 0.18)" strokeDasharray="4 6" />
          <line x1={trend.chart.left} y1={(trend.chart.top + trend.height - trend.chart.bottom) / 2} x2={trend.width - trend.chart.right} y2={(trend.chart.top + trend.height - trend.chart.bottom) / 2} stroke="rgba(148, 163, 184, 0.14)" strokeDasharray="4 6" />
          <line x1={trend.chart.left} y1={trend.height - trend.chart.bottom} x2={trend.width - trend.chart.right} y2={trend.height - trend.chart.bottom} stroke="rgba(148, 163, 184, 0.18)" strokeDasharray="4 6" />
          <text x={trend.chart.left - 8} y={trend.chart.top + 4} textAnchor="end" className="fill-text-secondary text-[10px]">
            {formatAxisValue(metric.unit, trend.maxValue)}
          </text>
          <text x={trend.chart.left - 8} y={(trend.chart.top + trend.height - trend.chart.bottom) / 2 + 4} textAnchor="end" className="fill-text-secondary text-[10px]">
            {formatAxisValue(metric.unit, trend.midValue)}
          </text>
          <text x={trend.chart.left - 8} y={trend.height - trend.chart.bottom + 4} textAnchor="end" className="fill-text-secondary text-[10px]">
            {formatAxisValue(metric.unit, trend.minValue)}
          </text>
          <text
            x={16}
            y={(trend.chart.top + trend.height - trend.chart.bottom) / 2}
            textAnchor="middle"
            transform={`rotate(-90 16 ${(trend.chart.top + trend.height - trend.chart.bottom) / 2})`}
            className="fill-text-secondary text-[10px] font-semibold uppercase tracking-[0.18em]"
          >
            {metric.yAxisLabel}
          </text>
          <text
            x={(trend.chart.left + trend.width - trend.chart.right) / 2}
            y={trend.height - 8}
            textAnchor="middle"
            className="fill-text-secondary text-[10px] font-semibold uppercase tracking-[0.18em]"
          >
            {metric.xAxisLabel}
          </text>
          <path
            d={trend.path}
            fill="none"
            stroke={accent}
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {trend.points.map((point) => (
            <circle
              key={`${metric.key}-${point.timestamp}`}
              cx={point.x}
              cy={point.y}
              r="3.5"
              fill={accent}
              stroke={theme === "dark" ? "#0f172a" : "#ffffff"}
              strokeWidth="1.5"
            />
          ))}
        </svg>
      ) : (
        <div className="flex h-32 items-center justify-center rounded-xl border border-dashed border-border text-sm text-text-secondary">
          No sampled data yet
        </div>
      )}

      <div className="mt-3 flex items-center justify-between text-xs text-text-secondary">
        <span>{formatHistoryTime(earliestPoint?.timestamp)}</span>
        <span>Latest {formatHistoryTime(latestPoint?.timestamp)}</span>
      </div>
    </div>
  );
}

export default function HistoricalTrends({ history, theme, title, subtitle, loading }) {
  return (
    <section className="rounded-3xl border border-border bg-bg-card p-5 shadow-lg">
      <div className="flex flex-col gap-3 border-b border-border/70 pb-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-text-secondary">
            Historical Trends
          </p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-text-primary">
            {title}
          </h2>
          <p className="mt-1 text-sm text-text-secondary">
            {subtitle}
          </p>
        </div>
        <div className="text-sm text-text-secondary">
          {loading ? "Refreshing history..." : `${history.sample_count ?? 0} samples loaded`}
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-2">
        {METRICS.map((metric) => (
          <MetricTrendCard
            key={metric.key}
            metric={metric}
            history={history}
            theme={theme}
          />
        ))}
      </div>
    </section>
  );
}
