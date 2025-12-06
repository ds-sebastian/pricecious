
import {
    CartesianGrid,
    Label,
    Legend,
    Line,
    LineChart,
    ReferenceDot,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

const COLORS = [
    "hsl(var(--primary))",
    "#ef4444", // red-500
    "#3b82f6", // blue-500
    "#22c55e", // green-500
    "#eab308", // yellow-500
    "#a855f7", // purple-500
    "#ec4899", // pink-500
    "#f97316", // orange-500
];

export function PriceChart({ data, series = [], annotations = [] }) {
    if (!data || data.length === 0) {
        return (
            <div className="flex h-[300px] w-full items-center justify-center rounded-lg border border-dashed text-muted-foreground">
                No price history available
            </div>
        );
    }

    // Default series if none provided
    const chartSeries =
        series.length > 0
            ? series
            : [{ key: "price", name: "Price", color: "hsl(var(--primary))" }];

    const sortedData = [...data].sort(
        (a, b) => new Date(a.timestamp) - new Date(b.timestamp),
    );

    const CustomTooltip = ({ active, payload, label }) => {
        if (active && payload && payload.length) {
            return (
                <div className="rounded-lg border bg-background p-2 shadow-sm">
                    <p className="font-medium text-foreground">
                        {new Date(label).toLocaleString()}
                    </p>
                    {payload.map((entry, index) => (
                        <p key={index} className="text-sm" style={{ color: entry.color }}>
                            {entry.name}: ${entry.value?.toFixed(2)}
                        </p>
                    ))}
                </div>
            );
        }
        return null;
    };

    return (
        <div className="h-[400px] w-full">
            <ResponsiveContainer width="100%" height="100%">
                <LineChart
                    data={sortedData}
                    margin={{
                        top: 5,
                        right: 10,
                        left: 10,
                        bottom: 5,
                    }}
                >
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis
                        dataKey="timestamp"
                        tickFormatter={(value) => new Date(value).toLocaleDateString()}
                        className="text-xs text-muted-foreground"
                    />
                    <YAxis
                        domain={["auto", "auto"]}
                        tickFormatter={(value) => `$${value} `}
                        className="text-xs text-muted-foreground"
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend />
                    {chartSeries.map((s, index) => (
                        <Line
                            key={s.key}
                            type="monotone"
                            dataKey={s.key}
                            name={s.name}
                            stroke={s.color || COLORS[index % COLORS.length]}
                            strokeWidth={2}
                            dot={{ r: 4, fill: "hsl(var(--background))", strokeWidth: 2 }}
                            activeDot={{ r: 6 }}
                            connectNulls
                        />
                    ))}
                    {/* Annotations */}
                    {series.length === 1 && annotations?.map((note, index) => (
                        <ReferenceDot
                            key={index}
                            x={note.timestamp}
                            y={note.value}
                            r={6}
                            fill={note.type === "min" ? "#22c55e" : "#ef4444"}
                            stroke="white"
                            strokeWidth={2}
                        >
                            <Label
                                value={note.label}
                                position="top"
                                offset={10}
                                className="fill-foreground text-xs font-medium"
                                style={{ fill: "currentColor" }}
                            />
                        </ReferenceDot>
                    ))}

                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
