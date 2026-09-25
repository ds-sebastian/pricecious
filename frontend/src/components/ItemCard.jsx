import { clsx } from "clsx";
import {
	AlertTriangle,
	ExternalLink,
	Pencil,
	RefreshCw,
	Trash2,
} from "lucide-react";
import { Link } from "react-router-dom";
import { api, useAction } from "@/api";
import { Badge, Button, Spinner, StockBadge } from "@/components/ui";
import {
	formatDateTime,
	formatPrice,
	hostname,
	relativeTime,
	splitTags,
	WARNING_TYPES,
} from "@/format";

export function ItemStatus({ item, className }) {
	if (!item.last_error) return null;
	const warning = WARNING_TYPES.has(item.error_type);
	return (
		<p
			className={clsx(
				"flex gap-1.5 text-xs",
				warning
					? "text-amber-700 dark:text-amber-400"
					: "text-red-700 dark:text-red-400",
				className,
			)}
			title={item.last_error}
		>
			<AlertTriangle className="mt-px size-3.5 shrink-0" />
			<span className="line-clamp-2">{item.last_error}</span>
		</p>
	);
}

export function CheckButton({ item }) {
	const check = useAction(() => api.post(`/items/${item.id}/check`), {
		invalidate: [["items"]],
	});
	const busy = item.is_refreshing || check.isPending;
	return (
		<Button
			variant="ghost"
			icon
			aria-label="Check now"
			title="Check now"
			disabled={busy}
			onClick={() => check.mutate()}
		>
			<RefreshCw className={clsx("size-4", busy && "animate-spin")} />
		</Button>
	);
}

export function checkedLabel(item) {
	if (item.is_refreshing) return "Checking now…";
	if (!item.last_checked) return "Not checked yet";
	return `Checked ${relativeTime(item.last_checked)}`;
}

export function scheduleTitle(item) {
	const parts = [];
	if (item.last_checked)
		parts.push(`Last check: ${formatDateTime(item.last_checked)}`);
	if (!item.is_active) parts.push("Scheduled checks are paused");
	else if (item.next_check)
		parts.push(
			`Next check ${relativeTime(item.next_check)} (every ${item.interval} min)`,
		);
	return parts.join("\n") || undefined;
}

export function ItemCard({ item, onEdit, onDelete, onViewScreenshot }) {
	const targetMet =
		item.target_price != null &&
		item.current_price != null &&
		item.current_price <= item.target_price;
	const tags = splitTags(item.tags);

	return (
		<article className="flex flex-col overflow-hidden rounded-lg border border-border bg-surface">
			<button
				type="button"
				onClick={() => onViewScreenshot(item)}
				disabled={!item.screenshot_url}
				aria-label={`View screenshot of ${item.name}`}
				className="relative flex aspect-[16/10] items-center justify-center overflow-hidden border-b border-border bg-subtle enabled:cursor-zoom-in"
			>
				{item.screenshot_url ? (
					<img
						src={item.screenshot_url}
						alt=""
						loading="lazy"
						className="size-full object-cover object-left-top"
					/>
				) : (
					<span className="text-xs text-muted">No screenshot yet</span>
				)}
				<span className="absolute top-2 left-2 flex gap-1">
					{item.is_refreshing && (
						<Badge tone="blue">
							<Spinner className="size-3 text-current" />
							Checking
						</Badge>
					)}
					{!item.is_active && <Badge>Paused</Badge>}
				</span>
			</button>

			<div className="flex flex-1 flex-col gap-3 p-4">
				<div className="min-w-0">
					<Link
						to={`/items/${item.id}`}
						className="line-clamp-2 font-medium hover:underline"
						title={item.name}
					>
						{item.name}
					</Link>
					<a
						href={item.url}
						target="_blank"
						rel="noreferrer"
						className="inline-flex max-w-full items-center gap-1 text-xs text-muted hover:text-fg"
					>
						<span className="truncate">{hostname(item.url)}</span>
						<ExternalLink className="size-3 shrink-0" />
					</a>
				</div>

				<div className="flex items-end justify-between gap-2">
					<div>
						<div
							className={clsx(
								"text-2xl font-semibold tabular-nums",
								targetMet && "text-emerald-600 dark:text-emerald-400",
							)}
						>
							{formatPrice(item.current_price)}
						</div>
						{item.target_price != null && (
							<div className="text-xs text-muted">
								Target {formatPrice(item.target_price)}
								{targetMet && " · reached"}
							</div>
						)}
					</div>
					<StockBadge inStock={item.in_stock} />
				</div>

				<ItemStatus item={item} />

				{tags.length > 0 && (
					<div className="mt-auto flex flex-wrap gap-1">
						{tags.map((tag) => (
							<Badge key={tag}>{tag}</Badge>
						))}
					</div>
				)}
			</div>

			<footer className="flex items-center justify-between gap-2 border-t border-border py-1.5 pr-2 pl-4">
				<span
					className="truncate text-xs text-muted"
					title={scheduleTitle(item)}
				>
					{checkedLabel(item)}
				</span>
				<div className="flex">
					<CheckButton item={item} />
					<Button
						variant="ghost"
						icon
						aria-label="Edit"
						title="Edit"
						onClick={() => onEdit(item)}
					>
						<Pencil className="size-4" />
					</Button>
					<Button
						variant="ghost"
						icon
						aria-label="Delete"
						title="Delete"
						onClick={() => onDelete(item)}
					>
						<Trash2 className="size-4" />
					</Button>
				</div>
			</footer>
		</article>
	);
}
