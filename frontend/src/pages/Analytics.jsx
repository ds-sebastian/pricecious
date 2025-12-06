
import { useState, useEffect } from "react";
import axios from "axios";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { PriceChart } from "../components/dashboard/PriceChart";
import { Loader2 } from "lucide-react";

export default function Analytics() {
    const [items, setItems] = useState([]);
    const [selectedItemId, setSelectedItemId] = useState(null);
    const [analyticsData, setAnalyticsData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [filterOutliers, setFilterOutliers] = useState(false);

    useEffect(() => {
        fetchItems();
    }, []);

    useEffect(() => {
        if (selectedItemId) {
            fetchAnalytics(selectedItemId, filterOutliers);
        }
    }, [selectedItemId, filterOutliers]);

    const fetchItems = async () => {
        try {
            const response = await axios.get("/api/items");
            setItems(response.data);
            if (response.data.length > 0) {
                setSelectedItemId(response.data[0].id.toString());
            }
        } catch (error) {
            console.error("Failed to fetch items:", error);
        }
    };

    const fetchAnalytics = async (itemId, filter) => {
        setLoading(true);
        try {
            let url = `/api/items/${itemId}/analytics`;
            if (filter) {
                url += `?std_dev_threshold=2.0`;
            }
            const response = await axios.get(url);
            setAnalyticsData(response.data);
        } catch (error) {
            console.error("Failed to fetch analytics:", error);
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
                <Card className="w-full md:w-[300px]">
                    <CardHeader>
                        <CardTitle>Configuration</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
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

                        <div className="flex items-center space-x-2">
                            <Switch
                                id="outliers"
                                checked={filterOutliers}
                                onCheckedChange={setFilterOutliers}
                            />
                            <Label htmlFor="outliers">Remove Outliers (2σ)</Label>
                        </div>
                    </CardContent>
                </Card>

                <div className="flex-1 space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Price History</CardTitle>
                            <CardDescription>
                                Historical price data over time
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {loading ? (
                                <div className="flex h-[400px] items-center justify-center">
                                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                                </div>
                            ) : (
                                <PriceChart
                                    data={analyticsData?.history || []}
                                    showOutliers={!filterOutliers}
                                />
                            )}
                        </CardContent>
                    </Card>

                    {analyticsData && (
                        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                            <Card>
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm font-medium">
                                        Current Price
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold">
                                        ${analyticsData.stats.latest_price.toFixed(2)}
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
                                        ${analyticsData.stats.avg_price.toFixed(2)}
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
                                        ${analyticsData.stats.min_price.toFixed(2)}
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
                                        ${analyticsData.stats.max_price.toFixed(2)}
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
