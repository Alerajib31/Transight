const METRICS = [
  {
    key: "eta",
    label: "ETA Trend",
    accent: {
      dark: "#60a5fa",
      light: "#2563eb",
    },
    unit: "min",
  },
  {
    key: "delay_minutes",
    label: "Delay Trend",
    accent: {
      dark: "#f87171",
      light: "#dc2626",
    },
    unit: "min",
  },
  {
    key: "passenger_count",
    label: "Passenger Trend",
    accent: {
      dark: "#34d399",
      light: "#059669",
    },
    unit: "pax",
  },
  {
    key: "traffic_delay",
    label: "Traffic Trend",
    accent: {
      dark: "#fbbf24",
      light: "#d97706",
    },
    unit: "sec",
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

function buildTrendPoints(points, metricKey, width = 320, height = 130, padding = 14) {
  const metricPoints = points
    .map((point) => ({
      timestamp: point.timestamp,
      value: point[metricKey],
    }))
    .filter((point) => isNumericValue(point.value));

  if (metricPoints.length === 0) {
    return { path: "", points: [] };
  }

  const values = metricPoints.map((point) => point.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const span = maxValue - minValue || 1;

  const svgPoints = metricPoints.map((point, index) => {
    const x =
      metricPoints.length === 1
        ? width / 2
        : padding + (index / (metricPoints.length - 1)) * (width - padding * 2);
    const normalized = (point.value - minValue) / span;
    const y = height - padding - normalized * (height - padding * 2);
    return {
      ...point,
      x,
      y,
    };
  });

  const path = svgPoints
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");

  return { path, points: svgPoints };
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
        </div>
        <div className="text-right text-xs text-text-secondary">
          <p>Avg {formatMetricValue(metric.unit, stat?.average)}</p>
          <p>Peak {formatMetricValue(metric.unit, stat?.max)}</p>
        </div>
      </div>

      {trend.points.length > 0 ? (
        <svg viewBox="0 0 320 130" className="h-32 w-full overflow-visible">
          <line x1="14" y1="14" x2="306" y2="14" stroke="rgba(148, 163, 184, 0.18)" strokeDasharray="4 6" />
          <line x1="14" y1="65" x2="306" y2="65" stroke="rgba(148, 163, 184, 0.14)" strokeDasharray="4 6" />
          <line x1="14" y1="116" x2="306" y2="116" stroke="rgba(148, 163, 184, 0.18)" strokeDasharray="4 6" />
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
