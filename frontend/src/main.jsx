import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import Items from "@/pages/Items";
import Settings from "@/pages/Settings";
import "./index.css";

// The chart pages pull in recharts; load them on demand.
const ItemDetail = lazy(() => import("@/pages/ItemDetail"));
const Compare = lazy(() => import("@/pages/Compare"));

const queryClient = new QueryClient({
	defaultOptions: { queries: { retry: 1 } },
});

createRoot(document.getElementById("root")).render(
	<StrictMode>
		<QueryClientProvider client={queryClient}>
			<BrowserRouter>
				<Routes>
					<Route element={<Layout />}>
						<Route index element={<Items />} />
						<Route path="items/:id" element={<ItemDetail />} />
						<Route path="compare" element={<Compare />} />
						<Route path="settings" element={<Settings />} />
						<Route path="*" element={<Navigate to="/" replace />} />
					</Route>
				</Routes>
			</BrowserRouter>
		</QueryClientProvider>
	</StrictMode>,
);
