import { PackageSearch, Plus, RefreshCw, Search } from "lucide-react";
import { useState } from "react";
import { api, useAction, useItems } from "@/api";
import { ItemCard } from "@/components/ItemCard";
import { ItemFormDialog } from "@/components/ItemForm";
import { ScreenshotDialog } from "@/components/ScreenshotDialog";
import {
	Button,
	ConfirmDialog,
	EmptyState,
	Input,
	Spinner,
} from "@/components/ui";

const matches = (item, query) =>
	[item.name, item.url, item.tags, item.description].some((text) =>
		text?.toLowerCase().includes(query),
	);

export default function Items() {
	const { data: items, isLoading, error } = useItems();
	const [query, setQuery] = useState("");
	const [editing, setEditing] = useState(null); // an item, "new", or null
	const [deleting, setDeleting] = useState(null);
	const [viewing, setViewing] = useState(null);

	const checkAll = useAction(() => api.post("/items/check-all"), {
		success: ({ queued }) =>
			queued
				? `Checking ${queued} item${queued === 1 ? "" : "s"}`
				: "All items are already being checked",
		invalidate: [["items"]],
	});
	const remove = useAction((id) => api.delete(`/items/${id}`), {
		success: "Item deleted",
		invalidate: [["items"]],
		onSuccess: () => setDeleting(null),
	});

	const visible =
		items?.filter((item) => matches(item, query.trim().toLowerCase())) ?? [];

	let content;
	if (isLoading) {
		content = <Spinner className="mx-auto mt-24" />;
	} else if (error) {
		content = (
			<EmptyState title="Couldn't load items">{error.message}</EmptyState>
		);
	} else if (items.length === 0) {
		content = (
			<EmptyState
				icon={PackageSearch}
				title="Track your first product"
				action={
					<Button variant="primary" onClick={() => setEditing("new")}>
						<Plus className="size-4" /> Add item
					</Button>
				}
			>
				Add a product page and Pricecious reads its price and stock from a
				screenshot, on a schedule.
			</EmptyState>
		);
	} else if (visible.length === 0) {
		content = (
			<p className="py-16 text-center text-sm text-muted">
				Nothing matches “{query}”.
			</p>
		);
	} else {
		content = (
			<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
				{visible.map((item) => (
					<ItemCard
						key={item.id}
						item={item}
						onEdit={setEditing}
						onDelete={setDeleting}
						onViewScreenshot={setViewing}
					/>
				))}
			</div>
		);
	}

	return (
		<>
			<div className="mb-6 flex flex-wrap items-center gap-3">
				<h1 className="mr-auto text-2xl font-semibold">
					Items
					{items?.length > 0 && (
						<span className="ml-2 text-base font-normal text-muted">
							{items.length}
						</span>
					)}
				</h1>
				{items?.length > 0 && (
					<>
						<div className="relative w-full sm:w-56">
							<Search className="pointer-events-none absolute top-2.5 left-2.5 size-4 text-muted" />
							<Input
								type="search"
								aria-label="Search items"
								placeholder="Search"
								className="pl-8"
								value={query}
								onChange={(event) => setQuery(event.target.value)}
							/>
						</div>
						<Button busy={checkAll.isPending} onClick={() => checkAll.mutate()}>
							{!checkAll.isPending && <RefreshCw className="size-4" />}
							Check all
						</Button>
						<Button variant="primary" onClick={() => setEditing("new")}>
							<Plus className="size-4" /> Add item
						</Button>
					</>
				)}
			</div>

			{content}

			<ItemFormDialog
				open={editing !== null}
				item={editing === "new" ? undefined : editing}
				onClose={() => setEditing(null)}
			/>
			<ConfirmDialog
				open={!!deleting}
				title="Delete item?"
				onClose={() => setDeleting(null)}
				onConfirm={() => remove.mutate(deleting.id)}
				busy={remove.isPending}
			>
				“{deleting?.name}” and its price history will be removed.
			</ConfirmDialog>
			<ScreenshotDialog item={viewing} onClose={() => setViewing(null)} />
		</>
	);
}
