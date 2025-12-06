
import {
    CartesianGrid,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

export function PriceChart({ data, showOutliers = true }) {
    if (!data || data.length === 0) {
        return (
            <div className="flex h-[300px] w-full items-center justify-center rounded-lg border border-dashed text-muted-foreground">
                No price history available
            </div>
        );
    }

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
                    <p className="text-sm text-primary">
                        Price: ${payload[0].value.toFixed(2)}
                    </p>
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
                        tickFormatter={(value) => `$${value}`}
                        className="text-xs text-muted-foreground"
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Line
                        type="monotone"
                        dataKey="price"
                        stroke="hsl(var(--primary))"
                        strokeWidth={2}
                        dot={{ r: 4, fill: "hsl(var(--background))", strokeWidth: 2 }}
                        activeDot={{ r: 6 }}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
