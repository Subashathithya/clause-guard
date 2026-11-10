import type { CSSProperties, ReactNode } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export const CHART = {
  brand: '#4f46e5',
  brandLight: '#6366f1',
  red: '#dc2626',
  amber: '#d97706',
  green: '#16a34a',
  grid: 'rgba(148, 163, 184, 0.22)',
  axis: '#94a3b8',
  ink: '#0f172a',
} as const;

const tooltipStyle: CSSProperties = {
  borderRadius: 10,
  border: '1px solid var(--border, #e5e7eb)',
  background: '#ffffff',
  boxShadow: '0 10px 30px rgba(15, 23, 42, 0.12)',
  fontSize: 12,
  padding: '8px 10px',
  color: CHART.ink,
};

/** Centered label shown inside a donut. */
function DonutCenter({ total, label }: { total: number; label: string }) {
  return (
    <div className="chart-center">
      <span className="chart-center-value">{total}</span>
      <span className="chart-center-label">{label}</span>
    </div>
  );
}

export function RiskDonut({
  red,
  yellow,
  green,
  height = 230,
}: {
  red: number;
  yellow: number;
  green: number;
  height?: number;
}) {
  const data = [
    { name: 'High', value: red, color: CHART.red },
    { name: 'Moderate', value: yellow, color: CHART.amber },
    { name: 'Low', value: green, color: CHART.green },
  ].filter((d) => d.value > 0);
  const total = red + yellow + green;

  if (total === 0) {
    return <div className="chart-empty">No clauses analysed yet</div>;
  }

  return (
    <div className="chart-wrap" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius="62%"
            outerRadius="88%"
            paddingAngle={2}
            stroke="#ffffff"
            strokeWidth={2}
          >
            {data.map((d) => (
              <Cell key={d.name} fill={d.color} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} formatter={(v, n) => [`${v} clauses`, String(n)]} />
        </PieChart>
      </ResponsiveContainer>
      <DonutCenter total={total} label="clauses" />
    </div>
  );
}

export function CategoryBars({
  data,
  height = 260,
}: {
  data: { name: string; value: number }[];
  height?: number;
}) {
  if (data.length === 0) return <div className="chart-empty">Nothing to chart yet</div>;
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 18, left: 4, bottom: 4 }}>
          <CartesianGrid horizontal={false} stroke={CHART.grid} />
          <XAxis type="number" tick={{ fontSize: 11, fill: CHART.axis }} axisLine={false} tickLine={false} allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="name"
            width={118}
            tick={{ fontSize: 11, fill: CHART.axis }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(99, 102, 241, 0.08)' }} formatter={(v) => [`${v}`, 'clauses']} />
          <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={16}>
            {data.map((d, i) => (
              <Cell key={d.name} fill={i === 0 ? CHART.brand : i === 1 ? CHART.brandLight : '#a5b4fc'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ActivityArea({
  data,
  height = 230,
}: {
  data: { label: string; count: number }[];
  height?: number;
}) {
  if (data.length === 0) return <div className="chart-empty">No activity yet</div>;
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="cgArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART.brandLight} stopOpacity={0.45} />
              <stop offset="100%" stopColor={CHART.brandLight} stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: CHART.axis }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: CHART.axis }} axisLine={false} tickLine={false} allowDecimals={false} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v} contracts`, 'Analysed']} />
          <Area
            type="monotone"
            dataKey="count"
            stroke={CHART.brand}
            strokeWidth={2.5}
            fill="url(#cgArea)"
            dot={{ r: 3, fill: CHART.brand, strokeWidth: 0 }}
            activeDot={{ r: 5 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RiskStackedBars({
  data,
  height = 260,
}: {
  data: { name: string; high: number; moderate: number; low: number }[];
  height?: number;
}) {
  if (data.length === 0) return <div className="chart-empty">Nothing to chart yet</div>;
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: CHART.axis }} axisLine={false} tickLine={false} interval={0} />
          <YAxis tick={{ fontSize: 11, fill: CHART.axis }} axisLine={false} tickLine={false} allowDecimals={false} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(148, 163, 184, 0.12)' }} />
          <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" iconSize={8} />
          <Bar dataKey="low" name="Low" stackId="a" fill={CHART.green} radius={[0, 0, 0, 0]} barSize={26} />
          <Bar dataKey="moderate" name="Moderate" stackId="a" fill={CHART.amber} />
          <Bar dataKey="high" name="High" stackId="a" fill={CHART.red} radius={[5, 5, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ChartCard({
  title,
  subtitle,
  children,
  actions,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="card card-pad chart-card">
      <div className="card-header">
        <div>
          <h3 className="card-title">{title}</h3>
          {subtitle && <p className="card-subtitle mt-2">{subtitle}</p>}
        </div>
        {actions && <div>{actions}</div>}
      </div>
      {children}
    </div>
  );
}
