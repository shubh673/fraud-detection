import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHART_PALETTE } from "../utils/theme";

export interface Datum {
  name: string;
  value: number;
  color?: string;
}

const axisStyle = { fontSize: 11, fill: "#8b8b94" };
const cursorFill = "#26262b";
const tooltipStyle = {
  fontSize: 12,
  borderRadius: 8,
  border: "1px solid #2f2f36",
  background: "#161619",
  color: "#e9e9ee",
};

export function BarChartCard({ data, height = 240 }: { data: Datum[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -10, bottom: 4 }}>
        <XAxis dataKey="name" tick={axisStyle} interval={0} angle={0} />
        <YAxis tick={axisStyle} allowDecimals={false} />
        <Tooltip
          cursor={{ fill: cursorFill }}
          contentStyle={tooltipStyle}
          formatter={(v) => Number(v).toLocaleString()}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.color ?? CHART_PALETTE[i % CHART_PALETTE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function HBarChartCard({ data, height = 280 }: { data: Datum[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
        <XAxis type="number" tick={axisStyle} allowDecimals={false} />
        <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#a1a1aa" }} width={150} />
        <Tooltip
          cursor={{ fill: cursorFill }}
          contentStyle={tooltipStyle}
          formatter={(v) => Number(v).toLocaleString()}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.color ?? CHART_PALETTE[i % CHART_PALETTE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function DonutChartCard({ data, height = 240 }: { data: Datum[]; height?: number }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <div className="flex items-center gap-4">
      <ResponsiveContainer width="55%" height={height}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="85%" paddingAngle={2}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.color ?? CHART_PALETTE[i % CHART_PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v) => Number(v).toLocaleString()}
          />
        </PieChart>
      </ResponsiveContainer>
      <ul className="flex-1 space-y-1.5 text-xs">
        {data.map((d, i) => (
          <li key={d.name} className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-sm"
                style={{ background: d.color ?? CHART_PALETTE[i % CHART_PALETTE.length] }}
              />
              <span className="text-slate-600">{d.name}</span>
            </span>
            <span className="tabular font-medium text-slate-800">
              {d.value.toLocaleString()}
              {total > 0 && <span className="ml-1 text-slate-400">({((d.value / total) * 100).toFixed(0)}%)</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
