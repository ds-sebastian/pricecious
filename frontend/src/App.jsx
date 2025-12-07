import React from "react";
import { Route, BrowserRouter as Router, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import Layout from "@/components/layout/Layout";
import { useTheme } from "@/hooks/use-theme";
import Analytics from "@/pages/Analytics";
import Dashboard from "@/pages/Dashboard";
import History from "@/pages/History";
import Settings from "@/pages/Settings";

export default function App() {
	const { theme, toggleTheme } = useTheme();

	return (
		<Router>
			<Toaster position="bottom-right" theme={theme} />
			<Layout theme={theme} toggleTheme={toggleTheme}>
				<Routes>
					<Route path="/" element={<Dashboard />} />
					<Route path="/analytics" element={<Analytics />} />
					<Route path="/history" element={<History />} />
					<Route path="/settings" element={<Settings />} />
				</Routes>
			</Layout>
		</Router>
	);
}
