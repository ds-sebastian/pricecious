import { clsx } from "clsx";
import { Moon, Sun } from "lucide-react";
import { Suspense, useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { Toaster } from "sonner";
import { Button, Spinner } from "@/components/ui";

const LINKS = [
	{ to: "/", label: "Items", end: true },
	{ to: "/compare", label: "Compare" },
	{ to: "/settings", label: "Settings" },
];

function useDarkMode() {
	const [dark, setDark] = useState(() =>
		document.documentElement.classList.contains("dark"),
	);
	const toggle = () => {
		document.documentElement.classList.toggle("dark", !dark);
		try {
			localStorage.setItem("theme", dark ? "light" : "dark");
		} catch {}
		setDark(!dark);
	};
	return [dark, toggle];
}

export function Layout() {
	const [dark, toggleDark] = useDarkMode();

	return (
		<div className="min-h-dvh">
			<header className="sticky top-0 z-20 border-b border-border bg-bg/85 backdrop-blur">
				<div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-4 sm:gap-6">
					<Link to="/" className="flex items-center gap-2 font-semibold">
						<img src="/logo.png" alt="" className="size-7" />
						<span className="max-sm:sr-only">Pricecious</span>
					</Link>
					<nav className="flex gap-1 text-sm">
						{LINKS.map(({ to, label, end }) => (
							<NavLink
								key={to}
								to={to}
								end={end}
								className={({ isActive }) =>
									clsx(
										"rounded-md px-3 py-1.5 font-medium transition-colors",
										isActive ? "bg-subtle text-fg" : "text-muted hover:text-fg",
									)
								}
							>
								{label}
							</NavLink>
						))}
					</nav>
					<Button
						variant="ghost"
						icon
						className="ml-auto"
						onClick={toggleDark}
						aria-label={dark ? "Use light theme" : "Use dark theme"}
						title={dark ? "Use light theme" : "Use dark theme"}
					>
						{dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
					</Button>
				</div>
			</header>
			<main className="mx-auto max-w-6xl px-4 py-6">
				<Suspense fallback={<Spinner className="mx-auto mt-24" />}>
					<Outlet />
				</Suspense>
			</main>
			<Toaster position="top-center" theme={dark ? "dark" : "light"} />
		</div>
	);
}
