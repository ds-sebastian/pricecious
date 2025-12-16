import { Button } from "@/components/ui/button";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle({
	theme,
	toggleTheme,
	showLabel = false,
	className = "",
}) {
	const isDark = theme === "dark";
	const Icon = isDark ? Sun : Moon;
	const label = isDark ? "Light Mode" : "Dark Mode";

	return (
		<Button
			variant="ghost"
			size={showLabel ? "default" : "icon"}
			onClick={toggleTheme}
			className={showLabel ? `justify-start gap-2 ${className}` : className}
		>
			<Icon className="h-4 w-4" />
			{showLabel && <span>{label}</span>}
		</Button>
	);
}
