const priceFormat = new Intl.NumberFormat(undefined, {
	minimumFractionDigits: 2,
	maximumFractionDigits: 2,
});
const relativeFormat = new Intl.RelativeTimeFormat(undefined, {
	numeric: "auto",
	style: "short",
});
const UNITS = [
	["day", 86400],
	["hour", 3600],
	["minute", 60],
];

export const formatPrice = (value) =>
	value == null ? "—" : `$${priceFormat.format(value)}`;

export const formatPercent = (value) =>
	`${value > 0 ? "+" : ""}${value.toFixed(1)}%`;

export const formatDateTime = (date) =>
	new Date(date).toLocaleString(undefined, {
		dateStyle: "medium",
		timeStyle: "short",
	});

export function relativeTime(date) {
	const seconds = (new Date(date) - Date.now()) / 1000;
	for (const [unit, size] of UNITS) {
		if (Math.abs(seconds) >= size) {
			return relativeFormat.format(Math.round(seconds / size), unit);
		}
	}
	return seconds < 0 ? "just now" : "any moment";
}

export function hostname(url) {
	try {
		return new URL(url).hostname.replace(/^www\./, "");
	} catch {
		return url;
	}
}

export const splitTags = (tags) =>
	tags
		? tags
				.split(",")
				.map((tag) => tag.trim())
				.filter(Boolean)
		: [];

// Problems that don't stop tracking, as opposed to failed checks.
export const WARNING_TYPES = new Set([
	"low_confidence",
	"no_price",
	"outlier_rejected",
	"price_out_of_bounds",
]);
