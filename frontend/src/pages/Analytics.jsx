import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { API_URL, fetchAnalytics, fetchItems } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { Loader2 } from "lucide-react";
import { useMemo, useState } from "react";
import { PriceChart } from "../components/dashboard/PriceChart";

export default function Analytics() {
	const [mode, setMode] = useState("single"); // "single" or "tag"
	const [selectedItemId, setSelectedItemId] = useState(null);
	const [selectedTag, setSelectedTag] = useState(null);
	const [timeWindowDays, setTimeWindowDays] = useState("30");
	const [stdDevThreshold, setStdDevThreshold] = useState("2.0");
	const [filterOutliers, setFilterOutliers] = useState(false);
	const [showForecast, setShowForecast] = useState(false);

	// Fetch all items with React Query
	const { data: items = [] } = useQuery({
		queryKey: ["items"],
		queryFn: fetchItems,
		onSuccess: (data) => {
			// Auto-select first item if none selected
			if (data.length > 0 && !selectedItemId) {
				setSelectedItemId(data[0].id.toString());
			}
		},
	});

	// Extract unique tags from items
	const tags = useMemo(() => {
		const allTags = new Set();
		for (const item of items) {
			if (item.tags) {
				for (const tag of item.tags.split(",")) {
					allTags.add(tag.trim());
				}
			}
		}
		const tagList = Array.from(allTags);
		// Auto-select first tag if none selected
		if (tagList.length > 0 && !selectedTag) {
			setSelectedTag(tagList[0]);
		}
		return tagList;
	}, [items, selectedTag]);

	// Fetch single item analytics with React Query
	const analyticsParams = useMemo(
		() => ({
			days: timeWindowDays,
			stdDevThreshold: filterOutliers ? stdDevThreshold : null,
		}),
		[timeWindowDays, filterOutliers, stdDevThreshold],
	);

	const { data: analyticsData, isLoading: isSingleLoading } = useQuery({
		queryKey: ["analytics", selectedItemId, analyticsParams],
		queryFn: () => fetchAnalytics(selectedItemId, analyticsParams),
		enabled: mode === "single" && !!selectedItemId,
	});

	// Fetch tag analytics (multiple items) with React Query
	const taggedItemIds = useMemo(() => {
		if (mode !== "tag" || !selectedTag) return [];
		return items
			.filter((item) =>
				item.tags
					?.split(",")
					.map((t) => t.trim())
					.includes(selectedTag),
			)
			.map((item) => item.id);
	}, [items, selectedTag, mode]);

	const { data: tagAnalyticsData, isLoading: isTagLoading } = useQuery({
		queryKey: ["tagAnalytics", selectedTag, taggedItemIds, analyticsParams],
		queryFn: async () => {
			if (taggedItemIds.length === 0) return { series: [], data: [] };

			const promises = taggedItemIds.map((id) => {
				let url = `${API_URL}/items/${id}/analytics?days=${analyticsParams.days}`;
				if (analyticsParams.stdDevThreshold) {
					url += `&std_dev_threshold=${analyticsParams.stdDevThreshold}`;
				}
				return axios.get(url).then((res) => ({
					itemId: id,
					name: items.find((i) => i.id === id)?.name || `Item ${id}`,
					data: res.data.history,
				}));
			});

			const results = await Promise.all(promises);

			// Merge data for chart
			const COLORS = [
				"#ef4444",
				"#3b82f6",
				"#22c55e",
				"#eab308",
				"#a855f7",
				"#ec4899",
				"#f97316",
			];
			const mergedData = [];
			const series = [];

			let index = 0;
			for (const res of results) {
				const key = `price_${res.itemId}`;
				series.push({
					key,
					name: res.name,
					color: COLORS[index % COLORS.length],
				});
				index++;

				for (const point of res.data) {
					mergedData.push({
						timestamp: point.timestamp,
						[key]: point.price,
					});
				}
			}

			return { series, data: mergedData };
		},
		enabled: mode === "tag" && taggedItemIds.length > 0,
	});

	// Compute chart data and series based on mode
	const { chartData, chartSeries, annotations } = useMemo(() => {
		if (mode === "single" && analyticsData) {
			let historyData = analyticsData.history || [];
			const series = [
				{ key: "price", name: "Price", color: "hsl(var(--primary))" },
			];

			if (analyticsData.forecast?.length > 0) {
				const forecastPoints = analyticsData.forecast.map((f) => ({
					timestamp: f.forecast_date,
					predicted_price: f.predicted_price,
					yhat_lower: f.yhat_lower,
					yhat_upper: f.yhat_upper,
				}));
				historyData = [...historyData, ...forecastPoints];
				series.push({
					key: "predicted_price",
					name: "Forecast",
					color: "#a855f7",
					strokeDasharray: "5 5",
				});
			}

			return {
				chartData: historyData,
				chartSeries: series.filter(
					(s) => showForecast || s.key !== "predicted_price",
				),
				annotations: analyticsData.annotations,
			};
		}

		if (mode === "tag" && tagAnalyticsData) {
			return {
				chartData: tagAnalyticsData.data,
				chartSeries: tagAnalyticsData.series,
				annotations: null,
			};
		}

		return { chartData: [], chartSeries: [], annotations: null };
	}, [mode, analyticsData, tagAnalyticsData, showForecast]);

	const loading = mode === "single" ? isSingleLoading : isTagLoading;

	if (items.length === 0) {
		return (
			<div className="flex flex-col gap-4 p-8">
				<h1 className="text-3xl font-bold tracking-tight">Analytics</h1>
				<Card>
					<CardContent className="pt-6">
						<div className="flex h-[200px] items-center justify-center text-muted-foreground">
							No items found. Add items to see analytics.
						</div>
					</CardContent>
				</Card>
			</div>
		);
	}

	return (
		<div className="flex flex-col gap-6 p-8">
			<div className="flex flex-col gap-2">
				<h1 className="text-3xl font-bold tracking-tight">Analytics</h1>
				<p className="text-muted-foreground">
					Analyze price history and trends for your tracked items.
				</p>
			</div>

			<div className="flex flex-col gap-6 md:flex-row">
				<Card className="w-full md:w-[350px]">
					<CardHeader>
						<CardTitle>Configuration</CardTitle>
					</CardHeader>
					<CardContent className="space-y-6">
						<div className="space-y-2">
							<Label>Selection Mode</Label>
							<div className="flex gap-2">
								<Button
									variant={mode === "single" ? "default" : "outline"}
									onClick={() => setMode("single")}
									className="flex-1"
								>
									Single Item
								</Button>
								<Button
									variant={mode === "tag" ? "default" : "outline"}
									onClick={() => setMode("tag")}
									className="flex-1"
								>
									By Tag
								</Button>
							</div>
						</div>

						{mode === "single" ? (
							<div className="space-y-2">
								<Label>Select Item</Label>
								<Select
									value={selectedItemId?.toString()}
									onValueChange={setSelectedItemId}
								>
									<SelectTrigger>
										<SelectValue placeholder="Select an item" />
									</SelectTrigger>
									<SelectContent>
										{items.map((item) => (
											<SelectItem key={item.id} value={item.id.toString()}>
												{item.name}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</div>
						) : (
							<div className="space-y-2">
								<Label>Select Tag</Label>
								<Select value={selectedTag} onValueChange={setSelectedTag}>
									<SelectTrigger>
										<SelectValue placeholder="Select a tag" />
									</SelectTrigger>
									<SelectContent>
										{tags.map((tag) => (
											<SelectItem key={tag} value={tag}>
												{tag}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</div>
						)}

						<div className="space-y-2">
							<Label>Time Window (Days)</Label>
							<Input
								type="number"
								value={timeWindowDays}
								onChange={(e) => setTimeWindowDays(e.target.value)}
								min="1"
							/>
						</div>

						<div className="flex items-center justify-between">
							<div className="flex flex-col gap-1">
								<Label htmlFor="outliers">Remove Outliers</Label>
								<span className="text-xs text-muted-foreground">
									Filter spikes &gt; {stdDevThreshold}σ
								</span>
							</div>
							<Switch
								id="outliers"
								checked={filterOutliers}
								onCheckedChange={setFilterOutliers}
							/>
						</div>

						{/* Forecast Toggle - Only in Single Item Mode */}
						{mode === "single" && (
							<div className="flex items-center justify-between">
								<div className="flex flex-col gap-1">
									<Label htmlFor="forecast">Show Forecast [BETA]</Label>
									<span className="text-xs text-muted-foreground">
										Show predicted future prices
									</span>
								</div>
								<Switch
									id="forecast"
									checked={showForecast}
									onCheckedChange={setShowForecast}
								/>
							</div>
						)}

						{filterOutliers && (
							<div className="space-y-2">
								<Label>Threshold (σ)</Label>
								<Input
									type="number"
									value={stdDevThreshold}
									onChange={(e) => setStdDevThreshold(e.target.value)}
									step="0.1"
									min="0.1"
								/>
							</div>
						)}
					</CardContent>
				</Card>

				<div className="flex-1 space-y-6">
					<Card>
						<CardHeader>
							<CardTitle>Price History</CardTitle>
							<CardDescription>
								{mode === "single"
									? "Historical price data for selected item"
									: "Comparing items by tag"}
							</CardDescription>
						</CardHeader>
						<CardContent>
							{loading ? (
								<div className="flex h-[400px] items-center justify-center">
									<Loader2 className="h-8 w-8 animate-spin text-primary" />
								</div>
							) : (
								<PriceChart
									data={chartData}
									series={chartSeries}
									annotations={annotations}
								/>
							)}
						</CardContent>
					</Card>

					{mode === "single" && analyticsData && (
						<div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
							<Card>
								<CardHeader className="pb-2">
									<CardTitle className="text-sm font-medium">
										Current Price
									</CardTitle>
								</CardHeader>
								<CardContent>
									<div className="text-2xl font-bold">
										$
										{Number.parseFloat(
											analyticsData.stats.latest_price.toFixed(2),
										)}
									</div>
									{analyticsData.stats.price_change_24h !== 0 && (
										<p
											className={`text-xs ${
												analyticsData.stats.price_change_24h < 0
													? "text-green-500"
													: "text-red-500"
											}`}
										>
											{analyticsData.stats.price_change_24h > 0 ? "+" : ""}
											{analyticsData.stats.price_change_24h}% (24h)
										</p>
									)}
								</CardContent>
							</Card>
							<Card>
								<CardHeader className="pb-2">
									<CardTitle className="text-sm font-medium">
										Average Price
									</CardTitle>
								</CardHeader>
								<CardContent>
									<div className="text-2xl font-bold">
										$
										{Number.parseFloat(
											analyticsData.stats.avg_price.toFixed(2),
										)}
									</div>
									<p className="text-xs text-muted-foreground">
										σ: ${analyticsData.stats.std_dev}
									</p>
								</CardContent>
							</Card>
							<Card>
								<CardHeader className="pb-2">
									<CardTitle className="text-sm font-medium">
										Lowest Price
									</CardTitle>
								</CardHeader>
								<CardContent>
									<div className="text-2xl font-bold">
										$
										{Number.parseFloat(
											analyticsData.stats.min_price.toFixed(2),
										)}
									</div>
								</CardContent>
							</Card>
							<Card>
								<CardHeader className="pb-2">
									<CardTitle className="text-sm font-medium">
										Highest Price
									</CardTitle>
								</CardHeader>
								<CardContent>
									<div className="text-2xl font-bold">
										$
										{Number.parseFloat(
											analyticsData.stats.max_price.toFixed(2),
										)}
									</div>
								</CardContent>
							</Card>
						</div>
					)}
				</div>
			</div>
		</div>
	);
}
