import {
	Area,
	CartesianGrid,
	ComposedChart,
	Line,
	ReferenceArea,
	ReferenceDot,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import { formatAxisPrice, formatDateTime, formatPrice } from "@/format";

export const SERIES_COLORS = [
	"#2563eb",
	"#dc2626",
	"#16a34a",
	"#d97706",
	"#9333ea",
	"#db2777",
	"#0891b2",
	"#65a30d",
];
export const FORECAST_COLOR = "#9333ea";
const DAY = 86_400_000;
const AXIS = {
	stroke: "var(--muted)",
	fontSize: 12,
	tickLine: false,
	axisLine: false,
};

function ChartTooltip({ active, payload, series }) {
	if (!active || !payload?.length) return null;
	const point = payload[0].payload;
	return (
		<div className="rounded-md border border-border bg-surface px-3 py-2 text-xs shadow-md">
			<div className="mb-1 font-medium">{formatDateTime(point.t)}</div>
			{series.map(
				(s) =>
					point[s.key] != null && (
						<div key={s.key} className="flex items-center gap-2">
							<span
								className="size-2 rounded-full"
								style={{ background: s.color }}
							/>
							<span className="text-muted">{s.name}</span>
							<span className="ml-auto pl-3 font-medium tabular-nums">
								{formatPrice(point[s.key], s.currency)}
							</span>
						</div>
					),
			)}
			{point.in_stock === false && (
				<div className="mt-1 text-red-500">Out of stock</div>
			)}
		</div>
	);
}

/**
 * data: points sorted by `t` (ms) with a value per series key, plus optional
 * `band` ([low, high]) for the forecast range and `in_stock`.
 * currency labels the axis; leave it out when series use different currencies.
 */
export function PriceChart({
	data,
	series,
	currency,
	outOfStock = [],
	markers = [],
	band = false,
}) {
	const start = data[0]?.t ?? 0;
	const span = (data.at(-1)?.t ?? 0) - start;
	const ticks = Array.from({ length: 6 }, (_, i) => start + (span * i) / 5);
	const formatTick = (t) =>
		new Date(t).toLocaleString(
			undefined,
			span < 2 * DAY
				? { hour: "numeric", minute: "2-digit" }
				: { month: "short", day: "numeric" },
		);

	return (
		<div className="h-72 w-full sm:h-80">
			<ResponsiveContainer>
				<ComposedChart
					data={data}
					margin={{ top: 20, right: 12, bottom: 0, left: 0 }}
				>
					<CartesianGrid vertical={false} stroke="var(--border)" />
					<XAxis
						dataKey="t"
						type="number"
						scale="time"
						domain={["dataMin", "dataMax"]}
						ticks={ticks}
						tickFormatter={formatTick}
						{...AXIS}
					/>
					<YAxis
						domain={["auto", "auto"]}
						tickFormatter={(v) =>
							currency ? formatAxisPrice(v, currency) : v.toLocaleString()
						}
						width={64}
						{...AXIS}
					/>
					<Tooltip content={<ChartTooltip series={series} />} />
					{outOfStock.map(([start, end]) => (
						<ReferenceArea
							key={start}
							x1={start}
							x2={end}
							fill="#ef4444"
							fillOpacity={0.1}
						/>
					))}
					{band && (
						<Area
							dataKey="band"
							stroke="none"
							fill={FORECAST_COLOR}
							fillOpacity={0.12}
							isAnimationActive={false}
						/>
					)}
					{series.map((s) => (
						<Line
							key={s.key}
							dataKey={s.key}
							name={s.name}
							stroke={s.color}
							strokeWidth={2}
							strokeDasharray={s.dashed ? "5 4" : undefined}
							type={s.dashed ? "monotone" : "stepAfter"}
							dot={false}
							connectNulls
							isAnimationActive={false}
						/>
					))}
					{markers.map((m) => (
						<ReferenceDot
							key={`${m.type}-${m.t}`}
							x={m.t}
							y={m.price}
							r={4}
							fill={m.type === "min" ? "#16a34a" : "#dc2626"}
							stroke="var(--surface)"
							strokeWidth={2}
							label={{
								value: formatPrice(m.price, currency),
								position: m.type === "min" ? "bottom" : "top",
								fontSize: 11,
								fill: "var(--muted)",
							}}
						/>
					))}
				</ComposedChart>
			</ResponsiveContainer>
		</div>
	);
}

export const toTime = (timestamp) => new Date(timestamp).getTime();

/** [start, end] time ranges during which the item was out of stock. */
export function outOfStockRanges(points) {
	const ranges = [];
	let start = null;
	for (const [index, point] of points.entries()) {
		if (point.in_stock === false) {
			start ??= point.t;
		} else if (start !== null) {
			ranges.push([start, point.t]);
			start = null;
		}
		if (start !== null && index === points.length - 1)
			ranges.push([start, point.t]);
	}
	return ranges;
}
