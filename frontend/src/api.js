import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

function errorMessage(detail) {
	if (typeof detail === "string") return detail;
	if (Array.isArray(detail)) {
		return detail
			.map((e) => `${e.loc?.at(-1) ?? "value"}: ${e.msg}`)
			.join("; ");
	}
	return null;
}

// Some reverse-proxy firewalls only let GET and POST through, so edits and deletes travel as POST with the real
// method in the query; the server maps them back.
const OVERRIDDEN = new Set(["PUT", "DELETE"]);

async function request(method, path, body) {
	const override = OVERRIDDEN.has(method);
	const url = override
		? `/api${path}${path.includes("?") ? "&" : "?"}_method=${method}`
		: `/api${path}`;
	const response = await fetch(url, {
		method: override ? "POST" : method,
		headers: body === undefined ? {} : { "Content-Type": "application/json" },
		body: body === undefined ? undefined : JSON.stringify(body),
	});
	if (!response.ok) {
		const data = await response.json().catch(() => ({}));
		throw new Error(
			errorMessage(data.detail) ?? `Request failed (${response.status})`,
		);
	}
	return response.status === 204 ? null : response.json();
}

export const api = {
	get: (path) => request("GET", path),
	post: (path, body) => request("POST", path, body),
	put: (path, body) => request("PUT", path, body),
	delete: (path) => request("DELETE", path),
};

export function useItems() {
	return useQuery({
		queryKey: ["items"],
		queryFn: () => api.get("/items"),
		// Poll quickly while checks are running so results show up promptly.
		refetchInterval: (query) =>
			query.state.data?.some((item) => item.is_refreshing) ? 3000 : 30000,
	});
}

export function useProfiles() {
	return useQuery({
		queryKey: ["profiles"],
		queryFn: () => api.get("/notification-profiles"),
	});
}

export function useSettings() {
	// Only the Settings page changes these; refetching would make an open form look out of date.
	return useQuery({
		queryKey: ["settings"],
		queryFn: () => api.get("/settings"),
		staleTime: Number.POSITIVE_INFINITY,
	});
}

/** A mutation that toasts errors, and optionally a success message, then refreshes the given queries. */
export function useAction(
	mutationFn,
	{ success, invalidate = [], onSuccess } = {},
) {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn,
		onSuccess: (data, variables) => {
			const message = typeof success === "function" ? success(data) : success;
			if (message) toast.success(message);
			for (const queryKey of invalidate)
				queryClient.invalidateQueries({ queryKey });
			onSuccess?.(data, variables);
		},
		onError: (error) => toast.error(error.message),
	});
}

export function analyticsQuery(itemId, days, hideOutliers) {
	const params = new URLSearchParams();
	if (days) params.set("days", days);
	if (hideOutliers) params.set("std_dev_threshold", 2);
	return {
		queryKey: ["analytics", String(itemId), days, hideOutliers],
		queryFn: () => api.get(`/items/${itemId}/analytics?${params}`),
	};
}
