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
import axios from "axios";
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { PriceChart } from "../components/dashboard/PriceChart";

export default function Analytics() {
	const [items, setItems] = useState([]);
	const [tags, setTags] = useState([]);
	const [mode, setMode] = useState("single"); // "single" or "tag"

	const [selectedItemId, setSelectedItemId] = useState(null);
	const [selectedTag, setSelectedTag] = useState(null);

	const [timeWindowIds, setTimeWindowIds] = useState("30"); // days
	const [stdDevThreshold, setStdDevThreshold] = useState("2.0");

	const [analyticsData, setAnalyticsData] = useState(null);
	const [multiSeriesData, setMultiSeriesData] = useState([]);
	const [seriesConfig, setSeriesConfig] = useState([]);

	const [loading, setLoading] = useState(false);
	const [filterOutliers, setFilterOutliers] = useState(false);

	const [showForecast, setShowForecast] = useState(false);

	useEffect(() => {
		fetchItems();
	}, []);

	useEffect(() => {
		if (mode === "single" && selectedItemId) {
			fetchSingleAnalytics(
				selectedItemId,
				timeWindowIds,
				filterOutliers,
				stdDevThreshold,
			);
		} else if (mode === "tag" && selectedTag) {
			fetchTagAnalytics(
				selectedTag,
				timeWindowIds,
				filterOutliers,
				stdDevThreshold,
			);
		}
	}, [
		selectedItemId,
		selectedTag,
		mode,
		timeWindowIds,
		filterOutliers,
		stdDevThreshold,
	]);

	const fetchItems = async () => {
		try {
			const response = await axios.get("/api/items");
			setItems(response.data);

			// Extract unique tags
			const allTags = new Set();
			for (const item of response.data) {
				if (item.tags) {
					for (const tag of item.tags.split(",")) {
						allTags.add(tag.trim());
					}
				}
			}
			setTags(Array.from(allTags));

			if (response.data.length > 0) {
				setSelectedItemId(response.data[0].id.toString());
			}

			if (allTags.size > 0 && !selectedTag) {
				const tagList = Array.from(allTags);
				setSelectedTag(tagList[0]);
			}
		} catch (error) {
			console.error("Failed to fetch items:", error);
		}
	};

	const fetchSingleAnalytics = async (itemId, days, outliers, threshold) => {
		setLoading(true);
		try {
			let url = `/api/items/${itemId}/analytics?days=${days}`;
			if (outliers) {
				url += `&std_dev_threshold=${threshold}`;
			}
			const response = await axios.get(url);
			setAnalyticsData(response.data);

			// Setup data for PriceChart
			// Setup data for PriceChart
			let historyData = response.data.history;
			const series = [
				{ key: "price", name: "Price", color: "hsl(var(--primary))" },
			];

			if (response.data.forecast && response.data.forecast.length > 0) {
				// We need to merge or append forecast data
				// Current PriceChart expects a single array 'data'.
				// The forecast data has 'forecast_date' instead of 'timestamp'.
				// And 'predicted_price', 'yhat_lower', 'yhat_upper'.

				const forecastPoints = response.data.forecast.map((f) => ({
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

			setMultiSeriesData(historyData);
			setSeriesConfig(series);
		} catch (error) {
			console.error("Failed to fetch analytics:", error);
		} finally {
			setLoading(false);
		}
	};

	const fetchTagAnalytics = async (tag, days, outliers, threshold) => {
		setLoading(true);
		try {
			// Find all items with this tag
			const taggedItems = items.filter((item) =>
				item.tags
					?.split(",")
					.map((t) => t.trim())
					.includes(tag),
			);

			if (taggedItems.length === 0) {
				setMultiSeriesData([]);
				setSeriesConfig([]);
				setLoading(false);
				return;
			}

			const promises = taggedItems.map((item) => {
				let url = `/api/items/${item.id}/analytics?days=${days}`;
				if (outliers) {
					url += `&std_dev_threshold=${threshold}`;
				}
				return axios.get(url).then((res) => ({
					itemId: item.id,
					name: item.name,
					data: res.data.history,
				}));
			});

			const results = await Promise.all(promises);

			// Merge data for chart
			// We need a unified timestamp axis.
			// Strategy: Collect all unique timestamps, sort them.
			// For each timestamp, find the price for each item.
			// Since timestamps might not match exactly, we might want to round to hours or just plot points.
			// Simplest for now: Just flatten all points and let connectNulls do the work,
			// OR map each item's price to its own key "price_{itemId}" at its specific timestamp.

			const mergedData = [];
			const series = [];
			const COLORS = [
				"#ef4444",
				"#3b82f6",
				"#22c55e",
				"#eab308",
				"#a855f7",
				"#ec4899",
				"#f97316",
			];

			let index = 0;
			for (const res of results) {
				const key = `price_${res.itemId}`;
				series.push({
					key: key,
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

			setMultiSeriesData(mergedData);
			setSeriesConfig(series);
			setAnalyticsData(null); // Disable single item stats view
		} catch (error) {
			console.error("Failed to fetch tag analytics:", error);
		} finally {
			setLoading(false);
		}
	};

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
								value={timeWindowIds}
								onChange={(e) => setTimeWindowIds(e.target.value)}
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
									data={multiSeriesData}
									series={seriesConfig.filter(
										(s) => showForecast || s.key !== "predicted_price",
									)}
									annotations={analyticsData?.annotations}
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
											className={`text-xs ${analyticsData.stats.price_change_24h < 0
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
