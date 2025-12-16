import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
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
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { API_URL } from "@/lib/api";
import { format } from "date-fns";
import { ArrowLeft, ArrowRight, Edit2, Loader2, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

export default function History() {
	const [items, setItems] = useState([]);
	const [selectedItemId, setSelectedItemId] = useState(null);
	const [historyData, setHistoryData] = useState([]);
	const [loading, setLoading] = useState(false);
	const [page, setPage] = useState(1);
	const [totalPages, setTotalPages] = useState(1);
	const [totalRecords, setTotalRecords] = useState(0);
	const pageSize = 50;

	const [editingRecord, setEditingRecord] = useState(null);
	const [editDialogOpen, setEditDialogOpen] = useState(false);
	const [updatePrice, setUpdatePrice] = useState("");
	const [updateInStock, setUpdateInStock] = useState(false);

	// Filter states
	const [filterMinPrice, setFilterMinPrice] = useState("");
	const [filterMaxPrice, setFilterMaxPrice] = useState("");
	const [filterInStock, setFilterInStock] = useState("all");
	const [filterMinConfidence, setFilterMinConfidence] = useState("");

	useEffect(() => {
		fetchItems();
	}, []);

	useEffect(() => {
		if (selectedItemId) {
			fetchHistory(
				selectedItemId,
				page,
				filterMinPrice,
				filterMaxPrice,
				filterInStock,
				filterMinConfidence,
			);
		} else {
			setHistoryData([]);
			setTotalRecords(0);
		}
	}, [
		selectedItemId,
		page,
		filterMinPrice,
		filterMaxPrice,
		filterInStock,
		filterMinConfidence,
	]);

	const fetchItems = async () => {
		try {
			const res = await fetch(`${API_URL}/items`);
			if (!res.ok) throw new Error("Failed to fetch items");
			const data = await res.json();
			setItems(data);
		} catch (error) {
			toast.error("Failed to load items");
			console.error(error);
		}
	};

	const fetchHistory = async (
		itemId,
		pageNum,
		minPrice,
		maxPrice,
		inStock,
		minConfidence,
	) => {
		setLoading(true);
		try {
			const queryParams = new URLSearchParams({
				page: pageNum,
				size: pageSize,
				sort: "desc",
			});

			if (minPrice) queryParams.append("min_price", minPrice);
			if (maxPrice) queryParams.append("max_price", maxPrice);
			if (inStock !== "all") queryParams.append("in_stock", inStock === "true");
			if (minConfidence)
				queryParams.append("min_confidence", Number(minConfidence) / 100);

			const res = await fetch(
				`${API_URL}/items/${itemId}/history?${queryParams.toString()}`,
			);

			if (!res.ok) throw new Error("Failed to fetch history");
			const data = await res.json();
			setHistoryData(data.items);
			setTotalRecords(data.total);
			setTotalPages(Math.ceil(data.total / data.size));
		} catch (error) {
			toast.error("Failed to load history");
			console.error(error);
		} finally {
			setLoading(false);
		}
	};

	const handleDelete = async (historyId) => {
		if (!confirm("Are you sure you want to delete this record?")) return;

		try {
			const res = await fetch(`${API_URL}/items/history/${historyId}`, {
				method: "DELETE",
			});
			if (!res.ok) throw new Error("Failed to delete record");

			toast.success("Record deleted");
			fetchHistory(
				selectedItemId,
				page,
				filterMinPrice,
				filterMaxPrice,
				filterInStock,
				filterMinConfidence,
			); // Refresh
		} catch (error) {
			toast.error("Failed to delete");
			console.error(error);
		}
	};

	const handleEditClick = (record) => {
		setEditingRecord(record);
		setUpdatePrice(record.price);
		setUpdateInStock(record.in_stock ?? true);
		setEditDialogOpen(true);
	};

	const handleSaveEdit = async () => {
		try {
			const res = await fetch(`${API_URL}/items/history/${editingRecord.id}`, {
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					price: Number.parseFloat(updatePrice),
					in_stock: updateInStock,
				}),
			});

			if (!res.ok) throw new Error("Failed to update record");

			toast.success("Record updated");
			setEditDialogOpen(false);
			fetchHistory(
				selectedItemId,
				page,
				filterMinPrice,
				filterMaxPrice,
				filterInStock,
				filterMinConfidence,
			);
		} catch (error) {
			toast.error("Update failed");
			console.error(error);
		}
	};

	return (
		<div className="container mx-auto p-4 space-y-6">
			<div className="flex justify-between items-center">
				<h1 className="text-3xl font-bold">Item History</h1>
				<div className="w-1/3 min-w-[300px]">
					<Select
						value={selectedItemId ? selectedItemId.toString() : ""}
						onValueChange={(val) => {
							setSelectedItemId(val);
							setPage(1); // Reset to first page on item change
							// Reset filters when item changes? Maybe not, keep them persistent is better UX usually.
						}}
					>
						<SelectTrigger>
							<SelectValue placeholder="Select an item to view history" />
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
			</div>

			<Card>
				<CardHeader>
					<CardTitle>
						{selectedItemId
							? `History Records (${totalRecords})`
							: "Select an item"}
					</CardTitle>
				</CardHeader>
				<CardContent>
					{!selectedItemId ? (
						<div className="text-center py-10 text-muted-foreground">
							Please select an item to view its history database.
						</div>
					) : (
						<>
							{/* Filters Bar */}
							<div className="flex flex-wrap gap-4 mb-4 p-4 bg-muted/50 rounded-lg">
								<div className="space-y-1">
									<Label>Min Price</Label>
									<Input
										type="number"
										placeholder="Min"
										className="w-24"
										value={filterMinPrice}
										onChange={(e) => {
											setFilterMinPrice(e.target.value);
											setPage(1);
										}}
									/>
								</div>
								<div className="space-y-1">
									<Label>Max Price</Label>
									<Input
										type="number"
										placeholder="Max"
										className="w-24"
										value={filterMaxPrice}
										onChange={(e) => {
											setFilterMaxPrice(e.target.value);
											setPage(1);
										}}
									/>
								</div>
								<div className="space-y-1">
									<Label>Stock Status</Label>
									<Select
										value={filterInStock}
										onValueChange={(val) => {
											setFilterInStock(val);
											setPage(1);
										}}
									>
										<SelectTrigger className="w-32">
											<SelectValue />
										</SelectTrigger>
										<SelectContent>
											<SelectItem value="all">All</SelectItem>
											<SelectItem value="true">In Stock</SelectItem>
											<SelectItem value="false">Out of Stock</SelectItem>
										</SelectContent>
									</Select>
								</div>
								<div className="space-y-1">
									<Label>Min Confidence %</Label>
									<Input
										type="number"
										placeholder="0-100"
										className="w-32"
										value={filterMinConfidence}
										onChange={(e) => {
											setFilterMinConfidence(e.target.value);
											setPage(1);
										}}
										min="0"
										max="100"
									/>
								</div>
								<div className="flex items-end">
									<Button
										variant="secondary"
										onClick={() => {
											setFilterMinPrice("");
											setFilterMaxPrice("");
											setFilterInStock("all");
											setFilterMinConfidence("");
											setPage(1);
										}}
									>
										Reset
									</Button>
								</div>
							</div>

							<div className="rounded-md border">
								<Table>
									<TableHeader>
										<TableRow>
											<TableHead>Timestamp</TableHead>
											<TableHead>Price</TableHead>
											<TableHead>Stock Status</TableHead>
											<TableHead>Confidence (Price / Stock)</TableHead>
											<TableHead className="text-right">Actions</TableHead>
										</TableRow>
									</TableHeader>
									<TableBody>
										{loading ? (
											<TableRow>
												<TableCell colSpan={5} className="h-24 text-center">
													<div className="flex justify-center items-center">
														<Loader2 className="h-6 w-6 animate-spin mr-2" />
														Loading...
													</div>
												</TableCell>
											</TableRow>
										) : historyData.length === 0 ? (
											<TableRow>
												<TableCell colSpan={5} className="h-24 text-center">
													No history found.
												</TableCell>
											</TableRow>
										) : (
											historyData.map((record) => (
												<TableRow key={record.id}>
													<TableCell>
														{format(
															new Date(record.timestamp),
															"MMM d, yyyy HH:mm:ss",
														)}
													</TableCell>
													<TableCell>${record.price.toFixed(2)}</TableCell>
													<TableCell>
														<span
															className={`px-2 py-1 rounded text-xs ${
																record.in_stock
																	? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100"
																	: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100"
															}`}
														>
															{record.in_stock ? "In Stock" : "Out of Stock"}
														</span>
													</TableCell>
													<TableCell>
														{record.price_confidence
															? `${(record.price_confidence * 100).toFixed(0)}%`
															: "-"}{" "}
														/{" "}
														{record.in_stock_confidence
															? `${(record.in_stock_confidence * 100).toFixed(
																	0,
																)}%`
															: "-"}
													</TableCell>
													<TableCell className="text-right gap-2">
														<div className="flex justify-end gap-2">
															<Button
																variant="outline"
																size="sm"
																onClick={() => handleEditClick(record)}
															>
																<Edit2 className="h-4 w-4" />
															</Button>
															<Button
																variant="destructive"
																size="sm"
																onClick={() => handleDelete(record.id)}
															>
																<Trash2 className="h-4 w-4" />
															</Button>
														</div>
													</TableCell>
												</TableRow>
											))
										)}
									</TableBody>
								</Table>
							</div>

							{/* Pagination */}
							{totalPages > 1 && (
								<div className="flex items-center justify-end space-x-2 py-4">
									<Button
										variant="outline"
										size="sm"
										onClick={() => setPage((p) => Math.max(1, p - 1))}
										disabled={page === 1 || loading}
									>
										<ArrowLeft className="h-4 w-4 mr-2" />
										Previous
									</Button>
									<div className="text-sm font-medium">
										Page {page} of {totalPages}
									</div>
									<Button
										variant="outline"
										size="sm"
										onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
										disabled={page === totalPages || loading}
									>
										Next
										<ArrowRight className="h-4 w-4 ml-2" />
									</Button>
								</div>
							)}
						</>
					)}
				</CardContent>
			</Card>

			<Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Edit History Record</DialogTitle>
						<DialogDescription>
							Make changes to this historical record.
						</DialogDescription>
					</DialogHeader>
					<div className="grid gap-4 py-4">
						<div className="grid grid-cols-4 items-center gap-4">
							<Label htmlFor="price" className="text-right">
								Price
							</Label>
							<Input
								id="price"
								type="number"
								step="0.01"
								value={updatePrice}
								onChange={(e) => setUpdatePrice(e.target.value)}
								className="col-span-3"
							/>
						</div>
						<div className="grid grid-cols-4 items-center gap-4">
							<Label htmlFor="instock" className="text-right">
								In Stock
							</Label>
							<div className="col-span-3 flex items-center space-x-2">
								<Switch
									id="instock"
									checked={updateInStock}
									onCheckedChange={setUpdateInStock}
								/>
								<span>{updateInStock ? "Yes" : "No"}</span>
							</div>
						</div>
					</div>
					<DialogFooter>
						<Button variant="outline" onClick={() => setEditDialogOpen(false)}>
							Cancel
						</Button>
						<Button onClick={handleSaveEdit}>Save Changes</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}
