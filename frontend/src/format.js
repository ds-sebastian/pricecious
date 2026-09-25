const relativeFormat = new Intl.RelativeTimeFormat(undefined, {
	numeric: "auto",
	style: "short",
});
const UNITS = [
	["day", 86400],
	["hour", 3600],
	["minute", 60],
];

const currencyFormats = new Map();

function currencyFormat(currency, options = {}) {
	const key = `${currency}:${JSON.stringify(options)}`;
	if (!currencyFormats.has(key)) {
		let format;
		try {
			format = new Intl.NumberFormat(undefined, {
				style: "currency",
				currency,
				...options,
			});
		} catch {
			format = new Intl.NumberFormat(undefined, {
				minimumFractionDigits: 2,
				maximumFractionDigits: 2,
			});
		}
		currencyFormats.set(key, format);
	}
	return currencyFormats.get(key);
}

/** "$1,234.56", "1.234,56 €", "¥1,235": whatever the currency and the viewer's locale call for. */
export const formatPrice = (value, currency = "USD") =>
	value == null ? "—" : currencyFormat(currency).format(value);

/** Compact prices for chart axes: no decimals. */
export const formatAxisPrice = (value, currency = "USD") =>
	currencyFormat(currency, { maximumFractionDigits: 0 }).format(value);

export const itemName = (item) => item.name || hostname(item.url);

export const formatPercent = (value) =>
	`${value > 0 ? "+" : ""}${value.toFixed(1)}%`;

export function formatDateTime(date) {
	const value = new Date(date);
	return value.toLocaleString(undefined, {
		year:
			value.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
		month: "short",
		day: "numeric",
		hour: "numeric",
		minute: "2-digit",
	});
}

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

export const DEAL_LABELS = {
	lowest_seen: "Lowest price seen",
	lowest_90d: "Lowest in 90 days",
};

// Problems that don't stop tracking, as opposed to failed checks.
export const WARNING_TYPES = new Set([
	"low_confidence",
	"no_price",
	"outlier_rejected",
	"price_out_of_bounds",
]);
