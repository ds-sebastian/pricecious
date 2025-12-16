import { DeleteConfirmationModal } from "@/components/dashboard/DeleteConfirmationModal";
import { ItemCard } from "@/components/dashboard/ItemCard";
import { ItemModal } from "@/components/dashboard/ItemModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { Plus, RefreshCw, Search, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { API_URL } from "@/lib/api";

export default function Dashboard() {
	const queryClient = useQueryClient();
	const [searchTerm, setSearchTerm] = useState("");
	const [showAddModal, setShowAddModal] = useState(false);
	const [editingItem, setEditingItem] = useState(null);
	const [itemToDelete, setItemToDelete] = useState(null);
	const [zoomedImage, setZoomedImage] = useState(null);

	// Fetch items with polling
	const { data: items = [] } = useQuery({
		queryKey: ["items"],
		queryFn: async () => {
			const response = await axios.get(`${API_URL}/items`);
			return response.data.sort((a, b) => a.id - b.id);
		},
		refetchInterval: 30000,
		refetchOnWindowFocus: true,
	});

	// Mutations
	const checkMutation = useMutation({
		mutationFn: async (id) => {
			await axios.post(`${API_URL}/items/${id}/check`);
		},
		onSuccess: () => {
			toast.success("Check started in background");
			queryClient.invalidateQueries({ queryKey: ["items"] });
		},
		onError: (error) => {
			console.error("Error triggering check:", error);
			toast.error("Failed to trigger check");
		},
	});

	const refreshAllMutation = useMutation({
		mutationFn: async () => {
			await axios.post(`${API_URL}/jobs/refresh-all`);
		},
		onMutate: async () => {
			// Optimistically update UI to show refreshing state
			await queryClient.cancelQueries({ queryKey: ["items"] });
			const previousItems = queryClient.getQueryData(["items"]);
			queryClient.setQueryData(["items"], (old) =>
				old?.map((item) => ({ ...item, is_refreshing: true })),
			);
			return { previousItems };
		},
		onSuccess: () => {
			toast.success("Refresh all started");
		},
		onError: (error, variables, context) => {
			console.error("Error triggering refresh all:", error);
			toast.error("Failed to trigger refresh all");
			if (context?.previousItems) {
				queryClient.setQueryData(["items"], context.previousItems);
			}
		},
		onSettled: () => {
			queryClient.invalidateQueries({ queryKey: ["items"] });
		},
	});

	const deleteMutation = useMutation({
		mutationFn: async (id) => {
			await axios.delete(`${API_URL}/items/${id}`);
		},
		onSuccess: () => {
			toast.success("Item deleted");
			queryClient.invalidateQueries({ queryKey: ["items"] });
			setItemToDelete(null);
		},
		onError: (error) => {
			console.error("Error deleting item:", error);
			toast.error("Failed to delete item");
		},
	});

	const handleCheck = (id) => {
		toast.info("Check triggered...");
		checkMutation.mutate(id);
	};

	const handleRefreshAll = () => {
		toast.info("Triggering refresh for all items...");
		refreshAllMutation.mutate();
	};

	const handleDelete = () => {
		if (!itemToDelete) return;
		deleteMutation.mutate(itemToDelete.id);
	};

	const filteredItems = items.filter((item) => {
		const term = searchTerm.toLowerCase();
		return (
			item.name.toLowerCase().includes(term) ||
			item.url.toLowerCase().includes(term) ||
			item.tags?.toLowerCase().includes(term) ||
			item.description?.toLowerCase().includes(term)
		);
	});

	return (
		<div className="space-y-6 animate-in fade-in duration-500">
			<div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
				<div>
					<h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
					<p className="text-muted-foreground">
						Manage and monitor your product watchlist.
					</p>
				</div>
				<div className="flex items-center gap-2">
					<div className="relative w-full md:w-64">
						<Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
						<Input
							placeholder="Search items..."
							className="pl-8"
							value={searchTerm}
							onChange={(e) => setSearchTerm(e.target.value)}
						/>
					</div>
					<Button variant="outline" onClick={handleRefreshAll}>
						<RefreshCw className="mr-2 h-4 w-4" />
						Refresh All
					</Button>
					<Button onClick={() => setShowAddModal(true)}>
						<Plus className="mr-2 h-4 w-4" />
						Add Item
					</Button>
				</div>
			</div>

			<div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
				{filteredItems.map((item) => (
					<ItemCard
						key={item.id}
						item={item}
						onEdit={setEditingItem}
						onDelete={setItemToDelete}
						onCheck={handleCheck}
						onZoom={setZoomedImage}
					/>
				))}
			</div>

			<ItemModal
				open={showAddModal}
				onClose={() => setShowAddModal(false)}
				onSaved={() => queryClient.invalidateQueries({ queryKey: ["items"] })}
			/>

			<ItemModal
				open={!!editingItem}
				item={editingItem}
				onClose={() => setEditingItem(null)}
				onSaved={() => queryClient.invalidateQueries({ queryKey: ["items"] })}
			/>

			<DeleteConfirmationModal
				open={!!itemToDelete}
				item={itemToDelete}
				onClose={() => setItemToDelete(null)}
				onConfirm={handleDelete}
			/>

			{/* Image Zoom Modal */}
			{zoomedImage && (
				<button
					type="button"
					className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200 w-full h-full border-0 cursor-default"
					onClick={() => setZoomedImage(null)}
					onKeyDown={(e) => e.key === "Escape" && setZoomedImage(null)}
				>
					<div className="relative max-h-full max-w-full">
						<img
							src={zoomedImage}
							alt="Zoomed screenshot"
							className="max-h-[90vh] max-w-[90vw] rounded-lg shadow-2xl"
						/>
						<Button
							size="icon"
							variant="secondary"
							className="absolute -right-4 -top-4 rounded-full shadow-lg"
							onClick={() => setZoomedImage(null)}
						>
							<X className="h-4 w-4" />
						</Button>
					</div>
				</button>
			)}
		</div>
	);
}
