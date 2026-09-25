import { useQueries } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Tags } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { analyticsQuery, useItems } from "@/api";
import { PriceChart, SERIES_COLORS, toTime } from "@/components/PriceChart";
import { Card, EmptyState, Select, Spinner, Switch } from "@/components/ui";
import { formatPrice, splitTags } from "@/format";

const RANGES = [
	["Last 7 days", 7],
	["Last 30 days", 30],
	["Last 90 days", 90],
	["Last year", 365],
	["All time", null],
];

export default function Compare() {
	const { data: items = [], isLoading } = useItems();
	const tags = [
		...new Set(items.flatMap((item) => splitTags(item.tags))),
	].sort();
	const [selectedTag, setTag] = useState(null);
	const [days, setDays] = useState(30);
	const [hideOutliers, setHideOutliers] = useState(false);
	const tag = tags.includes(selectedTag) ? selectedTag : tags[0];
	const tagged = items.filter((item) => splitTags(item.tags).includes(tag));

	const results = useQueries({
		queries: tagged.map((item) => analyticsQuery(item.id, days, hideOutliers)),
	});

	if (isLoading) return <Spinner className="mx-auto mt-24" />;

	const series = tagged.map((item, index) => ({
		key: `item${item.id}`,
		name: item.name,
		color: SERIES_COLORS[index % SERIES_COLORS.length],
		item,
	}));
	const data = series
		.flatMap((s, index) =>
			(results[index]?.data?.history ?? []).map((p) => ({
				t: toTime(p.timestamp),
				[s.key]: p.price,
			})),
		)
		.sort((a, b) => a.t - b.t);

	return (
		<>
			<div className="mb-6 flex flex-wrap items-center gap-3">
				<h1 className="mr-auto text-2xl font-semibold">Compare</h1>
				{tags.length > 0 && (
					<div className="w-full sm:w-44">
						<Select
							aria-label="Time range"
							value={days ?? ""}
							onChange={(event) => setDays(Number(event.target.value) || null)}
						>
							{RANGES.map(([label, value]) => (
								<option key={label} value={value ?? ""}>
									{label}
								</option>
							))}
						</Select>
					</div>
				)}
			</div>

			{tags.length === 0 ? (
				<EmptyState icon={Tags} title="Nothing to compare yet">
					Give items a shared tag, like “gpu” or “coffee”, to see their prices
					on one chart.
				</EmptyState>
			) : (
				<Card>
					<fieldset className="flex flex-wrap gap-2 border-b border-border p-4">
						<legend className="sr-only">Tag</legend>
						{tags.map((t) => (
							<button
								key={t}
								type="button"
								aria-pressed={t === tag}
								onClick={() => setTag(t)}
								className={clsx(
									"rounded-full border px-3 py-1 text-sm",
									t === tag
										? "border-fg bg-fg text-bg"
										: "border-border text-muted hover:text-fg",
								)}
							>
								{t}
							</button>
						))}
					</fieldset>
					<div className="p-4">
						{results.some((r) => r.isLoading) ? (
							<Spinner className="mx-auto my-32" />
						) : data.length === 0 ? (
							<p className="py-24 text-center text-sm text-muted">
								No prices recorded in this period.
							</p>
						) : (
							<PriceChart data={data} series={series} />
						)}
					</div>
					<div className="border-t border-border p-4">
						<Switch
							label="Hide outliers"
							hint="Drop prices more than 2σ from each item's average."
							checked={hideOutliers}
							onChange={setHideOutliers}
						/>
					</div>
					<ul className="grid gap-x-6 gap-y-2 border-t border-border p-4 text-sm sm:grid-cols-2">
						{series.map((s) => (
							<li key={s.key} className="flex min-w-0 items-center gap-2">
								<span
									className="size-2.5 shrink-0 rounded-full"
									style={{ background: s.color }}
								/>
								<Link
									to={`/items/${s.item.id}`}
									className="truncate hover:underline"
								>
									{s.name}
								</Link>
								<span className="ml-auto tabular-nums text-muted">
									{formatPrice(s.item.current_price)}
								</span>
							</li>
						))}
					</ul>
				</Card>
			)}
		</>
	);
}
