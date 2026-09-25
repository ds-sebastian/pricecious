import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { ArrowLeft, ExternalLink, Pencil, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { analyticsQuery, api, useAction, useItems, useSettings } from "@/api";
import {
	CheckButton,
	checkedLabel,
	DealBadge,
	ItemStatus,
	PriceTag,
	SaleBadge,
	scheduleTitle,
} from "@/components/ItemCard";
import { ItemFormDialog } from "@/components/ItemForm";
import {
	FORECAST_COLOR,
	outOfStockRanges,
	PriceChart,
	SERIES_COLORS,
	toTime,
} from "@/components/PriceChart";
import { ScreenshotDialog } from "@/components/ScreenshotDialog";
import {
	Badge,
	Button,
	Card,
	Checkbox,
	ConfirmDialog,
	Dialog,
	EmptyState,
	Field,
	Input,
	Select,
	Spinner,
	StockBadge,
	Switch,
} from "@/components/ui";
import {
	formatDateTime,
	formatPercent,
	formatPrice,
	hostname,
	itemName,
	splitTags,
} from "@/format";

const RANGES = [
	["7D", 7],
	["30D", 30],
	["90D", 90],
	["1Y", 365],
	["All", null],
];
const PAGE_SIZE = 25;

export default function ItemDetail() {
	const { id } = useParams();
	const navigate = useNavigate();
	const { data: items, isLoading } = useItems();
	const item = items?.find((i) => String(i.id) === id);
	const [editing, setEditing] = useState(false);
	const [deleting, setDeleting] = useState(false);
	const [viewing, setViewing] = useState(false);

	const remove = useAction(() => api.delete(`/items/${id}`), {
		success: "Item deleted",
		invalidate: [["items"]],
		onSuccess: () => navigate("/"),
	});

	if (isLoading) return <Spinner className="mx-auto mt-24" />;
	if (!item) {
		return (
			<EmptyState
				title="Item not found"
				action={
					<Link to="/" className="text-sm underline">
						Back to items
					</Link>
				}
			/>
		);
	}

	const tags = splitTags(item.tags);

	return (
		<div className="flex flex-col gap-6">
			<div>
				<Link
					to="/"
					className="mb-4 inline-flex items-center gap-1 text-sm text-muted hover:text-fg"
				>
					<ArrowLeft className="size-4" /> Items
				</Link>
				<div className="flex flex-wrap items-start gap-4">
					{item.screenshot_url && (
						<button
							type="button"
							onClick={() => setViewing(true)}
							aria-label="View screenshot"
							className="hidden h-20 w-32 shrink-0 cursor-zoom-in overflow-hidden rounded-md border border-border sm:block"
						>
							<img
								src={item.screenshot_url}
								alt=""
								className="size-full object-cover object-left-top"
							/>
						</button>
					)}
					<div className="min-w-64 flex-1">
						<h1 className="text-2xl font-semibold">{itemName(item)}</h1>
						<div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
							<a
								href={item.url}
								target="_blank"
								rel="noreferrer"
								className="inline-flex items-center gap-1 hover:text-fg"
							>
								{hostname(item.url)} <ExternalLink className="size-3" />
							</a>
							<span title={scheduleTitle(item)}>· {checkedLabel(item)}</span>
							{!item.is_active && <Badge>Paused</Badge>}
							{tags.map((tag) => (
								<Badge key={tag}>{tag}</Badge>
							))}
						</div>
						<ItemStatus item={item} className="mt-2" />
					</div>
					<div className="flex items-center gap-3">
						<div className="sm:text-right">
							<div className="text-3xl font-semibold tabular-nums">
								<PriceTag price={item} currency={item.currency} />
							</div>
							{item.target_price != null && (
								<div className="text-xs text-muted">
									Target {formatPrice(item.target_price, item.currency)}
								</div>
							)}
						</div>
						<StockBadge inStock={item.in_stock} />
					</div>
				</div>
				{(item.deal || item.promotion || item.regular_price != null) && (
					<div className="mt-3 flex flex-wrap gap-1">
						<SaleBadge price={item} />
						{item.deal && <DealBadge deal={item.deal} />}
					</div>
				)}
				<div className="mt-4 flex gap-1">
					<CheckButton item={item} />
					<Button
						variant="ghost"
						icon
						aria-label="Edit"
						title="Edit"
						onClick={() => setEditing(true)}
					>
						<Pencil className="size-4" />
					</Button>
					<Button
						variant="ghost"
						icon
						aria-label="Delete"
						title="Delete"
						onClick={() => setDeleting(true)}
					>
						<Trash2 className="size-4" />
					</Button>
				</div>
			</div>

			<PriceHistory itemId={id} currency={item.currency} />
			<HistoryTable itemId={id} currency={item.currency} />

			<ItemFormDialog
				open={editing}
				item={item}
				onClose={() => setEditing(false)}
			/>
			<ConfirmDialog
				open={deleting}
				title="Delete item?"
				onClose={() => setDeleting(false)}
				onConfirm={() => remove.mutate()}
				busy={remove.isPending}
			>
				“{itemName(item)}” and its price history will be removed.
			</ConfirmDialog>
			<ScreenshotDialog
				item={viewing ? item : null}
				onClose={() => setViewing(false)}
			/>
		</div>
	);
}

function PriceHistory({ itemId, currency }) {
	const [days, setDays] = useState(30);
	const [hideOutliers, setHideOutliers] = useState(false);
	const [showForecast, setShowForecast] = useState(true);

	const { data, isLoading } = useQuery({
		...analyticsQuery(itemId, days, hideOutliers),
		placeholderData: keepPreviousData,
	});

	const history = (data?.history ?? []).map((p) => ({
		...p,
		t: toTime(p.timestamp),
	}));
	const forecast = showForecast && history.length ? (data?.forecast ?? []) : [];
	const chartData = [...history];
	const series = [
		{ key: "price", name: "Price", color: SERIES_COLORS[0], currency },
	];
	if (forecast.length) {
		// Start the forecast line at the last real price so the two connect.
		chartData.at(-1).forecast = history.at(-1).price;
		for (const f of forecast) {
			chartData.push({
				t: toTime(f.timestamp),
				forecast: f.price,
				band: [f.lower, f.upper],
			});
		}
		series.push({
			key: "forecast",
			name: "Forecast",
			color: FORECAST_COLOR,
			dashed: true,
			currency,
		});
	}
	const stats = data?.stats;

	return (
		<Card
			title="Price history"
			action={
				<fieldset className="flex rounded-md border border-border p-0.5">
					<legend className="sr-only">Time range</legend>
					{RANGES.map(([label, value]) => (
						<button
							key={label}
							type="button"
							aria-pressed={days === value}
							onClick={() => setDays(value)}
							className={clsx(
								"rounded px-2 py-1 text-xs font-medium",
								days === value
									? "bg-subtle text-fg"
									: "text-muted hover:text-fg",
							)}
						>
							{label}
						</button>
					))}
				</fieldset>
			}
		>
			<div className="p-4">
				{isLoading ? (
					<Spinner className="mx-auto my-32" />
				) : history.length === 0 ? (
					<p className="py-24 text-center text-sm text-muted">
						No prices recorded {days ? `in the last ${days} days` : "yet"}.
					</p>
				) : (
					<PriceChart
						data={chartData}
						series={series}
						currency={currency}
						outOfStock={outOfStockRanges(history)}
						markers={data.annotations
							.filter((a) => a.type === "min" || a.type === "max")
							.map((a) => ({ ...a, t: toTime(a.timestamp) }))}
						band={forecast.length > 0}
					/>
				)}
			</div>
			{stats && (
				<dl className="grid grid-cols-2 gap-px border-t border-border bg-border sm:grid-cols-5">
					<Stat
						label="Current"
						value={formatPrice(stats.latest, currency)}
						className="max-sm:col-span-2"
					/>
					<Stat
						label="24h change"
						value={
							stats.change_24h == null ? "—" : formatPercent(stats.change_24h)
						}
						valueClassName={clsx(
							stats.change_24h < 0 && "text-emerald-600 dark:text-emerald-400",
							stats.change_24h > 0 && "text-red-600 dark:text-red-400",
						)}
					/>
					<Stat label="Lowest" value={formatPrice(stats.min, currency)} />
					<Stat label="Highest" value={formatPrice(stats.max, currency)} />
					<Stat label="Average" value={formatPrice(stats.avg, currency)} />
				</dl>
			)}
			<div className="flex flex-wrap gap-x-8 gap-y-3 border-t border-border p-4">
				<Switch
					label="Hide outliers"
					hint="Drop prices more than 2σ from the average."
					checked={hideOutliers}
					onChange={setHideOutliers}
				/>
				{data?.forecast.length > 0 && (
					<Switch
						label="Forecast"
						hint="Projected from past prices; shaded area is the likely range."
						checked={showForecast}
						onChange={setShowForecast}
					/>
				)}
			</div>
		</Card>
	);
}

function Stat({ label, value, className, valueClassName }) {
	return (
		<div className={clsx("bg-surface px-4 py-3", className)}>
			<dt className="text-xs text-muted">{label}</dt>
			<dd className={clsx("mt-0.5 font-semibold tabular-nums", valueClassName)}>
				{value}
			</dd>
		</div>
	);
}

const NO_FILTERS = { min_price: "", max_price: "", stock: "", confidence: "" };

function useDebounced(value, delay = 300) {
	const [debounced, setDebounced] = useState(value);
	useEffect(() => {
		const timer = setTimeout(() => setDebounced(value), delay);
		return () => clearTimeout(timer);
	}, [value, delay]);
	return debounced;
}

/** The filters as the API takes them, for listing a page or acting on every match. */
function historyFilters(filters, threshold) {
	const out = {};
	for (const key of ["min_price", "max_price"]) {
		if (filters[key] !== "") out[key] = Number(filters[key]);
	}
	if (filters.stock) out.stock = filters.stock;
	if (filters.confidence === "unapplied") out.confidence_below = threshold;
	if (filters.confidence === "confident") out.min_confidence = 0.8;
	return out;
}

const readings = (count) => `${count} reading${count === 1 ? "" : "s"}`;

function HistoryTable({ itemId, currency }) {
	const [page, setPage] = useState(1);
	const [filters, setFilters] = useState(NO_FILTERS);
	const [editing, setEditing] = useState(null);
	const [deleting, setDeleting] = useState(null);
	// Either hand-picked ids, or every reading matching the filters (which can span many pages) except the
	// ones unticked since.
	const [selected, setSelected] = useState(() => new Set());
	const [allMatching, setAllMatching] = useState(false);
	const [excluded, setExcluded] = useState(() => new Set());
	const [bulkDialog, setBulkDialog] = useState(null); // "edit" | "delete"
	const { data: settings } = useSettings();
	const threshold = settings?.confidence_threshold_price ?? 0.5;
	const applied = useDebounced(filters);
	const filtering = Object.values(applied).some((value) => value !== "");
	const query = historyFilters(applied, threshold);

	const { data, isPlaceholderData } = useQuery({
		queryKey: ["history", itemId, page, applied, threshold],
		queryFn: () =>
			api.get(
				`/items/${itemId}/history?${new URLSearchParams({ page, size: PAGE_SIZE, ...query })}`,
			),
		placeholderData: keepPreviousData,
	});
	const invalidate = [["history", itemId], ["analytics", itemId], ["items"]];
	const clearSelection = () => {
		setSelected(new Set());
		setAllMatching(false);
		setExcluded(new Set());
	};
	const remove = useAction((id) => api.delete(`/history/${id}`), {
		success: "Reading deleted",
		invalidate,
		onSuccess: (_, id) => {
			setDeleting(null);
			// A deleted reading is neither picked nor a match any more, so it mustn't count as excluded either.
			const without = (ids) =>
				new Set([...ids].filter((other) => other !== id));
			setSelected(without);
			setExcluded(without);
		},
	});
	const bulk = useAction(
		async (body) => ({
			...(await api.post(`/items/${itemId}/history/bulk`, {
				...body,
				...(allMatching
					? { filters: query, exclude_ids: [...excluded] }
					: { ids: [...selected] }),
			})),
			action: body.action,
		}),
		{
			success: ({ count, action }) =>
				`${readings(count)} ${action === "delete" ? "deleted" : "updated"}`,
			invalidate,
			onSuccess: () => {
				setBulkDialog(null);
				clearSelection();
			},
		},
	);
	const setFilter = (key) => (event) => {
		setFilters({ ...filters, [key]: event.target.value });
		setPage(1);
		clearSelection();
	};

	if (!data || (!data.total && !filtering)) return null;
	const pages = Math.ceil(data.total / PAGE_SIZE);
	if (pages && page > pages) setPage(pages); // the last page was emptied by a delete

	const pageIds = data.items.map((record) => record.id);
	const isSelected = (id) =>
		allMatching ? !excluded.has(id) : selected.has(id);
	const pageSelected = pageIds.filter(isSelected).length;
	const count = allMatching ? data.total - excluded.size : selected.size;
	/** Tick or untick ids; in "all matching" mode unticking means excluding. */
	const mark = (ids, on) => {
		if (!allMatching) {
			const next = new Set(selected);
			for (const id of ids) on ? next.add(id) : next.delete(id);
			return setSelected(next);
		}
		const next = new Set(excluded);
		for (const id of ids) on ? next.delete(id) : next.add(id);
		if (next.size >= data.total) clearSelection();
		else setExcluded(next);
	};
	const toggle = (id) => mark([id], !isSelected(id));
	const togglePage = () =>
		mark(pageIds, !(pageIds.length > 0 && pageSelected === pageIds.length));

	return (
		<Card
			title={
				filtering
					? `Readings (${data.total} matching)`
					: `Readings (${data.total})`
			}
			action={
				filtering && (
					<Button
						variant="ghost"
						onClick={() => {
							setFilters(NO_FILTERS);
							setPage(1);
							clearSelection();
						}}
					>
						Clear filters
					</Button>
				)
			}
		>
			<fieldset className="grid grid-cols-2 gap-2 border-b border-border p-4 sm:grid-cols-4">
				<legend className="sr-only">Filter readings</legend>
				<Input
					type="number"
					min="0"
					step="any"
					placeholder="Min price"
					aria-label="Minimum price"
					value={filters.min_price}
					onChange={setFilter("min_price")}
				/>
				<Input
					type="number"
					min="0"
					step="any"
					placeholder="Max price"
					aria-label="Maximum price"
					value={filters.max_price}
					onChange={setFilter("max_price")}
				/>
				<Select
					aria-label="Stock"
					value={filters.stock}
					onChange={setFilter("stock")}
				>
					<option value="">Any stock</option>
					<option value="in">In stock</option>
					<option value="out">Out of stock</option>
					<option value="unknown">Stock unknown</option>
				</Select>
				<Select
					aria-label="Confidence"
					title="Low: below your minimum confidence, so these readings didn't change the price"
					value={filters.confidence}
					onChange={setFilter("confidence")}
				>
					<option value="">Any confidence</option>
					<option value="unapplied">
						Low (&lt;{Math.round(threshold * 100)}%)
					</option>
					<option value="confident">High (80%+)</option>
				</Select>
			</fieldset>
			{count > 0 && (
				<div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border bg-subtle px-4 py-2 text-sm">
					<span className="font-medium">
						{allMatching && excluded.size === 0
							? `All ${data.total}${filtering ? " matching" : ""} ${data.total === 1 ? "reading" : "readings"} selected`
							: allMatching
								? `${count} of ${data.total}${filtering ? " matching" : ""} readings selected`
								: `${readings(count)} selected`}
					</span>
					{!allMatching &&
						pageSelected === pageIds.length &&
						data.total > count && (
							<button
								type="button"
								className="font-medium text-accent hover:underline disabled:opacity-50"
								disabled={isPlaceholderData}
								onClick={() => setAllMatching(true)}
							>
								Select all {data.total}
								{filtering ? " matching" : ""}
							</button>
						)}
					<div className="ml-auto flex gap-1">
						<Button variant="ghost" onClick={clearSelection}>
							Clear
						</Button>
						<Button
							aria-label="Edit selected readings"
							onClick={() => setBulkDialog("edit")}
						>
							<Pencil className="size-4" />
							Edit
						</Button>
						<Button
							variant="danger"
							aria-label="Delete selected readings"
							onClick={() => setBulkDialog("delete")}
						>
							<Trash2 className="size-4" />
							Delete
						</Button>
					</div>
				</div>
			)}
			<div className="relative overflow-x-auto">
				<table className="w-full text-sm">
					<thead className="text-left text-xs text-muted">
						<tr className="border-b border-border">
							<th className="w-0 py-2 pr-0 pl-4">
								<Checkbox
									aria-label="Select all readings on this page"
									checked={
										pageIds.length > 0 && pageSelected === pageIds.length
									}
									indeterminate={
										pageSelected > 0 && pageSelected < pageIds.length
									}
									disabled={pageIds.length === 0}
									onChange={togglePage}
								/>
							</th>
							<th className="px-4 py-2 font-medium">Date</th>
							<th className="px-4 py-2 text-right font-medium">Price</th>
							<th className="px-4 py-2 font-medium">Stock</th>
							<th className="px-4 py-2 text-right font-medium max-sm:hidden">
								Confidence
							</th>
							<th className="px-4 py-2">
								<span className="sr-only">Actions</span>
							</th>
						</tr>
					</thead>
					<tbody>
						{data.items.length === 0 && (
							<tr>
								<td colSpan={6} className="px-4 py-10 text-center text-muted">
									No readings match these filters.
								</td>
							</tr>
						)}
						{data.items.map((record) => (
							<tr
								key={record.id}
								className={clsx(
									"border-b border-border last:border-0",
									isSelected(record.id) && "bg-subtle/60",
								)}
							>
								<td className="py-2 pr-0 pl-4">
									<Checkbox
										aria-label={`Select the reading from ${formatDateTime(record.timestamp)}`}
										checked={isSelected(record.id)}
										onChange={() => toggle(record.id)}
									/>
								</td>
								<td className="px-4 py-2 whitespace-nowrap">
									{formatDateTime(record.timestamp)}
								</td>
								<td className="px-4 py-2 text-right tabular-nums">
									<PriceTag price={record} currency={currency} />
									{record.promotion && (
										<div className="text-xs text-blue-700 dark:text-blue-300">
											{record.promotion}
										</div>
									)}
								</td>
								<td className="px-4 py-2">
									<StockBadge inStock={record.in_stock} />
								</td>
								<td
									className={clsx(
										"px-4 py-2 text-right tabular-nums max-sm:hidden",
										record.price_confidence < 0.5 &&
											"text-amber-600 dark:text-amber-400",
									)}
									title={
										record.price_confidence == null
											? "Entered or confirmed by hand"
											: undefined
									}
								>
									{record.price_confidence == null
										? "—"
										: `${Math.round(record.price_confidence * 100)}%`}
								</td>
								<td className="px-2 py-1 text-right whitespace-nowrap">
									<Button
										variant="ghost"
										icon
										aria-label="Edit reading"
										title="Edit"
										onClick={() => setEditing(record)}
									>
										<Pencil className="size-4" />
									</Button>
									<Button
										variant="ghost"
										icon
										aria-label="Delete reading"
										title="Delete"
										onClick={() => setDeleting(record)}
									>
										<Trash2 className="size-4" />
									</Button>
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
			{pages > 1 && (
				<div className="flex items-center justify-end gap-2 border-t border-border px-4 py-2 text-sm">
					<span className="mr-2 text-muted">
						Page {page} of {pages}
					</span>
					<Button disabled={page === 1} onClick={() => setPage(page - 1)}>
						Newer
					</Button>
					<Button disabled={page === pages} onClick={() => setPage(page + 1)}>
						Older
					</Button>
				</div>
			)}

			<Dialog
				open={!!editing}
				onClose={() => setEditing(null)}
				title="Edit reading"
			>
				{editing && (
					<EditReading
						record={editing}
						invalidate={invalidate}
						onDone={() => setEditing(null)}
						onSaved={(id) => {
							// The edit may have taken it out of the filter, so an exclusion could now be off by one.
							if (allMatching && excluded.has(id)) clearSelection();
						}}
					/>
				)}
			</Dialog>
			<Dialog
				open={bulkDialog === "edit"}
				onClose={() => setBulkDialog(null)}
				title={`Edit ${readings(count)}`}
			>
				{bulkDialog === "edit" && (
					<ReadingForm
						bulk
						busy={bulk.isPending}
						onCancel={() => setBulkDialog(null)}
						onSubmit={(body) => bulk.mutate({ action: "update", ...body })}
					/>
				)}
			</Dialog>
			<ConfirmDialog
				open={!!deleting}
				title="Delete reading?"
				onClose={() => setDeleting(null)}
				onConfirm={() => remove.mutate(deleting.id)}
				busy={remove.isPending}
			>
				The {formatPrice(deleting?.price, currency)} reading from{" "}
				{deleting && formatDateTime(deleting.timestamp)} will be removed.
			</ConfirmDialog>
			<ConfirmDialog
				open={bulkDialog === "delete"}
				title={`Delete ${readings(count)}?`}
				onClose={() => setBulkDialog(null)}
				onConfirm={() => bulk.mutate({ action: "delete" })}
				busy={bulk.isPending}
			>
				{allMatching && !filtering && excluded.size === 0
					? "Every reading of this item will be removed. This can't be undone."
					: `The ${readings(count)} you selected will be removed. This can't be undone.`}
			</ConfirmDialog>
		</Card>
	);
}

function EditReading({ record, invalidate, onDone, onSaved }) {
	const save = useAction((body) => api.put(`/history/${record.id}`, body), {
		success: "Reading updated",
		invalidate,
		onSuccess: () => {
			onSaved?.(record.id);
			onDone();
		},
	});
	return (
		<ReadingForm
			record={record}
			busy={save.isPending}
			onCancel={onDone}
			onSubmit={(body) => save.mutate(body)}
		/>
	);
}

/** Corrects one reading, or (bulk) sets a price and/or stock on many; blank bulk fields are left as they are. */
function ReadingForm({ record, bulk = false, busy, onCancel, onSubmit }) {
	const [price, setPrice] = useState(record ? String(record.price) : "");
	const [stock, setStock] = useState(
		record ? String(record.in_stock ?? "unknown") : "",
	);
	const empty = bulk && price === "" && stock === "";

	return (
		<form
			className="grid gap-4"
			onSubmit={(event) => {
				event.preventDefault();
				onSubmit({
					price: price === "" ? undefined : Number(price),
					// Blank leaves the stock as it is (bulk only); "unknown" clears it.
					in_stock:
						stock === ""
							? undefined
							: stock === "unknown"
								? null
								: stock === "true",
				});
			}}
		>
			{record && (
				<p className="text-sm text-muted">{formatDateTime(record.timestamp)}</p>
			)}
			<div className="grid grid-cols-2 gap-4">
				<Field label="Price">
					<Input
						type="number"
						min="0"
						step="0.01"
						required={!bulk}
						placeholder={bulk ? "Leave as is" : undefined}
						value={price}
						onChange={(e) => setPrice(e.target.value)}
					/>
				</Field>
				<Field label="Stock">
					<Select value={stock} onChange={(e) => setStock(e.target.value)}>
						{bulk && <option value="">Leave as is</option>}
						<option value="unknown">Unknown</option>
						<option value="true">In stock</option>
						<option value="false">Out of stock</option>
					</Select>
				</Field>
			</div>
			<p className="text-xs text-muted">
				Corrected readings count as confirmed, so "lowest price" deals and
				alerts use them even if the AI was unsure.
			</p>
			<div className="flex justify-end gap-2">
				<Button onClick={onCancel}>Cancel</Button>
				<Button type="submit" variant="primary" busy={busy} disabled={empty}>
					Save
				</Button>
			</div>
		</form>
	);
}
