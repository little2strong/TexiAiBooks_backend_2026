import { useLayoutEffect, useRef, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";
import { useReducedMotion } from "../theme/motion";

const example = [
  { month: "May", income: 22, expense: 14, tax: 6, mileage: 30, ai: null },
  { month: "Jun", income: 40, expense: 24, tax: 10, mileage: 42, ai: null },
  { month: "Jul", income: 32, expense: 20, tax: 14, mileage: 38, ai: null },
  { month: "Aug", income: 62, expense: 38, tax: 22, mileage: 65, ai: 62 },
  { month: "Sep", income: 56, expense: 30, tax: 20, mileage: 72, ai: 70 },
  { month: "Oct", income: 80, expense: 44, tax: 30, mileage: 94, ai: 84 },
];
const series = [
  ["income", "Income"],
  ["expense", "Expense"],
  ["info", "Tax"],
  ["brand-primary", "Mileage"],
  ["ai", "AI estimate"],
] as const;

/** Illustrative, unitless series: demonstrates tokens without implying real totals. */
export function ThemeChart() {
  const root = useRef<HTMLDivElement>(null);
  const [duration, setDuration] = useState(0);
  const reduced = useReducedMotion();
  useLayoutEffect(() => {
    if (root.current)
      setDuration(
        parseFloat(
          getComputedStyle(root.current).getPropertyValue("--motion-chart"),
        ),
      );
  }, []);
  return (
    <div ref={root} className="preview-chart">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <LineChart
          data={example}
          accessibilityLayer
          title="Illustrative chart palette, unitless example values"
        >
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis
            dataKey="month"
            axisLine={false}
            tickLine={false}
            tick={{
              fill: "var(--text-secondary)",
              fontSize: "var(--font-caption)",
            }}
          />
          <Tooltip
            content={<ChartTooltip />}
            isAnimationActive={false}
            cursor={{ stroke: "var(--border-strong)" }}
          />
          {series.map(([token, name], index) => (
            <Line
              key={token}
              name={name}
              dataKey={["income", "expense", "tax", "mileage", "ai"][index]}
              type="monotone"
              stroke={`var(--${token})`}
              strokeWidth="var(--focus-width)"
              strokeDasharray={token === "ai" ? "6 4" : undefined}
              dot={false}
              isAnimationActive={!reduced}
              animationDuration={duration}
              animationEasing="ease-out"
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: readonly {
    name?: string;
    value?: number | string;
    dataKey?: string | number;
  }[];
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <strong>{label} · illustrative index</strong>
      {payload.map((item) => (
        <div className="payment-row" key={item.dataKey}>
          <span>{item.name}</span>
          <span className="numeric">{Number(item.value).toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}
