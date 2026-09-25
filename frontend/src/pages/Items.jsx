import { PackageSearch, Plus, RefreshCw, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, useAction, useItems } from "@/api";
import { ItemCard } from "@/components/ItemCard";
import { ItemFormDialog } from "@/components/ItemForm";
import { ScreenshotDialog } from "@/components/ScreenshotDialog";
import {
	Button,
	ChipGroup,
	ConfirmDialog,
	EmptyState,
	Input,
	Spinner,
} from "@/components/ui";
import { itemName } from "@/format";

const matches = (item, query) =>
	[itemName(item), item.url, item.tags, item.description].some((text) =>
		text?.toLowerCase().includes(query),
	);

const VIEWS = {
	all: { label: "All", test: () => true, empty: "" },
	attention: {
		label: "Needs attention",
		test: (item) => !item.is_active || !!item.last_error,
		empty: "Nothing needs attention.",
	},
	deals: {
		label: "Deals",
		test: (item) => !!item.deal,
		empty: "No item is at its lowest price right now.",
	},
};

export default function Items() {
	const { data: items, isLoading, error } = useItems();
	const [query, setQuery] = useState("");
	const [view, setView] = useState("all");
	const [searchParams, setSearchParams] = useSearchParams();
	// null, an item to edit, or a draft ({} or { url } from the bookmarklet) to add
	const [editing, setEditing] = useState(() =>
		searchParams.has("add") ? { url: searchParams.get("add") } : null,
	);
	const [deleting, setDeleting] = useState(null);
	const [viewing, setViewing] = useState(null);

	const checkAll = useAction(() => api.post("/items/check-all"), {
		success: ({ queued, recently_checked: recent }) => {
			if (!queued)
				return "Every item was checked in the last 5 minutes or is being checked now";
			const message = `Checking ${queued} item${queued === 1 ? "" : "s"}`;
			return recent
				? `${message}; skipped ${recent} checked in the last 5 minutes`
				: message;
		},
		invalidate: [["items"]],
	});
	const remove = useAction((id) => api.delete(`/items/${id}`), {
		success: "Item deleted",
		invalidate: [["items"]],
		onSuccess: () => setDeleting(null),
	});

	useEffect(() => {
		if (searchParams.has("add")) setSearchParams({}, { replace: true });
	}, [searchParams, setSearchParams]);

	const counts = Object.fromEntries(
		Object.entries(VIEWS).map(([key, { test }]) => [
			key,
			items?.filter(test).length ?? 0,
		]),
	);
	const visible =
		items?.filter(
			(item) =>
				VIEWS[view].test(item) && matches(item, query.trim().toLowerCase()),
		) ?? [];

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
					<Button variant="primary" onClick={() => setEditing({})}>
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
				{query ? `Nothing matches “${query}”.` : VIEWS[view].empty}
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
						<Button
							busy={checkAll.isPending}
							onClick={() => checkAll.mutate()}
							title="Checks every item not checked in the last 5 minutes"
						>
							{!checkAll.isPending && <RefreshCw className="size-4" />}
							Check all
						</Button>
						<Button variant="primary" onClick={() => setEditing({})}>
							<Plus className="size-4" /> Add item
						</Button>
					</>
				)}
			</div>

			{(counts.attention > 0 || counts.deals > 0 || view !== "all") && (
				<ChipGroup
					label="Show"
					className="mb-4"
					options={Object.entries(VIEWS)
						.filter(([key]) => key === "all" || counts[key] > 0 || key === view)
						.map(([key, { label }]) => ({
							value: key,
							label: key === "all" ? label : `${label} (${counts[key]})`,
						}))}
					value={view}
					onChange={setView}
				/>
			)}
			{content}

			<ItemFormDialog
				open={editing !== null}
				item={editing}
				onClose={() => setEditing(null)}
			/>
			<ConfirmDialog
				open={!!deleting}
				title="Delete item?"
				onClose={() => setDeleting(null)}
				onConfirm={() => remove.mutate(deleting.id)}
				busy={remove.isPending}
			>
				“{deleting && itemName(deleting)}” and its price history will be
				removed.
			</ConfirmDialog>
			<ScreenshotDialog item={viewing} onClose={() => setViewing(null)} />
		</>
	);
}
